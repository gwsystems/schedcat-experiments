from __future__ import division, absolute_import

import time
import resource

def get_exec_time():
    """Get execution time in seconds."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime

class Timer(object):
    """Base class for timers that can (optionally)
       wrap a function report times on a function call basis.
    """
    def __init__(self, clock_func, delegate=None):
        self.reset()
        self.clock    = clock_func
        self.delegate = delegate

    def __call__(self, *args, **kargs):
        self.start()
        x = self.delegate(*args, **kargs)
        self.stop()
        return x

    def reset(self):
        self.count    = 0
        self.max      = 0
        self.elapsed  = 0

    def start(self):
        self.start_time = self.clock()

    def stop(self):
        stop  = self.clock()
        delta = stop - self.start_time
        del self.start_time
        self.elapsed += delta
        self.count += 1
        self.max = max(self.max, delta)

    def seconds(self):
        return self.elapsed

    def seconds_avg(self):
        return self.seconds() / (self.count if self.count else 1)

    def seconds_max(self):
        return self.max


def exec_timer(f=None):
    return Timer(get_exec_time, f)

def clock_timer(f=None):
    return Timer(time.clock, f)

def wc_timer(f=None):
    return Timer(time.time, f)

