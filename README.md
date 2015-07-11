pydns
===

Requirements: Python 3.4.4+ (`asyncio` is required)

Usage
---
``` python
from pydns import client
# get a DNSMessage object
print(client.query('gerald.top'))
# get an IP address
print(client.query_ip('gerald.top'))
```
