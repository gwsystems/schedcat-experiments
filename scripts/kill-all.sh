#!/bin/sh

# read configuration file
[ -f ./cluster-config.sh ] && source ./cluster-config.sh

# e.g., set CLUSTER_SSH_OPTS="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"

# read nodes.txt, stripping comments starting with '#'
sed -e 's/#.*//' -e '/^ *$/d' nodes.txt | while read SLAVE
do
    echo "$SLAVE:"
	ssh -n $CLUSTER_SSH_OPTS $SLAVE killall python
done
