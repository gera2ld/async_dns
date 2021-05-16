'''
Request using UDP protocol.
'''
import asyncio
import socket

from async_dns.core import Address, DNSMessage, REQUEST, RandId, Record, types


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

    def write_data(self, data, addr, timeout):
        '''
        Write data to request.
        '''
        qid = data[:2]
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.futures[qid] = future

        def clear(_=None):
            if not future.done():
                future.cancel()
            self.futures.pop(qid, None)

        future.add_done_callback(clear)
        loop.call_later(timeout, clear)
        self.transport.sendto(data, addr)
        return future


class Dispatcher:
    data = {}
    protocol: CallbackProtocol

    def __init__(self, ip_type, local_addr=None):
        self.ip_type = ip_type
        self.local_addr = local_addr
        self.initialized = None
        self.rand_id = RandId()

    async def initialize(self):
        if self.initialized is not None:
            await self.initialized
            return
        loop = asyncio.get_event_loop()
        self.initialized = loop.create_future()
        family = socket.AF_INET6 if self.ip_type is types.AAAA else socket.AF_INET
        _transport, self.protocol = await loop.create_datagram_endpoint(
            CallbackProtocol, family=family, local_addr=self.local_addr)
        self.initialized.set_result(None)

    async def send(self, req: DNSMessage, addr: Address, timeout: float):
        qid = self.rand_id.get()
        req.qid = qid
        try:
            return await self.protocol.write_data(req.pack(), addr.to_addr(),
                                                  timeout)
        finally:
            self.rand_id.put(qid)

    def destroy(self):
        self.protocol.transport.close()
        self.data.pop(self.ip_type, None)

    @classmethod
    def destroy_all(cls):
        for dis in list(cls.data.values()):
            dis.destroy()

    @classmethod
    async def get(cls, ip_type):
        dispatcher = cls.data.get(ip_type)
        if dispatcher is None:
            dispatcher = Dispatcher(ip_type)
            cls.data[ip_type] = dispatcher
        await dispatcher.initialize()
        return dispatcher


async def request(req: DNSMessage, addr: Address, timeout: float = 3.0):
    '''
    Send raw data through UDP.
    '''
    dispatcher = await Dispatcher.get(addr.ip_type)
    data = await dispatcher.send(req, addr, timeout)
    result = DNSMessage.parse(data)
    return result


if __name__ == '__main__':

    async def main():
        req = DNSMessage(qr=REQUEST)
        req.qd = [Record(REQUEST, 'www.google.com', types.A)]
        result = await request(req, Address.parse('udp://114.114.114.114'))
        print('query_udp:', result)

    asyncio.run(main())
