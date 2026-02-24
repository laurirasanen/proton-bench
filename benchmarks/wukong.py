import os
import time

from util import steam, input


class BenchWukong:
    def start():
        steam.launch_game(3132990)
        time.sleep(30)

    def stop():
        os.system("killall b1_benchmark.exe")
        time.sleep(3)

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

        benchmark_dir = steam.get_wine_user_dir(
            appid, "AppData", "Local", "Temp", "b1", "BenchMarkHistory", "Tool"
        )
        commit_hash = proton.get_vkd3d_commit()
        # todo glob latest result,
        # parse and add to output file
