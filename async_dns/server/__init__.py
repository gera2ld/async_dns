'''
Async DNS server
'''
import asyncio
import io
import struct
from async_dns.core import *
from async_dns.core.cache import CacheNode
from async_dns.resolver import ProxyResolver, Resolver

async def handle_dns(resolver, data, addr, protocol=None):
    '''Handle DNS requests'''

    msg = DNSMessage.parse(data)
    for question in msg.qd:
        try:
            error = None
            res, from_cache = await resolver.query_with_cache(question.name, question.qtype)
        except Exception as e:
            import traceback
            logger.debug('[server_handle][%s][%s] %s', types.get_name(question.qtype), question.name, traceback.format_exc())
            error = str(e)
            res, from_cache = None, None
        if res is not None:
            res.qid = msg.qid
            data = res.pack()
            yield data
            len_data = len(data)
            # if len_data > 512:
            #     print(res)
            #     print(data)
            res_code = res.r
        else:
            len_data = 0
            res_code = -1
        logger.info(
            '[%s|%s|%s|%s] %s %d %d %s',
            protocol,
            'cache' if from_cache else 'remote',
            addr[0],
            types.get_name(question.qtype),
            question.name,
            res_code,
            len_data,
            error or '',
        )
        break   # only one question is supported

class TCPHandler:
    def __init__(self, resolver):
        self.resolver = resolver

    async def handle_tcp(self, reader, writer):
        addr = writer.transport.get_extra_info('peername')
        while True:
            try:
                size, = struct.unpack('!H', await reader.readexactly(2))
            except asyncio.IncompleteReadError:
                break
            data = await reader.readexactly(size)
            async for result in handle_dns(self.resolver, data, addr, 'tcp'):
                bsize = struct.pack('!H', len(result))
                writer.write(bsize)
                writer.write(result)

class DNSDatagramProtocol(asyncio.DatagramProtocol):
    '''DNS server handler through UDP protocol.'''

    def __init__(self, resolver):
        super().__init__()
        self.resolver = resolver

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        asyncio.ensure_future(self.handle(data, addr))

    async def handle(self, data, addr):
        async for result in handle_dns(self.resolver, data, addr, 'udp'):
            self.transport.sendto(result, addr)

async def start_server(
    host='', port=53, enable_tcp=True, enable_udp=True,
    hosts=None, resolve_protocol=UDP, proxies=None):
    '''Start a DNS server.'''

    if not isinstance(resolve_protocol, InternetProtocol):
        resolve_protocol = InternetProtocol.get(resolve_protocol)
    cache = CacheNode()
    cache.add('1.0.0.127.in-addr.arpa', qtype=types.PTR, data='async-dns.local')
    cache.add('localhost', qtype=types.A, data='127.0.0.1')
    if hosts != 'none':
        for rec in parse_hosts_file(None if hosts == 'local' else hosts):
            cache.add(record=rec)
    if proxies is None:
        # recursive resolver
        resolver = Resolver(resolve_protocol, cache)
    else:
        # proxy resolver
        # if proxy is falsy, default proxies will be used
        resolver = ProxyResolver(resolve_protocol, cache, proxies=proxies)
    loop = asyncio.get_event_loop()
    if enable_tcp:
        server = await asyncio.start_server(TCPHandler(resolver).handle_tcp, host, port)
    else:
        server = None
    transport_arr = []
    if enable_udp:
        if host:
            host_arr = [host] if isinstance(host, str) else host
        else:
            host_arr = ['::'] # '::' means both IPv4 and IPv6
        for host_bind in host_arr:
            transport, _protocol = await loop.create_datagram_endpoint(
                lambda: DNSDatagramProtocol(resolver),
                local_addr=(host_bind, port))
            transport_arr.append(transport)
    return server, transport_arr, resolver
