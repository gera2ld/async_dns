'''
Request using TCP protocol.
'''

import asyncio

_DEFAULT_QUEUE_SIZE = 10
_DEFAULT_CONNECTION_LIFETIME = 120

connections = {}

class DNSConnectionError(ConnectionError):
    '''
    Error thrown when connection to nameserver fails.
    '''

class CallbackProtocol(asyncio.Protocol):
    '''
    Protocol class for asyncio connection callback.
    '''
    def __init__(self, key):
        super().__init__(self)
        self.key = key
        self.transport = None
        self.cached = False
        self._close_handle = None
        self._future = None

    def connection_made(self, transport):
        self.transport = transport
        self.cached = True
        self._close_handle = None
        self._reset_close()
        self._set_future()

    def _set_future(self, future=None):
        self._future = future
        transport = self.transport
        if future is None:
            transport.pause_reading()
            # transport.pause_writing()
        else:
            transport.resume_reading()
            # transport.resume_writing()

    def write_data(self, future, data):
        '''
        Set future to wait for response. Write data to request.
        '''
        self._reset_close()
        self._set_future(future)
        self.transport.write(data)

    def data_received(self, data):
        if self._future is not None:
            if not self._future.cancelled():
                self._future.set_result(data)
            self._set_future()

    def _reset_close(self):
        '''
        Reset timer to delay close of connection.
        '''
        if self._close_handle:
            self._close_handle.cancel()
        loop = asyncio.get_event_loop()
        self._close_handle = loop.call_later(_DEFAULT_CONNECTION_LIFETIME, self._close)

    def _close(self):
        connections.pop(self.key, None)
        self.cached = False
        self.transport.close()

    def connection_lost(self, exc):
        if self.cached:
            self._close()

async def _connect(addr, onconnect, timeout=3.0):
    loop = asyncio.get_event_loop()
    _transport, protocol = await asyncio.wait_for(
        loop.create_connection(onconnect, host=addr.hostname, port=addr.port),
        timeout
    )
    return protocol

async def request(qdata, addr, timeout=3.0):
    '''
    Send raw data with a connection pool.
    '''
    key = addr.to_str(53)
    queue = connections.get(key)
    if queue is None:
        queue = connections[key] = asyncio.Queue(maxsize=_DEFAULT_QUEUE_SIZE)
    try:
        protocol = queue.get_nowait()
        assert protocol.cached
    except (asyncio.QueueEmpty, AssertionError):
        onconnect = lambda: CallbackProtocol(key)
        for _retry in range(3):
            try:
                protocol = await _connect(addr, onconnect, timeout)
            except:
                pass
            else:
                break
        else:
            raise DNSConnectionError
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    protocol.write_data(future, qdata)
    data = await asyncio.wait_for(future, timeout)
    try:
        queue.put_nowait(protocol)
    except asyncio.QueueFull:
        pass
    return data
