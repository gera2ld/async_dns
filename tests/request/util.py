import io
from async_dns.request.util import ConnectionPool


class MockReader:
    def __init__(self):
        self.buffer = []

    def feed(self, data):
        self.buffer.append(data)

    async def read(self, size):
        data = self.buffer[0]
        del self.buffer[0]
        return data

    async def readexactly(self, size):
        data = await self.read(size)
        assert len(data) == size
        return data

    async def readline(self):
        data = await self.read(-1)
        assert data.endswith(b'\n')
        return data


class MockWriter:
    def __init__(self):
        self.buffer = io.BytesIO()

    def write(self, data):
        self.buffer.write(data)

    async def drain(self):
        pass


class MockConnection:
    def __init__(self):
        self.reader = MockReader()
        self.writer = MockWriter()


class MockConnectionHandle:
    conn = None

    def __init__(self, *k, **kw):
        self.pool = ConnectionPool.get(*k, **kw)
        assert isinstance(self.pool.addr[0], str)
        assert isinstance(self.pool.addr[1], int)

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        pass
