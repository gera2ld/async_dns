'''
Request using TCP protocol.
'''
import asyncio
import struct
from async_dns.core import DNSMessage
from .util import ConnectionPool


async def request(req, addr, timeout=3.0):
    '''
    Send raw data with a connection pool.
    '''
    pool = ConnectionPool.get(*addr.to_addr(), ssl=addr.protocol == 'tcps')
    conn = await pool.get_connection()
    try:
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
    finally:
        pool.put_connection(conn)
