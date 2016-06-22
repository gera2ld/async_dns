#!/usr/bin/env python
# coding=utf-8
import asyncio, logging
from . import utils, types, aresolver

class DNSMixIn:
    resolver = None

    async def handle(self, data, addr):
        if self.resolver is None:
            self.resolver = aresolver.AsyncProxyResolver()
        msg = utils.raw_parse(data)
        for c in msg.qd:
            res = await self.resolver.query(c.name, c.qtype)
            if res:
                res.qid = msg.qid
                data = res.pack()
                self.send_data(data, addr)
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

class DNSDatagramProtocol(DNSMixIn, asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        asyncio.ensure_future(self.handle(data, addr))

    def send_data(self, data, addr):
        self.transport.sendto(data, addr)

class DNSProtocol(DNSMixIn, asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport
        self.addr = transport.get_extra_info('peername')

    def data_received(self, data):
        asyncio.ensure_future(self.handle(data, self.addr))

    def send_data(self, data, addr):
        self.transport.write(data)

def serve(host = '0.0.0.0', port = 53, protocol_classes = (DNSProtocol, DNSDatagramProtocol),
        hosts = None, resolve_protocol = utils.UDP, proxies = None):
    DNSMixIn.resolver = aresolver.AsyncProxyResolver(resolve_protocol)
    if hosts is not None:
        DNSMixIn.resolver.cache.parse_file(hosts)
    if proxies:
        DNSMixIn.resolver.set_proxies(proxies)
    loop = asyncio.get_event_loop()
    logging.info('DNS server v2 - by Gerald')
    TCPProtocol, UDPProtocol = protocol_classes
    if TCPProtocol:
        listen = loop.create_server(TCPProtocol, host, port)
        server = loop.run_until_complete(listen)
        logging.info('Serving on %s, port %d, TCP', *(server.sockets[0].getsockname()[:2]))
    if UDPProtocol:
        listen = loop.create_datagram_endpoint(UDPProtocol, local_addr = (host, port))
        transport, protocol = loop.run_until_complete(listen)
        sock = transport.get_extra_info('socket')
        logging.info('Serving on %s, port %d, UDP', *(sock.getsockname()[:2]))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    transport.close()
    loop.close()

if __name__ == '__main__':
    import argparse
    logging.basicConfig(level = logging.INFO)
    parser = argparse.ArgumentParser(description = 'DNS server by Gerald.')
    parser.add_argument('-b', '--bind', default = ':', help = 'the address for the server to bind')
    parser.add_argument('--hosts', help = 'the path of a hosts file')
    parser.add_argument('-P', '--proxy', default = '114.114.114.114,180.76.76.76,223.5.5.5,223.6.6.6', help = 'the proxy DNS servers')
    parser.add_argument('-p', '--protocol', default='UDP', help = 'the default protocol to use to query remote servers')
    args = parser.parse_args()
    host, _, port = args.bind.rpartition(':')
    if not host: host = '0.0.0.0'
    if port:
        port = int(port)
    else:
        port = 53
    serve(host, port, hosts = args.hosts, resolve_protocol = args.protocol,
            proxies = map(str.strip, args.proxy.split(',')))
