'''
Async DNS server
'''
import asyncio
from .. import DNSMessage, UDP, InternetProtocol
from .. import resolver, logger, types
from ..cache import DNSMemCache

class DNSMixIn:
    '''DNS handler mix-in'''
    def __init__(self, resolver_, *k, **kw):
        super().__init__(*k, **kw)
        self.resolver = resolver_
        self.transport = None
        self.addr = None

    def send_data(self, data, addr):
        '''Send data to remote server.'''
        raise NotImplementedError

    async def handle(self, data, addr):
        '''Main handle method for protocols.'''
        msg = DNSMessage.parse(data)
        for question in msg.qd:
            res = await self.resolver.query(question.name, question.qtype)
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
                '%s %4s %s %d %d', addr[0], types.get_name(question.qtype),
                question.name, res_code, len_data)
            break   # only one question is supported

class DNSDatagramProtocol(DNSMixIn, asyncio.DatagramProtocol):
    '''DNS server handler through UDP protocol.'''
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        asyncio.ensure_future(self.handle(data, addr))

    def send_data(self, data, addr):
        self.transport.sendto(data, addr)

class DNSProtocol(DNSMixIn, asyncio.Protocol):
    '''DNS server handler through TCP protocol.'''
    def connection_made(self, transport):
        self.transport = transport
        self.addr = transport.get_extra_info('peername')

    def data_received(self, data):
        asyncio.ensure_future(self.handle(data, self.addr))

    def send_data(self, data, addr):
        self.transport.write(data)

async def start_server(
    host='0.0.0.0', port=53, protocol_classes=(DNSProtocol, DNSDatagramProtocol),
    hosts=None, resolve_protocol=UDP, proxies=None):
    '''Start a DNS server.'''
    if not isinstance(resolve_protocol, InternetProtocol):
        resolve_protocol = InternetProtocol.get(resolve_protocol)
    tcp_protocol, udp_protocol = protocol_classes
    cache = DNSMemCache()
    cache.add_root_servers()
    _resolver = resolver.ProxyResolver(resolve_protocol, cache)
    if hosts is not None:
        _resolver.cache.parse_file(hosts)
    if proxies:
        _resolver.set_proxies(proxies)
    loop = asyncio.get_event_loop()
    if tcp_protocol:
        server = await loop.create_server(lambda: tcp_protocol(_resolver), host, port)
    else:
        server = None
    if udp_protocol:
        transport, _protocol = await loop.create_datagram_endpoint(
            lambda: udp_protocol(_resolver), local_addr=(host, port))
    else:
        transport = None
    return server, transport
