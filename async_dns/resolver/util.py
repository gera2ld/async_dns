import asyncio
import functools
from collections import deque
from async_dns.core import logger


class Connection:
    def __init__(self, reader, writer, timer=None):
        self.reader = reader
        self.writer = writer
        self.timer = timer


class ConnectionPool:
    pools = {}

    @classmethod
    def get(cls, host, port=None, ssl=False, hostname=None, max_size=6):
        if port is None:
            port = 443 if ssl else 80
        key = host, port, ssl, hostname
        pool = cls.pools.get(key)
        if pool is None:
            pool = cls(host, port, ssl, hostname, max_size)
            cls.pools[key] = pool
        return pool

    def __init__(self, host, port, ssl, hostname, max_size):
        self.addr = host, port
        self.ssl = ssl
        self.hostname = hostname
        self.key = host, port, ssl, hostname
        self.tasks = set()
        self.connections = set()
        self.requests = deque()
        self.max_size = max_size
        self.size = 0

    def on_connection(self, result):
        reader, writer = result
        self.connections.add(Connection(reader, writer))
        self.check()

    def on_connection_error(self, exc):
        logger.debug('[connect_error] %s:%port', self.hostname or self.addr[0], self.addr[1])
        self.size -= 1

    def check(self):
        while len(self.requests) > 0 and len(self.connections) > 0:
            future = self.requests.popleft()
            conn = self.connections.pop()
            self.ensure_task(self.acquire_connection(conn, future))
        for _ in self.requests:
            if self.size >= self.max_size:
                break
            self.size += 1
            self.ensure_task(
                asyncio.open_connection(*self.addr,
                                        ssl=self.ssl,
                                        server_hostname=self.hostname),
                self.on_connection, self.on_connection_error)

    def check_later(self):
        loop = asyncio.get_event_loop()
        loop.call_soon(self.check)

    def ensure_task(self, coro, on_success=None, on_error=None):
        task = asyncio.ensure_future(coro)
        self.tasks.add(task)

        def on_done(task):
            try:
                result = task.result()
                if on_success is not None: on_success(result)
            except Exception as exc:
                if on_error is not None: on_error(exc)
            self.tasks.remove(task)

        task.add_done_callback(on_done)

    async def acquire_connection(self, conn, future):
        try:
            await conn.writer.drain()
        except Exception:
            self.discard_connection(conn)
            if not future.done():
                self.requests.appendleft(future)
            return False
        if conn.timer:
            conn.timer.cancel()
            conn.timer = None
        if future.done():
            self.put_connection(conn)
        else:
            future.set_result(conn)
        return True

    async def get_connection(self):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.requests.append(future)
        self.check_later()
        try:
            result = await future
            return result
        except asyncio.CancelledError:
            future.cancel()
            raise

    def put_connection(self, conn):
        self.connections.add(conn)
        loop = asyncio.get_running_loop()
        conn.timer = loop.call_later(
            10, functools.partial(self.discard_connection, conn))
        self.check_later()

    def discard_connection(self, conn):
        conn.writer.close()
        if conn.timer: conn.timer.cancel()
        self.connections.discard(conn)
        self.size -= 1

    def destroy(self):
        for task in self.tasks:
            task.cancel()
        for conn in self.connections:
            self.discard_connection(conn)
        for fut in self.requests:
            fut.cancel()
        self.tasks.clear()
        self.connections.clear()
        self.requests.clear()
        self.pools.pop(self.key, None)


class ConnectionHandle:
    def __init__(self, *k, **kw):
        self.pool = ConnectionPool.get(*k, **kw)
        self.conn = None

    async def __aenter__(self):
        self.conn = await self.pool.get_connection()
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        if exc is None:
            self.pool.put_connection(self.conn)
        else:
            self.pool.discard_connection(self.conn)
