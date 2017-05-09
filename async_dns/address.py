from collections import deque
from . import types

class InvalidHost(Exception):
    pass

class Address:
    def __init__(self, hostname, port=0, allow_domain=False):
        self.parse(hostname, port, allow_domain)

    def __eq__(self, other):
        return self.host == other.host and self.port == other.port

    def __repr__(self):
        return self.to_str()

    def parse(self, hostname, port=0, allow_domain=False):
        if isinstance(hostname, tuple):
            self.parse_tuple(hostname, allow_domain)
        elif isinstance(hostname, Address):
            self.parse_address(hostname)
        elif hostname.count(':') > 1:
            self.parse_ipv6(hostname, port)
        else:
            self.parse_ipv4_or_domain(hostname, port, allow_domain)

    def parse_tuple(self, addr, allow_domain=False):
        host, port = addr
        self.parse(host, port, allow_domain)

    def parse_address(self, addr):
        self.host, self.port, self.ip_type = addr.host, addr.port, addr.ip_type

    def parse_ipv4_or_domain(self, hostname, port=None, allow_domain=False):
        host, _, port_s = hostname.partition(':')
        if _: port = int(port_s)
        try:
            parts = host.split('.')
            assert len(parts) == 4
            for part in parts:
                assert 0 <= int(part) <= 0xff
        except AssertionError:
            if allow_domain:
                self.host, self.port, self.ip_type = host, port, None
                return
            else:
                raise InvalidHost(host)
        self.host, self.port, self.ip_type = host, port, types.A

    def parse_ipv6(self, hostname, port=None):
        if hostname.startswith('['):
            i = hostname.index(']')
            host = hostname[1 : i]
            port_s = hostname[i + 1 :]
            if port_s:
                assert port_s.startswith(':')
                port = int(port_s[1:])
        else:
            host = hostname
        parts = host.split(':')
        if '.' in parts[-1]:
            self.parse_ipv4(parts.pop())
            assert 2 <= len(parts) <= 6
        else:
            assert 3 <= len(parts) <= 8
        for part in parts:
            assert not part or 0 < int(part, 16) < 0xffff
        self.host, self.port, self.ip_type = host, port, types.AAAA

    def to_str(self, default_port = 0):
        if default_port is None or self.port == default_port:
            return self.host
        if self.ip_type is types.A:
            return '%s:%d' % self.to_addr()
        elif self.ip_type is types.AAAA:
            return '[%s]:%d' % self.to_addr()

    def to_addr(self):
        return self.host, self.port

class NameServers:
    def __init__(self, nameservers=None, default_port=53):
        self.default_port = default_port
        self.data = deque()
        if nameservers:
            for nameserver in nameservers:
                self.data.append(Address(nameserver, default_port))

    def __bool__(self):
        return len(self.data) > 0

    def __iter__(self):
        return iter(tuple(self.data))

    def __repr__(self):
        return '<NameServers [%s]>' % ','.join(map(str, self.data))

    def fail(self, addr):
        self.data.append(self.data.popleft())

    def add(self, addr):
        self.data.append(Address(addr, self.default_port))
