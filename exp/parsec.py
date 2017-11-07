from __future__ import division
import copy
import random

from schedcat.model.tasks import SporadicTask, TaskSystem
import schedcat.locking.bounds as bounds
import schedcat.sched.fp as fp

from overhead import *
from analysis import *

def init_smr_taskset(ts):
    for t in ts:
        t.blocked = 0
        t.uninflated_cost = t.cost
        t.response_old = 0
        t.response_time = t.cost
        t.q_blocked = 0
        t.read_response_time = task_max_read_cost(t)
        t.read_response_old = 0

def task_max_read_cost(t):
    r = 0
    for res_id in t.resmodel:
        req = t.resmodel[res_id]
        if req.max_reads and req.max_read_length > r:
            r = req.max_read_length
    return r

def get_highest_writer(ts):
    for i in xrange(len(ts)):
        req = ts[i].resmodel[0]
        if  req.max_writes > 0 and req.max_write_length > 0:
            return ts[i]
    return None

def get_min_qui_period(taskset):
    r = 0
    for ts in iter_partitions_ts(taskset):
        w = get_highest_writer(ts)
        if w != None and w.period > r:
            r = w.period
    return r

def get_max_quic_response(taskset):
    r = 0
    for ts in iter_partitions_ts(taskset):
        w = get_highest_writer(ts)
        if w != None and w.response_time > r:
            r = w.response_time
    return r

def get_max_read_response(ts):
    return max([t.read_response_time for t in ts])

# L^* is upper-bounded by max writer's response time
def get_max_L(ts):
    l = 0
    for t in ts:
        req = t.resmodel[0]
        if req.max_writes and req.max_write_length > 0 and t.response_time > l:
            l = t.response_time
    return l

def read_response_times_consistent(tasks):
	for t in tasks:
		if t.read_response_time != t.read_response_old:
			return False
	return True

def parsec_theta(ts, q):
    return get_max_L(ts) + get_max_read_response(ts) + q.period

def parsec_block(ts):
    return 0

def get_num_mem(ts, time, num):
    r = 0
    for t in ts:
        req = t.resmodel[0]
        if req.max_writes and req.max_write_length > 0:
            r += int(ceil((time + t.response_time)/ t.period))
    return num*r

def get_smr_max_mem(ts, theta, num):
    time = theta + get_max_quic_response(ts)
    return get_num_mem(ts, time, num)

# read section response time analysis
def rta_read_quiescence_aware(task, own_demand, higher_prio_tasks, qui, theta, ts):
    # see if we find a point where the demand is satisfied
    delta = sum([t.cost for t in higher_prio_tasks]) + own_demand
    while delta <= task.deadline:
        demand = own_demand
        for t in higher_prio_tasks:
            demand += t.cost * int(ceil(delta / t.period))
        if task.period > qui.priority:
            demand += qui.arpha_cost * int(ceil(delta / qui.period))
            mem = get_num_mem(ts, theta+delta, qui.num_mem)
            demand += mem*qui.beta_cost
            demand = int(ceil(demand))
        if demand == delta:
            # yep, demand will be met by time
            task.read_response_time = delta
            return True
        else:
            # try again
            delta = demand
    # if we get here, we didn't converge
    task.read_response_time = delta
    return False

def rta_read_calc(task, higher_prio_tasks, qui, theta, taskset):
    own_demand = task_max_read_cost(task)
    if own_demand == 0: return True
    return rta_read_quiescence_aware(task, own_demand, higher_prio_tasks, qui, theta, taskset)

def read_is_schedulable_with_qui(ts, qui, theta, taskset):
    for i, t in enumerate(ts):
        if not rta_read_calc(t, ts[0:i], qui, theta, taskset):
            return False
    return True

def fp_read_schedulable_with_qui(taskset, q, theta):
    for ts in iter_partitions_ts(taskset):
        w = get_highest_writer(ts)
        if w != None:
            q.priority = w.period
        else:
            q.priority = float("inf")
        if not read_is_schedulable_with_qui(ts, q, theta, taskset):
            return False
    return True

# response time analysis
def rta_quiescence_aware(task, own_demand, higher_prio_tasks, qui, theta, ts):
    # see if we find a point where the demand is satisfied
    delta = sum([t.cost for t in higher_prio_tasks]) + own_demand
    while delta <= task.deadline:
        demand = own_demand
        for t in higher_prio_tasks:
            demand += t.cost * int(ceil(delta / t.period))
        if task.period >= qui.priority:
            demand += qui.arpha_cost * int(ceil(delta / qui.period))
            mem = get_num_mem(ts, theta+delta, qui.num_mem)
            demand += mem*qui.beta_cost
            demand = int(ceil(demand))
        if demand == delta:
            # yep, demand will be met by time
            task.response_time = delta
            return True
        else:
            # try again
            delta = demand
    # if we get here, we didn't converge
    task.response_time = delta
    return False

def rta_calc(task, higher_prio_tasks, qui, theta, taskset):
    if 'mc_type' in task.__dict__:
        if task.mc_type == "reader": task.blocked = 0
    own_demand = task.cost + task.blocked + task.q_blocked
    r = rta_quiescence_aware(task, own_demand, higher_prio_tasks, qui, theta, taskset)

    return r

def is_schedulable_with_qui(ts, qui, theta, taskset):
    for i, t in enumerate(ts):
        if not rta_calc(t, ts[0:i], qui, theta, taskset):
            return False
    return True

def fp_schedulable_with_qui(taskset, q, theta, q_block):
    for ts in iter_partitions_ts(taskset):
        w = get_highest_writer(ts)
        if w != None:
            q.priority = w.period
            w.q_blocked = q_block
        else:
            q.priority = float("inf")
        if not is_schedulable_with_qui(ts, q, theta, taskset):
            return False
    return True

def smr_is_schedulable(ts, q, get_theta, get_block):
    init_smr_taskset(ts)
    stop = False

    while not stop:
        old_theta = get_theta(ts, q)
        old_block = get_block(ts)
        while True:
            for t in ts:
                t.cost = t.uninflated_cost
                if t.response_time < t.response_old:
                    print "[fp_test] Response times not monotonic! PID=%d" % os.getpid()
                    assert(False)
                t.response_old = t.response_time
            theta = get_theta(ts, q)
            block = get_block(ts)
            bounds.apply_pfp_lp_smr_msrp_bounds(ts)
#            dbg_human_print(ts, 40)
            if not fp_schedulable_with_qui(ts, q, theta, block):
                return 0
            if response_times_consistent(ts):
                break

        while True:
            for t in ts:
                if t.read_response_time < t.read_response_old:
                    print "[fp_test] Read response times not monotonic! PID=%d" % os.getpid()
                    assert(False)                    
                t.read_response_old = t.read_response_time
            theta = get_theta(ts, q)
            block = get_block(ts)
            if not fp_read_schedulable_with_qui(ts, q, theta):
                return 0
            if read_response_times_consistent(ts):
                break

        stop = response_times_consistent(ts)
        stop = stop and read_response_times_consistent(ts)
        assert stop == True
        if old_theta != get_theta(ts, q) or old_block != get_block(ts):
            stop = False
    return 1

def quiescence_selection_test(ts, qui, max_q, min_q, get_theta, get_block):
    while min_q < max_q:
        qp = int((min_q + max_q)/2)
        qui.period = qp
        r = smr_is_schedulable(ts, qui, get_theta, get_block)
        if r: max_q = qp
        else: min_q = qp + 1
    r = 1
    if r: m = get_smr_max_mem(ts, get_theta(ts, qui), qui.num_mem)
    else: m = 0

    return (r, m, max_q)

def rt_parsec_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_parsec_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.parsec_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    max_q = ts.max_period()
    min_q = get_min_qui_period(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    if not smr_is_schedulable(ts, q, parsec_theta, parsec_block):
        return (0, mem)
    (r, m, qp) = quiescence_selection_test(ts, q, max_q, min_q, parsec_theta, parsec_block)
    return (r, m)

def timed_parsec_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_time_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.time_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    max_q = ts.max_period()
    min_q = get_min_qui_period(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    if not smr_is_schedulable(ts, q, parsec_theta, parsec_block):
        return (0, mem)
    (r, m, qp) = quiescence_selection_test(ts, q, max_q, min_q, parsec_theta, parsec_block)
    return (r, m)

def linear_quiescence_selection(ts, qui, max_q, min_q, get_theta, get_block):
    qp = min_q
    r = 0
    while qp <= max_q:
        qui.period = qp
        r = smr_is_schedulable(ts, qui, get_theta, get_block)
        if r: break;
        else: qp += min_q

    if r: m = get_smr_max_mem(ts, get_theta(ts, qui), qui.num_mem)
    else: m = 0

    return (r, m, qp)

def rt_parsec_test_linear(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_parsec_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.parsec_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    max_q = ts.max_period()
    min_q = get_min_qui_period(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    (r, m, qp) = linear_quiescence_selection(ts, q, max_q, min_q, parsec_theta, parsec_block)
    return (r, m)

def timed_parsec_test_linear(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_time_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.time_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    max_q = ts.max_period()
    min_q = get_min_qui_period(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    (r, m, qp) = linear_quiescence_selection(ts, q, max_q, min_q, parsec_theta, parsec_block)
    return (r, m)

def rt_parsec_taskset_qui_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_parsec_overheads(oh, ts, conf)
    ncores    = int(conf.num_cpus)
    q_arpha_c = oh.parsec_q[ncores]
    q_beta_c  = oh.mem_free[ncores]
    q_mem     = int(conf.num_mem)
    q         = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.period  = int(conf.qui)
    r         = smr_is_schedulable(ts, q, parsec_theta, parsec_block)
    if r: mem = get_smr_max_mem(ts, parsec_theta(ts, q), q.num_mem)
    return (r, mem)

def timed_parsec_taskset_qui_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_time_overheads(oh, ts, conf)
    ncores    = int(conf.num_cpus)
    q_arpha_c = oh.time_q[ncores]
    q_beta_c  = oh.mem_free[ncores]
    q_mem     = int(conf.num_mem)
    q         = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.period  = int(conf.qui)
    r         = smr_is_schedulable(ts, q, parsec_theta, parsec_block)
    if r: mem = get_smr_max_mem(ts, parsec_theta(ts, q), q.num_mem)
    return (r, mem)

def mc_parsec_test_linear(taskset_in, oh, conf, oh_scale=1):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_parsec_overheads_wo_mem(oh, ts, conf, oh_scale)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.parsec_q[ncores]*oh_scale
    q_beta_c = oh.mem_free[ncores]*oh_scale
    q_mem = int(conf.num_mem)
    max_q = ts.max_period()
    min_q = get_min_qui_period(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.period = max_q
    if min_q == 0:
        print "min q", min_q
        init_smr_taskset(ts)
        if fp_schedulable_with_qui(ts, q, 0, 0): return (1, mem, -1, None)
        else: return (0, mem, -1, None)
    (r, m, qp) = linear_quiescence_selection(ts, q, max_q, min_q, parsec_theta, parsec_block)
    return (r, m, qp, ts)





def smr_is_schedulable_wo_ilp(ts, q, get_theta, get_block):
    init_smr_taskset(ts)
    stop = False

    while not stop:
        old_theta = get_theta(ts, q)
        old_block = get_block(ts)
        while True:
            for t in ts:
                t.cost = t.uninflated_cost
                if t.response_time < t.response_old:
                    print "[fp_test] Response times not monotonic! PID=%d" % os.getpid()
                    assert(False)
                t.response_old = t.response_time
            theta = get_theta(ts, q)
            block = get_block(ts)
            bounds.apply_smr_task_fair_mutex_bounds(ts, 1, pi_aware=True)
            if not fp_schedulable_with_qui(ts, q, theta, block):
                return 0
            if response_times_consistent(ts):
                break

        while True:
            for t in ts:
                if t.read_response_time < t.read_response_old:
                    print "[fp_test] Read response times not monotonic! PID=%d" % os.getpid()
                    assert(False)                    
                t.read_response_old = t.read_response_time
            theta = get_theta(ts, q)
            block = get_block(ts)
            if not fp_read_schedulable_with_qui(ts, q, theta):
                return 0
            if read_response_times_consistent(ts):
                break

        stop = response_times_consistent(ts)
        stop = stop and read_response_times_consistent(ts)
        assert stop == True
        if old_theta != get_theta(ts, q) or old_block != get_block(ts):
            stop = False
    return 1

def quiescence_selection_test_wo_ilp(ts, qui, max_q, min_q, get_theta, get_block):
    while min_q < max_q:
        qp = int((min_q + max_q)/2)
        qui.period = qp
        r = smr_is_schedulable_wo_ilp(ts, qui, get_theta, get_block)
        if r: max_q = qp
        else: min_q = qp + 1
    m = get_smr_max_mem(ts, get_theta(ts, qui), qui.num_mem)
    return (1, m, max_q)

def rt_parsec_wo_ilp_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_parsec_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.parsec_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    max_q = ts.max_period()
    min_q = get_min_qui_period(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    if not smr_is_schedulable_wo_ilp(ts, q, parsec_theta, parsec_block):
        return (0, mem)
    (r, m, qp) = quiescence_selection_test_wo_ilp(ts, q, max_q, min_q, parsec_theta, parsec_block)
    return (r, m)

def timed_parsec_wo_ilp_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_time_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.time_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    max_q = ts.max_period()
    min_q = get_min_qui_period(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    if not smr_is_schedulable_wo_ilp(ts, q, parsec_theta, parsec_block):
        return (0, mem)
    (r, m, qp) = quiescence_selection_test_wo_ilp(ts, q, max_q, min_q, parsec_theta, parsec_block)
    return (r, m)
