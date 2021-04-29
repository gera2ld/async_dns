# async_dns

[![PyPI](https://img.shields.io/pypi/v/async_dns.svg)]()

## Features

- Built with `asyncio` in pure Python, no third party dependency is required
- Support DNS over UDP / TCP
- Support DNS over HTTPS
- Support DNS over TLS

## Prerequisite

- Python >=3.6

## Installation

``` sh
$ pip3 install async_dns
# or
$ pip3 install git+https://github.com/gera2ld/async_dns.git
```

## CLI

### Resolver

```
usage: python3 -m async_dns.resolver [-h] [-n NAMESERVERS [NAMESERVERS ...]] [-t TYPES [TYPES ...]]
                                     hostnames [hostnames ...]

Async DNS resolver

positional arguments:
  hostnames             the hostnames to query

optional arguments:
  -h, --help            show this help message and exit
  -n NAMESERVERS [NAMESERVERS ...], --nameservers NAMESERVERS [NAMESERVERS ...]
                        name servers
  -t TYPES [TYPES ...], --types TYPES [TYPES ...]
                        query types, default as `any`
```

Examples:

``` sh
# Resolve an IP
$ python3 -m async_dns.resolver www.google.com
$ python3 -m async_dns.resolver -t mx -- gmail.com

# Query via TCP
$ python3 -m async_dns.resolver -n tcp://127.0.0.1 -- www.google.com

# Query via TLS
$ python3 -m async_dns.resolver -n tcps://dns.alidns.com -- www.google.com

# Query from non-standard ports
$ python3 -m async_dns.resolver -n udp://127.0.0.1:1053 -- www.google.com

# Query from HTTPS
$ python3 -m async_dns.resolver -n https://dns.alidns.com/dns-query -- www.google.com
```

**Note:** `--` is required before `hostname`s if the previous option can have multiple arguments.

### Server

```
usage: python3 -m async_dns.server [-h] [-b BIND] [--hosts HOSTS] [-x [PROXY [PROXY ...]]]

DNS server by Gerald.

optional arguments:
  -h, --help            show this help message and exit
  -b BIND, --bind BIND  the address for the server to bind
  --hosts HOSTS         the path of a hosts file, `none` to disable hosts, `local` to read from
                        local hosts file
  -x [PROXY [PROXY ...]], --proxy [PROXY [PROXY ...]]
                        the proxy DNS servers, `none` to serve as a recursive server, `default` to
                        proxy to default nameservers
```

**Note:** TLS and HTTPS are not supported in `async_dns` server. Consider [async-doh](https://github.com/gera2ld/async-doh) for DoH server support.

Examples:

``` sh
# Start a DNS proxy server on :53
$ python3 -m async_dns.server -b :53 --hosts /etc/hosts

# Start a DNS server over TCP proxy
$ python3 -m async_dns.server -x tcp://114.114.114.114

# Start a DNS recursive server
$ python3 -m async_dns.server -x none
```

## API

``` python
import asyncio
from async_dns.core import types
from async_dns.resolver import ProxyResolver

resolver = ProxyResolver()
res, cached = asyncio.run(resolver.query('www.baidu.com', types.A))
print(res)
```

### Client

The client sends a request to a remote server and returns the message directly. Unlike resolvers, client does not have a cache and does not modify the response.

```python
import asyncio
from async_dns.core import types, Address
from async_dns.resolver import DNSClient

async def query():
    client = DNSClient()
    res = await client.query('www.google.com', types.A,
                             Address.parse('8.8.8.8'))
    print(res)
    print(res.aa)

asyncio.run(query())
```

### Routing

ProxyResolver supports routing based on domains:

```python
resolver = ProxyResolver(proxies=[
    ('*.lan', ['192.168.1.1']),                             # query 'udp://192.168.1.1:53' for '*.lan' domains
    (lambda d: d.endswith('.local'), ['tcp://127.0.0.1']),  # query tcp://127.0.0.1:53 for domains ending with '.local'
    '8.8.8.8',                                              # equivalent to (None, ['8.8.8.8']), matches all others
])
```

## DoH support

This library contains a simple implementation of DoH (aka DNS over HTTPS) client with partial HTTP protocol implemented.

If you need a more powerful DoH client based on [aiohttp](https://docs.aiohttp.org/en/stable/), or a DoH server, consider [async-doh](https://github.com/gera2ld/async-doh).

## Test

``` sh
$ python3 -m unittest

# Or with tox
$ tox -e py
```

## References

- <https://tools.ietf.org/html/rfc1034>
- <https://tools.ietf.org/html/rfc1035>
- <https://tools.ietf.org/html/rfc2915> NAPTR
