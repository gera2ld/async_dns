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
        self.initialized = None

    def get_qid(self):
        self._qid = (self._qid + 1) % 65536
        return self._qid

    async def initialize(self):
        if self.initialized is not None:
            await self.initialized
            return
        loop = asyncio.get_event_loop()
        self.initialized = loop.create_future()
        family = socket.AF_INET6 if self.ip_type is types.AAAA else socket.AF_INET
        _transport, self.protocol = await loop.create_datagram_endpoint(
                CallbackProtocol, family=family, reuse_port=True, local_addr=self.local_addr)
        self.initialized.set_result(None)

    def send(self, req, addr):
        req.qid = self.get_qid()
        return self.protocol.write_data(req.pack(), addr.to_addr())

    @classmethod
    async def get(cls, ip_type):
        dispatcher = cls.data.get(ip_type)
        if dispatcher is None:
            dispatcher = Dispatcher(ip_type)
            cls.data[ip_type] = dispatcher
        await dispatcher.initialize()
        return dispatcher

async def request(req, addr, timeout=3.0):
    '''
    Send raw data through UDP.
    '''
    dispatcher = await Dispatcher.get(addr.ip_type)
    data = await asyncio.wait_for(dispatcher.send(req, addr), timeout)
    return data
