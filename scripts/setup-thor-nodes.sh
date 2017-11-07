#!/bin/bash

# read configuration file
[ -f ./cluster-config.sh ] && source ./cluster-config.sh

# Where do we find sched-experiments on the remote cluster?
if [ -z "$CLUSTER_REPO_DIR" ]
then
    # default: in the home/src directory
    CLUSTER_REPO_DIR=~/src/sched-experiments
fi

# Where is the distribution server running?
if [ -z "$CONFSERVER_HOST" ]
then
    # default: on this machine
    CONFSERVER_HOST=`hostname`
    echo "Defaulting to CONFSERVER_HOST=$CONFSERVER_HOST."
fi

# read nodes.txt, stripping comments starting with '#'
for CLIENT in `sed -e 's/#.*//' -e '/^ *$/d' nodes.txt`
do
    # launch client
    echo "Launching on $CLIENT: $CLUSTER_REPO_DIR/scripts/launch-comp-client.sh $CONFSERVER_HOST $CLUSTER_REPO_DIR"
	ssh -n $CLUSTER_SSH_OPTS $CLIENT screen -d -m $CLUSTER_REPO_DIR/scripts/launch-comp-client.sh $CONFSERVER_HOST $CLUSTER_REPO_DIR

if [ -z "$LAUNCH_DELAY" ]
then
    sleep $LAUNCH_DELAY
fi

done
