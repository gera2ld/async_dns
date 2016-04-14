#!/usr/bin/env python
# coding=utf-8
'''
Asynchronous DNS client to query a queue of domains asynchronously.
This is designed to improve performance of the server.
'''
import asyncio, os, logging
from . import utils, types, address

A_TYPES = types.A, types.AAAA

cachefile = os.path.expanduser('~/.gerald/named.cache.txt')
def get_name_cache(url = 'ftp://rs.internic.net/domain/named.cache',
        fname = cachefile):
    from urllib import request
    logging.info('Fetching named.cache...')
    try:
        r = request.urlopen(url)
    except:
        logging.warning('Error fetching named.cache')
    else:
        open(fname, 'wb').write(r.read())
def get_root_servers(fname = cachefile):
    if not os.path.isfile(fname):
        os.makedirs(os.path.dirname(fname), exist_ok = True)
        get_name_cache(fname = fname)
    # in case failed fetching named.cache
    if os.path.isfile(fname):
        for line in open(fname, 'r'):
            if line.startswith(';'): continue
            it = iter(filter(None, line.split()))
            data = [next(it).rstrip('.')]   # name
            expires = next(it)  # ignored
            data.append(types.MAP_TYPES.get(next(it), 0))   # qtype
            data.append(next(it).rstrip('.'))   # data
            yield data

class CallbackProtocol(asyncio.DatagramProtocol):
    def __init__(self, future):
        self.future = future

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.transport.close()
        if not self.future.cancelled():
            self.future.set_result((data, addr))

class DNSMemCache(utils.Hosts):
    name = 'DNSMemD/Gerald'
    def __init__(self, filename = None):
        super().__init__(filename)
        self.add_item('1.0.0.127.in-addr.arpa', types.PTR, self.name)
        self.add_item('localhost', types.A, '127.0.0.1')
        for i in get_root_servers():
            self.add_item(*i)

    def add_item(self, key, qtype, data):
        self.add_host(utils.Record(name = key, data = data, qtype = qtype, ttl = -1))

class AsyncResolver:
    recursive = 1
    rootdomains = ['.lan']
    def __init__(self):
        self.queue = asyncio.Queue()
        self.futures = {}
        self.lock = asyncio.Lock()
        self.cache = DNSMemCache()
        asyncio.ensure_future(self.loop())

    async def query_future(self, fqdn, qtype = types.ANY):
        key = fqdn, qtype
        with (await self.lock):
            future = self.futures.get(key)
            if future is None:
                future = self.futures[key] = asyncio.Future()
                await self.queue.put(key)
        return future

    async def query_cache(self, res, fqdn, qtype):
        # cached CNAME
        cname = list(self.cache.query(fqdn, types.CNAME))
        if cname:
            res.an.extend(cname)
            if not self.recursive or qtype == types.CNAME:
                return True
            for rec in cname:
                cres = await self.query(rec.data, qtype)
                if cres is None or cres.r > 0: continue
                res.an.extend(cres.an)
                res.ns = cres.ns
                res.ar = cres.ar
            return True
        # cached else
        data = list(self.cache.query(fqdn, qtype))
        n = 0
        if data:
            for rec in data:
                if rec.qtype in (types.NS,):
                    nres = list(self.cache.query(r.data, A_TYPES))
                    empty = not nres
                    if not empty:
                        res.ar.extend(nres)
                        res.ns.append(rec)
                        if rec.qtype == qtype: n += 1
                else:
                    res.an.append(rec.copy(name = fqdn))
                    if qtype == types.CNAME or rec.qtype != types.CNAME:
                        n += 1
        if list(filter(None, map(fqdn.endswith, self.rootdomains))):
            if not n:
                res.r = 3
                n = 1
            # can only be added for domains that are resolved by this server
            res.aa = 1  # Authoritative answer
            res.ns.append(utils.Record(name = fqdn, qtype = types.NS, data = 'localhost', ttl = -1))
            res.ar.append(utils.Record(name = fqdn, qtype = types.A, data = '127.0.0.1', ttl = -1))
        if n:
            return True

    def get_nameservers(self, fqdn):
        empty = True
        while fqdn and empty:
            sub, _, fqdn = fqdn.partition('.')
            for rec in self.cache.query(fqdn, types.NS):
                host = rec.data
                if address.Address(host, allow_domain=True).ip_type is None:
                    for r in self.cache.query(host, A_TYPES):
                        yield address.Address(r.data, 53)
                        empty = False
                else:
                    yield address.Address(host, 53)
                    empty = False

    async def query_remote(self, res, fqdn, qtype):
        # look up from other DNS servers
        nameservers = address.NameServers(self.get_nameservers(fqdn))
        cname = [fqdn]
        req = utils.dns_request()
        n = 0
        while not n:
            if not cname: break
            # XXX it seems that only one qd is supported by most NS
            req.qd = [utils.Record(utils.REQUEST, cname[0], qtype)]
            qdata = req.pack()
            del cname[:]
            qid = qdata[:2]
            loop = asyncio.get_event_loop()
            for addr in nameservers:
                future = asyncio.Future()
                try:
                    transport, protocol = await asyncio.wait_for(
                        loop.create_datagram_endpoint(lambda : CallbackProtocol(future), remote_addr = addr.to_addr()),
                        1.0
                    )
                    transport.sendto(qdata)
                    data, _addr = await asyncio.wait_for(future, 3.0)
                    transport.close()
                    if not data.startswith(qid):
                        raise utils.DNSError(-1, 'Message id does not match!')
                    cres = utils.raw_parse(data)
                    assert cres.r != 2
                except (asyncio.TimeoutError, AssertionError):
                    nameservers.fail(addr)
                except utils.DNSError:
                    pass
                else:
                    break
            else:
                break
            for r in cres.an + cres.ns + cres.ar:
                if r.ttl > 0 and r.qtype not in (types.SOA, types.MX):
                    self.cache.add_host(r)
            for r in cres.an:
                res.an.append(r)
                if r.qtype == types.CNAME:
                    cname.append(r.data)
                if qtype == types.CNAME or r.qtype != types.CNAME:
                    n += 1
            for r in cres.ns:
                if not self.recursive:
                    res.ns.append(r)
                    n += 1
                elif r.qtype == types.SOA or qtype == types.NS:
                    n += 1
            if not self.recursive:
                res.ar.extend(cres.ar)
            nameservers = address.NameServers([i.data for i in cres.ar if i.qtype in A_TYPES])
            if not nameservers:
                for i in cres.ns:
                    host = i.data.mname if i.qtype == types.SOA else i.data
                    try:
                        ns = await self.query(host)
                        assert ns
                    except (AssertionError, asyncio.TimeoutError):
                        pass
                    except Exception as e:
                        logging.error(host)
                        logging.error(e)
                    else:
                        if ns:
                            for j in ns.an:
                                if j.qtype in A_TYPES:
                                    nameservers.add(j.data)
            res.r = cres.r
        return n > 0

    async def query(self, fqdn, qtype = types.ANY):
        logging.debug('query %s', fqdn)
        future = await self.query_future(fqdn, qtype)
        try:
            res = await asyncio.wait_for(future, 3.0)
        except (AssertionError, asyncio.TimeoutError, asyncio.CancelledError):
            pass
        else:
            return res

    async def query_key(self, key):
        fqdn, qtype = key
        res = utils.DNSMessage(ra = self.recursive)
        res.qd.append(utils.Record(utils.REQUEST, name = fqdn, qtype = qtype))
        future = self.futures[key]
        ret = (await self.query_cache(res, fqdn, qtype)) or (await self.query_remote(res, fqdn, qtype))
        if not ret and not res.r:
            res.r = 2
        with (await self.lock):
            self.futures.pop(key)
        if not future.cancelled():
            future.set_result(res)

    async def loop(self):
        while True:
            key = await self.queue.get()
            asyncio.ensure_future(self.query_key(key))

class AsyncProxyResolver(AsyncResolver):
    proxies = address.NameServers(['114.114.114.114', '180.76.76.76', '223.5.5.5', '223.6.6.6'])

    def get_nameservers(self, fdqn = None):
        return self.proxies

    def set_proxies(self, proxies):
        self.proxies = address.NameServers(proxies)
