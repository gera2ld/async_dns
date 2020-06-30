import sys
import random
from .address import Address

__all__ = [
    'NameServers',
]

class RandMixIn:
    def get(self):
        if not self.data: return
        return random.choice(self.data)

    def success(self, item):
        pass

    def fail(self, item):
        pass

if sys.version_info > (3, 6):
    class WeightMixIn:
        def __init__(self, *k, init_score=128, min_score=1, max_score=8192, **kw):
            self.init_score = init_score
            self.min_score = min_score
            self.max_score = max_score
            self.weights = [init_score] * len(self.data)

        def success(self, item):
            index = self.data.index(item)
            self.weights[index] = min(self.weights[index] * 2, self.max_score)

        def fail(self, item):
            index = self.data.index(item)
            self.weights[index] = max(self.weights[index] // 2, self.min_score)

        def get(self):
            if not self.data: return
            return random.choices(self.data, weights=self.weights)[0]
else:
    class WeightMixIn:
        pass

class NameServers(WeightMixIn, RandMixIn):
    def __init__(self, nameservers=[], **kw):
        self.data = [Address.parse(item, default_port=53, default_protocol='udp') for item in nameservers]
        super().__init__(**kw)

    def __bool__(self):
        return len(self.data) > 0

    def __iter__(self):
        return iter(self.data)

    def __repr__(self):
        return '<NameServers [%s]>' % ','.join(map(str, self.data))
