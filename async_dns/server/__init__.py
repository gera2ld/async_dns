'''
Async DNS server
'''
import asyncio
from async_dns.core import *
from async_dns.core.cache import CacheNode
from async_dns.resolver import ProxyResolver, Resolver

class DNSMixIn:
    '''DNS handler mix-in'''

    def __init__(self, resolver, *k, **kw):
        super().__init__(*k, **kw)
        self.resolver = resolver
        self.transport = None
        self.addr = None

    def send_data(self, data, addr):
        '''Send data to remote server.'''

        raise NotImplementedError

    async def handle(self, data, addr):
        '''Main handle method for protocols.'''

        msg = DNSMessage.parse(data)
        for question in msg.qd:
            res, from_cache = await self.resolver.query_with_cache(question.name, question.qtype)
            if res:
                res.qid = msg.qid
                data = res.pack()
                self.send_data(data, addr)
                len_data = len(data)
                # if len_data > 512:
                #     print(res)
                #     print(data)
                res_code = res.r
            else:
                len_data = 0
                res_code = -1
            logger.info(
                '[%s|%s|%s|%s] %s %d %d',
                self.protocol,
                'cache' if from_cache else 'remote',
                addr[0],
                types.get_name(question.qtype),
                question.name,
                res_code,
                len_data,
            )
            break   # only one question is supported

class DNSDatagramProtocol(DNSMixIn, asyncio.DatagramProtocol):
    '''DNS server handler through UDP protocol.'''

    protocol = 'udp'

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        asyncio.ensure_future(self.handle(data, addr))

    def send_data(self, data, addr):
        self.transport.sendto(data, addr)

class DNSProtocol(DNSMixIn, asyncio.Protocol):
    '''DNS server handler through TCP protocol.'''

    protocol = 'tcp'

    def connection_made(self, transport):
        self.transport = transport
        self.addr = transport.get_extra_info('peername')

    def data_received(self, data):
        asyncio.ensure_future(self.handle(data, self.addr))

    def send_data(self, data, addr):
        self.transport.write(data)

async def start_server(
    host='', port=53, protocol_classes=(DNSProtocol, DNSDatagramProtocol),
    hosts=None, resolve_protocol=UDP, proxies=None):
    '''Start a DNS server.'''

    if not isinstance(resolve_protocol, InternetProtocol):
        resolve_protocol = InternetProtocol.get(resolve_protocol)
    tcp_protocol, udp_protocol = protocol_classes
    cache = CacheNode()
    cache.add('1.0.0.127.in-addr.arpa', qtype=types.PTR, data='async-dns.local')
    cache.add('localhost', qtype=types.A, data='127.0.0.1')
    if hosts != 'none':
        for rec in parse_hosts_file(None if hosts == 'local' else hosts):
            cache.add(record=rec)
    if proxies == ['none']:
        resolver = Resolver(resolve_protocol, cache)
    else:
        if proxies == ['default']: proxies = None
        resolver = ProxyResolver(resolve_protocol, cache, proxies=proxies)
    loop = asyncio.get_event_loop()
    if tcp_protocol:
        server = await loop.create_server(
            lambda: tcp_protocol(resolver), host, port)
    else:
        server = None
    transport_arr = []
    if udp_protocol:
        if host:
            host_arr = [host] if isinstance(host, str) else host
        else:
            host_arr = ['::'] # '::' means both IPv4 and IPv6
        for host_bind in host_arr:
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: udp_protocol(resolver),
                local_addr=(host_bind, port))
            transport_arr.append(transport)
    return server, transport_arr, resolver
