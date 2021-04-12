import asyncio

from async_dns.core import (
    DNSMessage,
    NameServers,
    REQUEST,
    Record,
    core_config,
    logger,
    types,
)

from .base_resolver import BaseResolver
from .util import Memoizer


class ProxyResolver(BaseResolver):
    '''Proxy DNS resolver.

    Resolve hostnames from another recursive DNS server instead of root servers.
    '''
    name = 'ProxyResolver'
    default_nameservers = core_config['default_nameservers']
    memoizer = Memoizer()

    def __init__(self, *k, proxies=None, **kw):
        super().__init__(*k, **kw)
        self.set_proxies(proxies or self.default_nameservers)

    def _get_nameservers(self, fqdn):
        logger.debug('[ProxyResolver._get_nameservers][%s] %s', fqdn,
                     self.ns_pairs)
        for test, ns in self.ns_pairs:
            if test is None or test(fqdn): break
        else:
            ns = []
        return NameServers(ns)

    @staticmethod
    def build_tester(rule):
        if rule is None or callable(rule): return rule
        assert isinstance(rule, str)
        if rule.startswith('*.'):
            suffix = rule[1:]
            return lambda d: d.endswith(suffix)
        return lambda d: d == rule

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
                ns_pairs.append((self.build_tester(test), NameServers(ns)))
        if fallback:
            ns_pairs.append((None, NameServers(fallback)))
        self.ns_pairs = ns_pairs

    @memoizer.memoize_async(lambda _, fqdn, qtype: (fqdn, qtype))
    async def _query(self, fqdn: str, qtype: int):
        msg = DNSMessage()
        msg.qd.append(Record(REQUEST, name=fqdn, qtype=qtype))

        has_result, fqdn = self.query_cache(msg, fqdn, qtype)
        from_cache = has_result

        while not has_result:
            nameservers = self._get_nameservers(fqdn)
            for addr in nameservers.iter():
                try:
                    res = await self.request(fqdn, qtype, addr)
                    assert res.ra, 'The upstream name server must be in recursive mode'
                    assert res.r == 0, 'Remote server failed'
                except:
                    nameservers.fail(addr)
                    raise
                else:
                    nameservers.success(addr)
                    self.cache_message(res)
                    msg.an.extend(res.an)
                    has_result = True
                    # has_result, fqdn = self.query_cache(msg, fqdn, qtype)
                    break
        return msg, from_cache


if __name__ == '__main__':
    resolver = ProxyResolver(proxies=['114.114.114.114'])

    async def main():
        result = await asyncio.gather(
            resolver.query('www.baidu.com', types.A),
            resolver.query('www.baidu.com', types.A),
            resolver.query('www.baidu.com', types.AAAA),
        )
        print(result)

    asyncio.run(main())
