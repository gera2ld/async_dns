#!/usr/bin/env python
# coding=utf-8
import socket, random
from . import utils, types

def raw_send(b, addr, timeout = 3.0):
    qid = b[:2]
    t = utils.ip_type(addr[0])
    if t == types.A:
        af = socket.AF_INET
    elif t == types.AAAA:
        af = socket.AF_INET6
    else:
        return
    sock = socket.socket(af, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.sendto(b, addr)
    try:
        while True:
            data, addr = sock.recvfrom(512)    # max length of udp packs
            if data.startswith(qid): break
    except socket.error:
        data = None
        if sock: sock.close()
    return data

class Resolver(utils.Resolver):
    def query(self, name, qtype = types.ANY, qclass = 1, recursive = 1, no_cache = False):
        # query hosts
        if not no_cache:
            cached = list(self.hosts.query(name, qtype))
            if cached:
                res = utils.DNSMessage(ra = recursive)
                res.qd.append(utils.Record(utils.REQUEST, name = name, qtype = qtype))
                res.an.extend(cached)
                return res
        # query remote server
        qid = random.randint(0, 65535)
        qdata = utils.raw_pack(qid, name, qtype, qclass, recursive)
        for i in self.nameservers:
            data = raw_send(qdata, (i, 53), self.timeout)
            if data: break
        else:
            return
        ans = utils.raw_parse(data, qid)
        if ans.r > 0:
            raise DNSError(ans.r)
        return ans

resolver = Resolver()
def query(*k, **kw):
    return resolver.query(*k, **kw)
def query_ip(*k, **kw):
    return resolver.query_ip(*k, **kw)
