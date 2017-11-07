from  __future__ import absolute_import

import random

from .git import path_to_repository

def save_state(fname):
    """Store the current PRNG state to 'fname'."""
    f = open(fname, 'w')
    s = random.getstate()
    f.write(repr(s))
    f.close()

def load_state(fname):
    """Set the current PRNG state to the state read from 'fname'."""
    f = open(fname, 'r')
    s = eval(f.readline())
    f.close()
    random.setstate(s)

def load_std_state():
    """For repeatability, it may be beneficial to start from
    a known 'standard' PRNG state."""
    load_random_state(path_to_repository() + '/data/random.conf')
