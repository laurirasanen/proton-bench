#!/bin/python

import argparse
import os
import matplotlib.pyplot as plt


def graph_wukong():
    data_path = os.path.abspath("data/result_wukong")
    commits = []
    avg_fps = []
    max_fps = []
    min_fps = []
    p5_fps = []
    with open(data_path, "r") as data_file:
        lines = reversed(data_file.readlines())
        for l in lines:
            values = l.strip().split(" ")
            commits.append(values[1])
            avg_fps.append(int(values[2]))
            max_fps.append(int(values[3]))
            min_fps.append(int(values[4]))
            p5_fps.append(int(values[5]))

    plt.title("vkd3d-proton | Black Myth: Wukong Benchmark")
    plt.ylabel("FPS")
    plt.xlabel("Commit")

    plt.tick_params(axis="x", labelrotation=90)

    line_max = plt.plot(commits, max_fps, label="max")[0]
    line_avg = plt.plot(commits, avg_fps, label="avg")[0]
    line_p5 = plt.plot(commits, p5_fps, label="5% low")[0]
    line_min = plt.plot(commits, min_fps, label="min")[0]

    plt.legend(handles=[line_max, line_avg, line_p5, line_min], ncols=4)

    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-b",
        "--benchmark",
        default="wukong",
        choices=["wukong"],
        help="The benchmark to graph.",
    )
    args = parser.parse_args()

    if args.benchmark == "wukong":
        graph_wukong()
