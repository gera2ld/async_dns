'''
Asynchronous DNS client
'''
import asyncio
import os
from . import tcp, udp
from async_dns.core import *
from async_dns.core.cache import CacheNode
__all__ = ['Resolver', 'ProxyResolver']

A_TYPES = types.A, types.AAAA

class Resolver:
    '''
    Asynchronous DNS resolver.
    '''
    name = 'AsyncDNSResolver'
    recursive = 1

    # If listed in root domains, the result will be regarded as authorative
    rootdomains = ['.lan']

    def __init__(self, protocol=UDP, cache=None, request_timeout=3.0, timeout=3.0):
        self.futures = {}
        if cache is None:
            cache = CacheNode()
        self.cache = cache
        self.protocol = InternetProtocol.get(protocol)
        self.request_timeout = request_timeout
        self.timeout = timeout
        self.add_root_servers()

    def add_root_servers(self):
        for rec in get_root_servers():
            self.cache.add(record=rec)

    async def query_cache(self, res, fqdn, qtype):
        '''Returns a boolean whether a cache hit occurs.'''
        # if cached CNAME
        cname = list(self.cache.query(fqdn, types.CNAME))
        if cname:
            res.an.extend(rec.copy(name=fqdn) for rec in cname)
            if all(rec.ttl < 0 for rec in cname):
                res.aa = 1
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
        cache_hit = False
        for rec in self.cache.query(fqdn, qtype):
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
        if any(fqdn.endswith(root) for root in self.rootdomains):
            if not cache_hit:
                # not found
                res.r = 3
                cache_hit = True
            # should only be added for domains that are resolved by this server
            res.aa = 1  # Authoritative answer
            res.ns.append(Record(name=fqdn, qtype=types.NS, data='localhost', ttl=-1))
            res.ar.append(Record(name=fqdn, qtype=types.A, data='127.0.0.1', ttl=-1))
        return cache_hit

    def get_nameservers(self, fqdn):
        '''Return a generator of parent domains'''
        empty = True
        hosts = []
        while fqdn and empty:
            _sub, _, fqdn = fqdn.partition('.')
            for rec in self.cache.query(fqdn, types.NS):
                host = rec.data
                if Address(host, allow_domain=True).ip_type is None:
                    # host is a hostname instead of IP address
                    for res in self.cache.query(host, A_TYPES):
                        hosts.append(Address(res.data, 53))
                        empty = False
                else:
                    hosts.append(Address(host, 53))
                    empty = False
        logger.debug('[get_nameservers][%s] %s', fqdn, hosts)
        return NameServers(hosts)

    async def request(self, req, addr, protocol=None):
        '''Return response to a request.

        Send DNS request data according to `protocol`.
        '''
        if protocol is None:
            protocol = self.protocol
        if protocol is TCP:
            request = tcp.request
        else:
            request = udp.request
        data = await request(req, addr, self.request_timeout)
        return data

    async def get_remote(self, nameservers, req, future=None):
        while True:
            if future and future.cancelled() or not nameservers:
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
        req = DNSMessage(qr=REQUEST)
        has_result = False
        key = fqdn, qtype
        future = self.futures.get(key)
        names = [fqdn]
        nameservers = None
        while not has_result:
            # seems that only one qd is supported by most NS
            if not names: break
            fqdn = names[0]
            if not nameservers:
                nameservers = self.get_nameservers(fqdn)
            req.qd = [Record(REQUEST, fqdn, qtype)]
            logger.debug('[get_remote][%s][%s] %s', types.get_name(qtype), fqdn, nameservers)
            cres = await self.get_remote(nameservers, req, future)
            if not cres: break
            for rec in cres.an + cres.ns + cres.ar:
                if rec.ttl > 0 and rec.qtype not in (types.SOA,):
                    self.cache.add(record=rec)
            cname = []
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
            if self.recursive:
                if not has_result and not cname: cname.append(fqdn)
            else:
                res.ar.extend(cres.ar)
            names = cname
            nameservers = NameServers(i.data for i in cres.ar if i.qtype in A_TYPES)
            if not nameservers:
                for ns_r in cres.ns:
                    host = ns_r.data.mname if ns_r.qtype == types.SOA else ns_r.data
                    try:
                        ns_res = await self.query(host)
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

    async def query(self, fqdn, qtype=types.ANY, timeout=None):
        '''Return query result.

        Cache queries for hostnames and types to avoid repeated requests at the same time.
        '''
        res, _from_cache = await self.query_with_timeout(fqdn, qtype, timeout)
        return res

    async def query_with_timeout(self, fqdn, qtype, timeout=None):
        if timeout is None:
            timeout = self.timeout
        future = self.memoized_query(fqdn, qtype)
        try:
            res, from_cache = await asyncio.wait_for(future, timeout)
        except (AssertionError, asyncio.TimeoutError, asyncio.CancelledError):
            import traceback
            logger.debug('[query_with_timeout][%s][%s] %s', types.get_name(qtype), fqdn, traceback.format_exc())
            return None, False
        else:
            return res, from_cache

    def memoized_query(self, fqdn, qtype):
        key = fqdn, qtype
        future = self.futures.get(key)
        if future is None:
            loop = asyncio.get_event_loop()
            future = self.futures[key] = loop.create_future()
            asyncio.ensure_future(self.do_query(fqdn, qtype))
        return future

    async def do_query(self, fqdn, qtype):
        '''
        Starts a query asynchronously, add the future object to cache.
        '''
        key = fqdn, qtype
        res = DNSMessage(ra=self.recursive)
        res.qd.append(Record(REQUEST, name=fqdn, qtype=qtype))
        future = self.futures[key]
        from_cache = await self.query_cache(res, fqdn, qtype)
        logger.debug('[query_cache][%s][%s] %s', types.get_name(qtype), fqdn, from_cache)
        has_result = from_cache or await self.query_remote(res, fqdn, qtype)
        if not has_result and not res.r:
            res.r = 2
        self.futures.pop(key)
        if not future.cancelled():
            future.set_result((res, from_cache))

class ProxyResolver(Resolver):
    '''Proxy DNS resolver.
    Resolve hostnames from remote proxy servers instead of root servers.
    '''
    name = 'AsyncDNSProxyResolver'
    default_nameservers = [
        '223.5.5.5',
        '223.6.6.6',
    ]

    def __init__(self, *k, proxies=None, **kw):
        super().__init__(*k, **kw)
        self.set_proxies(proxies or self.default_nameservers)

    def get_nameservers(self, fqdn):
        logger.debug('[get_proxy_nameservers][%s] %s', fqdn, self.proxies)
        return NameServers(self.proxies) if self.proxies else super().get_nameservers(fqdn)

    def add_root_servers(self):
        pass

    def set_proxies(self, proxies):
        '''Set proxy servers.'''
        self.proxies = NameServers(proxies)
