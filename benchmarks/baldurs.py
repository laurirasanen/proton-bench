"""
Baldurs Gate 3

Steam:
Select local proton build as the compatibility tool.

Launch arguments:
MANGOHUD_CONFIG=output_folder=/path/to/vkd3d-bench/data/mango,fps_metrics=avg+0.01+0.001,toggle_logging=F1,reset_fps_metrics=F2 gamescope --mangoapp -W 1920 -w 1920 -H 1080 -h 1080 --force-grab-cursor -- %command% --skip-launcher
"""

import os
import time
import glob
import json

from util import steam, input, proton


class BenchBaldurs:
    appid = 1086940

    def start(wait_time):
        steam.launch_game(BenchBaldurs.appid)
        time.sleep(wait_time)

    def stop():
        os.system("killall --signal SIGTERM bg3_dx11.exe")
        os.system("killall --signal SIGTERM gamescope-wl")
        time.sleep(3)
        os.system("killall --signal SIGKILL bg3_dx11.exe")
        os.system("killall --signal SIGKILL gamescope-wl")
        time.sleep(1)

    def run(run_time):
        client = input.InputClient.create()
        client.connect()
        client.sleep(1)

        # press any button to start
        key_enter = 28
        client.keyboard_key(key_enter)
        client.sleep(3)

        # click 'Continue'
        client.pointer_motion_absolute(380.0, 480.0)
        client.sleep(0.5)
        btn_left = 272
        client.mouse_button(btn_left)
        client.sleep(20)

        # mangoapp log
        key_f1 = 59
        key_f2 = 60
        client.keyboard_key(key_f2, 0.1)
        client.sleep(1)
        client.keyboard_key(key_f1, 0.1)
        client.sleep(run_time)
        client.keyboard_key(key_f1, 0.1)

        client.disconnect()

        BenchBaldurs._parse()

    def _parse():
        # find the latest bench result
        benchmark_dir = os.path.abspath("data/mango")
        result_files = glob.glob(f"{benchmark_dir}/*_summary.csv")
        assert len(result_files) > 0, f"No bench results in {benchmark_dir}"

        latest_filename = max(result_files, key=os.path.getctime).split("/")[-1]

        output_path = os.path.abspath("data/result_baldurs")

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

        # parse benchmark file
        result_path = os.path.join(benchmark_dir, latest_filename)
        avg = 0.0
        p1_low = 0.0
        p01_low = 0.0
        with open(result_path, "r") as bench_file:
            values = bench_file.readlines()[1].split(",")
            p01_low = values[0]
            p1_low = values[1]
            avg = values[3]

        # append to result file
        commit_hash = proton.get_vkd3d_commit()
        result_line = f"{latest_filename} {commit_hash} {avg} {p1_low} {p01_low}"

        with open(output_path, "a") as output_file:
            output_file.write(f"{result_line}\n")
