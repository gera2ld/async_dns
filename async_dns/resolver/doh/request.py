import asyncio
import functools
import urllib.parse

class Connection:
    def __init__(self, reader, writer, timer=None):
        self.reader = reader
        self.writer = writer
        self.timer = timer

class ConnectionPool:
    pools = {}

    @classmethod
    def get(cls, host, port=None, ssl=False, max_size=5):
        if port is None:
            port = 443 if ssl else 80
        key = host, port, ssl
        pool = cls.pools.get(key)
        if pool is None:
            pool = cls(host, port, ssl, max_size)
            cls.pools[key] = pool
        return pool

    def __init__(self, host, port, ssl, max_size):
        self.addr = host, port
        self.ssl = ssl
        self.connections = set()
        self.requests = asyncio.Queue()
        self.booting = set()
        self.max_size = max_size
        self.size = 0

    def create_connection(self):
        task = asyncio.create_task(asyncio.open_connection(*self.addr, ssl=self.ssl))
        self.booting.add(task)
        task.add_done_callback(functools.partial(self.on_connection))

    def on_connection(self, task):
        self.booting.discard(task)
        try:
            reader, writer = task.result()
            self.connections.add(Connection(reader, writer))
            self.check()
        except Exception:
            self.size -= 1

    def check(self):
        while self.requests.qsize() > 0:
            try:
                conn = self.connections.pop()
            except KeyError:
                break
            else:
                future = self.requests.get_nowait()
                future.set_result(conn)
        for _ in range(self.requests.qsize()):
            if self.size < self.max_size:
                self.size += 1
                self.create_connection()
            else:
                break

    async def get_connection(self):
        try:
            conn = self.connections.pop()
        except KeyError:
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            await self.requests.put(future)
            loop.call_soon(self.check)
            conn = await future
        try:
            await conn.writer.drain()
        except Exception:
            self.discard_connection(conn)
            raise
        if conn.timer:
            conn.timer.cancel()
            conn.timer = None
        return conn

    def put_connection(self, conn):
        self.connections.add(conn)
        loop = asyncio.get_running_loop()
        conn.timer = loop.call_later(10, functools.partial(self.discard_connection, conn))

    def discard_connection(self, conn):
        conn.writer.close()
        if conn.timer: conn.timer.cancel()
        self.connections.discard(conn)
        self.size += 1

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

async def request(url, method='GET', params=None, data=None, headers=None, ip=None):
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
    pool = ConnectionPool.get(ip or res.hostname, res.port, ssl)
    conn = await pool.get_connection()
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
    pool.put_connection(conn)
    return Response(status, message, headers, data, url)

if __name__ == '__main__':
    async def main():
        print(await request('https://www.baidu.com'))

    asyncio.run(main())
