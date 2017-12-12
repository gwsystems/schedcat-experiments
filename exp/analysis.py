from __future__ import division
import copy
import random

from schedcat.model.tasks import SporadicTask, TaskSystem
import schedcat.locking.bounds as bounds
import schedcat.sched.fp as fp

from overhead import *

def dbg_human_print(taskset, max_cpu):    
    for cpuid in range(0, int(max_cpu)):
        print "------------------------------------------"
        print "--------------- [ CPU #%d ] ---------------" % cpuid
        print "------------------------------------------"
        
        U = 0
        for id,t in enumerate(taskset):
            if(t.partition==cpuid):
                U = U + (t.cost/float(t.period))
                print '### TASK ', id, '###'
		tsk = [(key,value) for key, value in t.__dict__.items() if key not in ['resmodel']]
		print tsk   
		for r in t.resmodel:
		    print r, t.resmodel[r].__dict__
        
    print "------------------------------------------"
    print "------------------------------------------"

def iter_partitions_ts(taskset):
    """ Generate a Taskset for every partition. """
    partitions = {}
    for t in taskset:
        if t.partition not in partitions:
            partitions[t.partition] = []
        partitions[t.partition].append(t)
    for p in partitions.itervalues():
        yield TaskSystem(p)
        
def fp_schedulable_without_qui(taskset):
    for ts in iter_partitions_ts(taskset):
        if not fp.is_schedulable(1, ts):
#            dbg_human_print(ts, 1)
            return False
    return True
	
def response_times_consistent(tasks):
	for t in tasks:
		if t.response_time != t.response_old:
			return False
	return True
	
def no_blocking_test(taskset_in, oh, conf):
	mem = 0
	ts = copy.deepcopy(taskset_in)
	for t in ts:
		t.response_time = t.cost
	if fp_schedulable_without_qui(ts): return (1, mem)
	else: return (0, mem)
	
def spinlock_naive_test(taskset_in, oh, conf):
	mem = 0
	ts = copy.deepcopy(taskset_in)
	charge_spinlock_overheads(oh, ts, conf)
	for t in ts:
		t.uninflated_cost = t.cost
		t.response_time = t.cost
		t.response_old = 0

	while not response_times_consistent(ts):
		for t in ts:
		    t.cost = t.uninflated_cost
		    if t.response_time < t.response_old:
		    	print "[fp_test] Response times not monotonic! PID=%d" % os.getpid()
		    	assert(False)
		    t.response_old = t.response_time
		bounds.apply_task_fair_mutex_bounds(ts, 1, pi_aware=True)
		if not fp_schedulable_without_qui(ts): 
			return (0, mem)	
	return (1, mem)

def spinlock_ilp_test(taskset_in, oh, conf, oh_scale=1):
	mem = 0
	ts = copy.deepcopy(taskset_in)
	charge_spinlock_overheads(oh, ts, conf, oh_scale)
	# response-time and blocking initialization
	for t in ts:
		t.uninflated_cost = t.cost
		t.response_old = 0
		t.response_time = t.cost
		t.blocked = 0

	while not response_times_consistent(ts):
		for t in ts:
		    t.cost = t.uninflated_cost
		    if t.response_time < t.response_old:
		    	print "[fp_test] Response times not monotonic! PID=%d" % os.getpid()
		    	assert(False)
		    t.response_old = t.response_time
		bounds.apply_pfp_lp_msrp_bounds(ts)
#                dbg_human_print(ts, int(conf.num_cpus))
		if not fp_schedulable_without_qui(ts):
			return (0, mem, None)

	return (1, mem, ts)
	
def pfrwlock_test(taskset_in, oh, conf, oh_scale=1):
	mem = 0
	ts = copy.deepcopy(taskset_in)
	charge_pfrwlock_overheads(oh, ts, conf, oh_scale)
	for t in ts:
		t.response_old = 0
		t.uninflated_cost = t.cost
		t.response_time = t.cost

	while not response_times_consistent(ts):
		for t in ts:
		    t.cost = t.uninflated_cost
		    if t.response_time < t.response_old:
		    	print "[fp_test] Response times not monotonic! PID=%d" % os.getpid()
		    	assert(False)
		    t.response_old = t.response_time
		bounds.apply_phase_fair_rw_bounds(ts, 1, pi_aware=True)
		for t in ts:
		    if 'prio_inversion' in t.__dict__ and 'mc_type' in t.__dict__:
		        t.prio_inversion = 0
		if not fp_schedulable_without_qui(ts):
			return (0, mem, None)
	return (1, mem, ts)

class Quiescence(object):
    def __init__(self, arpha = 0, beta = 0, mem = 0):
        self.arpha_cost = arpha
        self.beta_cost = beta
        self.num_mem = mem
        self.period = 0
        self.priority = float("inf")
        self.core = -1
