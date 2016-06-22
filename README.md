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

# Start a DNS server on :53 via TCP
$ python3 -m pydns.server -b :53 -p TCP --hosts /etc/hosts

# Start a DNS server over TCP proxy
$ python3 -m pydns.server -P 8.8.8.8 -p TCP
```

Test
---
``` sh
$ python3 -m test
```
