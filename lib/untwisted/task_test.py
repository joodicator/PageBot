from network import *
from task import *

def call(data, number):
    print(data, number)


gear = Gear()
sched = Schedule(gear)
sched.mark(2, call, 'tau', number=32)
gear.mainloop()
