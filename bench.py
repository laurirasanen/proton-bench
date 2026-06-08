#!/bin/python

import argparse
import os

from benchmarks.apitrace import BenchApitrace
from benchmarks.baldurs import BenchBaldurs
from benchmarks.wukong import BenchWukong

from util import input, steam
from util.proton import Proton

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
        choices=["apitrace", "baldurs", "wukong"],
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
    parser.add_argument(
        "-t",
        "--trace",
        default="",
        type=str,
        help="Apitrace file to bench."
    )
    parser.add_argument(
        "-s",
        "--skip_build",
        action="store_const",
        const=True,
        help="Skip proton build. Useful for single pass tests with already built proton."
    )

    args = parser.parse_args()

    data_dir = os.path.abspath("data")
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)
    mango_path = os.path.abspath("data/mango")
    if not os.path.exists(mango_path):
        os.mkdir(mango_path)

    proton_src = Proton("../proton/proton")
    proton_dist = Proton(os.path.join(steam.get_compat_tools_dir(), "bleeding-edge-local", "proton"))

    if args.benchmark == "wukong":
        bench = BenchWukong(proton_src)
        compat_layer = "vkd3d"
    elif args.benchmark == "baldurs":
        bench = BenchBaldurs(proton_src, mango_path)
        compat_layer = "dxvk"
    elif args.benchmark == "apitrace":
        bench = BenchApitrace(proton_src, proton_dist, args.trace, mango_path)
        compat_layer = "dxvk"
    else:
        error(f"unknown bench {args.benchmark}")

    if compat_layer == "dxvk":
        func_rewind = proton_src.rewind_dxvk
        func_commit = proton_src.get_dxvk_commit
    else:
        func_rewind = proton_src.rewind_vkd3d
        func_commit = proton_src.get_vkd3d_commit

    commit_count = 0
    commit_pass = 0
    while True:
        if not args.skip_build:
            max_build_attempts = 3
            for i in range(max_build_attempts):
                if proton_src.rebuild():
                    break
                print(f"make failed for {compat_layer} {func_commit()}")
                if i < max_build_attempts - 1:
                    print(f"rewinding another {args.commit_interval} commits")
                    commit_pass = 0
                    func_rewind(args.commit_interval)
                else:
                    print(f"max attempts exceeded")
                    exit(1)

        print(f"starting {args.benchmark} pass {commit_pass} for {compat_layer} commit {func_commit()}")
        bench.start(args.wait_time)
        bench.run(args.run_time, commit_pass)
        bench.stop()

        commit_pass += 1
        if commit_pass < args.passes:
            continue

        commit_pass = 0
        commit_count += 1

        if args.skip_build:
            print("Done checking single build")
            break

        if args.commit_limit > 0 and commit_count >= args.commit_limit:
            print(f"Done checking {args.commit_limit} commits")
            break

        func_rewind(args.commit_interval)
