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
        i, mname = utils.load_name(data, l)
        i, rname = utils.load_name(data, i)
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

class MX_RData(RData):
    '''Mail exchanger record'''

    rtype = types.MX

    def __init__(self, *k):
        self.preference, self.exchange = k

    def __repr__(self):
        return '<%s-%s: %s>' % (self.type_name, self.preference, self.exchange)

    @classmethod
    def load(cls, data, l):
        preference, = struct.unpack('!H', data[l: l + 2])
        i, exchange = utils.load_name(data, l + 2)
        return i, cls(preference, exchange)

    def dump(self, pack_name, offset):
        yield struct.pack('!H', self.preference)
        yield pack_name(self.exchange, offset + 4)

class SRV_RData(RData):
    '''Service record'''

    rtype = types.SRV

    def __init__(self, *k):
        self.priority, self.weight, self.port, self.hostname = k

    def __repr__(self):
        return '<%s-%s: %s:%s>' % (self.type_name, self.priority, self.hostname, self.port)

    @classmethod
    def load(cls, data, l):
        priority, weight, port = struct.unpack('!HHH', data[l: l + 6])
        i, hostname = utils.load_name(data, l + 6)
        return i, cls(priority, weight, port, hostname)

    def dump(self, pack_name, offset):
        yield struct.pack('!HHH', self.priority, self.weight, self.port)
        yield pack_name(self.hostname, offset + 8)

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
                _, self.data = MX_RData.load(data, l)
            elif self.qtype == types.SRV:
                _, self.data = SRV_RData.load(data, l)
            elif self.qtype == types.SOA:
                self.data = SOA_RData.load(data, l)
            elif self.qtype in (types.CNAME, types.NS, types.PTR):
                self.data = utils.load_name(data, l)[1]
            else:
                self.data = data[l: l + dl]
            l += dl
        return l

    def pack(self, names, offset=0):
        def pack_name(name, pack_offset):
            return utils.pack_name(name, names, pack_offset)
        buf = io.BytesIO()
        buf.write(utils.pack_name(self.name, names, offset))
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
                data_str = b''.join(self.data.dump(pack_name, offset + buf.tell()))
                buf.write(utils.pack_string(data_str, '!H'))
            elif self.qtype == types.A:
                buf.write(utils.pack_string(socket.inet_aton(self.data), '!H'))
            elif self.qtype == types.AAAA:
                buf.write(utils.pack_string(socket.inet_pton(socket.AF_INET6, self.data), '!H'))
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
