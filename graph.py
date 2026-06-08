#!/bin/python

import argparse
import os
import matplotlib.pyplot as plt


def graph(args):
    data_path = os.path.abspath(args.data)
    commits = []
    avg_fps = []
    p1_fps = []
    p01_fps = []
    with open(data_path, "r") as data_file:
        lines = reversed(data_file.readlines())
        commit_pass = 1
        for l in lines:
            values = l.strip().split(" ")

            if args.avg_pass:
                commit = values[1].split("_")[0]
            else:
                commit = values[1]

            if (
                len(commits) > 0
                and commit == commits[-1]
            ):
                weight = 1.0 / commit_pass
                avg_fps[-1] = avg_fps[-1] * (1.0 - weight) + float(values[2]) * weight
                p1_fps[-1] = p1_fps[-1] * (1.0 - weight) + float(values[3]) * weight
                p01_fps[-1] = p01_fps[-1] * (1.0 - weight) + float(values[4]) * weight
                commit_pass += 1
            else:
                commit_pass = 1
                commits.append(commit)
                avg_fps.append(float(values[2]))
                p1_fps.append(float(values[3]))
                p01_fps.append(float(values[4]))

    plt.title(args.title)
    plt.ylabel("FPS")
    plt.xlabel("Commit")

    plt.tick_params(axis="x", labelrotation=90)
    plt.grid(color="#000000", alpha=0.25, linestyle=":", linewidth=1)

    line_avg = plt.plot(commits, avg_fps, label="avg")[0]
    line_p1 = plt.plot(commits, p1_fps, label="1% low")[0]
    line_p01 = plt.plot(commits, p01_fps, label="0.1% low")[0]

    plt.legend(handles=[line_avg, line_p1, line_p01], ncols=3)

    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--title",
        default="proton benchmark",
        help="Title of the graph.",
    )
    parser.add_argument(
        "-d",
        "--data",
        default="data/result_wukong",
        help="Data file for the benchmark",
    )
    parser.add_argument(
        "-a",
        "--avg_pass",
        action="store_const",
        const=True,
        help="Show the average of multiple passes instead of each one separately.",
    )
    args = parser.parse_args()
    graph(args)
