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

    while True:
        max_build_attempts = 3
        for i in range(max_build_attempts):
            if proton.rebuild():
                break
            print(f"make failed for {compat_layer} {func_commit()}")
            if i < max_build_attempts - 1:
                print(f"rewinding another {args.commit_interval} commits")
                func_rewind(args.commit_interval)
            else:
                print(f"max attempts exceeded")
                exit(1)

        bench.start(args.wait_time)
        bench.run(args.run_time)
        bench.stop()

        func_rewind(args.commit_interval)
