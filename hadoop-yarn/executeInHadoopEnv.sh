#!/bin/sh

. $1
echo $HADOOP_PREFIX
shift
eval $@
