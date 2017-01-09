from collections import deque
from . import types

class InvalidHost(Exception):
    pass

class Address:
    def __init__(self, host, port = 0, allow_domain = False):
        if isinstance(host, tuple):
            host, port = host
        elif isinstance(host, Address):
            host, port = host.hostname, host.port
        for try_parse, ip_type in [
            (self.try_parse_ipv4, types.A),
            (self.try_parse_ipv6, types.AAAA),
        ]:
            try:
                hostname, port = try_parse(host, port)
            except:
                pass
            else:
                self.hostname = hostname
                self.port = port
                self.ip_type = ip_type
                break
        else:
            if allow_domain:
                self.hostname = host
                self.port = port
                self.ip_type = None
            else:
                raise InvalidHost(host)

    def __eq__(self, other):
        return self.hostname == other.hostname and self.port == other.port

    def __repr__(self):
        return self.to_str()

    def try_parse_ipv4(self, host, port = None):
        hostname, _, _port = host.partition(':')
        if _: port = int(_port)
        parts = hostname.split('.')
        assert len(parts) == 4
        for part in parts:
            assert 0 <= int(part) <= 0xff
        return hostname, port

    def try_parse_ipv6(self, host, port = None):
        if host.startswith('['):
            i = host.index(']')
            hostname = host[1 : i]
            port = int(host[i + 1 :])
        else:
            hostname = host
        parts = hostname.split(':')
        if '.' in parts[-1]:
            self.try_parse_ipv4(parts.pop())
            assert 2 <= len(parts) <= 6
        else:
            assert 3 <= len(parts) <= 8
        for part in parts:
            assert not part or 0 < int(part, 16) < 0xffff
        return hostname, port

    def to_str(self, default_port = 0):
        if default_port is None or self.port == default_port:
            return self.hostname
        if self.ip_type is types.A:
            return '%s:%d' % self.to_addr()
        elif self.ip_type is types.AAAA:
            return '[%s]:%d' % self.to_addr()

    def to_addr(self):
        return self.hostname, self.port

class NameServers:
    def __init__(self, nameservers = None, default_port = 53):
        self.default_port = default_port
        self.data = deque()
        if nameservers:
            for nameserver in nameservers:
                self.data.append(Address(nameserver, default_port))

    def __bool__(self):
        return len(self.data) > 0

    def __iter__(self):
        return iter(tuple(self.data))

    def fail(self, addr):
        self.data.append(self.data.popleft())

    def add(self, addr):
        self.data.append(Address(addr, self.default_port))
