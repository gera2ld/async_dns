import asyncio
import base64
import json
from typing import TYPE_CHECKING, Union
import urllib.parse

from async_dns.core import DNSMessage, REQUEST, Record, types

from ..util import ConnectionHandle

if TYPE_CHECKING:
    from async_dns.resolver import BaseResolver


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
                       resolver: 'BaseResolver' = None):
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
    assert host, 'Invalid host'
    if resolver is not None:
        msg, _ = await resolver.query(host)
        rdata = msg.get_record((types.A, types.AAAA))
        assert rdata, 'DNS lookup failed'
        host = rdata.data
    async with ConnectionHandle(host, res.port, ssl, res.hostname) as conn:
        reader = conn.reader
        writer = conn.writer
        writer.write(f'{method} {path} HTTP/1.1\r\n'.encode())
        merged_headers = {
            'host': res.hostname,
        }
        if headers:
            for key, value in headers.items():
                merged_headers[key.lower()] = value
        if data:
            merged_headers['content-length'] = str(len(data))
        for key, value in merged_headers.items():
            writer.write(f'{key}: {value}\r\n'.encode())
        writer.write(b'\r\n')
        if data:
            writer.write(data)
        await writer.drain()
        status, message, headers, data = await read_data(reader)
        resp = Response(status, message, headers, data, url)
        return resp


class DoHClient:
    session = None

    def __init__(self,
                 resolver: 'BaseResolver' = None,
                 default_method: str = 'GET'):
        if resolver is None:
            from async_dns import get_nameservers
            from async_dns.resolver import ProxyResolver
            resolver = ProxyResolver(proxies=get_nameservers())
        self.resolver = resolver
        self.default_method = default_method

    def request(self, url, method, params=None, data=None, headers=None):
        return send_request(url,
                            method=method,
                            params=params,
                            data=data,
                            headers=headers,
                            resolver=self.resolver)

    async def request_message(self, url, req, method=None):
        headers = {
            'accept': 'application/dns-message',
            'content-type': 'application/dns-message',
        }
        message = req.pack()
        if method is None:
            method = self.default_method
        if method == 'GET':
            dns = base64.urlsafe_b64encode(message).decode().rstrip('=')
            params = {'dns': dns}
            data = None
        else:
            assert method == 'POST', f'Unsupported method: {method}'
            params = None
            data = message
        resp = await self.request(url,
                                  method=method,
                                  params=params,
                                  data=data,
                                  headers=headers)
        assert 200 <= resp.status < 300, f'Request error: {resp.status}'
        result = DNSMessage.parse(resp.data)
        return result

    async def query(self,
                    url: str,
                    name: str,
                    qtype: Union[int, str] = types.A,
                    method: str = None):
        req = DNSMessage(qr=REQUEST)
        qtype_code = qtype = types.get_code(qtype) if isinstance(
            qtype, str) else qtype
        req.qd = [Record(REQUEST, name, qtype_code)]
        return await self.request_message(url, req, method)

    async def query_json(self,
                         url: str,
                         name: str,
                         qtype: Union[int, str] = types.A):
        '''Query via JSON APIs for DNS over HTTPS.

        All API calls are HTTP GET requests.
        Reference: https://developers.google.com/speed/public-dns/docs/doh/json
        '''
        if isinstance(qtype, int):
            qtype = types.get_name(qtype)
        resp = await self.request(url,
                                  method='GET',
                                  params={
                                      'name': name,
                                      'qtype': qtype
                                  },
                                  headers={'accept': 'application/dns-json'})
        assert 200 <= resp.status < 300, f'Request error: {resp.status}'
        data = json.loads(resp.data)
        return data


if __name__ == '__main__':

    async def main():
        print(await send_request('https://www.baidu.com'))

        client = DoHClient()
        result = await client.query('https://dns.alidns.com/dns-query',
                                    'www.google.com', 'A')
        print('query:', result)
        result = await client.query_json('https://dns.alidns.com/resolve',
                                         'www.google.com', 'A')
        print('query_json:', result)

    asyncio.run(main())
