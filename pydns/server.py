#!/usr/bin/env python
# coding=utf-8
import asyncio, logging, time, random, os, itertools
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
            data = []
            for i in filter(None, line.split()):
                if i == '3600000': data.append(-1)
                elif i == 'NS': data.append(types.NS)
                elif i == 'A': data.append(types.A)
                elif i == 'AAAA': data.append(types.AAAA)
                elif i != 'IN': data.append(i.strip('.'))
            yield data

class MemCache:
    name = 'DNSMemD/Gerald'
    def __init__(self):
        self.data = {}
        self.save_items([('1.0.0.127.in-addr.arpa', -1, types.PTR, self.name)])
        self.save_items(get_root_servers())

    def save_items(self, items):
        for name, timeout, qtype, data in items:
            item = self.data.setdefault(name.lower(), {})
            t = item.setdefault(qtype, [None, None])
            if t[0] is None or t[0] > 0 and t[0] < timeout:
                t[0] = timeout
                t[1] = set()
            if t[0] == timeout:
                t[1].add(data)

    def query(self, fqdn, qtype, qany = False):
        todel = []
        data = []
        fqdn = fqdn.lower()
        d = self.data.get(fqdn, {})
        now = time.time()
        for i in d:
            if qtype == i or qany and qtype != types.CNAME:
                v = d[i]
                if v[0] < 0 or v[0] > now:
                    for a in v[1]:
                        data.append((fqdn, v[0], qtype, a))
                else:
                    todel.append(i)
        for i in todel:
            d.pop(i)
        return data

    def load_hosts(self, hosts = utils.hosts):
        if not hosts: return
        self.save_items([
            (rec.name, -1, rec.qtype, rec.data)
            for rec in itertools.chain.from_iterable(hosts.data.values())
        ])

class DNSServerProtocol(asyncio.DatagramProtocol):
    recursion_available = 1
    cache = MemCache()

    def connection_made(self, transport):
        self.transport = transport

    def get_nameservers(self, fqdn):
        empty = True
        while fqdn and empty:
            sub, _, fqdn = fqdn.partition('.')
            for i in self.cache.query(fqdn, types.NS):
                for r in self.cache.query(i[3], None, True):
                    yield r[3]
                    empty = False

    @asyncio.coroutine
    def query(self, fqdn, qtype = types.ANY):
        # cached CNAME
        cname = self.cache.query(fqdn, types.CNAME)
        res = utils.DNSMessage(ra = self.recursion_available)
        res.qd.append(utils.Record(utils.REQUEST, name = fqdn, qtype = qtype))
        for i in cname:
            res.an.append(utils.Record(name = i[0], ttl = i[1], qtype = i[2], data = i[3]))
        if cname:
            if not self.recursion_available or qtype == types.CNAME:
                return res
            for i in cname:
                cres = yield from self.query(i[3], qtype)
                if cres is None or cres.r > 0: continue
                res.an.extend(cres.an)
                res.ns = cres.ns
                res.ar = cres.ar
            return res
        # cached others
        data = self.cache.query(fqdn, qtype, qtype == types.ANY)
        if data:
            n = 0
            for i in data:
                r = utils.Record(name = i[0], ttl = i[1], qtype = i[2], data = i[3])
                if i[2] in (types.NS,):
                    ip = self.cache.query(r.data, None, True)
                    empty = True
                    for j in ip:
                        res.ar.append(dns.record(name = j[0], ttl = j[1], qtype = j[2], data = j[3]))
                        empty = False
                    if not empty:
                        res.ns.append(r)
                        if i[2] == qtype: n += 1
                else:
                    res.an.append(r)
                    if qtype == types.CNAME or r.qtype != types.CNAME:
                        n += 1
            if n > 0:
                # can only be added for local domains
                # res.ns.append(dns.record(name = 12, qtype = types.NS, data = 'localhost'))
                # res.ar.append(dns.record(name = 12, qtype = types.A, data = '127.0.0.1'))
                return res

        # look up from other DNS servers
        nsip = self.get_nameservers(fqdn)
        req = utils.DNSMessage(utils.REQUEST, random.randint(0, 65535))
        cname = [fqdn]
        updates = []
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
                except (asyncio.TimeoutError, utils.DNSError) as e:
                    print(e)
                    pass
                else:
                    break
            else:
                break
            cres = utils.raw_parse(data)
            for r in cres.an + cres.ns + cres.ar:
                if r.ttl > 0 and r.qtype not in (types.SOA, types.MX):
                    updates.append((r.name,r.ttl,r.qtype,r.data))
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
        if updates:
            self.cache.save_items(updates)
        if n > 0:
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

def serve(host = '0.0.0.0', port = 53):
    loop = asyncio.get_event_loop()
    listen = loop.create_datagram_endpoint(
        DNSServerProtocol, local_addr = (host, port))
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
