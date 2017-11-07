#!/usr/bin/python

from __future__ import division

from math import sqrt, floor

def mean(lst):
    "Average of the samples in lst."
    n = len(lst)
    if not n:
        return None
    else:
        return sum(lst) / n

def median(lst, is_sorted=False):
    "Median of the samples in lst."
    sorted_lst = sorted(lst) if not is_sorted else lst
    n = len(sorted_lst)
    if not n:
        return None
    if n % 2 == 1:
        return sorted_lst[n // 2]
    else:
        return (sorted_lst[n // 2] + sorted_lst[n // 2 - 1]) / 2

def stdev(lst, mean=None):
    "Standard deviation of the samples in lst."
    n = len(lst)
    if n <= 1:
        return None
    if mean is None:
        mean = sum(lst) / n
    dev2 = 0.0
    for x in lst:
        dev = mean - x
        dev2 += dev * dev
    return sqrt(dev2 / (n - 1))

def safe_max(lst):
    "Don't raise an exception if lst is empty."
    if lst:
        return max(lst)
    else:
        return None

def stats(lst, is_sorted=False, want_max=False):
    "Returns (mean, median, standard deviation) of the samples in lst."
    _mean = mean(lst)
    if want_max:
        if is_sorted:
            _max = lst[-1] if lst else 0
        else:
            _max = safe_max(lst)
        return (_max,
                _mean, median(lst, is_sorted), stdev(lst, mean=_mean))
    else:
        return (_mean, median(lst, is_sorted), stdev(lst, mean=_mean))

class Histogram(object):
    def __init__(self, vmin, vmax, bins):
        self.underflow = 0
        self.overflow = 0
        self.vmin = vmin
        self.vmax = vmax
        self.bin_size = (vmax - vmin) / bins
        self.bins = [0 for _ in xrange(bins)]

    def __call__(self, val):
        if val < self.vmin:
            self.underflow += 1
        elif val >= self.vmax:
            self.overflow += 1
        else:
            idx = int(floor((val - self.vmin) / self.bin_size))
            self.bins[idx] += 1

    def count(self, val):
        self(val)

    def count_all(self, vals):
        for x in vals:
            self(x)

    def total_count(self):
        return self.underflow + sum(self.bins) + self.overflow

    def sample(self, f, count=100):
        for _ in xrange(count):
            self(f())

    def as_ascii_bars(self, width=80, val_fmt="%.2f", count_fmt ="%d", star="*",
                      relative_counts=False, scaled=True):
        norm  = max(self.bins)
        norm  = max(self.underflow, norm, self.overflow)

        total = self.total_count();

        labels = []
        labels.append(("x < " + val_fmt) % self.vmin)
        for i in xrange(len(self.bins)):
            labels.append((val_fmt + " <= x < " + val_fmt) %
                          (self.vmin + i * self.bin_size,
                           self.vmin + (i + 1) * self.bin_size))
        labels.append((val_fmt + " <= x ") % self.vmax)

        def count(b):
            if relative_counts and total:
                return b / total * 100;
            else:
                return b

        counts = []
        counts.append(count_fmt % count(self.underflow))
        for b in self.bins:
            counts.append(count_fmt % count(b))
        counts.append(count_fmt % count(self.overflow))

        lwidth = max([len(l) for l in labels])
        cwidth = max([len(c) for c in counts])
        lfmt   = "%%-%ds" % lwidth
        cfmt   = ": %%%ds " % cwidth
        fst_fmt  = "%%%ds" % lwidth

        bwidth = max(1, width - lwidth - cwidth - 2)

        def num_stars(b):
            div = norm if scaled else total
            if div:
                return int(round(bwidth * (b / div)))
            else:
                return 0

        bars = []
        bars.append(star * num_stars(self.underflow))
        for b in self.bins:
            bars.append(star * num_stars(b))
        bars.append(star * num_stars(self.overflow))

        rows = [(lfmt % l) + (cfmt % c) + b for (l, c, b)
                in zip(labels[1:], counts[1:], bars[1:])]
        return "\n".join([(fst_fmt % labels[0]) + (cfmt % counts[0]) + bars[0]]
                         + rows)
