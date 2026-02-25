import os
import subprocess


def get_source_path():
    return os.path.abspath("../proton")


def rebuild():
    source = get_source_path()
    os.system(f"cd {source} && make install > make.log 2&1")


def rewind_vkd3d(commits):
    source = get_source_path()
    os.system(
        f"cd {source}/vkd3d-proton &&\
        git reset HEAD~{commits} --hard &&\
        git submodule update --recursive --init"
    )


def get_vkd3d_commit() -> str:
    source = get_source_path()
    return (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=source)
        .decode("ascii")
        .strip()
    )
