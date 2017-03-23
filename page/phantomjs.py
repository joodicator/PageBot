#===============================================================================
# Provides pools of cached reusable Selenium PhantomJS web drivers, to reduce
# the cost of repeatedly creating and destroying driver instances.
#
# Usage (with the shared global pool):
#
#   with phantomjs.pool.get_driver() as driver:
#       ...
#
# or (with a private locally isolated pool):
#
#   pool = phantomjs.DriverPool()
#   ...
#   with pool.get_driver() as driver:
#       ...

from __future__ import print_function

import threading
import weakref
import time
import sys
import re

import selenium.common.exceptions
import selenium.webdriver

DEFAULT_WINDOW_SIZE = 1600, 1200
DEFAULT_DRIVER_CACHE_S = 60

class Driver(selenium.webdriver.PhantomJS):
    __slots__ = 'pool'
    def __init__(self, pool, *args, **kwds):
        super(Driver, self).__init__(*args, **kwds)
        self.set_window_size(*DEFAULT_WINDOW_SIZE)
        self.pool = pool
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.pool.release_driver(self)
    def log(self, action):
        print('*** Driver %x in pool %x %s.' % (
            id(self), id(self.pool), action))

class DriverPool(object):
    __slots__ = ('drivers', 'rlock', 'remove_driver_cond', 'destroyed',
                 'driver_cache_s', 'debug', '__weakref__')

    def __init__(self, driver_cache_s=DEFAULT_DRIVER_CACHE_S, debug=False):
        self.drivers = []
        self.rlock = threading.RLock()
        self.remove_driver_cond = threading.Condition(self.rlock)
        self.destroyed = False
        self.driver_cache_s = driver_cache_s
        self.debug = debug

        threading.Thread(
            name='DriverPool.run_pool(%r)' % self,
            target=self.run_pool,
            args=(threading.current_thread(),)
        ).start()

    def get_driver(self):
        driver = None
        with self.rlock:
            if self.destroyed: raise Exception(
                'This driver pool has been destroyed and is unusable.')
            if len(self.drivers):
                driver = self.drivers.pop(0)
                self.remove_driver_cond.notify_all()
                if self.debug: driver.log('removed')
            else:
                driver = Driver(self)
                if self.debug: driver.log('created and removed')
        return driver

    def release_driver(self, driver):
        with self.rlock:
            if self.destroyed: return
            if self.debug: driver.log('returned')
            self.drivers.append(driver)
            threading.Thread(
                name='DriverPool.destroy_driver(%r)' % driver,
                target=self.destroy_driver,
                args=(driver,)
            ).start()

    def destroy_driver(self, driver):
        start = time.time()
        remain = self.driver_cache_s
        with self.rlock:
            remove_driver_cond = self.remove_driver_cond
            while remain > 0:
                if driver not in self.drivers: return
                if self.destroyed: break
                remain = self.driver_cache_s - (time.time() - start)
                self, driver = weakref.ref(self), weakref.ref(driver)
                remove_driver_cond.wait(remain)
                self, driver = self(), driver()
                if self is None or driver is None: break
            if self is not None and driver is not None:
                self.drivers.remove(driver)
        if driver is not None:
            if self.debug: driver.log('destroyed')
            driver.quit()

    def run_pool(self, parent_thread):
        self = weakref.ref(self)
        parent_thread.join()
        self = self()
        if self is None: return
        with self.rlock:
            if self.debug: print(
                '*** Driver pool %x destroyed.' % id(self),
                file=sys.stderr)
            self.destroyed = True
            self.remove_driver_cond.notify_all()

pool = DriverPool(debug='--debug' in sys.argv[1:])
