import os
import subprocess


class Proton:

    def __init__(self, py_path):
        if not os.path.isabs(py_path):
            py_path = os.path.abspath(py_path)
        assert os.path.isfile(py_path), f"{py_path} is not a file"
        self.path = py_path
        self.directory = os.path.dirname(py_path)


    def is_dist(self) -> bool:
        return os.path.exists(os.path.join(self.directory, "version"))


    def rebuild(self) -> bool:
        assert not self.is_dist()
        print("building proton")
        retval = os.system(f"cd {self.directory} && make install > make.log 2>&1")
        if retval != 0:
            printf(f"build failed, check {self.directory}/make.log")
        return retval == 0


    def rewind_vkd3d(self, commits):
        assert not self.is_dist()
        os.system(
            f"cd {self.directory}/vkd3d-proton &&\
            git reset HEAD~{commits} --hard &&\
            git submodule update --recursive --init"
        )


    def get_vkd3d_commit(self) -> str:
        assert not self.is_dist()
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=f"{self.directory}/vkd3d-proton"
            )
            .decode("ascii")
            .strip()
        )


    def rewind_dxvk(self, commits):
        assert not self.is_dist()
        os.system(
            f"cd {self.directory}/dxvk &&\
            git reset HEAD~{commits} --hard &&\
            git submodule update --recursive --init"
        )


    def get_dxvk_commit(self) -> str:
        assert not self.is_dist()
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=f"{self.directory}/dxvk"
            )
            .decode("ascii")
            .strip()
        )


    def backup_user_settings(self):
        assert self.is_dist()
        settings = os.path.join(self.directory, "user_settings.py")
        backup = os.path.join(self.directory, "user_settings.bak")
        if os.path.exists(settings):
            if os.path.exists(backup):
                raise f"{backup} already exists"
            os.rename(settings, backup)
            print(f"Moved {settings} to {backup}")


    def restore_user_settings(self):
        assert self.is_dist()
        settings = os.path.join(self.directory, "user_settings.py")
        backup = os.path.join(self.directory, "user_settings.bak")
        if os.path.exists(backup):
            if os.path.exists(settings):
                os.unlink(settings)
            os.rename(backup, settings)
            print(f"Restored {backup} to {settings}")


    def set_bench_env_vars(self, mango_path):
        assert self.is_dist()
        if not os.path.exists("/tmp/proton-bench"):
            os.mkdir("/tmp/proton-bench")
        os.environ["STEAM_COMPAT_DATA_PATH"] = "/tmp/proton-bench"
        os.environ["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = "$HOME/.local/share/steam"
        os.environ["MANGOHUD"] = "1"
        os.environ["MANGOHUD_CONFIG"] = f"output_folder={mango_path},autostart_log=1"
        print(os.environ["MANGOHUD_CONFIG"])


    def clean_env(self):
        del os.environ["MANGOHUD"]
        del os.environ["STEAM_COMPAT_DATA_PATH"]
        del os.environ["STEAM_COMPAT_CLIENT_INSTALL_PATH"]
        del os.environ["MANGOHUD_CONFIG"]


    def launch_prog(self, prog_path, args):
        assert self.is_dist()
        if not os.path.isabs(prog_path):
            prog_path = os.path.abspath(prog_path)
        assert os.path.isfile(prog_path), f"{prog_path} is not a file"
        os.system(f"{self.path} run {prog_path} {args}")
