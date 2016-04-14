#!/usr/bin/env python
# coding=utf-8
import socket, struct, io, time, os, random
from . import types
REQUEST = 0
RESPONSE = 1
nameservers = []
hosts = None
MAXAGE = 3600000

class DNSError(Exception):
    errors = {
        1: 'Format error: bad request',
        2: 'Server failure: error occurred',
        3: 'Name error: not exist',
        4: 'Not implemented: query type not supported',
        5: 'Refused: policy reasons'
    }
    def __init__(self, code, message = None):
        message = self.errors.get(code, message) or 'Unknown reply code: %d' % code
        super().__init__(message)
        self.code = code

class SOA_RData:
    def __init__(self, data, l):
        i, self.mname = get_name(data, l)
        i, self.rname = get_name(data, i)
        (
            self.serial,
            self.refresh,
            self.retry,
            self.expire,
            self.minimum,
        ) = struct.unpack('!LLLLL', data[i: i + 20])

    def __repr__(self):
        return '<%s>' % self.rname

class Record:
    def __init__(self, q = RESPONSE, name = '', qtype = types.ANY, qclass = 1, ttl = 0, data = None):
        self.q = q
        self.name = name
        self.qtype = qtype
        self.qclass = qclass
        if q == RESPONSE:
            self.ttl = ttl    # 0 means item should not be cached
            self.data = data
            self.timestamp = int(time.time())

    def __repr__(self):
        if self.q == REQUEST:
            return str((self.name, types.type_name(self.qtype)))
        else:
            return str((self.name, types.type_name(self.qtype), self.data, self.ttl))

    def copy(self, **kw):
        return Record(
            q = kw.get('q', self.q),
            name = kw.get('name', self.name),
            qtype = kw.get('qtype', self.qtype),
            qclass = kw.get('qclass', self.qclass),
            ttl = kw.get('ttl', self.ttl),
            data = kw.get('data', self.data)
        )

    def update(self, other):
        if (self.name, self.qtype, self.data) == (other.name, other.qtype, other.data):
            if self.ttl and other.ttl > self.ttl:
                self.ttl = other.ttl
            return self

    def parse(self, data, l):
        l, self.name = get_name(data, l)
        self.qtype, self.qclass = struct.unpack('!HH', data[l: l + 4])
        l += 4
        if self.q == RESPONSE:
            self.timestamp = int(time.time())
            self.ttl, dl = struct.unpack('!LH', data[l: l + 6])
            l += 6
            if self.qtype == types.A:
                self.data = socket.inet_ntoa(data[l: l + dl])
            elif self.qtype == types.AAAA:
                self.data = inet_ntop(socket.AF_INET6, data[l: l + dl])
            elif self.qtype == types.MX:
                # priority, hostname
                self.data = struct.unpack('!H', data[l: l + 2]) + (get_name(data, l + 2)[1], )
            elif self.qtype == types.SRV:
                # priority, weight, port, hostname
                self.data = struct.unpack('!HHH', data[l: l + 6]) + (get_name(data, l + 6)[1], )
            elif self.qtype == types.SOA:
                self.data = SOA_RData(data, l)
            elif self.qtype in (types.CNAME, types.NS, types.PTR):
                self.data = get_name(data, l)[1]
            else:
                self.data = data[l: l + dl]
            l += dl
        return l

    def pack(self, buf = None, names = {}):
        if buf is None:
            buf = io.BytesIO()
        pack_name(self.name, buf, names)
        buf.write(struct.pack('!HH', self.qtype, self.qclass))
        if self.q == RESPONSE:
            if self.ttl < 0:
                ttl = MAXAGE
            else:
                now = int(time.time())
                self.ttl -= now - self.timestamp
                if self.ttl < 0:
                    self.ttl = 0
                self.timestamp = now
                ttl = self.ttl
            buf.write(struct.pack('!L', ttl))
            if self.qtype == types.A:
                buf.write(pack_string(socket.inet_aton(self.data), '!H'))
            elif self.qtype == types.AAAA:
                buf.write(pack_string(socket.inet_pton(socket.AF_INET6, self.data), '!H'))
            elif self.qtype == types.MX:
                buf.write(pack_string(struct.pack('!H', self.data[0]) +
                    pack_name(self.data[1], names = names, offset = buf.tell() + 4), '!H'))
            elif self.qtype == types.SRV:
                buf.write(pack_string(struct.pack('!HHH', self.data[:3]) +
                    pack_name(self.data[3], names = names, offset = buf.tell() + 8), '!H'))
            elif self.qtype == types.SOA:
                mname = pack_name(self.data[0], names = names, offset = buf.tell() + 2)
                rname = pack_name(self.data[1], names = names, offset = buf.tell() + 2 + len(mname))
                buf.write(pack_string(mname + rname + struct.pack('!LLLLL', *self.data[2:]), '!H'))
            elif self.qtype in (types.CNAME, types.NS, types.PTR):
                buf.write(pack_string(pack_name(self.data, names = names, offset = buf.tell() + 2), '!H'))
            else:
                buf.write(pack_string(self.data, '!H'))
        return buf.getvalue()

class Hosts:
    def __init__(self, filename = None):
        self.data = {}
        self.changed = False
        if filename:
            self.parse_file(filename)

    def __bool__(self):
        return bool(self.data)

    def __repr__(self):
        return '<%s [%s]>' % (self.__class__.__name__, ', '.join(self.data.keys()))

    def update(self, other):
        for k, v in other.data.items():
            item = self.data.setdefault(k, [])
            item.extend(v)

    def parse_file(self, filename):
        filename = os.path.expanduser(filename)
        if not filename or not os.path.isfile(filename):
            return
        for line in open(filename, 'r'):
            line = line.strip()
            if not line or line.startswith('#'): continue
            ip = None
            values = []
            # str.split will discard redundant white spaces
            for i in line.split():
                if ip is None:
                    ip, tp = i, ip_type(i)
                    if tp is None: break
                elif i.startswith('#'):
                    break
                else:
                    values.append(i.lower())
            for i in values:
                self.add_host(Record(name = i, qtype = tp, ttl = -1, data = ip))

    def add_host(self, record):
        if record.ttl == 0:
            # RFC 1035: should not be cached while TTL=0
            return
        key = record.name.lower()
        item = self.data.get(key, [])
        for i in item:
            if i.update(record): break
        else:
            item.append(record)
        if item:
            self.data[key] = item
        self.changed = True

    def get(self, key, default = None):
        # TODO improve cache GC performance
        vs = self.data.get(key)
        now = time.time()
        if vs is not None:
            i = 0
            while i < len(vs):
                v = vs[i]
                if v.ttl >= 0 and v.timestamp + v.ttl < now:
                    last = vs.pop()
                    if last is not v:
                        vs[i] = last
                    self.changed = True
                else:
                    i += 1
        if vs is None:
            vs = [] if default is None else default
        return vs

    def get_ip(self, key, default = None):
        a = aaaa = cname = None
        for i in self.data.get(key):
            if aaaa is None and i.qtype == types.AAAA:
                aaaa = i
            elif a is None and i.qtype == types.A:
                a = i
            elif cname is None and i.qtype == types.CNAME:
                cname = i
        return aaaa or a or cname or default

    def query(self, name, qtype = types.ANY):
        name = name.lower()
        while True:
            host = self.get(name)
            if host: break
            i = name.find('.', 1)
            if i < 0: break
            name = name[i:]
        try:
            qtype = tuple(qtype)
        except:
            qtype = qtype,
        return filter(lambda h: h.qtype in qtype, host)

def ip_type(host):
    try:
        if ':' in host:
            # IPv6
            parts = host.split(':')
            if '.' in parts[-1]:
                # IPv4 nested
                assert ip_type(parts.pop()) == types.A
                assert 2 <= len(parts) <= 6
            else:
                assert 3 <= len(parts) <= 8
            for part in parts:
                assert not part or 0 < int(part, 16) < 0xffff
            return types.AAAA
        else:
            # IPv4
            parts = host.split('.')
            assert len(parts) == 4
            for part in parts:
                assert 0 <= int(part) <= 0xff
            return types.A
    except:
        pass

def get_name(data, i):
    a = []
    k = None
    while True:
        l = ord(data[i: i + 1])
        i += 1
        if l == 0:
            if k is None: k = i
            break
        elif l >= 0xc0:
            if k is None: k = i + 1
            i = (l - 0xc0) * 256 + ord(data[i: i+1])
            continue
        a.append(data[i: i + l])
        i += l
    return k, b'.'.join(a).decode().lower()

def pack_string(s, b = 'B'):
    if not isinstance(s, bytes):
        s = s.encode()
    l = len(s)
    return struct.pack('%s%ds' % (b, l), l, s)

def pack_name(name, buf = None, names = {}, offset = 0):
    parts = name.split('.')
    if buf is None:
        buf = io.BytesIO()
    while parts:
        subname = '.'.join(parts)
        u = names.get(subname)
        if u:
            buf.write(struct.pack('!H', 0xc000 + u))
            break
        else:
            names[subname] = buf.tell() + offset
        buf.write(pack_string(parts.pop(0)))
    else:
        buf.write(b'\0')
    return buf.getvalue()

class DNSMessage:
    def __init__(self, qr = RESPONSE, qid = 0, o = 0, aa = 0, tc = 0, rd = 1, ra = 0, r = 0):
        self.qr = qr      # 0 for request, 1 for response
        self.qid = qid    # id for UDP package
        self.o = o        # opcode: 0 for standard query
        self.aa = aa      # Authoritative Answer
        self.tc = tc      # TrunCation
        self.rd = rd      # Recursion Desired for request
        self.ra = ra      # Recursion Available for response
        self.r = r        # rcode: 0 for success
        self.qd = []
        self.an = []
        self.ns = []
        self.ar = []

    def __getitem__(self, i):
        return self.an[i]

    def __iter__(self):
        return iter(self.an)

    def __repr__(self):
        return 'QD: %s\nAN: %s\nNS: %s\nAR: %s' % (self.qd, self.an, self.ns, self.ar)

    def pack(self):
        z = 0
        # TODO update self.tc
        buf = io.BytesIO()
        names = {}
        buf.write(struct.pack('!HHHHHH', self.qid,
            ((((((self.qr*16 + self.o) * 2 + self.aa) * 2 + self.tc) * 2 + self.rd) * 2 + self.ra) * 8 + z) * 16 + self.r,
            len(self.qd), len(self.an), len(self.ns), len(self.ar)))
        for i in self.qd, self.an, self.ns, self.ar:
            for j in i: j.pack(buf, names)
        return buf.getvalue()

def get_bits(x, b):
    return x % b, x // b

def parse_entry(qr, data, l, n, res):
    for i in range(n):
        r = Record(qr)
        l = r.parse(data, l)
        if res is not None:
            res.append(r)
    return l

def dns_request(qid = None, recursive = 1):
    if qid is None:
        qid = random.randint(0, 65535)
    req = DNSMessage(REQUEST, qid, rd = recursive)
    return req

def raw_parse(data, qid = None):
    _qid, x, qd, an, ns, ar = struct.unpack('!HHHHHH', data[:12])
    if qid is not None and qid != _qid:
        raise DNSError(-1, 'Message id does not match!')
    r, x = get_bits(x, 16)
    z, x = get_bits(x, 8)
    ra, x = get_bits(x, 2)
    rd, x = get_bits(x, 2)
    tc, x = get_bits(x, 2)
    aa, x = get_bits(x, 2)
    o, x = get_bits(x, 8)
    qr, x = get_bits(x, 2)
    ans = DNSMessage(qr, _qid, o, aa, tc, rd, ra, r)
    l = parse_entry(REQUEST, data, 12, qd, ans.qd)
    l = parse_entry(RESPONSE, data, l, an, ans.an)
    l = parse_entry(RESPONSE, data, l, ns, ans.ns)
    l = parse_entry(RESPONSE, data, l, ar, ans.ar)
    return ans

# Shim for Python 3.4-
#
# def inet_ntop(fa, ip):
#     if fa == socket.AF_INET:
#         return socket.inet_ntoa(ip)
#     elif fa == socket.AF_INET6:
#         z = 0
#         a = []
#         for i in struct.unpack('!HHHHHHHH', ip):
#             if i == 0:
#                 if z < 2:
#                     z += 1
#                     if z == 2: a[-1] = ''
#             elif z == 2:
#                 z = 3
#             elif z < 2:
#                 z = 0
#             if z != 2:
#                 a.append('%x' % i)
#         if not a[-1]:
#             a.append('')
#         if not a[0]:
#             a.insert(0,'')
#         return ':'.join(a)
#
# def inet_pton(fa, ip):
#     if fa == socket.AF_INET:
#         return socket.inet_aton(ip)
#     elif fa == socket.AF_INET6:
#         ip_parts = ip.split(':')
#         if ip_parts[-1].find('.') > 0:
#             # IPv4 nested IPv6
#             ipv4 = [int(i) for i in ip_parts.pop().split('.')]
#             ip_parts.append(ipv4[0] * 256 + ipv4[1])
#             ip_parts.append(ipv4[2] * 256 + ipv4[3])
#         if not ip_parts[0]: ip_parts.pop(0)
#         if not ip_parts[-1]: ip_parts.pop()
#         l = len(ip_parts)
#         b = []
#         for i in ip_parts:
#             if isinstance(i, int): b.append(i)
#             elif i: b.append(int(i, 16))
#             else: b.extend([0] * (9 - l))
#         return struct.pack('!HHHHHHHH',*b)
#
# if not hasattr(socket, 'inet_ntop'): socket.inet_ntop = inet_ntop
# if not hasattr(socket, 'inet_pton'): socket.inet_pton = inet_pton

if os.name == 'nt':
    import sys, winreg
    def _nt_read_key(lm, key):
        regkey = winreg.OpenKey(lm, key)
        try:
            value, rtype = winreg.QueryValueEx(regkey, 'NameServer')
            if not value:
                value, rtype = winreg.QueryValueEx(regkey, 'DhcpNameServer')
        except:
            value = None
        regkey.Close()
        if value:
            sep = ',' if ',' in value else ' '
            nameservers.extend(value.split(sep))
    def _nt_is_enabled(lm, guid):
        connection_key = winreg.OpenKey(lm, r'SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}\%s\Connection' % guid)
        (pnp_id, ttype) = winreg.QueryValueEx(connection_key, 'PnpInstanceID')
        device_key = winreg.OpenKey(lm, r'SYSTEM\CurrentControlSet\Enum\%s' % pnp_id)
        try:
            flags, ttype = winreg.QueryValueEx(device_key, 'ConfigFlags')
            return not (flags & 0x1)
        finally:
            device_key.Close()
        connection_key.Close()
        return False
    def get_servers():
        lm = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        _nt_read_key(lm, r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters')
        interfaces = winreg.OpenKey(lm, r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces')
        i = 0
        while True:
            try:
                guid = winreg.EnumKey(interfaces, i)
                i += 1
                if not _nt_is_enabled(lm, guid): continue
                _nt_read_key(interfaces, guid)
            except EnvironmentError:
                break
        interfaces.Close()
        lm.Close()

elif os.name == 'posix':
    def get_servers(filename = '/etc/resolv.conf'):
        for line in open(filename, 'r'):
            if line.startswith('#'): continue
            parts = line.split()
            if len(parts) < 2: continue
            if parts[0] == 'nameserver':
                nameservers.append(parts[1])
