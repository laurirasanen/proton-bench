"""
Steam:
Select local proton build as the compatibility tool.
Launch arguments:
gamescope -W 1920 -w 1920 -H 1080 -h 1080 --force-grab-cursor -- %command%
"""

import os
import time
import glob
import json

from util import steam, input, proton


class BenchWukong:
    appid = 3132990

    def start(wait_time):
        steam.launch_game(BenchWukong.appid)
        time.sleep(wait_time)

    def stop():
        os.system("killall --signal SIGTERM b1_benchmark.exe")
        os.system("killall --signal SIGTERM gamescope-wl")
        time.sleep(3)
        os.system("killall --signal SIGKILL b1_benchmark.exe")
        os.system("killall --signal SIGKILL gamescope-wl")
        time.sleep(1)

    def run():
        client = input.InputClient.create()
        client.connect()
        client.sleep(1)

        # press any button to start
        key_enter = 28
        client.keyboard_key(key_enter)
        client.sleep(3)

        # click 'Benchmark'
        client.pointer_motion_absolute(150.0, 480.0)
        client.sleep(0.5)
        btn_left = 272
        client.mouse_button(btn_left)
        client.sleep(1)

        # 'Confirm'
        client.keyboard_key(key_enter)
        client.sleep(1)

        client.disconnect()

        # wait for bench to finish
        time.sleep(160)

        # find the latest bench result
        benchmark_dir = steam.get_wine_user_dir(
            BenchWukong.appid,
            "AppData",
            "Local",
            "Temp",
            "b1",
            "BenchMarkHistory",
            "Tool",
        )
        result_files = glob.glob("*", root_dir=benchmark_dir)
        assert len(result_files) > 0, f"No bench results in {benchmark_dir}"
        # the file names should seconds since epoch
        latest_filename = None
        for f in result_files:
            if latest_filename is None or int(f) > int(latest_filename):
                latest_filename = f

        output_path = os.path.abspath("data/result_wukong")

        # sanity check
        if os.path.exists(output_path):
            with open(output_path, "r") as output_file:
                lines = output_file.readlines()
            for l in lines:
                if l.startswith(latest_filename):
                    # latest bench run failed and we're trying to append same result again...
                    assert False, (
                        f"result {latest_filename} already included in results"
                    )

        # parse latest bench
        result_path = os.path.join(benchmark_dir, latest_filename)
        with open(result_path, "r") as bench_file:
            bench_text = bench_file.read()
            result = json.loads(bench_text)

        # append to result file
        result_keys = ["FPSAvg", "FPSMax", "FPSMin", "FPS95"]
        commit_hash = proton.get_vkd3d_commit()
        result_line = f"{latest_filename} {commit_hash}"
        for k in result_keys:
            assert k in result, f"key {k} not in result json"
            result_line += f" {result[k]}"

        with open(output_path, "a") as output_file:
            output_file.write(f"{result_line}\n")
