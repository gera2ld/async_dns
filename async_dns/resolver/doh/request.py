import asyncio
import functools
import urllib.parse
from collections import deque
from async_dns import types


class Connection:
    def __init__(self, reader, writer, timer=None):
        self.reader = reader
        self.writer = writer
        self.timer = timer


class ConnectionPool:
    pools = {}

    @classmethod
    def get(cls, host, port=None, ssl=False, max_size=6):
        if port is None:
            port = 443 if ssl else 80
        key = host, port, bool(ssl)
        pool = cls.pools.get(key)
        if pool is None:
            pool = cls(host, port, ssl, max_size)
            cls.pools[key] = pool
        return pool

    def __init__(self, host, port, ssl, max_size):
        self.addr = host, port
        self.ssl = ssl
        self.key = host, port, bool(ssl)
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
            self.ensure_task(asyncio.open_connection(*self.addr, ssl=self.ssl),
                             self.on_connection, self.on_connection_error)

    def check_later(self):
        loop = asyncio.get_event_loop()
        loop.call_soon(self.check)

    def ensure_task(self, coro, on_success=None, on_error=None):
        task = asyncio.create_task(coro)
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


class Response:
    def __init__(self, status, message, headers, data, url):
        self.status = status
        self.message = message
        self.headers = headers
        self.data = data
        self.url = url

    def __repr__(self):
        return f'<Response status={self.status} message="{self.message}" url="{self.url}" data={self.data}>'


async def read_data(reader):
    headers = []
    first_line = await reader.readline()
    _proto, status, message = first_line.strip().decode().split(' ', 2)
    status = int(status)
    length = 0 if status == 204 else None
    while True:
        line = await reader.readline()
        line = line.strip().decode()
        if not line:
            break
        key, _, value = line.partition(':')
        headers.append((key, value.strip()))
        if key.lower() == 'content-length':
            length = int(value)
    data = await reader.read(length)
    return status, message, headers, data


async def send_request(url,
                       method='GET',
                       params=None,
                       data=None,
                       headers=None,
                       resolver=None):
    if '://' not in url:
        url = 'http://' + url
    if params:
        url += '&' if '?' in url else '?'
        qs = urllib.parse.urlencode(params)
        url += qs
    res = urllib.parse.urlparse(url)
    kw = {}
    if res.port: kw['port'] = res.port
    path = res.path or '/'
    if res.query: path += '?' + res.query
    ssl = res.scheme == 'https'
    hostname = res.hostname
    if resolver is not None:
        msg = await resolver.query(hostname)
        hostname = msg.get_record((types.A, types.AAAA))
        assert hostname, 'DNS lookup failed'
    pool = ConnectionPool.get(hostname, res.port, ssl)
    conn = await pool.get_connection()
    try:
        reader = conn.reader
        writer = conn.writer
        writer.write(f'{method} {path} HTTP/1.1\r\n'.encode())
        merged_headers = {
            'Host': res.hostname,
        }
        if headers: merged_headers.update(headers)
        if data:
            merged_headers['Content-Length'] = len(data)
        for key, value in merged_headers.items():
            writer.write(f'{key}: {value}\r\n'.encode())
        writer.write(b'\r\n')
        if data:
            writer.write(data)
        await writer.drain()
        status, message, headers, data = await read_data(reader)
        return Response(status, message, headers, data, url)
    finally:
        pool.put_connection(conn)


if __name__ == '__main__':

    async def main():
        print(await send_request('https://www.baidu.com'))

    asyncio.run(main())
