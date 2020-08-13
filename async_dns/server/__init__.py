'''
Async DNS server
'''
import asyncio
import io
import struct
from async_dns.core import *
from async_dns.core.cache import CacheNode
from async_dns.resolver import ProxyResolver, Resolver
from .serve import *

async def handle_dns(resolver, data, addr, protocol):
    '''Handle DNS requests'''

    msg = DNSMessage.parse(data)
    for question in msg.qd:
        try:
            error = None
            res, cached = await resolver.query_with_timeout(question.name, question.qtype)
        except Exception as e:
            import traceback
            logger.debug('[server_handle][%s][%s] %s', types.get_name(question.qtype), question.name, traceback.format_exc())
            error = str(e)
            res, cached = None, None
        if res is not None:
            res.qid = msg.qid
            data = res.pack(size_limit=512 if protocol == 'udp' else None) # rfc2181
            len_data = len(data)
            yield data
            res_code = res.r
        else:
            len_data = 0
            res_code = -1
        logger.info(
            '[%s|%s|%s|%s] %s %d %d %s',
            protocol,
            'cache' if cached else 'remote',
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

async def start_dns_server(
    bind=':53', enable_tcp=True, enable_udp=True,
    hosts=None, proxies=None):
    '''Start a DNS server.'''

    cache = CacheNode()
    cache.add('1.0.0.127.in-addr.arpa', qtype=types.PTR, data='async-dns.local')
    cache.add('localhost', qtype=types.A, data='127.0.0.1')
    if hosts != 'none':
        for rec in parse_hosts_file(None if hosts == 'local' else hosts):
            cache.add(record=rec)
    if proxies is None:
        # recursive resolver
        resolver = Resolver(cache)
    else:
        # proxy resolver
        # if proxy is falsy, default proxies will be used
        resolver = ProxyResolver(cache, proxies=proxies)
    loop = asyncio.get_event_loop()
    host = Host(bind)
    urls = []
    if enable_tcp:
        server = await start_server(TCPHandler(resolver).handle_tcp, bind)
        urls.extend(get_server_hosts([server], 'tcp:'))
    else:
        server = None
    if enable_udp:
        hostname = host.hostname or '::' # '::' includes both IPv4 and IPv6
        transport, _protocol = await loop.create_datagram_endpoint(
            lambda: DNSDatagramProtocol(resolver),
            local_addr=(hostname, host.port))
        urls.append(get_url_items([transport.get_extra_info('sockname')], 'udp:'))
    else:
        transport = None
    for line in repr_urls(urls):
        logger.info('%s', line)
    logger.info('%s started', resolver.name)
    return resolver, server, transport
