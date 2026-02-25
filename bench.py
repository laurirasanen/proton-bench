#!/bin/python

import argparse
import os

from benchmarks.wukong import BenchWukong
from util import proton, input

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--commit_interval",
        default=100,
        help="Commit interval to rewind for each benchmark pass.",
    )
    parser.add_argument(
        "-b",
        "--benchmark",
        default="wukong",
        choices=["wukong"],
        help="The benchmark to run.",
    )
    parser.add_argument(
        "-w",
        "--wait_time",
        default=60,
        help="Game launch wait time.",
    )
    args = parser.parse_args()

    if args.benchmark == "wukong":
        bench = BenchWukong
    else:
        error(f"unknown bench {args.benchmark}")

    data_dir = os.path.abspath("data")
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)

    while True:
        max_build_attempts = 3
        for i in range(max_build_attempts):
            if proton.rebuild():
                break
            print(f"make failed for vkd3d {proton.get_vkd3d_commit()}")
            if i < max_build_attempts - 1:
                print(f"rewinding another {args.commit_interval} commits")
                proton.rewind_vkd3d(args.commit_interval)
            else:
                print(f"max attempts exceeded")
                exit(1)

        bench.start(args.wait_time)
        bench.run()
        bench.stop()

        proton.rewind_vkd3d(args.commit_interval)
