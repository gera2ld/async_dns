#!/usr/bin/env python
# coding=utf-8
'''
Synchronous DNS resolver.
'''
import socket, random
from . import utils, types, address

def request(data, addr, timeout = 3.0, protocol = utils.UDP):
    qid = data[:2]
    addr = address.Address(addr)
    if addr.ip_type == types.A:
        af = socket.AF_INET
    elif addr.ip_type == types.AAAA:
        af = socket.AF_INET6
    else:
        return
    sock_type = socket.SOCK_DGRAM if protocol is utils.UDP else socket.SOCK_STREAM
    sock = socket.socket(af, sock_type)
    sock.settimeout(timeout)
    try:
        sock.connect(addr.to_addr())
        sock.send(data)
        data = sock.recv(2048)
    except socket.error:
        pass
    else:
        return data

class SyncResolver:
    '''
    A synchronous DNS resolver.
    '''
    expected_types = types.AAAA, types.A
    def __init__(self, nameservers = None, timeout = 3.0, hosts_file = None, protocol = utils.UDP):
        self.timeout = timeout
        self.protocol = protocol
        if nameservers:
            # Resolve nameservers using default DNS
            self.nameservers = list(map(_resolver.query_ip, nameservers))
        else:
            self.nameservers = list(utils.nameservers)
        if hosts_file:
            self.hosts = Hosts(hosts_file)
        else:
            self.hosts = utils.hosts

    def query(self, name, qtype = types.ANY, qclass = 1, recursive = 1, no_cache = False):
        rec = utils.Record(utils.REQUEST, name = name, qtype = qtype, qclass = qclass)
        # query hosts
        if not no_cache:
            cached = list(self.hosts.query(name, qtype))
            if cached:
                res = utils.DNSMessage(ra = recursive)
                res.qd.append(rec)
                res.an.extend(cached)
                return res
        # query remote server
        qid = random.randint(0, 65535)
        req = utils.dns_request(qid, recursive = recursive)
        req.qd.append(rec)
        qdata = req.pack()
        for ns in self.nameservers:
            data = request(qdata, (ns, 53), self.timeout, self.protocol)
            if data is not None:
                try:
                    return utils.raw_parse(data, qid)
                except utils.DNSError:
                    pass

    def query_ip(self, name):
        if address.Address(name, allow_domain=True).ip_type in self.expected_types:
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
        # return last

_resolver = SyncResolver()
query = _resolver.query
query_ip = _resolver.query_ip

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description = 'DNS resolver')
    parser.add_argument('hostnames', nargs='+', help='the hostnames to query')
    parser.add_argument('-p', '--protocol', default=utils.UDP, help='the protocol to use to communicate with the DNS server, either UDP or TCP, default as UDP')
    parser.add_argument('-n', '--nameservers', default=None, help='the name servers')
    args = parser.parse_args()
    nameservers = args.nameservers
    if nameservers: nameservers = nameservers.split(',')
    resolver = SyncResolver(nameservers=nameservers, protocol=args.protocol)
    for hostname in args.hostnames:
        ip = resolver.query_ip(hostname)
        print(ip)
