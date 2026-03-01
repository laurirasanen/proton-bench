#!/bin/python

import argparse
import os
import matplotlib.pyplot as plt


def graph_wukong():
    data_path = os.path.abspath("data/result_wukong")
    commits = []
    avg_fps = []
    p1_fps = []
    p01_fps = []
    with open(data_path, "r") as data_file:
        lines = reversed(data_file.readlines())
        for l in lines:
            values = l.strip().split(" ")
            commits.append(values[1])
            avg_fps.append(float(values[2]))
            p1_fps.append(float(values[3]))
            p01_fps.append(float(values[4]))

    plt.title("vkd3d-proton | Black Myth: Wukong Benchmark")
    plt.ylabel("FPS")
    plt.xlabel("Commit")

    plt.tick_params(axis="x", labelrotation=90)
    plt.grid(color="#000000", alpha=0.25, linestyle=":", linewidth=1)

    line_avg = plt.plot(commits, avg_fps, label="avg")[0]
    line_p1 = plt.plot(commits, p1_fps, label="1% low")[0]
    line_p01 = plt.plot(commits, p01_fps, label="0.1% low")[0]

    plt.legend(handles=[line_avg, line_p1, line_p01], ncols=3)

    plt.show()


def graph_baldurs():
    data_path = os.path.abspath("data/result_baldurs")
    commits = []
    avg_fps = []
    p1_fps = []
    p01_fps = []
    with open(data_path, "r") as data_file:
        lines = reversed(data_file.readlines())
        for l in lines:
            values = l.strip().split(" ")
            commits.append(values[1])
            avg_fps.append(float(values[2]))
            p1_fps.append(float(values[3]))
            p01_fps.append(float(values[4]))

    plt.title("dxvk | Baldurs Gate 3 Benchmark")
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
        "-b",
        "--benchmark",
        default="wukong",
        choices=["wukong", "baldurs"],
        help="The benchmark to graph.",
    )
    args = parser.parse_args()

    if args.benchmark == "wukong":
        graph_wukong()
    elif args.benchmark == "baldurs":
        graph_baldurs()
