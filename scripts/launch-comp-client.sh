#!/bin/sh


SERVER=$1
REPO_DIR=$2

if [ ! -z "$REPO_DIR" ]
then
    cd $REPO_DIR
fi

HOST=`hostname`

nice python -u -m dist.compclient -p $1 >> compclient.$HOST.log 2>&1
