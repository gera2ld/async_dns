# aiodnsresolver

Asyncio Python DNS resolver: to resolve the A or AAAA record of a domain name. Only Python, with no dependencies or threads.

----

This is an unfinished work in progress. This README is a rough design spec.


## Installation

```bash
pip install aiodnsresolver
```


## Usage

```python
from aiodnsresolver import Resolver, types

resolve = Resolver()
ip_address = resolve('www.google.com', types.A)
```
