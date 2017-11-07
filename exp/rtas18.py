import copy
import itertools
import random
from collections import defaultdict
from functools import partial
from toolbox.stats import mean

from schedcat.model.tasks import SporadicTask, TaskSystem
import schedcat.model.resources as resources
import schedcat.generator.generator_emstada as emstada
from toolbox.io import write_data, Config

from overhead import *
from analysis import *
from urcu import *
from parsec import *

def mean_mem(mems):
    mem = filter(lambda a: a != 0, mems)
    ret = float(sum(mem)) / max(len(mem), 1)
    return ret

def human_print(taskset, max_cpu):    
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

def generate_requests(conf, ts):
    r_len = int(conf.read_len)
    w_len = int(conf.write_len)
    partitions = defaultdict(TaskSystem)
    for t in ts:
        partitions[t.partition].append(t)
    resources.initialize_resource_model(ts)

    # a little hack make reader or writer not get too low priority
    rp = random.randint(0, len(partitions[0])-1)
    rs = random.sample(range(int(conf.num_cpus)), int(conf.num_reads))
    for r in rs:
        partitions[r][rp].resmodel[0].add_read_request(r_len)

    wp = random.randint(0, len(partitions[0])-1)        
    ws = random.sample(range(int(conf.num_cpus)), int(conf.num_writes))
    for w in ws:
        partitions[w][wp].resmodel[0].add_write_request(w_len)

def generate_task_set(conf):
    ts = TaskSystem()
    # generate taskset for each cpu
    for cpuid in range(0,int(conf.num_cpus)):
        # generate a task set for CPU cpuid
        ntask = int(conf.num_task)
        u = float(conf.util)
        tmp = emstada.gen_taskset(PERIODS[conf.periods], 'unif', ntask, u, 0.01)
        for t in tmp:
            t.partition = cpuid
        # add to the global task set    
        ts.extend(tmp)
    
    ts.sort_by_period()
    ts.assign_ids()
    bounds.assign_fp_preemption_levels(ts)
    generate_requests(conf, ts)
#    human_print(ts, int(conf.num_cpus))
    return ts

def get_overheads(fname):
    oh = Overheads.from_file(fname)
    return oh

def run_tests(confs, tests, oh):
    for conf in confs:
        samples = [[] for _ in tests]
        mems = [[] for _ in tests]
        for sample in xrange(int(conf.samples)):
            if sample % 20 == 0: print "finish", sample
            ts = conf.make_taskset()
            for i in xrange(len(tests)):
                # This assumes that the no-blocking test is the first in tests.
                if i == 0: # This is the no-blocking test. We need to run this in any case.
                    (sched, mem) = tests[i](ts, oh, conf)
                    samples[i].append(sched)
                    mems[i].append(mem)
                else:
                    if samples[0][-1]:
                        re = tests[i](ts, oh, conf)
                        (sched, mem) = (re[0], re[1])
                    else:
                        (sched, mem) = (0, 0)
                    samples[i].append(sched)
                    mems[i].append(mem)

        row = []
        for i in xrange(len(tests)):
            row.append((mean(samples[i]), mean_mem(mems[i])))

        yield [conf.var] + ['%.2f %.2f' % (x, y) for (x, y) in row]

def run_read_num_config(conf):
    oh = get_overheads("./overhead/rtas18_micro.csv")
    set = range(int(conf.read_num_min), int(conf.read_num_max)+1, int(conf.step))
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].num_reads = set[i]
        confs[i].var = set[i]
        confs[i].make_taskset = partial(generate_task_set, confs[i])

    (titles, tests) = zip(*setup_tests())
    header = ['NUM OF READERS']
    header += titles

    data = run_tests(confs, tests, oh)
    write_data(conf.output, data, header, 13)

def run_write_num_config(conf):
    oh = get_overheads("./overhead/rtas18_micro.csv")
    set = range(int(conf.write_num_min), int(conf.write_num_max)+1, int(conf.step))
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].num_writes = set[i]
        confs[i].var = set[i]
        confs[i].make_taskset = partial(generate_task_set, confs[i])

    (titles, tests) = zip(*setup_tests())
    header = ['NUM OF WRITERS']
    header += titles

    data = run_tests(confs, tests, oh)
    write_data(conf.output, data, header, 13)

def run_read_len_config(conf):
    oh = get_overheads("./overhead/rtas18_micro.csv")
    tm = int(conf.read_len_min)
    if tm == 1: tm = 0
    set = range(tm, int(conf.read_len_max)+1, int(conf.step))
    set[0] = int(conf.read_len_min)
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].read_len = set[i]
        confs[i].var = set[i]
        confs[i].make_taskset = partial(generate_task_set, confs[i])

    (titles, tests) = zip(*setup_tests())
    header = ['LEN OF READERS']
    header += titles

    data = run_tests(confs, tests, oh)
    write_data(conf.output, data, header, 13)

def run_write_len_config(conf):
    oh = get_overheads("./overhead/rtas18_micro.csv")
    tm = int(conf.write_len_min)
    if tm == 1: tm = 0
    set = range(tm, int(conf.write_len_max)+1, int(conf.step))
    set[0] = int(conf.write_len_min)
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].write_len = set[i]
        confs[i].var = set[i]
        confs[i].make_taskset = partial(generate_task_set, confs[i])

    (titles, tests) = zip(*setup_tests())
    header = ['LEN OF WRITERS']
    header += titles

    data = run_tests(confs, tests, oh)
    write_data(conf.output, data, header, 13)

def run_mem_num_config(conf):
    oh = get_overheads("./overhead/rtas18_micro.csv")
    set = range(0, int(conf.mem_num_max)+1, int(conf.step))
    set[0] = int(conf.mem_num_min)
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].num_mem = set[i]
        confs[i].var = set[i]
        confs[i].make_taskset = partial(generate_task_set, confs[i])

    (titles, tests) = zip(*setup_tests())
    rtests = []
    rtitles = []
    rtests.append(tests[0])
    rtitles.append(titles[0])
    for i in xrange(1, len(tests)):
        rtests.append(tests[i])
        rtitles.append(titles[i])
    header = ['NUM OF MEMORY']
    header += rtitles

    data = run_tests(confs, rtests, oh)
    write_data(conf.output, data, header, 13)

def run_core_num_config(conf):
    oh = get_overheads("./overhead/rtas18_micro.csv")
    set = range(0, int(conf.cpu_num_max)+1, int(conf.step))
    set[0] = int(conf.cpu_num_min)
    confs = [i for i in range(len(set))]
    i = 0
    confs[i] = copy.copy(conf)
    confs[i].num_cpus = set[i]
    confs[i].num_reads = confs[i].num_writes = (set[i]+1)/2
    confs[i].var = set[i]
    confs[i].make_taskset = partial(generate_task_set, confs[i])
    read_type = int(conf.read_type)
    for i in range(1, len(set)):
        confs[i] = copy.copy(conf)
        confs[i].num_cpus = set[i]
        if read_type == 0:
            confs[i].num_reads = set[i]/5*4
            confs[i].num_writes = set[i]/5
        elif read_type == 1:
            confs[i].num_reads = confs[i].num_writes = (set[i]+1)/2
        else:
            confs[i].num_reads = set[i]/5
            confs[i].num_writes = set[i]/5*4
        confs[i].var = set[i]
        confs[i].make_taskset = partial(generate_task_set, confs[i])

    (titles, tests) = zip(*setup_tests())
    header = ['NUM OF CORE']
    header += titles

    data = run_tests(confs, tests, oh)
    write_data(conf.output, data, header, 13)

def run_qui_period_config(conf):
    oh = get_overheads("./overhead/rtas18_micro.csv")
    set = range(int(conf.qui_period_min), int(conf.qui_period_max)+1, int(conf.step))
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].qui = set[i]
        confs[i].var = set[i]
        confs[i].make_taskset = partial(generate_task_set, confs[i])

    (titles, tests) = zip(*setup_qui_tests())
    header = ['QUI PERIODS']
    header += titles

    data = run_tests(confs, tests, oh)
    write_data(conf.output, data, header, 13)

def drange(start, stop, step):
    ret = []
    r = start
    while r <= stop:
        ret.append(r)
        r += step
    return ret

def run_util_num_config(conf):
    oh = get_overheads("./overhead/rtas18_micro.csv")
    set = drange(float(conf.util_num_min), float(conf.util_num_max), float(conf.step))
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].util = set[i]
        confs[i].var = set[i]
        confs[i].make_taskset = partial(generate_task_set, confs[i])

    (titles, tests) = zip(*setup_tests())
    header = ['UTILIZATION']
    header += titles

    data = run_tests(confs, tests, oh)
    write_data(conf.output, data, header, 13)

def generate_mc_requests(conf, ts):
    r_len = int(conf.read_len)
    w_len = int(conf.write_len)
    resources.initialize_resource_model(ts)
    for t in ts:
        if t.mc_type == "reader":
            t.resmodel[0].add_read_request(r_len)
        else:
            t.resmodel[0].add_write_request(w_len)

def generate_mc_task_set(conf):
    ts = TaskSystem()
    # generate taskset for each cpu
    for cpuid in range(0,int(conf.num_cpus)):
        # generate a task set for CPU cpuid
        tmp = TaskSystem([SporadicTask(1000,1)])
        for t in tmp:
            t.partition = cpuid
            t.mc_type = "reader"
        # add to the global task set    
        ts.extend(tmp)
        tmp = TaskSystem([SporadicTask(1000,2)])
        for t in tmp:
            t.partition = cpuid
            t.mc_type = "writer"
        ts.extend(tmp)
    
    ts.sort_by_period()
    ts.assign_ids()
    bounds.assign_fp_preemption_levels(ts)
    generate_mc_requests(conf, ts)
    return ts

def get_mc_ret(ts, rp, wp, m, qp):
    getn = (1000000000/rp * 2)
    setn = (1000000000/wp * 2)
    thput = getn + setn
    up = float(setn)/float(thput)*100
    u = 0
    for t in ts:
        if t.partition == 1:
            u += float(t.uninflated_cost)/float(t.period)
    for t in ts:
        if t.mc_type == "writer": wr = t.response_time
        else: rr = t.response_time
    return (int(rp), int(rr), int(wr), int(thput), int(100*u), int(up), int(m), int(qp))

def mc_mcs_test(conf, oh, mc_oh, oh_scale=1):
    charge_mc_mcs(mc_oh, conf)
    num_cpu = int(conf.num_cpus)
    wp = int(conf.write_period)
    r_cost = int(conf.read_cost)
    w_cost = int(conf.write_cost)
    inflate_r = r_cost + oh.spin_lock[num_cpu]*oh_scale
    inflate_w = w_cost + oh.spin_lock[num_cpu]*oh_scale
    if wp <= inflate_w + inflate_r: return (-1, -1, -1, -1, -1, -1, -1, -1)
    ts = generate_mc_task_set(conf)
    for t in ts:
        if t.mc_type == "writer":
            t.period = t.deadline = wp
            t.cost = w_cost
        if t.mc_type == "reader":
            t.cost = r_cost

    for t in ts:
        if t.mc_type == "reader":
            t.period = t.deadline = wp
    (s, m, re_ts) = spinlock_ilp_test(ts, oh, conf, oh_scale)
    if s != 1: return (-1, -1, -1, -1, -1, -1, -1, -1)

    min_rp = int(inflate_r)
    max_rp = wp+1
    while min_rp < max_rp:
        rp = (min_rp + max_rp)/2
        for t in ts:
            if t.mc_type == "reader":
                t.period = t.deadline = rp
        (s, m, re_ts) = spinlock_ilp_test(ts, oh, conf, oh_scale)
        if s == 1: max_rp = rp
        else: min_rp = rp+1

    for t in ts:
        if t.mc_type == "reader":
            t.period = t.deadline = max_rp
    (s, m, re_ts) = spinlock_ilp_test(ts, oh, conf, oh_scale)
    assert s == 1
    return get_mc_ret(re_ts, max_rp, wp, m, 0)

def mc_pfrw_test(conf, oh, mc_oh, oh_scale=1):
    charge_mc_pfrw(mc_oh, conf)
    num_cpu = int(conf.num_cpus)
    wp = int(conf.write_period)
    r_cost = int(conf.read_cost)
    w_cost = int(conf.write_cost)
    inflate_r = r_cost + oh.read_lock[num_cpu]*oh_scale
    inflate_w = w_cost + oh.read_unlock[num_cpu]*oh_scale
    if wp <= inflate_w + inflate_r: return (-1, -1, -1, -1, -1, -1, -1, -1)
    ts = generate_mc_task_set(conf)
    for t in ts:
        if t.mc_type == "writer":
            t.period = t.deadline = wp
            t.cost = w_cost
        if t.mc_type == "reader":
            t.cost = r_cost

    for t in ts:
        if t.mc_type == "reader":
            t.period = t.deadline = wp
    (s, m, re_ts) = pfrwlock_test(ts, oh, conf, oh_scale)
    if s != 1: return (-1, -1, -1, -1, -1, -1, -1, -1)

    min_rp = int(inflate_r)
    max_rp = wp+1
    while min_rp < max_rp:
        rp = (min_rp + max_rp)/2
        for t in ts:
            if t.mc_type == "reader":
                t.period = t.deadline = rp
#        human_print(ts, int(conf.num_cpus))
        (s, m, re_ts) = pfrwlock_test(ts, oh, conf, oh_scale)
        if s == 1: max_rp = rp
        else: min_rp = rp+1

    for t in ts:
        if t.mc_type == "reader":
            t.period = t.deadline = max_rp
    (s, m, re_ts) = pfrwlock_test(ts, oh, conf, oh_scale)
    assert s == 1
    return get_mc_ret(re_ts, max_rp, wp, m, 0)

def mc_parsec_test(conf, oh, mc_oh, oh_scale=1):
    charge_mc_parsec(mc_oh, conf)
    num_cpu = int(conf.num_cpus)
    wp = int(conf.write_period)
    r_cost = int(conf.read_cost)
    w_cost = int(conf.write_cost)
    inflate_r = r_cost + oh.parsec_read[num_cpu]*oh_scale
    inflate_w = w_cost + oh.spin_lock[num_cpu]*oh_scale + oh.parsec_q[num_cpu]*oh_scale
    if wp <= inflate_w + inflate_r: return (-1, -1, -1, -1, -1, -1, -1, -1)
    ts = generate_mc_task_set(conf)
    for t in ts:
        if t.mc_type == "writer":
            t.period = t.deadline = wp
            t.cost = w_cost
        if t.mc_type == "reader":
            t.cost = r_cost

    for t in ts:
        if t.mc_type == "reader":
            t.period = t.deadline = wp
    (s, m, qp, re_ts) = mc_parsec_test_linear(ts, oh, conf, oh_scale)
    if s != 1: return (-1, -1, -1, -1, -1, -1, -1, -1)
    print (s, m, qp)

    min_rp = int(inflate_r)
    max_rp = wp+1
    while min_rp < max_rp:
        rp = (min_rp + max_rp)/2
        for t in ts:
            if t.mc_type == "reader":
                t.period = t.deadline = rp
        (s, m, qp, re_ts) = mc_parsec_test_linear(ts, oh, conf, oh_scale)
        print (s, rp, m, qp)
        if s == 1: max_rp = rp
        else: min_rp = rp+1

    for t in ts:
        if t.mc_type == "reader":
            t.period = t.deadline = max_rp
    (s, m, qp, re_ts) = mc_parsec_test_linear(ts, oh, conf, oh_scale)
    assert s == 1
    return get_mc_ret(re_ts, max_rp, wp, m, qp)

def run_mc_tests(confs, tests, oh, mc_oh):
    for conf in confs:
        row = []
        for i in xrange(len(tests)):
            (rp, rr, wr, thput, util, u_presentage, mem, qp) = tests[i](conf, oh, mc_oh)
            row.append((int(conf.write_period), rp, rr, wr, thput, util, u_presentage, mem, qp))
        yield [conf.var] + ['%d, %d, %d, %d, %d, %d, %d, %d, %d' % (x1, x2, x3, x4, x5, x6, x7, x8, x9) for (x1, x2, x3, x4, x5, x6, x7, x8, x9) in row]

def run_mc_core_config(conf):
    mc_oh = get_overheads("./overhead/rtas18_avg_mc.csv")
    oh = mc_oh
    # mc_oh = get_overheads("./overhead/rtas18_99th_mc.csv")
    # oh = get_overheads("./overhead/rtas18_micro.csv")
    tm = int(conf.cpu_num_min)
    if tm == 1: tm = 0
    set = range(tm, int(conf.cpu_num_max)+1, int(conf.step))
    set[0] = int(conf.cpu_num_min)
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].num_cpus = set[i]
        confs[i].var = set[i]
        # confs[i].make_taskset = partial(generate_mc_task_set, confs[i])

    (titles, tests) = zip(*mc_setup_tests())
    header = ['NUM OF CORES']
    header += titles

    data = run_mc_tests(confs, tests, oh, mc_oh)
    write_data(conf.output, data, header, 37)

def run_mc_perod_config(conf):
    mc_oh = get_overheads("./overhead/rtas18_avg_mc.csv")
    oh = mc_oh
    # mc_oh = get_overheads("./overhead/rtas18_99th_mc.csv")
    # oh = get_overheads("./overhead/rtas18_micro.csv")
    set = range(int(conf.write_period_min), int(conf.write_period_max)+1, int(conf.step))
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].write_period = set[i]
        confs[i].var = set[i]
        # confs[i].make_taskset = partial(generate_mc_task_set, confs[i])

    (titles, tests) = zip(*mc_setup_tests())
    header = ['LEN OF W_PERIOD']
    header += titles

    data = run_mc_tests(confs, tests, oh, mc_oh)
    write_data(conf.output, data, header, 37)

def run_mc_seclect_w_period(confs, tests, oh, mc_oh):
    for conf in confs:
        row = []
        for i in xrange(len(tests)):
            min_wp = 2000
            max_wp = 1000000001/128
            while min_wp < max_wp:
                wp = (min_wp + max_wp)/2
                conf.write_period = int(wp)
                (rp, rr, wr, thput, mem, qp) = tests[i](conf, oh, mc_oh)
                print ('wp', 'rp'), (wp, rp)
                if (rp != -1): max_wp = wp
                else: min_wp = wp+1
            conf.write_period = int(max_wp)
            (rp, rr, wr, thput, util, u_presentage, mem, qp) = tests[i](conf, oh, mc_oh)
            assert rp != -1
            row.append((int(max_wp), rp, rr, wr, thput, util, u_presentage, mem, qp))
        yield [conf.var] + ['%d, %d, %d, %d, %d, %d, %d, %d, %d' % (x1, x2, x3, x4, x5, x6, x7, x8, x9) for (x1, x2, x3, x4, x5, x6, x7, x8, x9) in row]

def run_mc_core_write_period_config(conf):
    mc_oh = get_overheads("./overhead/rtas18_avg_mc.csv")
    oh = mc_oh
    # mc_oh = get_overheads("./overhead/rtas18_99th_mc.csv")
    # oh = get_overheads("./overhead/rtas18_micro.csv")
    tm = int(conf.cpu_num_min)
    if tm == 1: tm = 0
    set = range(tm, int(conf.cpu_num_max)+1, int(conf.step))
    set[0] = int(conf.cpu_num_min)
    confs = [i for i in range(len(set))]
    for i in range(len(set)):
        confs[i] = copy.copy(conf)
        confs[i].num_cpus = set[i]
        confs[i].var = set[i]
        # confs[i].make_taskset = partial(generate_mc_task_set, confs[i])

    (titles, tests) = zip(*mc_setup_tests())
    header = ['NUM OF CORES']
    header += titles

    data = run_mc_seclect_w_period(confs, tests, oh, mc_oh)
    write_data(conf.output, data, header, 37)

def generate_test_configs(options):
	print "this is test generate configured"

def unit_test(conf):
    ts = TaskSystem([SporadicTask(5,20),
                     SporadicTask(10,30),
                     SporadicTask(2,10),
                     SporadicTask(5,20),
                     SporadicTask(5,20),
                     SporadicTask(10,30)])
    ts[0].partition = ts[1].partition = 0
    ts[2].partition = ts[3].partition = 1
    ts[4].partition = ts[5].partition = 2
    for i in xrange(6):
        ts[i].id = i
    bounds.assign_fp_preemption_levels(ts)
    resources.initialize_resource_model(ts)
    init_smr_taskset(ts)
    num_mem = int(conf.num_mem)
    r_len = int(conf.read_len)
    w_len = int(conf.write_len)
    q = Quiescence()
    q.arpha_cost = 1
    q.beta_cost = 1.0/50
    q.period = 30
    q.num_mem = num_mem

    for t in ts:
        assert task_max_read_cost(t) == 0
    for t in iter_partitions_ts(ts):
        assert get_highest_writer(t) == None
    assert get_min_qui_period(ts) == 0
    assert get_max_read_response(ts) == 0
    assert get_num_mem(ts, 1, num_mem) == 0
    assert fp_read_schedulable_with_qui(ts, q, 0) == True
    for t in ts:
        assert t.read_response_time == task_max_read_cost(t)
    bounds.apply_pfp_lp_smr_msrp_bounds(ts)
    for t in ts:
        assert t.blocked == 0
        assert t.uninflated_cost == t.cost
    assert fp_schedulable_with_qui(ts, q, 0, 0) == True
    assert smr_is_schedulable(ts, q, parsec_theta, parsec_block) == True
    print "\033[1;32;40mno locking test pass"

    ts[0].resmodel[0].add_read_request(r_len)
    ts[2].resmodel[0].add_read_request(r_len)
    ts[4].resmodel[0].add_read_request(r_len)
    init_smr_taskset(ts)

    assert task_max_read_cost(ts[0]) == r_len
    assert task_max_read_cost(ts[1]) == 0
    assert task_max_read_cost(ts[2]) == r_len
    assert task_max_read_cost(ts[3]) == 0
    assert task_max_read_cost(ts[4]) == r_len
    assert task_max_read_cost(ts[5]) == 0
    for t in iter_partitions_ts(ts):
        assert get_highest_writer(t) == None
    assert get_min_qui_period(ts) == 0
    assert get_max_read_response(ts) == r_len
    assert get_num_mem(ts, 1, num_mem) == 0
    assert fp_read_schedulable_with_qui(ts, q, 0) == True
    for t in ts:
        assert t.read_response_time == task_max_read_cost(t)
    bounds.apply_pfp_lp_smr_msrp_bounds(ts)
    for t in ts:
        assert t.blocked == 0
        assert t.uninflated_cost == t.cost
    assert fp_schedulable_with_qui(ts, q, 0, 0) == True
    assert smr_is_schedulable(ts, q, parsec_theta, parsec_block) == True
    print "read only test pass"

    for t in ts:
        req = t.resmodel[0]
        req.max_reads = req.max_read_length = 0
    ts[1].resmodel[0].add_write_request(w_len)
    ts[3].resmodel[0].add_write_request(w_len)
    ts[5].resmodel[0].add_write_request(w_len)
    init_smr_taskset(ts)

    for t in ts:
        assert task_max_read_cost(t) == 0
    for t in iter_partitions_ts(ts):
        assert get_highest_writer(t) == t[1]
    assert get_min_qui_period(ts) == 30
    assert get_max_read_response(ts) == 0
    assert get_num_mem(ts, 1, num_mem) == num_mem*3
    assert get_num_mem(ts, 15, num_mem) == num_mem*3
    assert get_num_mem(ts, 20, num_mem) == num_mem*4
    assert get_num_mem(ts, 30, num_mem) == num_mem*6
    assert get_num_mem(ts, 100, num_mem) == num_mem*14
    assert fp_read_schedulable_with_qui(ts, q, 0) == True
    for t in ts:
        assert t.read_response_time == task_max_read_cost(t)
    bounds.apply_pfp_lp_smr_msrp_bounds(ts)
    for t in ts:
        assert t.uninflated_cost == t.cost
    for i in xrange(0, 6, 2):
        assert ts[i].blocked == 3*w_len
    for i in xrange(1, 6, 2):
        assert ts[i].blocked == 2*w_len
    assert parsec_theta(ts, q) == 10+30
    assert fp_schedulable_with_qui(ts, q, 30, 0) == True
    assert smr_is_schedulable(ts, q, parsec_theta, parsec_block) == True
    assert fp_schedulable_with_qui(ts, q, 49, 0) == True
    print "write only test pass"

    ts[0].resmodel[0].add_read_request(r_len)
    ts[2].resmodel[0].add_read_request(r_len)
    ts[4].resmodel[0].add_read_request(r_len)
    init_smr_taskset(ts)

    assert task_max_read_cost(ts[0]) == r_len
    assert task_max_read_cost(ts[1]) == 0
    assert task_max_read_cost(ts[2]) == r_len
    assert task_max_read_cost(ts[3]) == 0
    assert task_max_read_cost(ts[4]) == r_len
    assert task_max_read_cost(ts[5]) == 0
    for t in iter_partitions_ts(ts):
        assert get_highest_writer(t) == t[1]
    assert get_min_qui_period(ts) == 30
    assert get_max_read_response(ts) == r_len
    assert get_num_mem(ts, 1, num_mem) == num_mem*3
    assert get_num_mem(ts, 15, num_mem) == num_mem*3
    assert get_num_mem(ts, 20, num_mem) == num_mem*4
    assert get_num_mem(ts, 30, num_mem) == num_mem*6
    assert get_num_mem(ts, 100, num_mem) == num_mem*14
    assert fp_read_schedulable_with_qui(ts, q, 0) == True
    for t in ts:
        assert t.read_response_time == task_max_read_cost(t)
    bounds.apply_pfp_lp_smr_msrp_bounds(ts)
    for t in ts:
        assert t.uninflated_cost == t.cost
    for i in xrange(0, 6, 2):
        assert ts[i].blocked == 3*w_len
    for i in xrange(1, 6, 2):
        assert ts[i].blocked == 2*w_len
    assert parsec_theta(ts, q) == 10 + r_len + q.period
    assert fp_schedulable_with_qui(ts, q, parsec_theta(ts, q), 0) == True
    assert smr_is_schedulable(ts, q, parsec_theta, parsec_block) == True
    print "mem", get_smr_max_mem(ts, parsec_theta(ts, q), q.num_mem), "theta:", parsec_theta(ts, q), "L:", get_max_L(ts), "qui response:", get_max_quic_response(ts), "read resopnse:", get_max_read_response(ts), "qui period", q.period, "block", parsec_block(ts) 
    print "read write test pass\033[0m"

    init_smr_taskset(ts)
    assert urcu_theta(ts, q) == 10 + q.period
    assert fp_schedulable_with_qui(ts, q, urcu_theta(ts, q), urcu_block(ts)) == True
    assert smr_is_schedulable(ts, q, urcu_theta, urcu_block) == True
    print "mem", get_smr_max_mem(ts, urcu_theta(ts, q), q.num_mem), "theta:", urcu_theta(ts, q), "L:", get_max_L(ts), "qui response:", get_max_quic_response(ts), "read resopnse:", get_max_read_response(ts), "qui period", q.period, "block", urcu_block(ts) 

def setup_tests():
    return [
        ("#no-blocking",      no_blocking_test),
        ("#naive-spinlock",   spinlock_naive_test),
        ("#spinlock-lp",      spinlock_ilp_test),
        ("#pf-rwlock",        pfrwlock_test),
        ("#urcu-line",        urcu_test_linear),
        ("#rt-parsec-line",   rt_parsec_test_linear),
        ("#timed-linear",     timed_parsec_test_linear),
        # ("#urcu",             urcu_test),
        # ("#rt-parsec",        rt_parsec_test),
        # ("#timed-quiscence",  timed_parsec_test),
        # ("#parsec-sig-line",  parsec_single_test_linear),
        # ("#urcu-no-ilp",      urcu_wo_ilp_test),
        # ("#rt-parsec-no-ilp", rt_parsec_wo_ilp_test),
        # ("#timed-no-ilp",     timed_parsec_wo_ilp_test),    
]

def setup_qui_tests():
    return [
        ("#no-blocking",      no_blocking_test),
        ("#urcu",             urcu_taskset_qui_test),
        ("#rt-parsec",        rt_parsec_taskset_qui_test),
        ("#timed-quiscence",  timed_parsec_taskset_qui_test),
        ("#parsec-sig-line",  parsec_single_taskset_qui_test),
    ]

def mc_setup_tests():
    return [
        ("#mcs-lock",   mc_mcs_test),
        ("#pfrw-lock",  mc_pfrw_test),
        ("#rt-parsec",  mc_parsec_test),
    ]

PERIODS = { 
    #ranges for EMSDATA task generator
    '10-100'        : (10,100),
}
	
EXPERIMENTS = {
     'read_num'   : run_read_num_config,
     'write_num'  : run_write_num_config,
     'read_len'   : run_read_len_config,
     'write_len'  : run_write_len_config,
     'mem_num'    : run_mem_num_config,
     'util_num'   : run_util_num_config,
     'core_num'   : run_core_num_config,
     'qui_period' : run_qui_period_config,
     'mc_core'    : run_mc_core_config,
     'mc_period'  : run_mc_perod_config,
     'mc_core_period'  : run_mc_core_write_period_config,
     'rtas18/smr-unit-test'   : unit_test,
}

CONFIG_GENERATORS = {
     'rtas18'   : generate_test_configs,
}

