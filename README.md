pydns
===

This a DNS server and client library built with pure Python.

Requirements: Python 3.5+ (`asyncio` is required).

Installation
---
``` sh
$ pip3 install git+https://github.com/gera2ld/pydns.git
```

Usage
---
``` sh
# Resolve an IP
$ python3 -m pydns.resolver www.google.com

# Query via TCP
$ python3 -m pydns.resolver -n 127.0.0.1 -p tcp www.google.com

# Start a DNS server on :53 via TCP
$ python3 -m pydns.server -b :53 -p tcp --hosts /etc/hosts

# Start a DNS server over TCP proxy
$ python3 -m pydns.server -P 8.8.8.8 -p tcp
```

API
---
``` python
import asyncio
from pydns import types
from pydns.resolver import AsyncProxyResolver

loop = asyncio.get_event_loop()
resolver = AsyncProxyResolver()
res = loop.run_until_complete(resolver.query('www.baidu.com', types.A))
print(res)
```

Test
---
``` sh
$ python3 -m unittest
```
