'''
Asynchronous DNS client
'''
import asyncio
import os
from .query import Query
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

    # If listed in root domains, the result will be regarded as authorative, e.g. ['.lan']
    rootdomains = []

    def __init__(self, protocol=UDP, cache=None, request_timeout=3.0, timeout=5.0):
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

    async def query(self, fqdn, qtype=types.ANY, timeout=None, tick=5):
        '''Return query result.

        Cache queries for hostnames and types to avoid repeated requests at the same time.
        '''
        result, _from_cache = await self.query_with_cache(fqdn, qtype, timeout)
        return result

    async def query_with_cache(self, fqdn, qtype, timeout=None, tick=5):
        if timeout is None:
            timeout = self.timeout
        future = self.memoized_query(fqdn, qtype, tick)
        try:
            return await asyncio.wait_for(future, timeout)
        except (AssertionError, asyncio.TimeoutError, asyncio.CancelledError):
            import traceback
            logger.debug('[query_with_cache][%s][%s] %s', types.get_name(qtype), fqdn, traceback.format_exc())
            return None, False

    def memoized_query(self, fqdn, qtype, tick):
        if fqdn.endswith('.'):
            fqdn = fqdn[:-1]
        if qtype is types.ANY:
            try:
                addr = Address(fqdn)
                ptr_name = addr.to_ptr()
            except (InvalidHost, InvalidIP):
                pass
            else:
                fqdn = ptr_name
                qtype = types.PTR
        key = fqdn, qtype
        future = self.futures.get(key)
        if future is None:
            loop = asyncio.get_event_loop()
            assert tick > 1, 'Maximum nested query times exceeded'
            query = Query(self, loop, fqdn, qtype, tick - 1)
            future = query.future
            self.futures[key] = future
            def clear(future):
                self.futures.pop(key, None)
            future.add_done_callback(clear)
            asyncio.ensure_future(query.query())
        return future

    def get_nameservers(self, fqdn):
        '''Return a generator of parent domains'''
        hosts = []
        if self.recursive:
            cache = self.cache
            empty = True
            while fqdn and empty:
                if fqdn in ('in-addr.arpa',):
                    break
                _sub, _, fqdn = fqdn.partition('.')
                for rec in cache.query(fqdn, types.NS):
                    host = rec.data
                    if Address(host, allow_domain=True).ip_type is None:
                        # host is a hostname instead of IP address
                        for res in cache.query(host, A_TYPES):
                            hosts.append(Address(res.data, 53))
                            empty = False
                    else:
                        hosts.append(Address(host, 53))
                        empty = False
        logger.debug('[get_nameservers][%s] %s', fqdn, hosts)
        return NameServers(hosts)

    def cache_message(self, msg):
        for rec in msg.an + msg.ns + msg.ar:
            if rec.ttl > 0 and rec.qtype not in (types.SOA,):
                self.cache.add(record=rec)

class ProxyResolver(Resolver):
    '''Proxy DNS resolver.
    Resolve hostnames from remote proxy servers instead of root servers.
    '''
    name = 'AsyncDNSProxyResolver'
    default_nameservers = core_config['default_nameservers']
    recursive = 0

    def __init__(self, *k, proxies=None, **kw):
        super().__init__(*k, **kw)
        self.set_proxies(proxies or self.default_nameservers)

    def get_nameservers(self, fqdn):
        logger.debug('[get_proxy_nameservers][%s] %s', fqdn, self.ns_pairs)
        for test, ns in self.ns_pairs:
            if test is None or test(fqdn): break
        else:
            ns = super().get_nameservers(fqdn)
        return NameServers(ns)

    def add_root_servers(self):
        pass

    def set_proxies(self, proxies):
        '''Set proxy servers.

        There are two available structures:

        1.  ['8.8.8.8', '8.8.4.4']
        2.  [
                ('*.lan', ['192.168.1.1']),
                (lambda d: d.endswith('.local'), ['127.0.0.1']),
                (None, ['8.8.8.8', '8.8.4.4']),
            ]
        '''
        ns_pairs = []
        if proxies:
            if isinstance(proxies[0], str):
                ns_pairs.append((None, NameServers(proxies)))
            else:
                for test, ns in proxies:
                    ns_pairs.append((build_tester(test), NameServers(ns)))
        self.ns_pairs = ns_pairs

def build_tester(rule):
    if rule is None or callable(rule): return rule
    assert isinstance(rule, str)
    if rule.startswith('*.'):
        suffix = rule[1:]
        return lambda d: d.endswith(suffix)
    return lambda d: d == rule
