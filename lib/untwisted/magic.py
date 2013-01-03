from misc import xmap, ymap

class sign(object):
    def __call__(self, mod, seq):
        mod.drive(self.event, *self.args)

    def __init__(self, event, *args):
        self.event = event
        self.args = args

class hold(object):
    def __call__(self, mod, seq):
        self.mod = mod
        self.seq = seq

        for ind in self.event_list:
            xmap(self.obj, ind, self.back, ind)

        raise StopIteration

    def __init__(self, obj, *event_list):
        self.obj = obj
        self.event_list = event_list

    def back(self, *args):
        try:
            while True:
                point = self.seq.send((args[-1], args[:-1]))
                if point is self:
                    break
                else:
                    point(self.mod, self.seq)
        except Exception as e:
            for ind in self.event_list:
                ymap(self.obj, ind, self.back)
            raise
