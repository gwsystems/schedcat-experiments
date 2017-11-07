import os
import sys
import optparse

from multiprocessing import Pool as process_pool
from datetime import datetime
from glob import glob
import random
import numpy

from toolbox.io import load_config, atomic_create_file, ensure_dir_exists
from exp import run_config, CONFIG_GENERATORS

def process_file(label, fname, overwrite, samples=None):
    random.seed()
    numpy.random.seed()
    try:
        config = load_config(fname)
        if samples:
            config.samples = samples
        ensure_dir_exists(config.output_file)
        if overwrite:
            config.output = open(config.output_file, 'w')
        else:
            config.output = atomic_create_file(config.output_file)
        if config.output:
            print "%s %s -> %s (started at %s)" \
             % (label, fname, config.output_file,
                datetime.now())
            time = run_config(config)
        else:
            print "%s skipped %s: output file '%s' exists." % \
                (label, fname, config.output_file)
    except IOError as msg:
        print "%s skipped %s: could not load config (%s)." % \
            (label, fname, msg)
    except KeyError as key:
        print "%s skipped %s: parameter %s missing." % \
            (label, fname, key)
    except ValueError as msg:
        print "%s skipped %s: %s." % \
            (label, fname, msg)
    sys.stdout.flush()
    sys.stderr.flush()

def process_files(files, parallel, overwrite, samples=None):
    if not files:
        print "usage: python -m exp [OPTIONS|-h] <config file>+ "
    else:
        output = None
        try:
            if parallel:
                procs = process_pool()
                ops   = []
            for i, f in enumerate(files):
                label = "[%d/%d]" % (i + 1, len(files))
                if parallel:
                    ops.append(procs.apply_async(process_file, [label, f, overwrite, samples]))
                else:
                    process_file(label, f, overwrite, samples)
            if parallel:
                procs.close()
                for op in ops:
                    # use timeout as a workaround:
                    # http://stackoverflow.com/questions/1408356/keyboard-interrupts-with-pythons-multiprocessing-pool
                    op.get(100000000)
        except KeyboardInterrupt:
            print 'Aborted.'
            if parallel:
                procs.terminate()
        print 'Terminating.'

from optparse import make_option as o
opts = [
    # output options
    o('-p', '--parallel', action='store_true', dest='parallel'),
    o('-s', '--shuffle-input', action='store_true', dest='shuffle'),
    o('-f', '--force', action='store_true', dest='overwrite'),
    o('-d', '--input-dir', action='store', dest='input_dir',
      help='Specify directory to search for input files'),
    o('-o', '--output-dir', action='store', dest='output_dir'),
    o('-g', '--generate', action='store', dest='generate'),
    o(None, '--samples', action='store', dest='samples',
      help='Override number of samples in input config(s).'),
]

defaults = {
    'parallel'   : False,
    'input_dir'  : None,
    'output_dir' : None,
    'shuffle'    : False,
    'overwrite'  : False,
    'generate'   : None,
    'samples'    : None,
}

def generate_configs(options, name):
    print 'Generating %s configurations...' % name
    for (fname, conf) in CONFIG_GENERATORS[name](options):
        if 'output_file' in conf:
            if options.output_dir:
                conf.output_file = os.path.join(options.output_dir,
                                                conf.output_file)
            else:
                conf.output_file = os.path.join(name, conf.output_file)
            conf.output_file = os.path.join('output', conf.output_file)

        fname = fname + '.conf'
        if options.input_dir is None:
            fname = os.path.join(name, fname)
        else:
            fname = os.path.join(options.input_dir, fname)
        fname = os.path.join('confs', fname)
        ensure_dir_exists(fname)
        if not 'experiment' in conf:
            conf.experiment = name
        conf.write_to_file(fname)

def generator_main(options):
    if options.generate in CONFIG_GENERATORS:
        generate_configs(options, options.generate)
    elif 'all' == options.generate:
        for key in CONFIG_GENERATORS:
            generate_configs(options, key)
    else:
        if options.generate != 'help':
            print "Unknown experiment: '%s'" % options.generate
        print "Available config generators: ",
        print " ".join(sorted(CONFIG_GENERATORS.keys()))

def experiment_main(options):
    if options.input_dir:
        extra_files = glob(os.path.join(options.input_dir, '*.conf'))
        files.extend(extra_files)
    if options.shuffle:
        random.shuffle(files)
    if files:
        process_files(files, options.parallel, options.overwrite, options.samples)

if __name__ == '__main__':
    parser = optparse.OptionParser(option_list=opts)
    parser.set_defaults(**defaults)
    (options, files) = parser.parse_args()
    print "\033[1;33;40m command options: ", options
    print "\033[1;34;40m conf file:", files, "\033[0m"
    if options.generate is None:
        experiment_main(options)
    else:
        generator_main(options)
