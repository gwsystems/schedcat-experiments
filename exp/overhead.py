from math import ceil
from schedcat.util.csv import load_columns as load_column_csv
from schedcat.util.math import const

class Overheads(object):
    """Legacy overhead objects"""
    def __init__(self):
        self.quantum_length = 1000 # microseconds
        self.zero_overheads()

    FIELD_MAPPING = [
        # memcached-related overheads
        ('MC-MCS-READ',      'mcs_read'),
        ('MC-MCS-WRITE',     'mcs_write'),
        ('MC-PFRW-READ',     'pfrw_read'),
        ('MC-PFRW-WRITE',    'pfrw_write'),
        ('MC-PARSEC-READ',   'parsec_read_mc'),
        ('MC-PARSEC-WRITE',  'parsec_write_mc'),
        ('MC-MCS-GET',       'mcs_get'),
        ('MC-MCS-SET',       'mcs_set'),
        ('MC-PFRW-GET',      'pfrw_get'),
        ('MC-PFRW-SET',      'pfrw_set'),
        ('MC-PARSEC-GET',    'parsec_get'),
        ('MC-PARSEC-SET',    'parsec_set'),

        # locking- and system-call-related overheads
        ('MCS-LOCK',     'spin_lock'),
        ('READ-LOCK',    'read_lock'),
        ('READ-UNLOCK',  'read_unlock'),
        ('URCU-READ',    'rcu_read'),
        ('PARSEC-READ',  'parsec_read'),
        ('TIME-READ',    'timed_read'),
        ('URCU_QUI',     'rcu_q'),
        ('PARSEC_QUI',   'parsec_q'),
        ('TIME_QUI',     'time_q'),
        ('MEM_ALLOC',    'mem_alloc'),
        ('MEM_FREE',     'mem_free'),
        ]

    def zero_overheads(self):
        for (name, field) in self.FIELD_MAPPING:
            self.__dict__[field] = const(0)

    def __str__(self):
        return " ".join(["%s: %s" % (name, self.__dict__[field])
                         for (name, field) in Overheads.FIELD_MAPPING])

    def load_approximations(self, fname, non_decreasing=True, custom_fields=None,
                            per_cpu_task_counts=False, num_cpus=None):
        if custom_fields is None:
            custom_fields = []

        data = load_column_csv(fname, convert=float)
        if not 'CORE-COUNT' in data.by_name:
            raise IOError, "CORE-COUNT column is missing"

        # initialize custom fields, if any
        for (name, field) in custom_fields:
            self.__dict__[field] = const(0)

        for (name, field) in Overheads.FIELD_MAPPING + custom_fields:
            if name in data.by_name:
                points = zip(data.by_name['CORE-COUNT'], data.by_name[name])
                d = {key: value for (key, value) in points}
                self.__dict__[field] = d
                # if per_cpu_task_counts:
                #     points = [(num_cpus * x, y) for (x, y) in points]
                # if non_decreasing:
                #     self.__dict__[field] = monotonic_pwlin(points)
                # else:
                #     self.__dict__[field] = piece_wise_linear(points)
                # print name, field, self.__dict__[field], points

    @staticmethod
    def from_file(fname, *args, **kargs):
        o = Overheads()
        o.source = fname
        o.load_approximations(fname, *args, **kargs)
        return o

def charge_overhead(tasks, rcost, wcost):
    for t in tasks:
        extra_wcet = 0
        for res_id in t.resmodel:
            req = t.resmodel[res_id]
            if req.max_reads:
                extra_wcet += req.max_reads * rcost
            if req.max_writes:
                extra_wcet += req.max_writes * wcost
        t.cost += int(ceil(extra_wcet))
    return tasks

def charge_spinlock_overheads(oheads, tasks, conf, oh_scale=1):
    if oheads is None or not tasks:
        return tasks

    ncores = int(conf.num_cpus)
    # the individual charges
    wcost = rcost = oheads.spin_lock[ncores]*oh_scale
    # inflate each request and each task's exec cost
    return charge_overhead(tasks, rcost, wcost)

def charge_pfrwlock_overheads(oheads, tasks, conf, oh_scale=1):
    if oheads is None or not tasks:
        return tasks

    ncores = int(conf.num_cpus)
    # the individual charges
    rcost = oheads.read_lock[ncores]*oh_scale
    wcost = oheads.read_unlock[ncores]*oh_scale
    # inflate each request and each task's exec cost
    return charge_overhead(tasks, rcost, wcost)

def charge_urcu_overheads(oheads, tasks, conf):
    if oheads is None or not tasks:
        return tasks

    ncores = int(conf.num_cpus)
    # the individual charges
    rcost = oheads.rcu_read[ncores]
    wcost = oheads.spin_lock[ncores]
    wcost += oheads.mem_alloc[ncores]*float(conf.num_mem)
    # inflate each request and each task's exec cost
    return charge_overhead(tasks, rcost, wcost)

def charge_parsec_overheads(oheads, tasks, conf):
    if oheads is None or not tasks:
        return tasks

    ncores = int(conf.num_cpus)
    # the individual charges
    rcost = oheads.parsec_read[ncores]
    wcost = oheads.spin_lock[ncores]
    wcost += oheads.mem_alloc[ncores]*float(conf.num_mem)
    # inflate each request and each task's exec cost
    return charge_overhead(tasks, rcost, wcost)

def charge_time_overheads(oheads, tasks, conf):
    if oheads is None or not tasks:
        return tasks

    ncores = int(conf.num_cpus)
    # the individual charges
    rcost = oheads.timed_read[ncores]
    wcost = oheads.spin_lock[ncores]
    wcost += oheads.mem_alloc[ncores]*float(conf.num_mem)
    # inflate each request and each task's exec cost
    return charge_overhead(tasks, rcost, wcost)

def charge_parsec_overheads_wo_mem(oheads, tasks, conf, oh_scale=1):
    if oheads is None or not tasks:
        return tasks

    ncores = int(conf.num_cpus)
    # the individual charges
    rcost = oheads.parsec_read[ncores]*oh_scale
    wcost = oheads.spin_lock[ncores]*oh_scale
    # inflate each request and each task's exec cost
    return charge_overhead(tasks, rcost, wcost)

def charge_mc_cost(conf, rlen, wlen):
    conf.read_len = rlen
    conf.write_len = wlen

def charge_mc_task_cost(conf, rlen, wlen):
    conf.read_cost = rlen
    conf.write_cost = wlen

def charge_mc_mcs(oheads, conf):
    ncores = int(conf.num_cpus)
    r_len = oheads.mcs_read[ncores]
    w_len = oheads.mcs_write[ncores]
    charge_mc_cost(conf, r_len, w_len)
    r_cost = oheads.mcs_get[ncores]
    w_cost = oheads.mcs_set[ncores]
    charge_mc_task_cost(conf, r_cost, w_cost)

def charge_mc_pfrw(oheads, conf):
    ncores = int(conf.num_cpus)
    r_len = oheads.pfrw_read[ncores]
    w_len = oheads.pfrw_write[ncores]
    charge_mc_cost(conf, r_len, w_len)
    r_cost = oheads.pfrw_get[ncores]
    w_cost = oheads.pfrw_set[ncores]
    charge_mc_task_cost(conf, r_cost, w_cost)

def charge_mc_parsec(oheads, conf):
    ncores = int(conf.num_cpus)
    r_len = oheads.parsec_read_mc[ncores]
    w_len = oheads.parsec_write_mc[ncores]
    charge_mc_cost(conf, r_len, w_len)
    r_cost = oheads.parsec_get[ncores]
    w_cost = oheads.parsec_set[ncores]
    charge_mc_task_cost(conf, r_cost, w_cost)

