'''
Request using TCP protocol.
'''
import asyncio
import struct
from async_dns.core import DNSMessage
from .util import ConnectionHandle


async def request(req, addr, timeout=3.0):
    '''
    Send raw data with a connection pool.
    '''
    async with ConnectionHandle(*addr.to_addr(), ssl=addr.protocol == 'tcps') as conn:
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
