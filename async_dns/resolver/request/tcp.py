'''
Request using TCP protocol.
'''
import asyncio
import struct

from async_dns.core import Address, DNSMessage, REQUEST, Record, types

from .util import ConnectionHandle


async def _request(req, addr):
    async with ConnectionHandle(*addr.to_addr(),
                                ssl=addr.protocol == 'tcps') as conn:
        reader = conn.reader
        writer = conn.writer
        qdata = req.pack()
        bsize = struct.pack('!H', len(qdata))
        writer.write(bsize)
        writer.write(qdata)
        await writer.drain()
        size, = struct.unpack('!H', await reader.readexactly(2))
        data = await reader.readexactly(size)
        result = DNSMessage.parse(data)
        return result


async def request(req, addr, timeout=3.0):
    '''
    Send raw data with a connection pool.
    '''
    result = await asyncio.wait_for(_request(req, addr), timeout)
    return result


if __name__ == '__main__':

    async def main():
        req = DNSMessage(qr=REQUEST)
        req.qd = [Record(REQUEST, 'www.google.com', types.A)]
        result = await request(req, Address.parse('tcp://114.114.114.114'))
        print('query_tcp:', result)

    asyncio.run(main())
