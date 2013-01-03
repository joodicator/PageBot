import time

class Schedule(object):
    def __init__(self, gear):
        self.gear = gear
        self.gear.pool.append(self)
        self.web = dict()

    def mark(self, timeout, callback, *args, **kwargs):
        start = time.time()
        self.web[timeout, callback] = [start,
                                       args, 
                                       kwargs]
        
    def unmark(self, timeout, callback):
        del self.web[timeout, callback]

    def update(self):
        for timeout, callback in self.web.keys():
            start, args, kwargs = self.web[timeout, callback]
            if time.time() - start >= timeout: 
                callback(*args, **kwargs)
                start = time.time()
                self.web[timeout, callback][0] = start

