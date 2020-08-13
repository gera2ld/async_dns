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

    def __init__(self, cache=None, request_timeout=3.0, timeout=5.0):
        self._queries = {}
        if cache is None:
            cache = CacheNode()
        self.cache = cache
        self.request_timeout = request_timeout
        self.timeout = timeout
        self.add_root_servers()

    def add_root_servers(self):
        for rec in get_root_servers():
            self.cache.add(record=rec)

    async def query(self, fqdn, qtype=types.ANY, timeout=None, tick=5):
        '''Return query result. Errors will be thrown.'''
        result, _cached = await self.query_with_timeout(fqdn, qtype, timeout, tick)
        return result

    async def query_safe(self, fqdn, qtype=types.ANY, timeout=None, tick=5):
        '''Return query result with errors ignored.'''
        try:
            return await self.query(fqdn, qtype, timeout, tick)
        except Exception:
            pass

    async def query_with_timeout(self, fqdn, qtype, timeout=None, tick=5):
        if timeout is None:
            timeout = self.timeout
        return await asyncio.wait_for(self._query(fqdn, qtype, tick), timeout)

    async def _query(self, fqdn, qtype, tick):
        assert tick > 0, 'Maximum nested query times exceeded'
        if fqdn.endswith('.'):
            fqdn = fqdn[:-1]
        if qtype is types.ANY:
            try:
                addr = Address.parse(fqdn)
                ptr_name = addr.to_ptr()
            except (InvalidHost, InvalidIP):
                pass
            else:
                fqdn = ptr_name
                qtype = types.PTR
        return await self._query_once(fqdn, qtype, tick)

    def _query_once(self, fqdn, qtype, tick):
        key = fqdn, qtype
        future = self._queries.get(key)
        if future is None:
            query = Query(self, fqdn, qtype, tick)
            def clear(future):
                self._queries.pop(key, None)
            future = asyncio.ensure_future(query.query())
            future.add_done_callback(clear)
            self._queries[key] = future
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
                    if Address.parse(host, allow_domain=True).ip_type is None:
                        # host is a hostname instead of IP address
                        for res in cache.query(host, A_TYPES):
                            hosts.append(Address.parse(res.data))
                            empty = False
                    else:
                        hosts.append(Address.parse(host))
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

        Each proxy item can be one of:
        - (test, nameserver_list)
        - nameserver

        Examples:
        [
            ('*.lan', ['tcp://192.168.1.1:53']),
            (lambda d: d.endswith('.local'), ['tcp://127.0.0.1:1053']),
            (None, ['8.8.8.8', 'udp://8.8.4.4']),
            '8.8.8.8', # equivalent to (None, ['udp://8.8.8.8'])
        ]
        '''
        ns_pairs = []
        fallback = []
        if proxies:
            for item in proxies:
                if isinstance(item, str):
                    fallback.append(item)
                    continue
                test, ns = item
                if test is None:
                    fallback.extend(ns)
                    continue
                ns_pairs.append((build_tester(test), NameServers(ns)))
        if fallback:
            ns_pairs.append((None, NameServers(fallback)))
        self.ns_pairs = ns_pairs

def build_tester(rule):
    if rule is None or callable(rule): return rule
    assert isinstance(rule, str)
    if rule.startswith('*.'):
        suffix = rule[1:]
        return lambda d: d.endswith(suffix)
    return lambda d: d == rule
