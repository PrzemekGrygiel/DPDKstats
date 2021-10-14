#! /usr/bin/env python

import psutil
import operator
import argparse
import subprocess
import sys
import os
import warnings
import time
import re


def get_dpdk_vrouter_pid():
    process_name = "contrail-vrouter-dpdk"
    pid = None
    for proc in psutil.process_iter():
        if process_name in proc.name():
            return proc.pid
    print("/!\ DPDK vRouter is not present!")
    sys.exit(1)


def get_core_n():
    vrouter_core_n = 0
    p = psutil.Process(get_dpdk_vrouter_pid())
    for th in p.threads():
        x = psutil.Process(th.id)
        if len(x.cpu_affinity()) != psutil.cpu_count():
            vrouter_core_n = vrouter_core_n + 1
    if vrouter_core_n == 0:
        print("/!\ DPDK vRouter is not present!")
        sys.exit(1)
    return vrouter_core_n


def parse_vif(vif, core):
    cmd = "vif --get {} --core {} | egrep '(TX|RX) packets'".format(vif, core)
    output = subprocess.check_output(["bash", "-c", cmd])
    out = []
    out = output.replace(":", " ").split()
    tx = [int(out[13]), int(out[15]), int(out[17])]
    rx = [int(out[4]), int(out[6]), int(out[8])]
    return tx, rx


def get_cpu_load_all(vif, core_n, timer):
    list1_tx = []
    list1_rx = []
    list2_tx = []
    list2_rx = []
    rx = []
    tx = []
    for i in range(core_n):
        t, r = parse_vif(vif, str(i + 10))
        list1_rx.extend(r)
        list1_tx.extend(t)
    time.sleep(timer)
    for i in range(core_n):
        t, r = parse_vif(vif, str(i + 10))
        list2_rx.extend(r)
        list2_tx.extend(t)
    for i in map(operator.sub, list2_rx, list1_rx):
        rx.append(i / int(timer))
    for i in map(operator.sub, list2_tx, list1_tx):
        tx.append(i / int(timer))
    return tx, rx


def all_vifs(vif, timer, core_n):
    table_length = 72
    cmd = "vif -l|awk '/tap/{print $1}' | cut -d'/' -f2"
    out = subprocess.check_output(["bash", "-c", cmd]).replace(":", " ").split()
    out.append(0)
    core = [0] * core_n
    tran = [0] * core_n
    recv = [0] * core_n
    print("-" * (table_length * 2 - 1))
    for j in out:
        tx, rx = get_cpu_load_all(j, core_n, timer)
        for i in range(core_n):
            print(
                "| VIF {:<3} |Core {:<3}| TX pps: {:<10}| RX pps: {:<10}| TX bps: {:<10}| RX bps: {:<10}| TX error: {:<10}| RX error {:<10}| ".format(
                    j,
                    i + 1,
                    tx[i * 3],
                    rx[i * 3],
                    tx[i * 3 + 1] * 8,
                    rx[i * 3 + 1] * 8,
                    tx[i * 3 + 2],
                    rx[i * 3 + 2],
                )
            )
            tran[i] = tran[i] + tx[i * 3]
            recv[i] = recv[i] + rx[i * 3]
            core[i] = core[i] + tx[i * 3] + rx[i * 3]
    print("-" * (table_length * 2 - 1))
    print("-" * table_length)
    print("|" + "pps per Core".center(table_length - 2) + "|")
    print("-" * table_length)
    for cpu in range(core_n):
        print(
            "|Core {:<3}|TX + RX pps: {:<10}| TX pps {:<10}| RX pps {:<10}|".format(
                cpu + 1, core[cpu], tran[cpu], recv[cpu]
            )
        )
    print("-" * table_length)
    print(
        "|Total   |TX + RX pps: {:<10}| TX pps {:<10}| RX pps {:<10}|".format(
            reduce(lambda x, y: x + y, core),
            reduce(lambda x, y: x + y, tran),
            reduce(lambda x, y: x + y, recv),
        )
    )
    print("-" * table_length)


def not_all_vifs(vif, timer, core_n):
    table_length = 133
    tx, rx = get_cpu_load_all(vif, core_n, timer)
    total = [0] * 6
    print("-" * table_length)
    for i in range(core_n):
        total[0] += tx[i * 3]
        total[1] += rx[i * 3]
        total[2] += tx[i * 3 + 1]
        total[3] += rx[i * 3 + 1]
        total[4] += tx[i * 3 + 2]
        total[5] += rx[i * 3 + 2]
        print(
            "|Core {:<3}| TX pps: {:<10}| RX pps: {:<10}| TX bps: {:<10}| RX bps: {:<10}| TX error: {:<10}| RX error {:<10}|".format(
                i + 1,
                tx[i * 3],
                rx[i * 3],
                tx[i * 3 + 1],
                rx[i * 3 + 1],
                tx[i * 3 + 2],
                rx[i * 3 + 2],
            )
        )
        print("-" * table_length)
    print(
        "|Total   | TX pps: {:<10}| RX pps: {:<10}| TX bps: {:<10}| RX bps: {:<10}| TX error: {:<10}| RX error {:<10}|".format(
            total[0], total[1], total[2] * 8, total[3] * 8, total[4], total[5]
        )
    )
    print("-" * table_length)


parser = argparse.ArgumentParser()
parser.add_argument(
    "-v", "--vif", help="vif number - only number after /", type=int, default=0
)
parser.add_argument(
    "-t", "--time", help="time for test default 3 seconds", type=int, default=3
)
parser.add_argument(
    "-c", "--cpu", help="number of CPUs - default 6", type=int, default=get_core_n()
)
parser.add_argument(
    "--all",
    help="total CPU utilisation from all VIFs",
    action="store_true",
    default="False",
)
args, _ = parser.parse_known_args(sys.argv[1:])

if args.all == True:
    all_vifs(args.vif, args.time, args.cpu)
else:
    not_all_vifs(args.vif, args.time, args.cpu)
