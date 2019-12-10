import random

class RandId:
    def __init__(self, start=0, stop=65535):
        self.start = start
        self.stop = stop
        self.range = stop - start + 1
        self.data = []

    def get(self):
        size = len(self.data)
        if size > 0:
            index = random.randrange(size)
            retry = 0
            while retry < 10:
                start = self.data[index + retry] + 1
                end = self.data[(index + retry + 1) % size]
                if (start + 1) % size != end: break
                retry += 1
            else:
                raise ValueError('No available number')
            if end < start:
                end += self.range
        else:
            index = -1
            start = 0
            end = self.range
        offset = random.randrange(start, end) % self.range
        self.data.insert(0 if offset < start else index + 1, offset)
        return self.start + offset

    def put(self, value):
        offset = value - self.start
        try:
            self.data.remove(offset)
        except ValueError:
            pass
