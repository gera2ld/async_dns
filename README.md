pydns
===

Requirements: Python 3.4+ (`asyncio` is required)

Usage
---
* Using a synchronous resolver (foo.py)
``` python
from pydns import resolver
# get a DNSMessage object
print(resolver.query('gerald.top'))
# get an IP address
print(resolver.query_ip('gerald.top'))
```

* Start a DNS server (type in shell)
``` bash
$ python3 -m pydns.server
# or with arguments:
$ python3 -m pydns.server -b 0.0.0.0:53 -c /etc/hosts
```
