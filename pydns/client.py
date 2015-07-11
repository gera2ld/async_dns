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

class Resolver:
    '''
    A synchronous DNS resolver.
    '''
    expected_types = types.AAAA, types.A
    def __init__(self, nameservers = None, timeout = 3.0, hosts_file = None):
        if nameservers:
            # Resolve nameservers using default DNS
            from . import client
            self.nameservers = list(map(client.query_ip, nameservers))
        else:
            self.nameservers = list(utils.nameservers)
        self.timeout = timeout
        if hosts_file:
            self.hosts = Hosts(hosts_file)
        else:
            self.hosts = utils.hosts

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

    def query_ip(self, name):
        if utils.ip_type(name) in self.expected_types:
            return name
        for t in self.expected_types:
            nm = name
            while True:
                a = None
                while True:
                    if self.hosts:
                        for c in self.hosts.query(nm, t):
                            if c.qtype == t:
                                return c.data
                            if a is None: a = c
                    if a:
                        nm, a = a.data, None
                    else:
                        break
                last = nm
                ans = self.query(nm, t)
                if not ans: break
                a = None
                for c in ans.an:
                    if c.qtype == t: return c.data
                    if a is None: a = c
                if a: nm = a.data
                else: break
        return last

resolver = Resolver()
def query(*k, **kw):
    return resolver.query(*k, **kw)
def query_ip(*k, **kw):
    return resolver.query_ip(*k, **kw)
