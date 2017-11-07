from __future__ import division

import os
import sys
import socket
import optparse
import traceback
from time import sleep
import random

from StringIO import StringIO

from multiprocessing import Process, cpu_count

from exp import run_config
from toolbox.io import get_hostname, Config
from toolbox.git import get_version_string
import dist.confserver as confserver

RETRY_LIMIT = 1000
retry_delay = lambda attempt: attempt * (1 + random.uniform(0, 0.5))

def client(server, port, proc_id=1):
    srv = confserver.connect_to_server(server, port)
    client_id = "%s/P%d/T%s" % (get_hostname(), os.getpid(), proc_id)

    try:
        count = 0

        while True:
            param_dict = None

            connect_retry_count = 0
            while True:
                try:
                    param_dict = srv.get_conf_dict(client_id)
                    break
                except IOError as err:
                    connect_retry_count += 1
                    if connect_retry_count > RETRY_LIMIT:
                        raise err # retry limit exceeded, give up
                    else:
                        delay = retry_delay(connect_retry_count)
                        print "[%d] RPC attempt %d failed (%s), retrying after %.2fs..." \
                                % (proc_id, connect_retry_count, err, delay)
                        sleep(delay)


            if param_dict:
                count += 1
                conf = Config(param_dict)
                conf.output = StringIO()
                time = None
                try:
                    print "[T%d] starting '%s'... (PID=%d)" % (proc_id, conf.fname, os.getpid())
                    time = run_config(conf)
                    print "[T%d] completed '%s' (time consumed: %s)." % (proc_id, conf.fname, time)

                    connect_retry_count = 0
                    while connect_retry_count <= RETRY_LIMIT:
                        try:
                            srv.report_results(conf.result_token, conf.output.getvalue())
                            break
                        except IOError as err:
                            connect_retry_count += 1
                            sleep(retry_delay(connect_retry_count))

                    if connect_retry_count > RETRY_LIMIT:
                        print >> sys.stderr, "[T%d] Could not connect to server => result lost."

                except KeyError as key:
                    print >> sys.stderr, "[T%d] skipped %s: parameter %s missing." % \
                        (proc_id, conf.fname, key)
                except ValueError as msg:
                    print >> sys.stderr, "[T%d] skipped %s: %s." % \
                        (proc_id, conf.fname, msg)
                except Exception as err:
                    print >> sys.stderr, '[T%d] Unhandled exception %s' % (proc_id, err)
                    traceback.print_exc()
                if time is None:
                    try:
                        srv.report_failure(conf.result_token)
                    except IOError as err:
                        pass # ignore connection errors when reporting failures

                sys.stdout.flush()
                sys.stderr.flush()
            else:
                print '[T%d] Out of work.' % proc_id
                break

    except IOError as err:
        print >> sys.stderr, "[T%d] Could not connect to server '%s:%d'." % \
            (proc_id, server, confserver.DEFAULT_PORT if port is None else port)
    except KeyboardInterrupt:
        print '[T%d] Aborted.' % proc_id
    sys.stdout.flush()
    sys.stderr.flush()

def launch_client(server, port, parallel=False):
    if parallel:
        procs = [Process(target=client, args=(server, port, (x + 1)))
                 for x in xrange(cpu_count())]
        for p in procs:
            p.start()
        for p in procs:
            try:
                p.join()
            except KeyboardInterrupt:
                pass
    else:
        client(server, port)

def server_version_matches(server, port):
    try:
        s = confserver.connect_to_server(server, port)

        connect_retry_count = 0
        while True:
            try:
                v = s.get_version()
                break
            except IOError as err:
                connect_retry_count += 1
                if connect_retry_count > RETRY_LIMIT:
                    raise err # retry limit exceeded, give up
                else:
                    delay = retry_delay(connect_retry_count)
                    print "[!!] RPC attempt %d failed (%s), retrying after %.2fs..." \
                            % (connect_retry_count, err, delay)
                    sleep(delay)

        us = get_version_string()
        if v != us:
            print >> sys.stderr, "[!!] Server '%s:%d' runs version %s, we are at %s." % \
                (server, confserver.DEFAULT_PORT if port is None else port, v, us)
            return False
        else:
            return True
    except IOError as err:
        print >> sys.stderr, "[!!] Could not connect to server '%s:%d'." % \
            (server, confserver.DEFAULT_PORT if port is None else port)
        return False

from optparse import make_option as o
opts = [
    # output options
    o('-p', '--parallel', action='store_true', dest='parallel',
        help='Launch one compute process for each physical core.'),
]

defaults = {
    'parallel'  : False,
}

if __name__ == '__main__':
    socket.setdefaulttimeout(3)

    parser = optparse.OptionParser(option_list=opts)
    parser.set_defaults(**defaults)
    (options, servers) = parser.parse_args()
    for s in servers:
        if server_version_matches(s, None):
            launch_client(s, None, options.parallel)
