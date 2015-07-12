#!/usr/bin/env python
# coding=utf-8
import asyncio, logging
from . import utils, types, client

class DNSServerProtocol(asyncio.DatagramProtocol):
    resolver = client.AsyncProxyResolver()

    def connection_made(self, transport):
        self.transport = transport

    @asyncio.coroutine
    def handle(self, data, addr):
        msg = utils.raw_parse(data)
        for c in msg.qd:
            res = yield from self.resolver.query(c.name, c.qtype)
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

def serve(host = '0.0.0.0', port = 53, protocolClass = DNSServerProtocol, hosts = None):
    if hosts:
        DNSServerProtocol.resolver.cache.parse_file(hosts)
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
