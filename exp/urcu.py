from __future__ import division
import copy
import random

from schedcat.model.tasks import SporadicTask, TaskSystem
import schedcat.locking.bounds as bounds
import schedcat.sched.fp as fp

from overhead import *
from analysis import *
from parsec import *

def get_min_qui_period_urcu(taskset):
    for ts in iter_partitions_ts(taskset):
        w = get_highest_writer(ts)
        if w != None:
            return (w.period, w.partition)
    return (0, -1)

def get_max_quic_response_urcu(taskset, qui):
    r = 0
    for ts in iter_partitions_ts(taskset):
        w = get_highest_writer(ts)
        if w != None and w.partition == qui.core and w.response_time > r:
            r = w.response_time
    return r

def urcu_theta(ts, q):
    return get_max_L(ts) + q.period

def urcu_block(ts):
    return get_max_read_response(ts)

def get_smr_max_mem_urcu(ts, theta, num, qui):
    time = theta + get_max_quic_response_urcu(ts, qui)
    return get_num_mem(ts, time, num)

def fp_read_schedulable_with_qui_urcu(taskset, q, theta):
    for ts in iter_partitions_ts(taskset):
        w = get_highest_writer(ts)
        if w != None and w.partition == q.core:
            q.priority = w.period
        else:
            q.priority = float("inf")
        if not read_is_schedulable_with_qui(ts, q, theta, taskset):
            return False
    return True

def fp_schedulable_with_qui_urcu(taskset, q, theta, q_block):
    for ts in iter_partitions_ts(taskset):
        w = get_highest_writer(ts)
        if w != None and w.partition == q.core:
            q.priority = w.period
            w.q_blocked = q_block
        else:
            q.priority = float("inf")
        if not is_schedulable_with_qui(ts, q, theta, taskset):
            return False
    return True

def smr_is_schedulable_urcu(ts, q, get_theta, get_block):
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
            if not fp_schedulable_with_qui_urcu(ts, q, theta, block):
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
            if not fp_read_schedulable_with_qui_urcu(ts, q, theta):
                return 0
            if read_response_times_consistent(ts):
                break

        stop = response_times_consistent(ts)
        stop = stop and read_response_times_consistent(ts)
        assert stop == True
        if old_theta != get_theta(ts, q) or old_block != get_block(ts):
            stop = False
    return 1

def quiescence_selection_test_urcu(ts, qui, max_q, min_q, get_theta, get_block):
    while min_q < max_q:
        qp = int((min_q + max_q)/2)
        qui.period = qp
        r = smr_is_schedulable_urcu(ts, qui, get_theta, get_block)
        if r: max_q = qp
        else: min_q = qp + 1
    r = 1
    if r: m = get_smr_max_mem_urcu(ts, get_theta(ts, qui), qui.num_mem, qui)
    else: m = 0

    return (r, m, max_q)

def urcu_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_urcu_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.rcu_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    max_q = ts.max_period()
    (min_q, c) = get_min_qui_period_urcu(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.core = c
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui_urcu(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    if not smr_is_schedulable_urcu(ts, q, urcu_theta, urcu_block):
        return (0, mem)
    (r, m, qp) = quiescence_selection_test_urcu(ts, q, max_q, min_q, urcu_theta, urcu_block)
    return (r, m)

def linear_quiescence_selection_urcu(ts, qui, max_q, min_q, get_theta, get_block):
    qp = min_q
    r = 0
    while qp <= max_q:
        qui.period = qp
        r = smr_is_schedulable_urcu(ts, qui, get_theta, get_block)
        if r: break
        else: qp += min_q

    if r: m = get_smr_max_mem_urcu(ts, get_theta(ts, qui), qui.num_mem, qui)
    else: m = 0

    return (r, m, qp)

def urcu_test_linear(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_urcu_overheads(oh, ts, conf)
    ncores     = int(conf.num_cpus)
    q_arpha_c  = oh.rcu_q[ncores]
    q_beta_c   = oh.mem_free[ncores]
    q_mem      = int(conf.num_mem)
    max_q      = ts.max_period()
    (min_q, c) = get_min_qui_period_urcu(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.core = c
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui_urcu(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    (r, m, qp) = linear_quiescence_selection_urcu(ts, q, max_q, min_q, urcu_theta, urcu_block)
    return (r, m)

def urcu_taskset_qui_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_urcu_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.rcu_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    (min_q, c) = get_min_qui_period_urcu(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.core = c
    q.period = int(conf.qui)
    r = smr_is_schedulable_urcu(ts, q, urcu_theta, urcu_block)
    if r: mem = get_smr_max_mem_urcu(ts, urcu_theta(ts, q), q.num_mem, q)
    return (r, mem)


def parsec_single_test_linear(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_parsec_overheads(oh, ts, conf)
    ncores     = int(conf.num_cpus)
    q_arpha_c  = oh.parsec_q[ncores]
    q_beta_c   = oh.mem_free[ncores]
    q_mem      = int(conf.num_mem)
    max_q      = ts.max_period()
    (min_q, c) = get_min_qui_period_urcu(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.core = c
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui_urcu(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    (r, m, qp) = linear_quiescence_selection_urcu(ts, q, max_q, min_q, parsec_theta, parsec_block)
    return (r, m)

def parsec_single_taskset_qui_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_parsec_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.parsec_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    (min_q, c) = get_min_qui_period_urcu(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.core = c
    q.period = int(conf.qui)
    r = smr_is_schedulable_urcu(ts, q, parsec_theta, parsec_block)
    if r: mem = get_smr_max_mem_urcu(ts, parsec_theta(ts, q), q.num_mem, q)
    return (r, mem)






def smr_is_schedulable_urcu_wo_ilp(ts, q, get_theta, get_block):
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
            if not fp_schedulable_with_qui_urcu(ts, q, theta, block):
                return False
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
            if not fp_read_schedulable_with_qui_urcu(ts, q, theta):
                return False
            if read_response_times_consistent(ts):
                break

        stop = response_times_consistent(ts)
        stop = stop and read_response_times_consistent(ts)
        assert stop == True
        if old_theta != get_theta(ts, q) or old_block != get_block(ts):
            stop = False
    return True

def quiescence_selection_test_urcu_wo_ilp(ts, qui, max_q, min_q, get_theta, get_block):
    while min_q < max_q:
        qp = int((min_q + max_q)/2)
        qui.period = qp
        r = smr_is_schedulable_urcu_wo_ilp(ts, qui, get_theta, get_block)
        if r: max_q = qp
        else: min_q = qp + 1
    m = get_smr_max_mem_urcu(ts, get_theta(ts, qui), qui.num_mem, qui)

    return (1, m, max_q)

def urcu_wo_ilp_test(taskset_in, oh, conf):
    mem = 0
    ts = copy.deepcopy(taskset_in)
    charge_urcu_overheads(oh, ts, conf)
    ncores = int(conf.num_cpus)
    q_arpha_c = oh.rcu_q[ncores]
    q_beta_c = oh.mem_free[ncores]
    q_mem = int(conf.num_mem)
    max_q = ts.max_period()
    (min_q, c) = get_min_qui_period_urcu(ts)
    q = Quiescence(q_arpha_c, q_beta_c, q_mem)
    q.core = c
    q.period = max_q
    if min_q == 0:
        init_smr_taskset(ts)
        if fp_schedulable_with_qui_urcu(ts, q, 0, 0): return (1, mem)
        else: return (0, mem)
    if not smr_is_schedulable_urcu_wo_ilp(ts, q, urcu_theta, urcu_block):
        return (0, mem)
    (r, m, qp) = quiescence_selection_test_urcu_wo_ilp(ts, q, max_q, min_q, urcu_theta, urcu_block)
    return (r, m)
