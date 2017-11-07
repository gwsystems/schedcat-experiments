from datetime import datetime

from toolbox.io import one_of
from toolbox.io import write_std_header, write_data, write_runtime

import exp.rtas18

experiment_modules = [
    exp.rtas18,
]

EXPERIMENTS = {
    # name  =>  run_exp(config)
    "ping" : lambda conf: conf.output.write("pong\n"),
}

CONFIG_GENERATORS = {
    # name  =>  generate_configs()
    "ping" : lambda _: [],
}

for mod in experiment_modules:
    EXPERIMENTS.update(mod.EXPERIMENTS)
    CONFIG_GENERATORS.update(mod.CONFIG_GENERATORS)

# experiment interface:
#
#   run_XXX_experiment(configuration)
#
# Semantics: run the experiment described by input_config and store
# the results in the file-like object conf.output, which could be either
# an actual file, a socket, or a StringIO object. The actual schedulability
# experiment should not care.

def run_config(conf):
    conf.check('experiment',   type=one_of(EXPERIMENTS.keys()))
    print "\033[1;32;40m configuration:", conf, "\033[0m"

    experiment_driver = EXPERIMENTS[conf.experiment]

    write_std_header(conf.output, conf=conf)
    start  = datetime.now()
    experiment_driver(conf)
    end = datetime.now()

    write_runtime(conf.output, start, end)
    return end - start
