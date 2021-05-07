import io
import socket
import struct
import time
from typing import Dict, Iterable, List, Tuple, Union

from . import types
from .util import get_bits, load_domain_name, load_string, pack_domain_name, pack_string

__all__ = [
    'REQUEST',
    'RESPONSE',
    'DNSError',
    'Record',
    'DNSMessage',
    'RData',
    'create_rdata',
    'load_rdata',
]

REQUEST = 0
RESPONSE = 1
MAXAGE = 3600000


class DNSError(Exception):
    errors = {
        1: 'Format error: bad request',
        2: 'Server failure: error occurred',
        3: 'Name error: not exist',
        4: 'Not implemented: query type not supported',
        5: 'Refused: policy reasons'
    }

    def __init__(self, code: int, message: str = None):
        message = self.errors.get(code,
                                  message) or 'Unknown reply code: %d' % code
        super().__init__(message)
        self.code = code


rdata_map = {}


def rdata(cls):
    rdata_map[cls.rtype] = cls
    return cls


def create_rdata(qtype: int, *k) -> 'RData':
    '''Create RData from parsed data.'''
    rcls = rdata_map.get(qtype, Unsupported_RData)
    return rcls(*k)


def load_rdata(qtype: int, data: bytes, l: int,
               size: int) -> Tuple[int, 'RData']:
    '''Load RData from a byte sequence.'''
    rcls = rdata_map.get(qtype)
    if rcls is None:
        return Unsupported_RData.load(data, l, size, qtype)
    return rcls.load(data, l, size)


class RData:
    '''Base class of RData'''
    rtype = -1
    data = None

    def __hash__(self):
        return hash(self.data)

    def __eq__(self, other: 'RData'):
        return self.__class__ == other.__class__ and self.data == other.data

    def __repr__(self):
        return '<%s: %s>' % (self.type_name, self.data)

    @property
    def type_name(self):
        return types.get_name(self.rtype).lower()

    @classmethod
    def load(cls, data: bytes, l: int, size: int):
        raise NotImplementedError

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        raise NotImplementedError


@rdata
class A_RData(RData):
    '''A record'''
    rtype = types.A

    def __init__(self, data: str):
        self.data = data

    @classmethod
    def load(cls, data: bytes, l: int, size: int):
        ip = socket.inet_ntoa(data[l:l + size])
        return l + size, cls(ip)

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        yield socket.inet_aton(self.data)


@rdata
class AAAA_RData(RData):
    '''AAAA record'''
    rtype = types.AAAA

    def __init__(self, data: str):
        self.data = data

    @classmethod
    def load(cls, data: bytes, l: int, size: int):
        ip = socket.inet_ntop(socket.AF_INET6, data[l:l + size])
        return l + size, cls(ip)

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        yield socket.inet_pton(socket.AF_INET6, self.data)


@rdata
class SOA_RData(RData):
    '''Start of Authority record'''
    rtype = types.SOA

    def __init__(self, *k):
        self.data = k
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
    def load(cls, data: bytes, l: int, size: int) -> Tuple[int, 'SOA_RData']:
        i, mname = load_domain_name(data, l)
        i, rname = load_domain_name(data, i)
        (
            serial,
            refresh,
            retry,
            expire,
            minimum,
        ) = struct.unpack('!LLLLL', data[i:i + 20])
        return i + 20, cls(mname, rname, serial, refresh, retry, expire,
                           minimum)

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        mname = pack_domain_name(self.mname, names, offset + 2)
        yield mname
        yield pack_domain_name(self.rname, names, offset + 2 + len(mname))
        yield struct.pack('!LLLLL', self.serial, self.refresh, self.retry,
                          self.expire, self.minimum)


@rdata
class MX_RData(RData):
    '''Mail exchanger record'''

    rtype = types.MX

    def __init__(self, *k):
        self.data = k
        self.preference, self.exchange = k

    def __repr__(self):
        return '<%s-%s: %s>' % (self.type_name, self.preference, self.exchange)

    @classmethod
    def load(cls, data: bytes, l: int, size: int) -> Tuple[int, 'MX_RData']:
        preference, = struct.unpack('!H', data[l:l + 2])
        i, exchange = load_domain_name(data, l + 2)
        return i, cls(preference, exchange)

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        yield struct.pack('!H', self.preference)
        yield pack_domain_name(self.exchange, names, offset + 4)


@rdata
class SRV_RData(RData):
    '''Service record'''

    rtype = types.SRV

    def __init__(self, *k):
        self.data = k
        self.priority, self.weight, self.port, self.hostname = k

    def __repr__(self):
        return '<%s-%s: %s:%s>' % (self.type_name, self.priority,
                                   self.hostname, self.port)

    @classmethod
    def load(cls, data: bytes, l: int, size: int) -> Tuple[int, 'SRV_RData']:
        priority, weight, port = struct.unpack('!HHH', data[l:l + 6])
        i, hostname = load_domain_name(data, l + 6)
        return i, cls(priority, weight, port, hostname)

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        yield struct.pack('!HHH', self.priority, self.weight, self.port)
        yield pack_domain_name(self.hostname, names, offset + 8)


@rdata
class NAPTR_RData(RData):
    '''NAPTR record'''

    rtype = types.NAPTR

    def __init__(self, *k):
        self.data = k
        self.order, self.preference, self.flags, self.service, self.regexp, self.replacement = k

    def __repr__(self):
        return '<%s-%s-%s: %s %s %s %s>' % (
            self.type_name, self.order, self.preference, self.flags,
            self.service, self.regexp, self.replacement)

    @classmethod
    def load(cls, data: bytes, l: int, size: int) -> Tuple[int, 'NAPTR_RData']:
        pos = l
        order, preference = struct.unpack('!HH', data[pos:pos + 4])
        pos += 4
        length = data[pos]
        pos += 1
        flags = data[pos:pos + length].decode()
        pos += length
        length = data[pos]
        pos += 1
        service = data[pos:pos + length].decode()
        pos += length
        length = data[pos]
        pos += 1
        regexp = data[pos:pos + length].decode()
        pos += length
        i, replacement = load_domain_name(data, pos)
        return i, cls(order, preference, flags, service, regexp, replacement)

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        raise NotImplementedError


class Domain_RData(RData):
    '''Domain record'''
    def __init__(self, data: str):
        self.data = data

    @classmethod
    def load(cls, data: bytes, l: int,
             size: int) -> Tuple[int, 'Domain_RData']:
        l, domain = load_domain_name(data, l)
        return l, cls(domain)

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        yield pack_domain_name(self.data, names, offset + 2)


@rdata
class CNAME_RData(Domain_RData):
    '''CNAME record'''
    rtype = types.CNAME


@rdata
class NS_RData(Domain_RData):
    '''NS record'''

    rtype = types.NS


@rdata
class PTR_RData(Domain_RData):
    '''PTR record'''

    rtype = types.PTR


@rdata
class TXT_RData(RData):
    '''TXT record'''

    rtype = types.TXT

    def __init__(self, data: str):
        self.data = data

    @classmethod
    def load(cls, data: bytes, l: int, size: int) -> Tuple[int, 'TXT_RData']:
        _, text = load_string(data, l)
        return l + size, cls(text.decode())

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        yield pack_string(self.data)


class Unsupported_RData(RData):
    '''Unsupported RData'''
    def __init__(self, rtype: int, raw: bytes):
        self.data = rtype, raw
        self.rtype = rtype
        self.raw = raw

    @classmethod
    def load(cls, data: bytes, l: int, size: int,
             qtype: int) -> Tuple[int, 'Unsupported_RData']:
        return l + size, cls(qtype, data[l:l + size])

    def dump(self, names: Dict[str, int], offset: int) -> Iterable[bytes]:
        yield self.raw


class Record:
    def __init__(self,
                 q: int = RESPONSE,
                 name: str = '',
                 qtype: int = types.ANY,
                 qclass: int = 1,
                 ttl: int = 0,
                 data: RData = None):
        self.q = q
        self.name = name
        self.qtype = qtype
        self.qclass = qclass
        if q == RESPONSE:
            self.ttl = ttl  # 0 means item should not be cached
            self.data = data
            self.timestamp = int(time.time())

    def __repr__(self):
        if self.q == REQUEST:
            return f'<Record type=request qtype={types.get_name(self.qtype)} name={self.name}>'
        else:
            return f'<Record type=response qtype={types.get_name(self.qtype)} name={self.name} ttl={self.ttl} data={self.data}>'

    def copy(self, **kw):
        return Record(q=kw.get('q', self.q),
                      name=kw.get('name', self.name),
                      qtype=kw.get('qtype', self.qtype),
                      qclass=kw.get('qclass', self.qclass),
                      ttl=kw.get('ttl', self.ttl),
                      data=kw.get('data', self.data))

    def parse(self, data: bytes, l: int):
        l, self.name = load_domain_name(data, l)
        self.qtype, self.qclass = struct.unpack('!HH', data[l:l + 4])
        l += 4
        if self.q == RESPONSE:
            self.timestamp = int(time.time())
            self.ttl, dl = struct.unpack('!LH', data[l:l + 6])
            l += 6
            _, self.data = load_rdata(self.qtype, data, l, dl)
            l += dl
        return l

    def pack(self, names, offset=0):
        buf = io.BytesIO()
        buf.write(pack_domain_name(self.name, names, offset))
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
            data_str = b''.join(self.data.dump(names, offset + buf.tell()))
            buf.write(pack_string(data_str, '!H'))
        return buf.getvalue()


class DNSMessage:
    def __init__(self, qr=RESPONSE, qid=0, o=0, aa=0, tc=0, rd=1, ra=1, r=0):
        self.qr = qr  # 0 for request, 1 for response
        self.qid = qid  # id for UDP package
        self.o = o  # opcode: 0 for standard query
        self.aa = aa  # Authoritative Answer
        self.tc = tc  # TrunCation, will be updated on .pack()
        self.rd = rd  # Recursion Desired for request
        self.ra = ra  # Recursion Available for response
        self.r = r  # rcode: 0 for success
        self.qd: List[Record] = []
        self.an: List[Record] = []  # answers
        self.ns: List[Record] = []  # authority records, aka nameservers
        self.ar: List[Record] = []  # additional records

    def __bool__(self):
        return any(map(len, (self.an, self.ns)))

    def __getitem__(self, i):
        return self.an[i]

    def __iter__(self):
        return iter(self.an)

    def __repr__(self):
        return '<DNSMessage type=%s qid=%d r=%d QD=%s AN=%s NS=%s AR=%s>' % (
            self.qr, self.qid, self.r, self.qd, self.an, self.ns, self.ar)

    def pack(self, size_limit: int = None):
        z = 0
        names: Dict[str, int] = {}
        buf = io.BytesIO()
        buf.seek(12)
        tc = 0
        for group in self.qd, self.an, self.ns, self.ar:
            if tc: break
            for rec in group:
                offset = buf.tell()
                brec = rec.pack(names, offset)
                if size_limit is not None and offset + len(brec) > size_limit:
                    tc = 1
                    break
                buf.write(brec)
        self.tc = tc
        buf.seek(0)
        buf.write(
            struct.pack('!HHHHHH', self.qid, (self.qr << 15) + (self.o << 11) +
                        (self.aa << 10) + (self.tc << 9) + (self.rd << 8) +
                        (self.ra << 7) + (z << 4) + self.r, len(self.qd),
                        len(self.an), len(self.ns), len(self.ar)))
        return buf.getvalue()

    @staticmethod
    def parse_entry(qr: int, data: bytes, l: int,
                    n: int) -> Tuple[int, List[Record]]:
        res = []
        for _ in range(n):
            r = Record(qr)
            l = r.parse(data, l)
            res.append(r)
        return l, res

    @classmethod
    def parse(cls, data: bytes, qid: bytes = None):
        rqid, x, qd, an, ns, ar = struct.unpack('!HHHHHH', data[:12])
        if qid is not None and qid != rqid:
            raise DNSError(-1, 'Transaction ID mismatch')
        r, x = get_bits(x, 4)  # rcode: 0 for no error
        z, x = get_bits(x, 3)  # reserved
        ra, x = get_bits(x, 1)  # recursion available
        rd, x = get_bits(x, 1)  # recursion desired
        tc, x = get_bits(x, 1)  # truncation
        aa, x = get_bits(x, 1)  # authoritative answer
        o, x = get_bits(x, 4)  # opcode
        qr, x = get_bits(x, 1)  # qr: 0 for query and 1 for response
        ans = cls(qr, rqid, o, aa, tc, rd, ra, r)
        l, ans.qd = ans.parse_entry(REQUEST, data, 12, qd)
        l, ans.an = ans.parse_entry(RESPONSE, data, l, an)
        l, ans.ns = ans.parse_entry(RESPONSE, data, l, ns)
        l, ans.ar = ans.parse_entry(RESPONSE, data, l, ar)
        return ans

    def get_record(self, qtypes: Union[int, Iterable[int]]):
        '''Get the first record of qtype defined in `qtypes` in answer list.
        '''
        if isinstance(qtypes, int):
            qtypes = qtypes,
        for item in self.an:
            if item.qtype in qtypes:
                return item.data
