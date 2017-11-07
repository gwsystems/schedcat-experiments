# A cache of confidence intervals for schedulability results.
# Caching confidence intervals is possible because all samples are either 0 or 1,
# so only the number of schedulable task sets and the total number of schedulable
# task sets affect the confidence value (of the mean).

import fcntl
import os
import sys
import pickle

from toolbox.stats import mean
import toolbox.bootstrap as boot
import toolbox.git as git

confidence_interval_cache = {}

def confidence_interval(sample):
    num_schedulable = sum(sample)
    total_tasksets  = len(sample)
    key = (num_schedulable, total_tasksets)
    if not key in confidence_interval_cache:
        ci = boot.confidence_interval(sample, stat=mean, iterations=10000)
        confidence_interval_cache[key] = ci
    return confidence_interval_cache[key]


CACHE_FNAME = ".sci_cache.bin"
DEFAULT_CACHE = os.path.join(git.path_to_repository(), CACHE_FNAME)

def lock(fname):
    f = open(fname + '.lck', 'a')
    fcntl.lockf(f, fcntl.LOCK_EX)
    return f

def unlock(file):
    fcntl.lockf(file, fcntl.LOCK_UN)
    file.close()

def load_object(fname):
    try:
        f = open(fname, 'r')
        cache = pickle.load(f)
        f.close()
    except Exception as err:
        print >> sys.stderr, "[!!] sci_cache.load_object: %s" % err
        cache = None
    return cache

def save_object(fname, obj):
    try:
        f = open(fname, 'w')
        cache = pickle.dump(obj, f)
        f.close()
    except Exception as err:
        print >> sys.stderr, "[!!] sci_cache.save_object: %s" % err
        cache = None

def load_cache(fname = DEFAULT_CACHE):
    global confidence_interval_cache
    if os.path.exists(fname):
        lck = lock(fname)
        confidence_interval_cache = load_object(fname)
        if not confidence_interval_cache:
            confidence_interval_cache = {}
        unlock(lck)

def save_cache(fname = DEFAULT_CACHE):
    global confidence_interval_cache

    lck = lock(fname)

    existing = None
    if os.path.exists(fname):
        existing = load_object(fname)

    if not existing:
        existing = {}

    confidence_interval_cache.update(existing)

    save_object(fname, confidence_interval_cache)

    unlock(lck)

def populate_cache(samples, fname = DEFAULT_CACHE):
    load_cache(fname)
    for i in xrange(samples + 1):
        vals = [0] * i  + [1] * (samples - i)
        assert len(vals) == samples
        print i, '->', mean(vals), confidence_interval(vals)
    save_cache(fname)

