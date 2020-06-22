'''
Request using TCP protocol.
'''
import asyncio
import struct

_DEFAULT_QUEUE_SIZE = 10
_DEFAULT_CONNECTION_LIFETIME = 120
_connections = {}

class DNSConnectionError(ConnectionError):
    '''
    Error thrown when connection to nameserver fails.
    '''

async def request(req, addr, timeout=3.0):
    '''
    Send raw data with a connection pool.
    '''
    qdata = req.pack()
    bsize = struct.pack('!H', len(qdata))
    key = addr.to_str(53)
    queue = _connections.setdefault(key, asyncio.Queue(maxsize=_DEFAULT_QUEUE_SIZE))
    for _retry in range(5):
        reader = writer = None
        try:
            reader, writer = queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        if reader is None:
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(addr.host, addr.port), timeout)
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
        return data
    else:
        raise DNSConnectionError
