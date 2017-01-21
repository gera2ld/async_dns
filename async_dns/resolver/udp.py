'''
Request using UDP protocol.
'''

import asyncio

class CallbackProtocol(asyncio.DatagramProtocol):
    '''
    Protocol class for asyncio connection callback.
    '''
    def __init__(self):
        self.future = None
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.transport.close()
        if not self.future.cancelled():
            self.future.set_result(data)

    def write_data(self, future, data):
        '''
        Set future to wait for response. Write data to request.
        '''
        self.future = future
        self.transport.sendto(data)

async def request(qdata, addr, timeout=3.0):
    '''
    Send raw data through UDP.
    '''
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    loop = asyncio.get_event_loop()
    _transport, protocol = await asyncio.wait_for(
        loop.create_datagram_endpoint(CallbackProtocol, remote_addr=addr.to_addr()),
        1.0
    )
    protocol.write_data(future, qdata)
    data = await asyncio.wait_for(future, timeout)
    return data
