from select import select
from event import *

class Gear(object):
    def __init__(self, timeout=None):
        self.timeout = timeout

        self.rlist = []
        self.wlist = []
        self.xlist = []

        self.tick_list = []

        self.SIZE = 1024

 
    def mainloop(self):
        while True:
            self.update()

    def update(self):
        r, w, x = [], [], []

        rmap = lambda obj: obj.is_read
        wmap = lambda obj: obj.is_write or obj.queue
        xmap = lambda obj: obj.is_write and obj.is_read
        
        r = filter(rmap, self.rlist)
        w = filter(wmap, self.wlist)
        x = filter(xmap, self.xlist)

        resource = select(r , w , x, self.timeout)

        self.rsock, self.wsock, self.xsock = resource

        self.process_rsock()
        self.process_wsock()
        self.process_xsock()

        for ind in self.tick_list:
            ind.poll.drive(TICK, ind)

        import time
        time.sleep(0.1)

    def process_rsock(self):
        for ind in self.rsock:
            ind.poll.drive(READ, ind)

    def process_wsock(self):
        for ind in self.wsock:
            ind.poll.drive(WRITE, ind)

    def process_xsock(self):
        for ind in self.xsock:
            ind.poll.drive(EXC, ind)

#it instantiates the reactor
#this variable is exposed to the
#other modules
gear = Gear(1.0)
