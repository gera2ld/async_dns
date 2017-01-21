import asyncio
from .. import DNSMessage, UDP, InternetProtocol
from .. import resolver, logger, types
from ..cache import DNSMemCache

class DNSMixIn:
    def __init__(self, resolver, *k, **kw):
        self.resolver = resolver

    async def handle(self, data, addr):
        msg = DNSMessage.parse(data)
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
            logger.info('%s %4s %s %d %d', addr[0], types.get_name(c.qtype), c.name, r, l)
            break   # only one question is supported

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

class DNSServer:
    def __init__(self, host='0.0.0.0', port=53, protocol_classes=(DNSProtocol, DNSDatagramProtocol), hosts=None, resolve_protocol=UDP, proxies=None):
        if not isinstance(resolve_protocol, InternetProtocol):
            resolve_protocol = InternetProtocol.get(resolve_protocol)
        self.host = host
        self.port = port
        self.TCPProtocol, self.UDPProtocol = protocol_classes
        cache = DNSMemCache()
        cache.add_root_servers()
        self.resolver = resolver.ProxyResolver(resolve_protocol, cache)
        if hosts is not None:
            self.resolver.cache.parse_file(hosts)
        if proxies:
            self.resolver.set_proxies(proxies)

    async def start_server(self):
        loop = asyncio.get_event_loop()
        if self.TCPProtocol:
            server = await loop.create_server(lambda : self.TCPProtocol(self.resolver), self.host, self.port)
        else:
            server = None
        if self.UDPProtocol:
            transport, protocol = await loop.create_datagram_endpoint(lambda : self.UDPProtocol(self.resolver), local_addr = (self.host, self.port))
        else:
            transport = None
        return server, transport
