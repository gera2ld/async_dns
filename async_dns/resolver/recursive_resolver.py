import asyncio
from typing import Tuple

from async_dns.core import (
    Address,
    DNSError,
    DNSMessage,
    NameServers,
    REQUEST,
    Record,
    get_root_servers,
    logger,
    types,
)

from .base_resolver import BaseResolver
from .util import Memoizer

A_TYPES = types.A, types.AAAA


class RecursiveResolver(BaseResolver):
    '''Recursive DNS resolver.

    Resolve hostnames recursively from upstream name servers.
    '''
    name = 'RecursiveResolver'
    memoizer = Memoizer()

    def __init__(self, *k, max_tick=5, **kw):
        super().__init__(*k, **kw)
        self.max_tick = max_tick
        for rec in get_root_servers():
            self.cache.add(record=rec)

    async def _query(self, fqdn: str, qtype: int):
        return await self._query_tick(fqdn, qtype, self.max_tick)

    def _get_nameservers(self, fqdn: str):
        '''Return a generator of parent domains'''
        hosts = []
        empty = True
        while fqdn and empty:
            if fqdn in ('in-addr.arpa', ):
                break
            _, _, fqdn = fqdn.partition('.')
            for rec in self.cache.query(fqdn, types.NS):
                host = rec.data
                if Address.parse(host, allow_domain=True).ip_type is None:
                    # host is a hostname instead of IP address
                    for res in self.cache.query(host, A_TYPES):
                        hosts.append(Address.parse(res.data))
                        empty = False
                else:
                    hosts.append(Address.parse(host))
                    empty = False
        logger.debug('[RecursiveResolver._get_nameservers][%s] %s', fqdn,
                     hosts)
        return NameServers(hosts)

    @memoizer.memoize_async(lambda _, fqdn, qtype, _tick: (fqdn, qtype))
    async def _query_tick(self, fqdn: str, qtype: int,
                          tick: int) -> Tuple[DNSMessage, bool]:
        msg = DNSMessage()
        msg.qd.append(Record(REQUEST, name=fqdn, qtype=qtype))

        has_result, fqdn = self.query_cache(msg, fqdn, qtype)
        from_cache = has_result

        last_err = None
        nameservers = self._get_nameservers(fqdn)
        while not has_result and tick > 0:
            tick -= 1
            for addr in nameservers.iter():
                try:
                    has_result, fqdn, nsips = await self._query_remote(
                        msg, fqdn, qtype, addr, tick)
                    nameservers = NameServers(nsips)
                except Exception as err:
                    last_err = err
                else:
                    break
            else:
                raise last_err or Exception('Unknown error')

        assert has_result, 'Maximum nested query times exceeded'
        return msg, from_cache

    async def _query_remote(self, msg: DNSMessage, fqdn: str, qtype: int,
                            addr: Address, tick: int):
        res = await self.request(fqdn, qtype, addr)
        if res.qd[0].name != fqdn:
            raise DNSError(-1, 'Question section mismatch')
        assert res.r != 2, 'Remote server fail'
        self.cache_message(res)

        has_cname = False
        has_result = False
        has_ns = False

        for rec in res.an:
            msg.an.append(rec)
            if rec.qtype == types.CNAME:
                fqdn = rec.data
                has_cname = True
            if rec.qtype != types.CNAME or qtype in (types.CNAME, types.ANY):
                has_result = True
        for rec in res.ns:
            if rec.qtype == types.SOA or qtype == types.NS:
                has_result = True
            else:
                has_ns = True

        if not has_cname and not has_ns:
            # Not found, return server fail since we are not authorative
            msg.r = 2
            has_result = True
        if has_result:
            return has_result, fqdn, []

        # Load name server IPs from res.ar
        nsip_map = {}
        for rec in res.ar:
            nsip_map[rec.name, rec.qtype] = rec.data
        hosts = [
            rec.data.mname if rec.qtype == types.SOA else rec.data
            for rec in res.ns
        ]
        nsips = []
        for host in hosts:
            for t in self.nameserver_types:
                ip = nsip_map.get((host, t))
                if ip is not None:
                    nsips.append(ip)

        # Usually name server IPs will be included in res.ar.
        # In case they are not, query from remote.
        if not nsips and hosts:
            tick -= 1
            for t in self.nameserver_types:
                for host in hosts:
                    try:
                        ns_res, _ = await asyncio.shield(
                            self._query_tick(host, t, tick))
                    except:
                        pass
                    else:
                        for rec in ns_res.an:
                            if rec.qtype == t:
                                nsips.append(rec.data)
                                break
                if nsips: break

        return has_result, fqdn, nsips


if __name__ == '__main__':
    resolver = RecursiveResolver()

    async def main():
        result = await asyncio.gather(
            resolver.query('www.baidu.com', types.A),
            resolver.query('www.baidu.com', types.A),
            resolver.query('www.baidu.com', types.AAAA),
        )
        print(result)

    asyncio.run(main())
