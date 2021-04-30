import asyncio

from .client import DoHClient

_client = None


def set_client(client=None):
    global _client
    if client is None:
        client = DoHClient()
    _client = client


async def request_message(req, addr, timeout=3.0):
    result = await asyncio.wait_for(_client.request_message(str(addr), req),
                                    timeout)
    return result


def request(req, addr, timeout=3.0):
    if _client is None:
        set_client()
    return request_message(req, addr, timeout)
