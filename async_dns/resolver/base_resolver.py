import asyncio
from typing import Tuple

from async_dns.core import (
    Address,
    CacheNode,
    DNSError,
    DNSMessage,
    InvalidHost,
    InvalidIP,
    types,
)

from .client import DNSClient

A_TYPES = types.A, types.AAAA


class BaseResolver:
    # If listed in zone domains, the resolver is authorative for the responses, e.g. ['.lan']
    zone_domains = []
    nameserver_types = [types.A]

    def __init__(self, cache=None, query_timeout=3.0, request_timeout=5.0):
        self._queries = {}
        if cache is None:
            cache = CacheNode()
        self.cache = cache
        self.request_timeout = request_timeout
        self.query_timeout = query_timeout
        self.client = DNSClient(request_timeout)

    def cache_message(self, msg: DNSMessage):
        for rec in msg.an + msg.ns + msg.ar:
            if rec.ttl > 0 and rec.qtype not in (types.SOA, ):
                self.cache.add(record=rec)

    async def _query(self, _fqdn: str, _qtype: int) -> Tuple[DNSMessage, bool]:
        raise NotImplementedError

    async def query(self,
                    fqdn: str,
                    qtype=types.ANY) -> Tuple[DNSMessage, bool]:
        if fqdn.endswith('.'):
            fqdn = fqdn[:-1]
        if qtype == types.ANY:
            try:
                addr = Address.parse(fqdn)
                ptr_name = addr.to_ptr()
            except (InvalidHost, InvalidIP):
                pass
            else:
                fqdn = ptr_name
                qtype = types.PTR
        return await asyncio.wait_for(self._query(fqdn, qtype),
                                      self.query_timeout)

    async def request(self, fqdn: str, qtype: int, addr: Address):
        '''Query remote records with the DNS client.
        '''
        result = await self.client.query(fqdn, qtype, addr)
        if result.qd[0].name != fqdn:
            raise DNSError(-1, 'Question section mismatch')
        assert result.r != 2, 'Remote server fail'
        self.cache_message(result)
        return result

    def _add_cache_cname(self, msg: DNSMessage, fqdn: str):
        '''Query cache for CNAME records and add to result msg.
        '''
        for cname in self.cache.query(fqdn, types.CNAME):
            msg.an.append(cname.copy(name=fqdn))
            return cname.data

    def _add_cache_qtype(self, msg: DNSMessage, fqdn: str, qtype: int) -> bool:
        '''Query cache for records other than CNAME and add to result msg.
        '''
        if qtype == types.CNAME:
            return False
        has_result = False
        for rec in self.cache.query(fqdn, qtype):
            if rec.qtype in (types.NS, ):
                a_res = list(self.cache.query(rec.data, A_TYPES))
                if a_res:
                    msg.ar.extend(a_res)
                    msg.ns.append(rec)
                    has_result = True
            else:
                msg.an.append(rec.copy(name=fqdn))
                has_result = True
        return has_result

    def query_cache(self, msg: DNSMessage, fqdn: str, qtype: int):
        cnames = set()
        while True:
            cname = self._add_cache_cname(msg, fqdn)
            if not cname: break
            if cname in cnames:
                # CNAME cycle detected
                break
            cnames.add(cname)
            # RFC1034: If a CNAME RR is present at a node, no other data should be present
            fqdn = cname
        has_result = bool(cname) and qtype in (types.CNAME, types.ANY)
        if qtype != types.CNAME:
            has_result = self._add_cache_qtype(msg, fqdn, qtype) or has_result
        if any(fqdn.endswith(root) for root in self.zone_domains):
            if not has_result:
                msg.r = 3
                has_result = True
            msg.aa = 1
        # fqdn may change due to CNAME
        return has_result, fqdn
