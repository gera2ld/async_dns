'''
Asynchronous DNS client
'''
import asyncio
import collections
import io
import os
import random
import socket
import struct
import time

REQUEST = 0
RESPONSE = 1
MAXAGE = 3600000

types = collections.namedtuple('Types', [
    'NONE', 'A', 'NS', 'CNAME', 'SOA', 'PTR', 'MX', 'AAAA', 'SRV', 'NAPTR', 'ANY',
])(
    NONE=0,
    A=1,
    NS=2,
    CNAME=5,
    SOA=6,
    PTR=12,
    MX=15,
    AAAA=28,
    SRV=33,
    NAPTR=35,
    ANY=255,
)

A_TYPES = types.A, types.AAAA

def _is_type(name):
    return not name.startswith('_') and name.upper() == name

_NAME_MAPPING = dict((name, code) for name, code in globals().items() if _is_type(name))
_CODE_MAPPING = dict((code, name) for name, code in globals().items() if _is_type(name))


def load_name(data, offset, lower=True):
    '''Return the full name and offset from packed data.'''
    parts = []
    cursor = None
    while True:
        length = ord(data[offset : offset + 1])
        offset += 1
        if length == 0:
            if cursor is None:
                cursor = offset
            break
        elif length >= 0xc0:
            if cursor is None:
                cursor = offset + 1
            offset = (length - 0xc0) * 256 + ord(data[offset : offset + 1])
            continue
        parts.append(data[offset : offset + length])
        offset += length
    data = b'.'.join(parts).decode()
    if lower:
        data = data.lower()
    return cursor, data

def pack_string(string, btype='B'):
    '''Pack string into `{length}{data}` format.'''
    if not isinstance(string, bytes):
        string = string.encode()
    length = len(string)
    return struct.pack('%s%ds' % (btype, length), length, string)

def get_bits(num, bit_len):
    '''Get lower and higher bits breaking at bit_len from num.'''
    high = num >> bit_len
    low = num - (high << bit_len)
    return low, high

def pack_name(name, names, offset=0):
    parts = name.split('.')
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

def get_name(code, default=None):
    '''
    Get type name from code
    '''
    name = _CODE_MAPPING.get(code, default)
    if name is None:
        name = str(code)
    return name

def get_code(name, default=None):
    '''
    Get code from type name
    '''
    return _NAME_MAPPING.get(name, default)


class InternetProtocol:
    protocols = {}

    def __init__(self, name):
        self.protocol = name
        self.protocols[name] = self

    @classmethod
    def get(cls, name):
        if isinstance(name, cls):
            return name
        if isinstance(name, str):
            name = name.lower()
        return cls.protocols.get(name, UDP)

UDP = InternetProtocol('udp')

class DNSError(Exception):
    errors = {
        1: 'Format error: bad request',
        2: 'Server failure: error occurred',
        3: 'Name error: not exist',
        4: 'Not implemented: query type not supported',
        5: 'Refused: policy reasons'
    }
    def __init__(self, code, message=None):
        message = self.errors.get(code, message) or 'Unknown reply code: %d' % code
        super().__init__(message)
        self.code = code

class RData:
    '''Base class of RData'''
    rtype = -1

    @property
    def type_name(self):
        return types.get_name(self.rtype).lower()

class SOA_RData(RData):
    '''Start of Authority record'''
    rtype = types.SOA

    def __init__(self, *k):
        (
            self.mname,
            self.rname,
            self.serial,
            self.refresh,
            self.retry,
            self.expire,
            self.minimum,
        ) = k

    def __repr__(self):
        return '<%s: %s>' % (self.type_name, self.rname)

    @classmethod
    def load(cls, data, l):
        i, mname = load_name(data, l)
        i, rname = load_name(data, i)
        (
            serial,
            refresh,
            retry,
            expire,
            minimum,
        ) = struct.unpack('!LLLLL', data[i: i + 20])
        return i + 20, cls(mname, rname, serial, refresh, retry, expire, minimum)

    def dump(self, pack_name, offset):
        mname = pack_name(self.mname, offset + 2)
        yield mname
        yield pack_name(self.rname, offset + 2 + len(mname))
        yield struct.pack('!LLLLL', self.serial, self.refresh, self.retry, self.expire, self.minimum)


class Record:
    def __init__(self, q=RESPONSE, name='', qtype=types.ANY, qclass=1, ttl=0, data=None):
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
            return str((self.name, types.get_name(self.qtype)))
        else:
            return str((self.name, types.get_name(self.qtype), self.data, self.ttl))

    def copy(self, **kw):
        return Record(
            q=kw.get('q', self.q),
            name=kw.get('name', self.name),
            qtype=kw.get('qtype', self.qtype),
            qclass=kw.get('qclass', self.qclass),
            ttl=kw.get('ttl', self.ttl),
            data=kw.get('data', self.data)
        )

    def update(self, other):
        if (self.name, self.qtype, self.data) == (other.name, other.qtype, other.data):
            if self.ttl and other.ttl > self.ttl:
                self.ttl = other.ttl
            return self

    def parse(self, data, l):
        l, self.name = load_name(data, l)
        self.qtype, self.qclass = struct.unpack('!HH', data[l: l + 4])
        l += 4
        if self.q == RESPONSE:
            self.timestamp = int(time.time())
            self.ttl, dl = struct.unpack('!LH', data[l: l + 6])
            l += 6
            if self.qtype == types.A:
                self.data = socket.inet_ntoa(data[l: l + dl])
            elif self.qtype == types.AAAA:
                self.data = socket.inet_ntop(socket.AF_INET6, data[l: l + dl])
            elif self.qtype == types.SOA:
                _, self.data = SOA_RData.load(data, l)
            elif self.qtype in (types.CNAME, types.NS, types.PTR):
                _, self.data = load_name(data, l)
            else:
                self.data = data[l: l + dl]
            l += dl
        return l

    def pack(self, names, offset=0):
        def pack_name_local(name, pack_offset):
            return pack_name(name, names, pack_offset)
        buf = io.BytesIO()
        buf.write(pack_name(self.name, names, offset))
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
            if isinstance(self.data, RData):
                data_str = b''.join(self.data.dump(pack_name_local, offset + buf.tell()))
                buf.write(pack_string(data_str, '!H'))
            elif self.qtype == types.A:
                buf.write(pack_string(socket.inet_aton(self.data), '!H'))
            elif self.qtype == types.AAAA:
                buf.write(pack_string(socket.inet_pton(socket.AF_INET6, self.data), '!H'))
            elif self.qtype in (types.CNAME, types.NS, types.PTR):
                name = pack_name_local(self.data, offset + buf.tell() + 2)
                buf.write(pack_string(name, '!H'))
            else:
                buf.write(pack_string(self.data, '!H'))
        return buf.getvalue()

class DNSMessage:
    def __init__(self, qr=RESPONSE, qid=0, o=0, aa=0, tc=0, rd=1, ra=0, r=0):
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
        buf.write(struct.pack(
            '!HHHHHH',
            self.qid,
            (self.qr << 15) + (self.o << 11) + (self.aa << 10) + (self.tc << 9) + (self.rd << 8) + (self.ra << 7) + (z << 4) + self.r,
            len(self.qd),
            len(self.an),
            len(self.ns),
            len(self.ar)
        ))
        for group in self.qd, self.an, self.ns, self.ar:
            for rec in group:
                buf.write(rec.pack(names, buf.tell()))
        return buf.getvalue()

    @staticmethod
    def parse_entry(qr, data, l, n):
        res = []
        for i in range(n):
            r = Record(qr)
            l = r.parse(data, l)
            res.append(r)
        return l, res

    @classmethod
    def parse(cls, data, qid=None):
        rqid, x, qd, an, ns, ar = struct.unpack('!HHHHHH', data[:12])
        if qid is not None and qid != rqid:
            raise DNSError(-1, 'Message id does not match!')
        r, x = get_bits(x, 4)   # rcode: 0 for no error
        z, x = get_bits(x, 3)   # reserved
        ra, x = get_bits(x, 1)  # recursion available
        rd, x = get_bits(x, 1)  # recursion desired
        tc, x = get_bits(x, 1)  # truncation
        aa, x = get_bits(x, 1)  # authoritative answer
        o, x = get_bits(x, 4)   # opcode
        qr, x = get_bits(x, 1)  # qr: 0 for query and 1 for response
        ans = cls(qr, rqid, o, aa, tc, rd, ra, r)
        l, ans.qd = ans.parse_entry(REQUEST, data, 12, qd)
        l, ans.an = ans.parse_entry(RESPONSE, data, l, an)
        l, ans.ns = ans.parse_entry(RESPONSE, data, l, ns)
        l, ans.ar = ans.parse_entry(RESPONSE, data, l, ar)
        return ans


class Hosts:
    def __init__(self):
        self.data = {}
        self.changed = False
        self.add_item('localhost', types.A, '127.0.0.1')

    def __bool__(self):
        return bool(self.data)

    def __repr__(self):
        return '<%s [%s]>' % (self.__class__.__name__, ', '.join(self.data.keys()))

    def update(self, other):
        for k, v in other.data.items():
            item = self.data.setdefault(k, [])
            item.extend(v)

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

    def add_item(self, name, qtype, data):
        '''
        Add an item to cache.
        '''
        self.add_host(Record(name=name, data=data, qtype=qtype, ttl=-1))

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



class InvalidHost(Exception):
    pass

class Address:
    def __init__(self, hostname, port=0, allow_domain=False):
        self.parse(hostname, port, allow_domain)

    def __eq__(self, other):
        return self.host == other.host and self.port == other.port

    def __repr__(self):
        return self.to_str()

    def parse(self, hostname, port=0, allow_domain=False):
        if isinstance(hostname, tuple):
            self.parse_tuple(hostname, allow_domain)
        elif isinstance(hostname, Address):
            self.parse_address(hostname)
        elif hostname.count(':') > 1:
            self.parse_ipv6(hostname, port)
        else:
            self.parse_ipv4_or_domain(hostname, port, allow_domain)

    def parse_tuple(self, addr, allow_domain=False):
        host, port = addr
        self.parse(host, port, allow_domain)

    def parse_address(self, addr):
        self.host, self.port, self.ip_type = addr.host, addr.port, addr.ip_type

    def parse_ipv4_or_domain(self, hostname, port=None, allow_domain=False):
        try:
            self.parse_ipv4(hostname, port)
        except InvalidHost as e:
            if not allow_domain:
                raise e
            host, _, port_s = hostname.partition(':')
            if _:
                port = int(port_s)
            self.host, self.port, self.ip_type = host, port, None

    def parse_ipv4(self, hostname, port=None):
        host, _, port_s = hostname.partition(':')
        if _:
            port = int(port_s)
        try:
            socket.inet_pton(socket.AF_INET, host)
        except OSError:
            raise InvalidHost(host)
        self.host, self.port, self.ip_type = host, port, types.A

    def parse_ipv6(self, hostname, port=None):
        if hostname.startswith('['):
            i = hostname.index(']')
            host = hostname[1 : i]
            port_s = hostname[i + 1 :]
            if port_s:
                if not port_s.startswith(':'):
                    raise InvalidHost(hostname)
                port = int(port_s[1:])
        else:
            host = hostname
        try:
            socket.inet_pton(socket.AF_INET6, host)
        except OSError:
            raise InvalidHost(host)
        self.host, self.port, self.ip_type = host, port, types.AAAA

    def to_str(self, default_port = 0):
        if default_port is None or self.port == default_port:
            return self.host
        if self.ip_type is types.A:
            return '%s:%d' % self.to_addr()
        elif self.ip_type is types.AAAA:
            return '[%s]:%d' % self.to_addr()

    def to_addr(self):
        return self.host, self.port

class NameServers:
    def __init__(self, nameservers=None, default_port=53):
        self.default_port = default_port
        self.data = []
        if nameservers:
            for nameserver in nameservers:
                self.add(nameserver)

    def __bool__(self):
        return len(self.data) > 0

    def __iter__(self):
        return iter(tuple(self.data))

    def __repr__(self):
        return '<NameServers [%s]>' % ','.join(map(str, self.data))

    def get(self):
        return random.choice(self.data)

    def add(self, addr):
        self.data.append(Address(addr, self.default_port))

    def fail(self, addr):
        # TODO
        pass



class CallbackProtocol(asyncio.DatagramProtocol):
    '''
    Protocol class for asyncio connection callback.
    '''

    def __init__(self):
        super().__init__()
        self.transport = None
        self.futures = {}

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        qid = data[:2]
        future = self.futures.pop(qid, None)
        if future is not None and not future.cancelled():
            future.set_result(data)

    def write_data(self, data, addr):
        '''
        Write data to request.
        '''
        qid = data[:2]
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.futures[qid] = future
        self.transport.sendto(data, addr)
        return future

class Dispatcher:
    data = {}

    def __init__(self, ip_type, local_addr=None):
        self._qid = 0
        self.ip_type = ip_type
        self.local_addr = local_addr
        self.initialized = None

    def get_qid(self):
        self._qid = (self._qid + 1) % 65536
        return self._qid

    async def initialize(self):
        if self.initialized is not None:
            await self.initialized
            return
        loop = asyncio.get_event_loop()
        self.initialized = loop.create_future()
        family = socket.AF_INET6 if self.ip_type is types.AAAA else socket.AF_INET
        _transport, self.protocol = await loop.create_datagram_endpoint(
                CallbackProtocol, family=family, reuse_port=True, local_addr=self.local_addr)
        self.initialized.set_result(None)

    def send(self, req, addr):
        req.qid = self.get_qid()
        return self.protocol.write_data(req.pack(), addr.to_addr())

    @classmethod
    async def get(cls, ip_type):
        dispatcher = cls.data.get(ip_type)
        if dispatcher is None:
            dispatcher = Dispatcher(ip_type)
            cls.data[ip_type] = dispatcher
        await dispatcher.initialize()
        return dispatcher

async def upd_request(req, addr, timeout=3.0):
    '''
    Send raw data through UDP.
    '''
    dispatcher = await Dispatcher.get(addr.ip_type)
    data = await asyncio.wait_for(dispatcher.send(req, addr), timeout)
    return data


class Resolver:
    '''
    Asynchronous DNS resolver.
    '''
    recursive = 1

    def __init__(self, protocol=UDP, request_timeout=3.0, timeout=3.0):
        self.futures = {}
        cache = Hosts()
        self.cache = cache
        self.protocol = InternetProtocol.get(protocol)
        self.request_timeout = request_timeout
        self.timeout = timeout

    async def query_cache(self, res, fqdn, qtype):
        '''Returns a boolean whether a cache hit occurs.'''
        # if cached CNAME
        cname = list(self.cache.query(fqdn, types.CNAME))
        if cname:
            res.an.extend(cname)
            if not self.recursive or qtype == types.CNAME:
                return True
            for rec in cname:
                cres = await self.query(rec.data, qtype)
                if cres is None or cres.r > 0:
                    continue
                res.an.extend(cres.an)
                res.ns = cres.ns
                res.ar = cres.ar
            return True
        # else
        data = list(self.cache.query(fqdn, qtype))
        cache_hit = False
        if data:
            for rec in data:
                if rec.qtype in (types.NS,):
                    nres = list(self.cache.query(rec.data, A_TYPES))
                    if nres:
                        res.ar.extend(nres)
                        res.ns.append(rec)
                        if rec.qtype == qtype:
                            cache_hit = True
                else:
                    res.an.append(rec.copy(name=fqdn))
                    if qtype == types.CNAME or rec.qtype != types.CNAME:
                        cache_hit = True
        return cache_hit

    def get_nameservers(self, fdqn):
        filename='/etc/resolv.conf'
        nameservers = []
        with open(filename, 'r') as file:
            for line in file:
                if line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                if parts[0] == 'nameserver':
                    nameservers.append(parts[1])
        return NameServers(nameservers)

    async def request(self, req, addr, protocol=None):
        '''Return response to a request.

        Send DNS request data according to `protocol`.
        '''
        if protocol is None:
            protocol = self.protocol
        request = upd_request
        data = await request(req, addr, self.request_timeout)
        return data

    async def get_remote(self, nameservers, req, future=None):
        while True:
            if future and future.cancelled():
                break
            addr = nameservers.get()
            try:
                data = await self.request(req, addr)
                cres = DNSMessage.parse(data)
                assert cres.r != 2
            except (asyncio.TimeoutError, AssertionError):
                nameservers.fail(addr)
            except DNSError:
                pass
            else:
                return cres

    async def query_remote(self, res, fqdn, qtype):
        '''Return a boolean indicating whether results are found.

        No cache is used and requests are sent to remote servers.
        '''
        # look up from other DNS servers
        nameservers = self.get_nameservers(fqdn)
        cname = [fqdn]
        req = DNSMessage(qr=REQUEST)
        has_result = False
        key = fqdn, qtype
        future = self.futures.get(key)
        while not has_result:
            if not cname:
                break
            # seems that only one qd is supported by most NS
            req.qd = [Record(REQUEST, cname[0], qtype)]
            del cname[:]
            cres = await self.get_remote(nameservers, req, future)
            if not cres: break
            for rec in cres.an + cres.ns + cres.ar:
                if rec.ttl > 0 and rec.qtype not in (types.SOA, types.MX):
                    self.cache.add_host(rec)
            for rec in cres.an:
                res.an.append(rec)
                if rec.qtype == types.CNAME:
                    cname.append(rec.data)
                if qtype == types.CNAME or rec.qtype != types.CNAME:
                    has_result = True
            for rec in cres.ns:
                if not self.recursive:
                    res.ns.append(rec)
                    has_result = True
                elif rec.qtype == types.SOA or qtype == types.NS:
                    has_result = True
            if not self.recursive:
                res.ar.extend(cres.ar)
            nameservers = NameServers(i.data for i in cres.ar if i.qtype in A_TYPES)
            if not nameservers:
                for ns_r in cres.ns:
                    host = ns_r.data.mname if ns_r.qtype == types.SOA else ns_r.data
                    try:
                        ns_res = await self(host)
                        assert ns_res
                    except (AssertionError, asyncio.TimeoutError):
                        pass
                    except Exception as e:
                        logger.error(host)
                        logger.error(e)
                    else:
                        if ns_res:
                            for ans in ns_res.an:
                                if ans.qtype in A_TYPES:
                                    nameservers.add(ans.data)
            res.r = cres.r
        return has_result

    async def __call__(self, fqdn, qtype=types.ANY, timeout=None):
        '''Return query result.

        Cache queries for hostnames and types to avoid repeated requests at the same time.
        '''
        key = fqdn, qtype
        future = self.futures.get(key)
        if future is None:
            loop = asyncio.get_event_loop()
            future = self.futures[key] = loop.create_future()
            asyncio.ensure_future(self.do_query(fqdn, qtype))
        if timeout is None:
            timeout = self.timeout
        try:
            res = await asyncio.wait_for(future, timeout)
        except (AssertionError, asyncio.TimeoutError, asyncio.CancelledError):
            pass
        else:
            return res

    async def do_query(self, fqdn, qtype):
        '''
        Starts a query asynchronously, add the future object to cache.
        '''
        key = fqdn, qtype
        res = DNSMessage(ra=self.recursive)
        res.qd.append(Record(REQUEST, name=fqdn, qtype=qtype))
        future = self.futures[key]
        ret = (
            await self.query_cache(res, fqdn, qtype)
        ) or (
            await self.query_remote(res, fqdn, qtype)
        )
        if not ret and not res.r:
            res.r = 2
        self.futures.pop(key)
        if not future.cancelled():
            future.set_result(res)
