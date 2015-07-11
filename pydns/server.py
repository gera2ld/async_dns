#!/usr/bin/env python
# coding=utf-8
import asyncio, logging, time, random, os
from urllib import request
from . import utils, types

A_TYPES = types.A, types.AAAA

class CallbackProtocol(asyncio.DatagramProtocol):
    def __init__(self, future):
        self.future = future

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.transport.close()
        if not self.future.cancelled():
            self.future.set_result((data, addr))

cachefile = os.path.expanduser('~/.gerald/named.cache.txt')
def get_name_cache(url = 'ftp://rs.internic.net/domain/named.cache',
        fname = cachefile):
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

class DNSMemCache(utils.Hosts):
    name = 'DNSMemD/Gerald'
    def __init__(self, filename = None):
        super().__init__(filename)
        self.add_item('1.0.0.127.in-addr.arpa', types.PTR, self.name)
        for i in get_root_servers():
            self.add_item(*i)

    def add_item(self, key, qtype, data):
        self.add_host(key, utils.Record(name = key, data = data, qtype = qtype, ttl = -1))

class DNSServerProtocol(asyncio.DatagramProtocol):
    recursion_available = 1
    cache = DNSMemCache()
    rootdomains = ['.lan']

    def connection_made(self, transport):
        self.transport = transport

    def get_nameservers(self, fqdn):
        empty = True
        while fqdn and empty:
            sub, _, fqdn = fqdn.partition('.')
            for rec in self.cache.query(fqdn, types.NS):
                host = rec.data
                if utils.ip_type(host) is None:
                    for r in self.cache.query(host, A_TYPES):
                        yield r.data
                        empty = False
                else:
                    yield host
                    empty = False

    @asyncio.coroutine
    def query_cache(self, res, fqdn, qtype):
        # cached CNAME
        cname = list(self.cache.query(fqdn, types.CNAME))
        if cname:
            res.an.extend(cname)
            if not self.recursion_available or qtype == types.CNAME:
                return True
            for rec in cname:
                cres = yield from self.query(rec.data, qtype)
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
            res.ns.append(utils.Record(name = fqdn, qtype = types.NS, data = 'localhost'))
            res.ar.append(utils.Record(name = fqdn, qtype = types.A, data = '127.0.0.1'))
        if n:
            return True

    @asyncio.coroutine
    def query_remote(self, res, fqdn, qtype):
        # look up from other DNS servers
        nsip = self.get_nameservers(fqdn)
        req = utils.DNSMessage(utils.REQUEST, random.randint(0, 65535))
        cname = [fqdn]
        n = 0
        while not n:
            if not cname: break
            req.qd = [utils.Record(utils.REQUEST, i, qtype) for i in cname]
            qdata = req.pack()
            del cname[:]
            qid = qdata[:2]
            loop = asyncio.get_event_loop()
            for ip in nsip:
                future = asyncio.Future()
                try:
                    transport, protocol = yield from asyncio.wait_for(
                        loop.create_datagram_endpoint(lambda : CallbackProtocol(future), remote_addr = (ip, 53)),
                        1.0
                    )
                    transport.sendto(qdata)
                    data, addr = yield from asyncio.wait_for(future, 3.0)
                    transport.close()
                    assert data.startswith(qid), utils.DNSError(-1, 'Message id does not match!')
                except asyncio.TimeoutError:
                    pass
                except utils.DNSError as e:
                    print('error', e)
                    pass
                else:
                    break
            else:
                break
            cres = utils.raw_parse(data)
            for r in cres.an + cres.ns + cres.ar:
                if r.ttl > 0 and r.qtype not in (types.SOA, types.MX):
                    self.cache.add_host(r.name, r)
            for r in cres.an:
                res.an.append(r)
                if r.qtype == types.CNAME:
                    cname.append(r.data)
                if (r.name.lower() == req.qd[0].name.lower() and
                    (qtype == types.CNAME or r.qtype != types.CNAME)):
                    n+=1
            for r in cres.ns:
                res.ns.append(r)
                if r.qtype == types.SOA or qtype == types.NS:
                    n+=1
            res.ar.extend(cres.ar)
            nsip = [i.data for i in cres.ar if i.qtype in A_TYPES]
            if not nsip:
                for i in cres.ns:
                    host = i.data[0] if i.qtype == types.SOA else i.data
                    ns = None
                    try:
                        ns = yield from self.query(host)
                    except Exception as e:
                        logging.error(host)
                        logging.error(e)
                    if ns is None:
                        continue
                    for j in ns.an:
                        if j.qtype in A_TYPES:
                            nsip.append(j.data)
            if cres.r > 0:
                res.r = cres.r
                n = 1
        if n: return res

    @asyncio.coroutine
    def query(self, fqdn, qtype = types.ANY):
        res = utils.DNSMessage(ra = self.recursion_available)
        res.qd.append(utils.Record(utils.REQUEST, name = fqdn, qtype = qtype))
        (yield from self.query_cache(res, fqdn, qtype)) or (yield from self.query_remote(res, fqdn, qtype))
        return res

    @asyncio.coroutine
    def handle(self, data, addr):
        msg = utils.raw_parse(data)
        for c in msg.qd:
            res = yield from self.query(c.name, c.qtype)
            if res:
                res.qid = msg.qid
                data = res.pack()
                self.transport.sendto(data, addr)
                l = len(data)
                #if l>512:
                    #print(res)
                    #print(data)
                r = res.r
            else:
                l = 0
                r = -1
            logging.info('%s %4s %s %d %d', addr[0], types.type_name(c.qtype), c.name, r, l)
            break   # only one request is supported

    def datagram_received(self, data, addr):
        asyncio.ensure_future(self.handle(data, addr))

class DNSProxyProtocol(DNSServerProtocol):
    proxies = ['114.114.114.114', '180.76.76.76', '223.5.5.5', '223.6.6.6']

    def get_nameservers(self, fdqn = None):
        return self.proxies

def serve(host = '0.0.0.0', port = 53, protocolClass = DNSProxyProtocol, hosts = None):
    if hosts:
        DNSServerProtocol.cache.parse_file(hosts)
    loop = asyncio.get_event_loop()
    listen = loop.create_datagram_endpoint(
        protocolClass, local_addr = (host, port))
    transport, protocol = loop.run_until_complete(listen)
    logging.info('DNS server v2 - by Gerald')
    sock = transport.get_extra_info('socket')
    logging.info('Serving DNS on %s, port %d', *(sock.getsockname()[:2]))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    transport.close()
    loop.close()

if __name__ == '__main__':
    import argparse, sys
    logging.basicConfig(level = logging.INFO)
    parser = argparse.ArgumentParser(description = 'DNS server by Gerald.')
    parser.add_argument('-b', '--bind', default = ':', help = 'the address for the server to bind')
    parser.add_argument('-c', help = 'the path of a hosts file')
    args = parser.parse_args()
    host, _, port = args.bind.rpartition(':')
    if not host: host = '0.0.0.0'
    if port:
        port = int(port)
    else:
        port = 53
    serve(host, port, hosts = args.c)
