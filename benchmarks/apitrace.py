"""
Apitrace

"""

import os
import time
import glob
import json
import math


class BenchApitrace:

    def __init__(self, proton_src, proton_dist, tracefile, mango_path) -> BenchApitrace:
        self.proton_src = proton_src
        self.proton_dist = proton_dist
        self.apitrace = os.path.expanduser("~/apitrace-14.0-win64/")
        self.d3dretrace = os.path.join(self.apitrace, "bin", "d3dretrace.exe")
        self.tracefile = os.path.abspath(tracefile)
        self.mango_path = mango_path


    def start(self, wait_time):
        self.proton_dist.backup_user_settings()
        self.proton_dist.set_bench_env_vars(self.mango_path)
        self.proton_dist.launch_prog(self.d3dretrace, self.tracefile)


    def stop(self):
        self.proton_dist.restore_user_settings()
        self.proton_dist.clean_env()


    def run(self, run_time, commit_pass):
        # in case mangohud is still writing
        time.sleep(1)
        os.system("sync")

        self._parse(commit_pass)


    def _parse(self, commit_pass):
        # find the latest bench result
        benchmark_dir = self.mango_path
        result_files = glob.glob(f"{benchmark_dir}/d3dretrace*.csv")
        assert len(result_files) > 0, f"No bench results in {benchmark_dir}"

        latest_filename = max(result_files, key=os.path.getctime).split("/")[-1]

        # since we never stop mangohud logging with a keybind,
        # it doesn't produce a summary,
        # and we parse the full result file ourselves.
        assert "summary" not in latest_filename, f"found unexpected summary file {latest_filename}"

        output_path = os.path.abspath("data/result_apitrace")

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
            lines = bench_file.readlines()
            data_start = 0
            for i in range(0, len(lines)):
                if "fps,frametime" in lines[i]:
                    data_start = i + 1

            fps = []
            for i in range(data_start, len(lines)):
                values = lines[i].split(",")
                fps.append(float(values[0]))

            fps.sort()

            # apitrace will randomly produce ridiculous fps values.
            # just drop the top 5% so it doesn't make the average go wild.
            framecount = math.floor(len(fps) * 0.95)
            print(f"reduce frames {len(fps)} -> {framecount}")
            print(f"max fps: {fps[framecount - 1]}")
            p01_count = min(framecount - 1, math.ceil(framecount * 0.001))
            p1_count = min(framecount - 1, math.ceil(framecount * 0.01))

            p01_low = sum(fps[:p01_count]) / p01_count
            p1_low  = sum(fps[:p1_count]) / p1_count
            avg     = sum(fps[:framecount]) / framecount

        # append to result file
        commit_hash = self.proton_src.get_dxvk_commit()
        if commit_pass > 0:
            commit_hash += f"_{commit_pass}"
        result_line = f"{latest_filename} {commit_hash} {avg} {p1_low} {p01_low}"

        with open(output_path, "a") as output_file:
            output_file.write(f"{result_line}\n")
