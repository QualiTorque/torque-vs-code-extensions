#!/bin/bash

ip=$1
hostname=$ip:$PORT

for (( ; ; ))
do
    sleep 1
    if [[ $(wget -q --spider -T1 -t1 ${hostname} && echo $?) == "0" ]] ; then
        echo 'connected to' ${hostname}
        exit 0
    else
        echo 'cannot connect to' ${hostname}
    fi
done
exit 1
