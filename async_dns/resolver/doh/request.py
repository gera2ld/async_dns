import urllib.parse
from async_dns import types
from ..util import ConnectionHandle


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
    host = res.hostname
    if resolver is not None:
        msg = await resolver.query(host)
        host = msg.get_record((types.A, types.AAAA))
        assert host, 'DNS lookup failed'
    async with ConnectionHandle(host, res.port, ssl, res.hostname) as conn:
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
        resp = Response(status, message, headers, data, url)
        return resp


if __name__ == '__main__':

    async def main():
        print(await send_request('https://www.baidu.com'))

    import asyncio
    asyncio.run(main())
