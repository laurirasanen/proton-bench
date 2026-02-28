import os
import subprocess


def get_source_path():
    return os.path.abspath("../proton")


def rebuild() -> bool:
    source = get_source_path()
    retval = os.system(f"cd {source} && make install > make.log 2>&1")
    return retval == 0


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
        subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=f"{source}/vkd3d-proton"
        )
        .decode("ascii")
        .strip()
    )


def rewind_dxvk(commits):
    source = get_source_path()
    os.system(
        f"cd {source}/dxvk &&\
        git reset HEAD~{commits} --hard &&\
        git submodule update --recursive --init"
    )


def get_dxvk_commit() -> str:
    source = get_source_path()
    return (
        subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=f"{source}/dxvk"
        )
        .decode("ascii")
        .strip()
    )
