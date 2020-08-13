# async_dns

[![PyPI](https://img.shields.io/pypi/v/async_dns.svg)]()

Asynchronous DNS server and client built with pure Python.

Requirements: Python >=3.6

## Installation

``` sh
$ pip3 install async_dns
# or
$ pip3 install git+https://github.com/gera2ld/async_dns.git
```

## CLI

### Resolver
```
usage: python3 -m async_dns.resolver [-h] [-n NAMESERVERS [NAMESERVERS ...]] [-t TYPES [TYPES ...]]
                                     hostnames [hostnames ...]

Async DNS resolver

positional arguments:
  hostnames             the hostnames to query

optional arguments:
  -h, --help            show this help message and exit
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
$ python3 -m async_dns.resolver -n tcp://127.0.0.1 www.google.com

# Query from non-standard ports
$ python3 -m async_dns.resolver -n udp://127.0.0.1:1053 www.google.com
```

### Server
```
usage: python3 -m async_dns.server [-h] [-b BIND] [--hosts HOSTS] [-x [PROXY [PROXY ...]]]

DNS server by Gerald.

optional arguments:
  -h, --help            show this help message and exit
  -b BIND, --bind BIND  the address for the server to bind
  --hosts HOSTS         the path of a hosts file, `none` to disable hosts, `local` to read from
                        local hosts file
  -x [PROXY [PROXY ...]], --proxy [PROXY [PROXY ...]]
                        the proxy DNS servers, `none` to serve as a recursive server, `default` to
                        proxy to default nameservers
```

Examples:
``` sh
# Start a DNS proxy server on :53
$ python3 -m async_dns.server -b :53 --hosts /etc/hosts

# Start a DNS server over TCP proxy
$ python3 -m async_dns.server -x tcp://114.114.114.114

# Start a DNS recursive server
$ python3 -m async_dns.server -x none
```

## API

``` python
import asyncio
from async_dns import types
from async_dns.resolver import ProxyResolver

resolver = ProxyResolver()
res = asyncio.run(resolver.query('www.baidu.com', types.A))
print(res)
```

### Routing

ProxyResolver supports routing based on domains:

```python
resolver = ProxyResolver(proxies=[
    ('*.lan', ['192.168.1.1']),                             # query 'udp://192.168.1.1:53' for '*.lan' domains
    (lambda d: d.endswith('.local'), ['tcp://127.0.0.1']),  # query tcp://127.0.0.1:53 for domains ending with '.local'
    '8.8.8.8',                                              # equivalent to (None, ['8.8.8.8']), matches all others
])
```

### Queries

Both `resolver.query(fqdn, qtype=ANY, timeout=3.0, tick=5)` and `resolver.query_safe(fqdn, qtype=ANY, timeout=3.0, tick=5)` do queries for domain names. The only difference is that `query_safe` returns `None` if there is an exception, while `query` always raises the exception.

## DoH support

DoH (aka DNS over HTTPS) is supported via [async-doh](https://github.com/gera2ld/async-doh), go there for more details.

## Test

``` sh
$ python3 -m unittest
```
