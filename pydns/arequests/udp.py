#!/usr/bin/env python
# coding=utf-8
import asyncio

class CallbackProtocol(asyncio.DatagramProtocol):
    def __init__(self, future):
        self.future = future

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.transport.close()
        if not self.future.cancelled():
            self.future.set_result(data)

async def request(qdata, addr, timeout = 3.0):
    future = asyncio.Future()
    loop = asyncio.get_event_loop()
    transport, protocol = await asyncio.wait_for(
        loop.create_datagram_endpoint(lambda : CallbackProtocol(future), remote_addr = addr.to_addr()),
        1.0
    )
    transport.sendto(qdata)
    data = await asyncio.wait_for(future, timeout)
    return data
