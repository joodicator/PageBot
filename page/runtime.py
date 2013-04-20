import time
import util
from untwisted.event import TICK
from untwisted.magic import sign

link = util.LinkSet()

mode = None
sleepers = list()

def install(a_mode):
    global mode
    assert mode == None
    mode = a_mode
    link.install(mode)

def uninstall(a_mode):
    global mode
    link.uninstall(mode)
    mode = None

def sleep(delta):
    return util.mmcall(mode, 'runtime.sleep', time.time() + delta)

@link('runtime.sleep')
def h_sleep(until):
    sleepers.append(until)
    sleepers.sort()

@link(TICK)
def h_tick(bot):
    while len(sleepers):
        if sleepers[0] > time.time(): break
        yield sign(('runtime.sleep', sleepers.pop(0)), None)
