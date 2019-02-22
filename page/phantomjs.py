#===============================================================================
# Provides pools of cached reusable Selenium PhantomJS web drivers, to reduce
# the cost of repeatedly creating and destroying driver instances.
#
# Usage:
#
#   with phantomjs.pool.get_driver() as driver:
#       ...

from __future__ import print_function

import threading
import traceback
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
    def destroy(self):
        if self.pool is not None:
            try:
                self.quit()
            except:
                traceback.print_exc()
            if self.pool.debug: self.log('destroyed')
            self.pool = None
    def log(self, action):
        print('*** Driver %x in pool %x %s.' % (id(self), id(self.pool), action))

class DriverPool(object):
    __slots__ = ('drivers', 'removed_drivers', 'rlock', 'remove_driver_cond',
                 'destroyed', 'driver_cache_s', 'debug', 'parent_thread',
                 '__weakref__')

    def __init__(self, driver_cache_s=DEFAULT_DRIVER_CACHE_S, debug=False):
        self.drivers = []
        self.removed_drivers = []
        self.rlock = threading.RLock()
        self.remove_driver_cond = threading.Condition(self.rlock)
        self.destroyed = False
        self.driver_cache_s = driver_cache_s
        self.debug = debug
        self.parent_thread = threading.current_thread()

        if not hasattr(self.parent_thread, 'phantomjs_lock'):
            self.parent_thread.phantomjs_lock = threading.Lock()
            self.parent_thread.phantomjs_pools = []
            threading.Thread(
                name   = 'DriverPool.run_parent(%r)' % self.parent_thread,
                target = self.run_parent,
                args   = (self.parent_thread,)
            ).start()

        with self.parent_thread.phantomjs_lock:
            self.parent_thread.phantomjs_pools.append(weakref.ref(self))

        if self.debug: print(
            '*** Driver pool %x created.' % id(self), file=sys.stderr)

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
        self.removed_drivers.append(weakref.ref(driver))
        return driver

    def release_driver(self, driver):
        with self.rlock:
            if self.destroyed: return
            if self.debug: driver.log('returned')
            self.removed_drivers.remove(driver.__weakref__)
            self.drivers.append(driver)
            driver.get('about:blank')
            driver.delete_all_cookies()
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
                if self is None or driver is None or time is None: break
            if self is not None and driver is not None:
                self.drivers.remove(driver)
        if driver is not None:
                driver.destroy()

    def __del__(self):
        with self.rlock:
            if self.destroyed: return
            with self.parent_thread.phantomjs_lock:
                for weak_driver in list(self.parent_thread.phantomjs_pools):
                    if weak_driver() == self:
                        self.parent_thread.phantomjs_pools.remove(weak_driver)
            self.destroyed = True
            self.remove_driver_cond.notify_all()

            for weak_driver in list(self.removed_drivers):
                driver = weak_driver()
                if driver is None: continue
                driver.destroy()
                
            if self.debug: print(
                '*** Driver pool %x destroyed.' % id(self), file=sys.stderr)

    @staticmethod
    def run_parent(parent_thread):
        parent_thread.join()
        with parent_thread.phantomjs_lock:
            pools = list(parent_thread.phantomjs_pools)
        for pool in pools:
            pool = pool()
            if pool is None: continue
            pool.__del__()

pool = DriverPool(debug = '--debug' in sys.argv)
