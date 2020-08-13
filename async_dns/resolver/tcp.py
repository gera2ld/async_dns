'''
Request using TCP protocol.
'''
import asyncio
import struct
from async_dns.core import DNSMessage

DEFAULT_QUEUE_SIZE = 10
_connections = {}

class DNSConnectionError(ConnectionError):
    '''
    Connection to nameserver fails.
    '''

async def request(req, addr, timeout=3.0):
    '''
    Send raw data with a connection pool.
    '''
    qdata = req.pack()
    bsize = struct.pack('!H', len(qdata))
    key = str(addr)
    queue = _connections.get(key)
    if queue is None:
        queue = asyncio.Queue(maxsize=DEFAULT_QUEUE_SIZE)
        _connections[key] = queue
    for _retry in range(5):
        reader = writer = None
        try:
            reader, writer = queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        if reader is None:
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(*addr.to_addr()), timeout)
            except asyncio.TimeoutError:
                pass
        if reader is None:
            continue
        writer.write(bsize)
        writer.write(qdata)
        try:
            await writer.drain()
            size, = struct.unpack('!H', await reader.readexactly(2))
            data = await reader.readexactly(size)
            queue.put_nowait((reader, writer))
        except asyncio.QueueFull:
            pass
        result = DNSMessage.parse(data)
        return result
    else:
        raise DNSConnectionError
