import random, time, socket, struct, io
from . import utils, types

__all__ = [
    'REQUEST', 'RESPONSE', 'DNSError',
    'InternetProtocol', 'UDP', 'TCP',
    'Record', 'DNSMessage',
]

REQUEST = 0
RESPONSE = 1
MAXAGE = 3600000

class InternetProtocol:
    protocols = {}

    def __init__(self, name):
        name = name.lower()
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
TCP = InternetProtocol('tcp')

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

class SOA_RData:
    def __init__(self, data, l):
        i, self.mname = utils.load_name(data, l)
        i, self.rname = utils.load_name(data, i)
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
        l, self.name = utils.load_name(data, l)
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
            elif self.qtype == types.MX:
                # priority, hostname
                self.data = struct.unpack('!H', data[l: l + 2]) + (utils.load_name(data, l + 2)[1], )
            elif self.qtype == types.SRV:
                # priority, weight, port, hostname
                self.data = struct.unpack('!HHH', data[l: l + 6]) + (utils.load_name(data, l + 6)[1], )
            elif self.qtype == types.SOA:
                self.data = SOA_RData(data, l)
            elif self.qtype in (types.CNAME, types.NS, types.PTR):
                self.data = utils.load_name(data, l)[1]
            else:
                self.data = data[l: l + dl]
            l += dl
        return l

    @staticmethod
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
            buf.write(utils.pack_string(parts.pop(0)))
        else:
            buf.write(b'\0')
        return buf.getvalue()

    def pack(self, names, offset=0):
        buf = io.BytesIO()
        chunk = self.pack_name(self.name, names, offset)
        buf.write(chunk)
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
                buf.write(utils.pack_string(socket.inet_aton(self.data), '!H'))
            elif self.qtype == types.AAAA:
                buf.write(utils.pack_string(socket.inet_pton(socket.AF_INET6, self.data), '!H'))
            elif self.qtype == types.MX:
                name = self.pack_name(self.data[1], names, offset + buf.tell() + 4)
                buf.write(utils.pack_string(struct.pack('!H', self.data[0]) + name, '!H'))
            elif self.qtype == types.SRV:
                name = self.pack_name(self.data[3], names, offset + buf.tell() + 8)
                buf.write(utils.pack_string(struct.pack('!HHH', self.data[:3]) + name, '!H'))
            elif self.qtype == types.SOA:
                mname = self.pack_name(self.data[0], names, offset + buf.tell() + 2)
                rname = self.pack_name(self.data[1], names, offset + buf.tell() + 2 + len(mname))
                buf.write(utils.pack_string(mname + rname + struct.pack('!LLLLL', *self.data[2:]), '!H'))
            elif self.qtype in (types.CNAME, types.NS, types.PTR):
                name = self.pack_name(self.data, names, offset + buf.tell() + 2)
                buf.write(utils.pack_string(name, '!H'))
            else:
                buf.write(utils.pack_string(self.data, '!H'))
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

    @classmethod
    def request(cls, qid=None, recursive=1):
        if qid is None:
            qid = random.randint(0, 65535)
        return cls(REQUEST, qid, rd=recursive)

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
        r, x = utils.get_bits(x, 4)   # rcode: 0 for no error
        z, x = utils.get_bits(x, 3)   # reserved
        ra, x = utils.get_bits(x, 1)  # recursion available
        rd, x = utils.get_bits(x, 1)  # recursion desired
        tc, x = utils.get_bits(x, 1)  # truncation
        aa, x = utils.get_bits(x, 1)  # authoritative answer
        o, x = utils.get_bits(x, 4)   # opcode
        qr, x = utils.get_bits(x, 1)  # qr: 0 for query and 1 for response
        ans = cls(qr, rqid, o, aa, tc, rd, ra, r)
        l, ans.qd = ans.parse_entry(REQUEST, data, 12, qd)
        l, ans.an = ans.parse_entry(RESPONSE, data, l, an)
        l, ans.ns = ans.parse_entry(RESPONSE, data, l, ns)
        l, ans.ar = ans.parse_entry(RESPONSE, data, l, ar)
        return ans
