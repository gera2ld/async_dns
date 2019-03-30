'''
Asynchronous DNS client
'''
import asyncio
import os
import random
import socket
import time
from async_dns import (
    REQUEST,
    UDP,
    DNSError,
    DNSMessage,
    InternetProtocol,
    Record,
    types,
)

A_TYPES = types.A, types.AAAA


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
        if fqdn.endswith('.in-addr.arpa'):
            # Reverse DNS lookup only occurs locally
            return
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
