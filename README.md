async_dns
===
[![PyPI](https://img.shields.io/pypi/v/async_dns.svg)]()

Asynchronous DNS server and client built with pure Python.

Requirements: Python 3.5+ (`asyncio` is required).

Installation
---
``` sh
$ pip3 install async_dns
# or
$ pip3 install git+https://github.com/gera2ld/async_dns.git
```

Usage
---
``` sh
# Resolve an IP
$ python3 -m async_dns.resolver www.google.com

# Query via TCP
$ python3 -m async_dns.resolver -n 127.0.0.1 -p tcp www.google.com

# Start a DNS server on :53 via TCP
$ python3 -m async_dns.server -b :53 -p tcp --hosts /etc/hosts

# Start a DNS server over TCP proxy
$ python3 -m async_dns.server -P 8.8.8.8 -p tcp
```

API
---
``` python
import asyncio
from async_dns import types
from async_dns.resolver import ProxyResolver

loop = asyncio.get_event_loop()
resolver = ProxyResolver()
res = loop.run_until_complete(resolver.query('www.baidu.com', types.A))
print(res)
```

Test
---
``` sh
$ python3 -m unittest
```
