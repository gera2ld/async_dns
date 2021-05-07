import asyncio
import base64
import json
from typing import TYPE_CHECKING, Union

from async_dns.core import DNSMessage, REQUEST, Record, types

from .request import send_request

if TYPE_CHECKING:
    from async_dns.resolver import BaseResolver


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
        client = DoHClient()
        result = await client.query('https://dns.alidns.com/dns-query',
                                    'www.google.com', 'A')
        print('query:', result)
        result = await client.query_json('https://dns.alidns.com/resolve',
                                         'www.google.com', 'A')
        print('query_json:', result)

    asyncio.run(main())
