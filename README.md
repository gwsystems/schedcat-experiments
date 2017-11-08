
# Schedulability Experiments Framewok
## Dependencies & Compilation
### Packages
To compile and run the experiments, the following standard packages are required:

* Python 2.7
* Python NumPy Library
* Python SciPy LIbrary
* GNU Make (make)
* SWIG 3.0 (swig)
* GNU C++ compiler (g++)
* GNU Multiple Precision Arithmetic Library (libgmp)
### Installing a Linear Program Solver
A linear program solver is also required. [IBM CPLEX](http://www-01.ibm.com/software/commerce/optimization/cplex-optimizer/)  is supported. 
IBM CPLEX is commercial software, but free academic licenses are available.

We test the file ```cplex_studio12.7.1.linux-x86-64.bin``` on Ubuntu 14.04 (x86_64). The filename may change when newer versions of CPLEX are released.
To install CPLEX, execute the following commands
```
$ chmod +x cplex_studio12.7.1.linux-x86-64.bin
# ./cplex_studio12.7.1.linux-x86-64.bin
```
### Compiling SchedCAT
[SchedCAT](https://github.com/gwsystems/schedcat) provides lots of schedulability test utilities. After set up and update the SchedCAT submodule, you can compile it by running
```
$ cd lib/schedcat
$ make
$ cd ../../
```
**Note:** The makefiles try to automatically locate an installation of CPLEX. In some cases this procedure may fail and the build process terminates with the error “No LP Solver available”. If this happens, the CPLEX path must be manually configured with the following command:
```
$ export CPLEX_PATH=<your_CPLEX_path_here>
```
For instance, the above tested CPLEX is installed with default options, and the path is configured as follows:
```
$ export CPLEX_PATH=/opt/ibm/ILOG/CPLEX_Studio1271
```
In addition, some installations of CPLEX may not create symbolic links of the CPLEX static libraries into the /usr/lib/ directory. Those links are created on the teste machine with the following commands:
```
# ln -s <your_CPLEX_path_here>/concert/lib/x86-64_linux/static_pic/libconcert.a /usr/lib/libconcert.a
# ln -s <your_CPLEX_path_here>/cplex/lib/x86-64_linux/static_pic/libcplex.a /usr/lib/libcplex.a 
# ln -s <your_CPLEX_path_here>/cplex/lib/x86-64_linux/static_pic/libilocplex.a /usr/lib/libilocplex.a 
```
## Schedulability Experiments and Configurations
Before launching the experiment, it is necessary to set an environmental variable for SchedCAT:
```
export PYTHONPATH=$PYTHONPATH:./lib/schedcat
export CPLEX_PATH=/opt/ibm/ILOG/CPLEX_Studio1271
```
A configuration represents all the settings for the task set generators and defines the experiment to be performed.

The directory ```./confs``` contains a .conf file for each configuration tested in the experiments. The name of each .conf file contains key-value pairs with the values for (most of) the parameters.

As example, a configuration file named
```
./confs/read_len/rn=10_wl=100_u=75_c=20_wn=10.conf
```
corresponds to a configuration
* 10 readers (rn=10)
* 10 writers (wn=10)
* 20 cores (c=20)
* 0.75 task set utilization (u=75)
* write request length of 10 (wl=10)

The following command runs the schedulability experiment for a specific configuration:
```
$ python -m exp -f ./confs/<configuration file>
```
For example
```
$ python -m exp -f ./confs/unit_test.conf
$ python -m exp -f ./confs/read_len/rn=10_wl=100_u=75_c=20_wn=10.conf
```
The experiment results are written to a output file in ```./output```
