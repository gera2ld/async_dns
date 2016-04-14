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

# Start a DNS Server
$ python3 -m pydns.server
# or with arguments:
$ python3 -m pydns.server -b 0.0.0.0:53 --hosts /etc/hosts
```

Test
---
``` sh
$ python3 -m test
```
