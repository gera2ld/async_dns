'''
Request using UDP protocol.
'''
import asyncio
import socket
from .. import types

class CallbackProtocol(asyncio.DatagramProtocol):
    '''
    Protocol class for asyncio connection callback.
    '''

    def __init__(self):
        super().__init__()
        self.transport = None
        self.futures = {}

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        qid = data[:2]
        future = self.futures.pop(qid, None)
        if future is not None and not future.cancelled():
            future.set_result(data)

    def write_data(self, data, addr):
        '''
        Write data to request.
        '''
        qid = data[:2]
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.futures[qid] = future
        self.transport.sendto(data, addr)
        return future

class Dispatcher:
    data = {}

    def __init__(self, ip_type, local_addr=None):
        self._qid = 0
        self.ip_type = ip_type
        self.local_addr = local_addr

    def get_qid(self):
        self._qid = (self._qid + 1) % 65536
        return self._qid

    async def initialize(self):
        family = socket.AF_INET6 if self.ip_type is types.AAAA else socket.AF_INET
        _transport, self.protocol = await loop.create_datagram_endpoint(
                CallbackProtocol, family=family, reuse_port=True, local_addr=self.local_addr)

    def send(self, req, addr):
        req.qid = self.get_qid()
        return self.protocol.write_data(req.pack(), addr.to_addr())

    @classmethod
    def get(cls, ip_type):
        return cls.data[ip_type]

Dispatcher.data.update((ip_type, Dispatcher(ip_type)) for ip_type in (types.A, types.AAAA))
loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.wait([dispatcher.initialize() for dispatcher in Dispatcher.data.values()]))

async def request(req, addr, timeout=3.0):
    '''
    Send raw data through UDP.
    '''
    future = Dispatcher.get(addr.ip_type).send(req, addr)
    data = await asyncio.wait_for(future, timeout)
    return data
