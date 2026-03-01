#!/bin/python

import argparse
import os

from benchmarks.wukong import BenchWukong
from benchmarks.baldurs import BenchBaldurs
from util import proton, input

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--commit_interval",
        default=50,
        type=int,
        help="Commit interval to rewind for each benchmark pass.",
    )
    parser.add_argument(
        "-l",
        "--commit_limit",
        default=0,
        type=int,
        help="Number of commits to check. 0 = unlimited",
    )
    parser.add_argument(
        "-b",
        "--benchmark",
        default="wukong",
        choices=["wukong", "baldurs"],
        help="The benchmark to run.",
    )
    parser.add_argument(
        "-w",
        "--wait_time",
        default=60,
        type=int,
        help="Game launch wait time.",
    )
    parser.add_argument(
        "-r",
        "--run_time",
        default=60,
        type=int,
        help="Game bench run time, if applicable.",
    )
    parser.add_argument(
        "-p",
        "--passes",
        default=1,
        type=int,
        help="Number of benchmark passes from the same commit.",
    )

    args = parser.parse_args()

    if args.benchmark == "wukong":
        bench = BenchWukong
        compat_layer = "vkd3d"
    elif args.benchmark == "baldurs":
        bench = BenchBaldurs
        compat_layer = "dxvk"
    else:
        error(f"unknown bench {args.benchmark}")

    data_dir = os.path.abspath("data")
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)
    mango_dir = os.path.abspath("data/mango")
    if not os.path.exists(mango_dir):
        os.mkdir(mango_dir)

    if compat_layer == "dxvk":
        func_rewind = proton.rewind_dxvk
        func_commit = proton.get_dxvk_commit
    else:
        func_rewind = proton.rewind_vkd3d
        func_commit = proton.get_vkd3d_commit

    commit_count = 0
    commit_pass = 0
    while True:
        max_build_attempts = 3
        for i in range(max_build_attempts):
            if proton.rebuild():
                break
            print(f"make failed for {compat_layer} {func_commit()}")
            if i < max_build_attempts - 1:
                print(f"rewinding another {args.commit_interval} commits")
                commit_pass = 0
                func_rewind(args.commit_interval)
            else:
                print(f"max attempts exceeded")
                exit(1)

        bench.start(args.wait_time)
        bench.run(args.run_time, commit_pass)
        bench.stop()

        commit_pass += 1
        if commit_pass < args.passes:
            continue
        commit_pass = 0

        commit_count += 1
        if args.commit_limit > 0 and commit_count >= args.commit_limit:
            print(f"Done checking {args.commit_limit} commits")
            break

        func_rewind(args.commit_interval)
