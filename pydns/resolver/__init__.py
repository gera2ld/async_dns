#!/usr/bin/env python
# coding=utf-8
'''
Asynchronous DNS client
This is designed to improve performance of the server.
'''
import asyncio, os
from .. import types, address
from .. import *
from ..logger import logger
from . import tcp, udp
from ..cache import DNSMemCache
__all__ = ['AsyncResolver', 'AsyncProxyResolver']

A_TYPES = types.A, types.AAAA

class AsyncResolver:
    recursive = 1
    rootdomains = ['.lan']

    def __init__(self, protocol=UDP, cache=None):
        self.futures = {}
        if cache is None: cache = DNSMemCache()
        self.cache = cache
        self.protocol = InternetProtocol.get(protocol)

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
            res.ns.append(Record(name = fqdn, qtype = types.NS, data = 'localhost', ttl = -1))
            res.ar.append(Record(name = fqdn, qtype = types.A, data = '127.0.0.1', ttl = -1))
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

    async def request(self, qdata, addr, timeout = 3.0, protocol = None):
        if protocol is None:
            protocol = self.protocol
        if protocol is TCP:
            request = tcp.request
        else:
            request = udp.request
        data = await request(qdata, addr, timeout)
        return data

    async def query_remote(self, res, fqdn, qtype):
        # look up from other DNS servers
        nameservers = address.NameServers(self.get_nameservers(fqdn))
        cname = [fqdn]
        req = DNSMessage.request()
        n = 0
        while not n:
            if not cname: break
            # XXX it seems that only one qd is supported by most NS
            req.qd = [Record(REQUEST, cname[0], qtype)]
            qdata = req.pack()
            del cname[:]
            qid = qdata[:2]
            for addr in nameservers:
                try:
                    data = await self.request(qdata, addr)
                    if not data.startswith(qid):
                        raise DNSError(-1, 'Message id does not match!')
                    cres = DNSMessage.parse(data)
                    assert cres.r != 2
                except (asyncio.TimeoutError, AssertionError):
                    nameservers.fail(addr)
                except DNSError:
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
                        logger.error(host)
                        logger.error(e)
                    else:
                        if ns:
                            for j in ns.an:
                                if j.qtype in A_TYPES:
                                    nameservers.add(j.data)
            res.r = cres.r
        return n > 0

    async def query(self, fqdn, qtype=types.ANY, timeout=3.0):
        key = fqdn, qtype
        future = self.futures.get(key)
        if future is None:
            loop = asyncio.get_event_loop()
            future = self.futures[key] = loop.create_future()
            asyncio.ensure_future(self.do_query(key))
        try:
            res = await asyncio.wait_for(future, timeout)
        except (AssertionError, asyncio.TimeoutError, asyncio.CancelledError):
            pass
        else:
            return res

    async def do_query(self, key):
        fqdn, qtype = key
        res = DNSMessage(ra = self.recursive)
        res.qd.append(Record(REQUEST, name = fqdn, qtype = qtype))
        future = self.futures[key]
        ret = (await self.query_cache(res, fqdn, qtype)) or (await self.query_remote(res, fqdn, qtype))
        if not ret and not res.r:
            res.r = 2
        self.futures.pop(key)
        if not future.cancelled():
            future.set_result(res)

class AsyncProxyResolver(AsyncResolver):
    proxies = address.NameServers(['114.114.114.114', '180.76.76.76', '223.5.5.5', '223.6.6.6'])

    def get_nameservers(self, fdqn = None):
        return self.proxies

    def set_proxies(self, proxies):
        self.proxies = address.NameServers(proxies)
