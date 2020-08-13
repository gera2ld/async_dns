import sys
import time
import random
from .address import Address

__all__ = [
    'NameServers',
    'NoNameServer',
]

class NoNameServer(Exception):
    pass

class IterMixIn:
    def iter(self):
        if not self.data: raise NoNameServer
        return iter(self.data)

    def success(self, item):
        pass

    def fail(self, item):
        pass

class WeightMixIn:
    def __init__(self, *k, **kw):
        self._failures = [0] * len(self.data)
        self.ts = 0
        self._update()

    def _update(self):
        if time.time() > self.ts + 60:
            self.ts = time.time()
            self._sorted = list(self.data[i] for i in sorted(range(len(self.data)), key=lambda i: self._failures[i]))
            self._last_min_failures = self._failures
            self._failures = [0] * len(self.data)

    def success(self, item):
        self._update()

    def fail(self, item):
        self._update()
        index = self.data.index(item)
        self._failures[index] += 1

    def iter(self):
        if not self.data: raise NoNameServer
        return iter(self._sorted)

class NameServers(WeightMixIn, IterMixIn):
    def __init__(self, nameservers=[], **kw):
        self.data = [Address.parse(item, default_protocol='udp', allow_domain=True) for item in nameservers]
        super().__init__(**kw)

    def __bool__(self):
        return len(self.data) > 0

    def __iter__(self):
        return iter(self.data)

    def __repr__(self):
        return '<NameServers [%s]>' % ','.join(map(str, self.data))
