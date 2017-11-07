from __future__ import division
from __future__ import absolute_import

import random

import numpy as np
from scipy.stats import scoreatpercentile

import toolbox.stats as stats

def bootstrap(samples, stat=stats.mean, iterations=1000):
    collected = []

    for _  in xrange(iterations):
        resample = [random.choice(samples) for _ in samples]
        collected.append(stat(resample))

    return  np.array(collected)

def confidence_interval(samples, stat=stats.mean, iterations=1000, level=0.95):
    observed = bootstrap(samples, stat, iterations)

    perc = (1 - level) / 2

    lower = scoreatpercentile(observed, perc * 100)
    upper = scoreatpercentile(observed, (1 - perc) * 100)

    return (lower, upper)
