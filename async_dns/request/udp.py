'''
Request using UDP protocol.
'''
import asyncio
import socket
from typing import Tuple

from async_dns.core import Address, DNSMessage, REQUEST, RandId, Record, logger, types


class CallbackProtocol(asyncio.DatagramProtocol):
    '''
    Protocol class for asyncio connection callback.
    '''
    def __init__(self):
        super().__init__()
        self.transport = None
        self.futures = {}
        self.data = []

    def connection_made(self, transport):
        self.transport = transport
        for data, addr in self.data:
            self.transport.sendto(data, addr)
        self.data = None

    def datagram_received(self, data, addr):
        qid = data[:2]
        future = self.futures.pop(qid, None)
        if future is not None and not future.cancelled():
            future.set_result(data)

    def error_received(self, exc):
        logger.error('UDP socket error: %s', exc)

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
        if self.data is None:
            self.transport.sendto(data, addr)
        else:
            self.data.append((data, addr))
        return future


class Dispatcher:
    data = {}

    def __init__(self, ip_type, local_addr=None):
        self.ip_type = ip_type
        self.local_addr = local_addr
        self.rand_id = RandId()
        self.protocol = CallbackProtocol()
        self.initialized = None

    async def _send(self, data: bytes, addr: Tuple[str, int], timeout: float):
        if self.initialized is None:
            loop = asyncio.get_event_loop()
            family = socket.AF_INET6 if self.ip_type is types.AAAA else socket.AF_INET
            self.initialized = asyncio.ensure_future(
                loop.create_datagram_endpoint(lambda: self.protocol,
                                              family=family,
                                              local_addr=self.local_addr))
        return await self.protocol.write_data(data, addr, timeout)

    async def send(self, req: DNSMessage, addr: Address, timeout: float):
        qid = self.rand_id.get()
        req.qid = qid
        try:
            host, port = addr.to_addr()
            return await self._send(req.pack(), (host, port or 53), timeout)
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
    def get(cls, ip_type):
        dispatcher = cls.data.get(ip_type)
        if dispatcher is None:
            dispatcher = Dispatcher(ip_type)
            cls.data[ip_type] = dispatcher
        return dispatcher


async def request(req: DNSMessage, addr: Address, timeout: float = 3.0):
    '''
    Send raw data through UDP.
    '''
    dispatcher = Dispatcher.get(addr.ip_type)
    data = await dispatcher.send(req, addr, timeout)
    result = DNSMessage.parse(data)
    return result


if __name__ == '__main__':

    async def main():
        req = DNSMessage(qr=REQUEST)
        req.qd = [Record(REQUEST, 'www.google.com', types.A)]
        result = await request(req, Address.parse('udp://114.114.114.114'))
        print('query_udp:', result)
        from async_dns.request import clean
        clean()

    asyncio.run(main())
