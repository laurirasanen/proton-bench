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
    args = parser.parse_args()

    if args.benchmark == "wukong":
        bench = BenchWukong
    else:
        error(f"unknown bench {args.benchmark}")

    data_dir = os.path.abspath("data")
    if os.path.exists(data_dir):
        os.mkdir(data_dir)

    while True:
        proton.rebuild()

        bench.start()
        bench.run()
        bench.stop()

        proton.rewind_vkd3d(args.commit_interval)
