import asyncio
import base64
import json
from functools import partial
from async_dns import DNSMessage, REQUEST, Record, types
from .request import request

class DoHClient:
    session = None

    async def request_message(self, url, req, method='GET'):
        headers = {
            'accept': 'application/dns-message',
            'content-type': 'application/dns-message',
        }
        message = req.pack()
        if method == 'GET':
            dns = base64.urlsafe_b64encode(message).decode().rstrip('=')
            params = { 'dns': dns }
            data = None
        else:
            assert method == 'POST', f'Unsupported method: {method}'
            params = None
            data = message
        resp = await request(url, method, params=params, data=data, headers=headers)
        assert 200 <= resp.status < 300, f'Request error: {resp.status}'
        result = DNSMessage.parse(resp.data)
        return result

    async def query(self, url, name, qtype=types.A, method='GET'):
        req = DNSMessage(qr=REQUEST)
        if isinstance(qtype, str):
            qtype = types.get_code(qtype)
        req.qd = [Record(REQUEST, name, qtype)]
        return await self.request_message(url, req, method)

    async def query_json(self, url, name, qtype=types.A):
        '''Query via JSON APIs for DNS over HTTPS.

        All API calls are HTTP GET requests.
        Reference: https://developers.google.com/speed/public-dns/docs/doh/json
        '''
        if isinstance(qtype, int):
            qtype = types.get_name(qtype)
        resp = await request(url,
                params={ 'name': name, 'qtype': qtype },
                headers={ 'accept': 'application/dns-json' })
        assert 200 <= resp.status < 300, f'Request error: {resp.status}'
        data = json.loads(resp.data)
        return data

_client = None

async def request_message(client, req, addr, timeout=3.0, method='POST'):
    result = await asyncio.wait_for(client.request_message(str(addr), req, method), timeout)
    return result

def request_wrapper(method='POST'):
    return partial(request_message, DoHClient(), method=method)

if __name__ == '__main__':
    async def main():
        client = DoHClient()
        result = await client.query('https://dns.alidns.com/dns-query', 'www.google.com', 'A')
        print('query:', result)
        result = await client.query_json('https://dns.alidns.com/resolve', 'www.google.com', 'A')
        print('query_json:', result)
    asyncio.run(main())
