pydns
===

Requirements: Python 3.5+ (`asyncio` is required)

Installation
---
``` sh
$ pip3 install git+https://github.com/gera2ld/pydns.git
```

Usage
---
``` sh
# Using a synchronous resolver
$ python3 -m pydns.resolver www.google.com

# Query via TCP
$ python3 -m pydns.resolver -n 127.0.0.1 -p TCP www.google.com

# Start a DNS server
$ python3 -m pydns.server

# Start a DNS server with arguments:
$ python3 -m pydns.server -b :53 --hosts /etc/hosts
```

Test
---
``` sh
$ python3 -m test
```
