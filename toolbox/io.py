# I/O helpers---formatting, etc.

import sys
import csv
import os
import errno

from datetime import datetime

import toolbox.git as git

def cmp_sym(a, b):
    if a < b:
        return '+'
    elif a > b:
        return '-'
    else:
        return '='

def list_delta_symbols(lst):
    return ''.join([cmp_sym(prev, next) for (prev, next) in zip(lst, lst[1:])])

def print_row(row, f=sys.stdout, col_width=14, col_sep=" ",
              prepend='', append='\n'):
    field_fmt = "%%%ds" % col_width
    f.write(prepend)
    f.write(col_sep.join([field_fmt % str(field) for field in row]))
    f.write(append)
    f.flush()

def print_rows(rows, *args, **kargs):
    for r in rows:
        print_row(r, *args, **kargs)

def output_table(data, title=None, col_width=None, prepend=' ',
                 out=sys.stdout):
    if col_width is None:
        col_width = max([len(x) for x in title]) + 3
    if title:
        print_row(title, f=out, prepend='#', col_width=col_width)
    print_rows(data, f=out, col_sep=' ', prepend=prepend, col_width=col_width)

def dotted(label, width=10):
    return label + '.' *  (width - len(label))

def header(label, width=78, fill="#", space=" "):
    n = len(label) + 2 * len(space)
    l = (width - n) / 2
    r = width - n - l
    return fill * l + space + label + space + fill * r

def write_std_header(f, exp_name=None, conf=None, width=15):
    if exp_name or conf:
        f.write('%s\n' % header('CONFIGURATION'))
    if exp_name:
        f.write('# %s: %s\n' % (dotted('Experiment', width), exp_name));
    if conf:
        for key in sorted(conf):
            if key != 'output':
                f.write('# %s: %s\n' % (dotted(key, width), str(conf[key])));
    f.write('%s\n' % header('ENVIRONMENT'))
    head     = git.get_head()
    modified = git.modified_files()
    f.write("# %s: %s%s\n" % \
            (dotted('Version', width),
             head if head else "<unkown>",
             '+' if modified else ''))
    f.write('# %s: %s\n' % (dotted('CWD', width), os.getcwd()))
    f.write('# %s: %s\n' % (dotted('Host', width), get_hostname()))
    f.write('# %s: %s\n' % (dotted('Python', width), sys.version.replace('\n', ' ')))

def write_data(f, data, title=None, col_width=None):
    f.write('%s\n' % header('DATA'))
    output_table(data, title, col_width, out=f)

def write_runtime(f, start, end, width=15):
    f.write('%s\n' % header('RUN'))
    f.write('# %s: %s\n' % (dotted('Started', width), start))
    f.write('# %s: %s\n' % (dotted('Completed', width), end))
    f.write('# %s: %s\n' % (dotted('Duration', width), end - start))


def get_arg(index, default, list=sys.argv):
    "safely retrieve command line argument"
    if len(list) > index:
        return list[index]
    else:
        return default

def get_env(key, default):
    return os.environ[key] if key in os.environ else default

def get_hostname():
    return os.uname()[1]

def load_csv(fname, convert=lambda x: x):
    f = open(fname)
    d = [[convert(x) for x in row]
         for row in csv.reader(f)]
    f.close()
    return d

def atomic_create_file(fname):
    """Atomically create a file. Returns None if it already exists."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(fname, flags)
        return os.fdopen(fd, 'w')
    except OSError as err:
        if err.errno == errno.EEXIST:
            # Somebody else beat us to it.
            return None
        else:
            # Huh, something else went wrong?
            raise # rethrow

def ensure_dir_exists(fname):
    dir = os.path.dirname(fname)
    if dir and not os.path.exists(dir):
        try:
            os.makedirs(dir)
        except OSError as err:
            if err.errno == errno.EEXIST:
                # Somebody else beat us to it. Nothing to do.
                pass
            else:
                # Something else went wrong?
                raise # rethrow

def one_of(collection):
    def is_one_of(val):
        if not val in collection:
            raise ValueError, "must be one of %s" % sorted(collection)
        return val
    return is_one_of

def boolean_flag(val):
    val = val.strip().lower()
    if val in ['1', 'true', 'yes']:
        return True
    elif val in ['0', 'false', 'no']:
        return False
    else:
        raise ValueError, "must be either 1|true|yes or 0|false|no"


class Config(dict):
    """Simple dictionary wrapper representing configuration files
    with default options.
    """

    @staticmethod
    def from_file(fname):
        c = Config()
        f = open(fname, 'r')
        for line in f.readlines():
            if line.strip() and line[0] != '#':
                kv = line.split('=', 1)
                k = kv[0].strip()
                v = kv[1].strip() if len(kv) > 1 else None
                c[k] = v
        f.close()
        return c

    def get(self, key, default=None, type=None, required=False):
        if key in self:
            if type is None:
                return self[key]
            else:
                try:
                    return type(self[key])
                except ValueError as msg:
                    raise ValueError, "parameter '%s' malformed (%s)" % (key, msg)
        elif not required:
            return default
        else:
            raise KeyError, key

    def check(self, key, default=None, type=None, min=None, max=None):
        if key in self:
            if not type is None:
                try:
                    self[key] = type(self[key])
                    if not min is None and self[key] < min:
                        raise ValueError, "parameter '%s' less than minimum (%s)" % (key, min)
                    if not max is None and self[key] > max:
                        raise ValueError, "parameter '%s' exceeds maximum (%s)" % (key, min)
                except ValueError as msg:
                    raise ValueError, "parameter '%s' malformed (%s)" % (key, msg)
            return True
        elif not default is None:
            self[key] = default
            return False
        else:
            raise KeyError, key

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        del self[key]

    def write_to_file(self, fname):
        f = open(fname, 'w')
        for key in sorted(self):
            f.write("%s = %s\n" % (str(key), str(self[key])))
        f.close()

load_config = Config.from_file
