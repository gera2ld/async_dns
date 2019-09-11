# async_dns

[![PyPI](https://img.shields.io/pypi/v/async_dns.svg)]()

Asynchronous DNS server and client built with pure Python.

Requirements: Python 3.5+ (`asyncio` is required).

## Installation

``` sh
$ pip3 install async_dns
# or
$ pip3 install git+https://github.com/gera2ld/async_dns.git
```

## CLI

### Resolver
```
usage: python3 -m async_dns.resolver [-h] [-p {udp,tcp}]
                                     [-n NAMESERVERS [NAMESERVERS ...]]
                                     [-t TYPES [TYPES ...]]
                                     hostnames [hostnames ...]

Async DNS resolver

positional arguments:
  hostnames             the hostnames to query

optional arguments:
  -h, --help            show this help message and exit
  -p {udp,tcp}, --protocol {udp,tcp}
                        whether to use TCP protocol as default to query remote
                        servers
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
$ python3 -m async_dns.resolver -n 127.0.0.1 -p tcp www.google.com
```

### Server
```
usage: python3 -m async_dns.server [-h] [-b BIND] [--hosts HOSTS]
                                   [-P PROXY [PROXY ...]] [-p {udp,tcp}]

DNS server by Gerald.

optional arguments:
  -h, --help            show this help message and exit
  -b BIND, --bind BIND  the address for the server to bind
  --hosts HOSTS         the path of a hosts file
  -x PROXY [PROXY ...], --proxy PROXY [PROXY ...]
                        the proxy DNS servers, `none` to serve as a recursive
                        server, `default` to proxy to default nameservers
  -p {udp,tcp}, --protocol {udp,tcp}
                        whether to use TCP protocol as default to query remote
                        servers
```

Examples:
``` sh
# Start a DNS proxy server on :53 via TCP
$ python3 -m async_dns.server -b :53 -p tcp --hosts /etc/hosts

# Start a DNS server over TCP proxy
$ python3 -m async_dns.server -x 8.8.8.8 -p tcp

# Start a DNS recursive server
$ python3 -m async_dns.server -x none
```

## API

``` python
import asyncio
from async_dns import types
from async_dns.resolver import ProxyResolver

loop = asyncio.get_event_loop()
resolver = ProxyResolver()
res = loop.run_until_complete(resolver.query('www.baidu.com', types.A))
print(res)
```

## Test

``` sh
$ python3 -m unittest
```
