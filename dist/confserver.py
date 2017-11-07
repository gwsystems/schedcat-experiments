from __future__ import absolute_import

import os
import sys
import optparse
import hashlib
from glob import glob

import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer

from toolbox.io import Config, ensure_dir_exists
from toolbox.git import get_version_string

options = None

DEFAULT_PORT = 5112
DEFAULT_HOST = '' # empty string <=> bind to all interfaces

def conf_output_exists(conf_file, output_dir=None):
    try:
        conf = Config.from_file(conf_file)
        conf.check('output_file')
        output = conf.output_file
        if output_dir:
            output = os.path.join(output_dir, output)
        if os.path.exists(output):
            return True
        else:
            return False
    except KeyError as err:
            print >> sys.stderr, "Configuration key %s missing in '%s'." % (err, conf_file)
    except IOError as err:
        print >> sys.stderr, "Could not process '%s': %s." % (conf_file, err)
    return None

def filter_existing(files, output_dir=None):
    return [cf for cf in files if not conf_output_exists(cf, output_dir) is True]

def load_with_hash(path):
    conf = Config.from_file(path)
    h = hashlib.md5()
    h.update(open(path, "r").read())
    conf.result_token = h.hexdigest()
    if not 'fname' in conf:
        conf.fname = path
    return conf

class ConfRepository(object):
    def __init__(self, filelist):
        self.files = sorted(filelist)
        self.next  = 0
        self.completed = []
        self.version = get_version_string()
        self.expected_results = {}
        self.stop_cycling = False
        self.cycles = 0

    def get_version(self):
        return self.version

    def request_termination(self):
        print 'Termination requested.'
        self.stop_cycling = True

    def confirm_completion(self, fname, ok=True):
        self.completed.append(fname)
        print '(%d/%d) %s %s, in-progress: %d, unassigned: %d' % \
            (len(self.completed), len(self.files), fname,
             "completed" if ok else "failed",
             len(self.expected_results),
             len(self.files) - self.next)

    def get_conf_file(self, client=None):
        if self.next < len(self.files):
            f = self.files[self.next]
            self.next += 1
            client = ' -> %s' % client if client else ''
            print '[%d/%d] %s%s' % (self.next, len(self.files), f, client)
            if options.cycle and not self.stop_cycling:
                self.next = self.next % len(self.files)
                if not self.next:
                    self.cycles += 1
                    print '::: Completed %d cycles.' % self.cycles
            return f
        else:
            print 'Work queue empty.'
            return None

    def get_conf_dict(self, client=None):
        fname = self.get_conf_file(client)
        if fname:
            conf = load_with_hash(fname)
            if options.cycle and 'samples' in conf:
                conf.samples = options.cycle
            if 'output_file' in conf:
                self.expected_results[conf.result_token] = conf.output_file
            return dict(conf)
        else:
            return None

    # totally insecure... use only on trusted networks
    def report_results(self, token, results):
        if token in self.expected_results:
            fname = self.expected_results[token]
        else:
            print 'report_results: unexpected result token: %s' % token
            # Let's store whatever they sent us. Perhaps it was a bug in
            # the server or a restart and we don't want to lose the result.
            fname = "unexpected-data/%s.csv" % token

        ensure_dir_exists(fname)
        if options.cycle:
            # append when cycling through configs
            f = open(fname, "a")
        else:
            # overwrite otherwise
            f = open(fname, "w")
            del self.expected_results[token]
        f.write(results)
        f.close()
        self.confirm_completion(fname)


    def report_failure(self, token):
        if token in self.expected_results:
            fname = self.expected_results[token]
            del self.expected_results[token]
            self.confirm_completion(fname, False)
        else:
            print 'report_failure: unexpected result token: %s' % token


def connect_to_server(host=None, port=None):
    if host is None:
        host = 'localhost'
    if port is None:
        port = DEFAULT_PORT
    url = 'http://%s:%d' % (host, port)
    return xmlrpclib.ServerProxy(url)

def start_server(files, host=None, port=None):
    if host is None:
        host = DEFAULT_HOST
    if port is None:
        port = DEFAULT_PORT
    repo = ConfRepository(files)

    srv = SimpleXMLRPCServer((host, port), allow_none=True)
    srv.register_introspection_functions()
    srv.register_instance(repo)
    try:
        print '%d configurations waiting for clients...' % (len(files))
        srv.serve_forever()
    except KeyboardInterrupt:
        print '\nShutting down.'

from optparse import make_option as o
opts = [
    o('-p', '--port', action='store', dest='port', type='int'),
    o(None, '--host', action='store', dest='host'),
    o('-d', '--input-dir', action='append', dest='input_dir',
      help='Specify directory to search for input files'),
    o('-f', '--force', action='store_true', dest='force'),
    o('-o', '--output-dir', action='store', dest='output_dir'),
    o('-s', '--sort', action='store_true', dest='sort_input'),
    o(None, '--list-missing', action='store_true', dest='list_missing'),
    o('-c', '--cycle', action='store', type='int', dest='cycle',
      help='compute everything repeatedly until interrupted'),
    o(None, '--stop', action='store_true', dest='cmd_stop'),
]

defaults = {
    'host'       : DEFAULT_HOST,
    'port'       : DEFAULT_PORT,
    'input_dir'  : [],
    'output_dir' : None,
    'force'      : False,
    'sort_input' : False,
    'cycle'      : False,
    'cmd_stop'   : False,
}

if __name__ == '__main__':
    parser = optparse.OptionParser(option_list=opts)
    parser.set_defaults(**defaults)
    (options, files) = parser.parse_args()

    if options.cmd_stop:
        try:
            srv = connect_to_server(options.host, options.port)
            srv.request_termination()
        except IOError as err:
            print 'Connection failed: %s' % err
        sys.exit(0)

    for dir in options.input_dir:
        print 'Looking for input files in %s...' % dir
        extra_files = glob(os.path.join(dir, '*.conf'))
        files.extend(extra_files)
    if options.sort_input:
        files.sort()
    if not options.force:
        print 'Filtering inputs for which outputs exists...'
        files = filter_existing(files, options.output_dir)
        if options.list_missing:
            for f in files:
                print f
    if options.cycle:
        print 'Cycling through all configs in chunks of %d.' % options.cycle
    start_server(files, options.host, options.port)
