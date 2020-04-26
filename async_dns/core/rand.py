import random

class RandId:
    def __init__(self, start=0, stop=65535):
        self.data = [(start, stop)]

    def get(self):
        index = random.randrange(len(self.data))
        rng = self.data[index]
        id = random.randrange(rng[0], rng[1] + 1)
        rngs = []
        if id > rng[0]:
            rngs.append((rng[0], id - 1))
        if id < rng[1]:
            rngs.append((id + 1, rng[1]))
        self.data[index : index + 1] = rngs
        return id

    def put(self, value):
        size = len(self.data)
        for index, rng in enumerate(self.data):
            if value < rng[0]: break
        else:
            index = size
        last_rng = self.data[index - 1] if index > 0 else None
        next_rng = self.data[index] if index < size else None
        if last_rng is not None and last_rng[1] == value - 1:
            last_rng = last_rng[0], value
        if next_rng is not None and next_rng[0] == value + 1:
            next_rng = value, next_rng[1]
        if last_rng is not None and next_rng is not None and last_rng[1] == next_rng[0]:
            last_rng = last_rng[0], next_rng[1]
            next_rng = None
        rngs = []
        if last_rng is not None:
            rngs.append(last_rng)
        if (last_rng is None or last_rng[1] < value) and (next_rng is None or value < next_rng[0]):
            rngs.append((value, value))
        if next_rng is not None:
            rngs.append(next_rng)
        start = max(0, index - 1)
        end = min(index + 1, size)
        self.data[start : end] = rngs
