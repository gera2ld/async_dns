import asyncio
from . import tcp, udp, doh
from async_dns.core import DNSError, DNSMessage, NameServers, logger, types, REQUEST, Record

A_TYPES = types.A, types.AAAA
PENDING = 0
RESOLVED = 1
REJECTED = 2

class Query:
    protocols = {
        'tcp': tcp.request,
        'tcps': tcp.request,
        'udp': udp.request,
        'https': doh.request,
    }

    def __init__(self, resolver, fqdn, qtype, tick):
        self.resolver = resolver
        self.fqdn = fqdn
        self.qtype = qtype
        self.tick = tick
        self._cached = False
        self._status = PENDING
        self._result = DNSMessage(ra=resolver.recursive)
        self._result.qd.append(Record(REQUEST, name=fqdn, qtype=qtype))

    async def query(self):
        domain = self.fqdn
        nameservers = None
        while True:
            self._cached = await self.query_cache(domain)
            logger.debug('[query_cache][%s][%s] %s', types.get_name(self.qtype), domain, self._cached)
            if self._cached: break
            remote_res = await self.query_remote(domain, nameservers)
            logger.debug('[query_remote][%s][%s] %s', types.get_name(self.qtype), domain, remote_res)
            if remote_res is None: break
            domain, nameservers = remote_res
        return self._result, self._cached

    async def query_cache(self, domain):
        '''Returns a boolean whether a cache hit occurs.'''
        resolver = self.resolver
        cache = resolver.cache
        result = self._result
        # if cached CNAME
        cname = list(cache.query(domain, types.CNAME))
        if cname:
            result.an.extend(rec.copy(name=domain) for rec in cname)
            if all(rec.ttl < 0 for rec in cname):
                result.aa = 1
            if self.qtype == types.CNAME:
                return True
            for rec in cname:
                inter_res = await resolver.query_safe(rec.data, self.qtype)
                if inter_res is None or inter_res.r > 0:
                    continue
                result.an.extend(inter_res.an)
                result.ns = inter_res.ns
                result.ar = inter_res.ar
            return True
        # else
        cache_hit = False
        for rec in cache.query(domain, self.qtype):
            if rec.qtype in (types.NS,):
                inter_res = list(cache.query(rec.data, A_TYPES))
                if inter_res:
                    result.ar.extend(inter_res)
                    result.ns.append(rec)
                    if rec.qtype == self.qtype:
                        cache_hit = True
            else:
                result.an.append(rec.copy(name=domain))
                if self.qtype == types.CNAME or rec.qtype != types.CNAME:
                    cache_hit = True
        if any(domain.endswith(root) for root in self.resolver.rootdomains):
            if not cache_hit:
                # not exists
                result.r = 3
                cache_hit = True
            # should only be added for domains that are resolved by this server
            result.aa = 1  # Authoritative answer
            # result.ns.append(Record(name=domain, qtype=types.NS, data='localhost', ttl=-1))
            # result.ar.append(Record(name=domain, qtype=types.A, data='127.0.0.1', ttl=-1))
        return cache_hit

    async def query_remote(self, domain, nameservers):
        '''Query domain from remote servers.'''
        resolver = self.resolver
        result = self._result
        has_result = False
        inter_res = await self.query_remote_once(domain, nameservers)
        cname = []
        has_ns = False
        for rec in inter_res.an:
            result.an.append(rec)
            if rec.qtype == types.CNAME:
                cname.append(rec.data)
            if self.qtype == types.CNAME or rec.qtype != types.CNAME:
                has_result = True
        for rec in inter_res.ns:
            if not resolver.recursive:
                result.ns.append(rec)
            if rec.qtype == types.SOA or self.qtype == types.NS:
                has_result = True
            else:
                has_ns = True
        if not resolver.recursive:
            result.ar.extend(inter_res.ar)
        if has_result:
            return
        if cname:
            return cname[0], None
        if not resolver.recursive:
            result.r = inter_res.r
            return
        if not has_ns:
            result.r = 2
            return
        # load recursive name servers
        nsip_map = {}
        for rec in inter_res.ar:
            nsip_map[rec.name, rec.qtype] = rec.data
        hosts = [rec.data.mname if rec.qtype == types.SOA else rec.data for rec in inter_res.ns]
        nsips = []
        for host in hosts:
            ip = nsip_map.get((host, types.A))
            if ip is not None:
                nsips.append(ip)
        # query ips of name servers
        if not nsips and hosts:
            self.tick -= 1
            try:
                dns_res = await asyncio.shield(self.resolver.query(hosts[0], types.A, tick=self.tick))
            except:
                dns_res = None
            if dns_res:
                for rec in dns_res.an:
                    if rec.qtype == types.A:
                        nsips.append(rec.data)
        return domain, NameServers(nsips)

    async def query_remote_once(self, domain, nameservers=None):
        resolver = self.resolver
        req = DNSMessage(qr=REQUEST)
        if nameservers is None:
            nameservers = resolver.get_nameservers(domain)
        req.qd = [Record(REQUEST, domain, self.qtype)]
        logger.debug('[query_remote_once][%s][%s] %s', types.get_name(self.qtype), domain, nameservers)
        inter_res = await self.request_remote(nameservers, req)
        resolver.cache_message(inter_res)
        return inter_res

    async def request_remote(self, nameservers, req):
        last_err = None
        for addr in nameservers.iter():
            try:
                inter_res = await self.request_once(req, addr)
                logger.debug('[request_remote] %s', inter_res)
                if inter_res.qd[0].name != req.qd[0].name:
                    raise DNSError(-1, 'Question section mismatch')
                assert inter_res.r != 2, 'Remote server fail'
            except Exception as e:
                error_type = 'error'
                if isinstance(e, (asyncio.TimeoutError, AssertionError)):
                    error_type = 'server_error'
                elif isinstance(e, DNSError):
                    error_type = 'dns_error'
                else:
                    error_type = 'error'
                    import traceback
                    traceback.print_exc()
                logger.debug('[request_remote][%s] %s %s', error_type, str(addr), repr(e))
                last_err = e
            else:
                nameservers.success(addr)
                return inter_res
            nameservers.fail(addr)
        else:
            raise last_err

    async def request_once(self, req, addr):
        '''Return response to a request.

        Send DNS request data with `protocol`.
        '''
        request = self.protocols[addr.protocol]
        data = await request(req, addr, self.resolver.request_timeout)
        return data
