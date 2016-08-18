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
# Resolve an IP
$ python3 -m pydns.resolver www.google.com

# Query via TCP
$ python3 -m pydns.resolver -n 127.0.0.1 -p tcp www.google.com

# Start a DNS server on :53 via TCP
$ python3 -m pydns.server -b :53 -p tcp --hosts /etc/hosts

# Start a DNS server over TCP proxy
$ python3 -m pydns.server -P 8.8.8.8 -p tcp
```

Test
---
``` sh
$ python3 -m unittest
```
