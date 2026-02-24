import os
import pathlib


def launch_game(appid):
    print(f"Launching appid {appid}...")
    os.system(f"steam -applaunch {appid}")


def get_library_dirs():
    dirs = []

    vdf_path = os.path.expanduser("~/.steam/root/steamapps/libraryfolders.vdf")
    if not os.path.exists(vdf_path):
        raise FileNotFoundError(f"Could not find Steam library vdf: '{vdf_path}'")

    print(f"Reading libraries from '{vdf_path}'")
    vdf = open(vdf_path, "r")
    vdf_lines = vdf.readlines()

    for line in vdf_lines:
        if '"path"' in line:
            dir = line.split('"')[-2]
            dir = os.path.join(dir)
            if os.path.exists(dir):
                dirs.append(dir)

    if len(dirs) == 0:
        raise FileNotFoundError(
            f"Could not find Steam library directories in '{vdf_path}'"
        )

    print(f"Found libraries: '{dirs}'")
    return dirs


def get_game_dir(appid):
    libraries = get_library_dirs()
    acf_name = f"appmanifest_{appid}.acf"

    for lib_path in libraries:
        acf_path = os.path.join(lib_path, "steamapps", acf_name)
        if os.path.exists(acf_path):
            break

    if not os.path.exists(acf_path):
        raise FileNotFoundError(f"Could not find Steam appmanifest: '{acf_name}'")

    print(f"Reading installdir from '{acf_path}'")
    acf = open(acf_path, "r")
    acf_lines = acf.readlines()

    game_dir = None
    for line in acf_lines:
        if '"installdir"' in line:
            game_dir = line.split('"')[-2]
            break

    if game_dir is None:
        raise FileNotFoundError(f"Could not find installdir in '{acf_path}'")

    full_game_path = None

    for lib_path in libraries:
        full_path = os.path.join(lib_path, "steamapps", "common", game_dir)
        if os.path.exists(full_path):
            full_game_path = full_path
            break

    if full_game_path is None:
        raise FileNotFoundError(
            f"Could not find game '{game_dir}' in libraries {libraries}"
        )

    print(f"Found game path: '{full_game_path}'")
    return full_game_path


def get_game_compat_dir(appid):
    libraries = get_library_dirs()
    for lib_path in libraries:
        compatdata_path = os.path.join(lib_path, "steamapps", "compatdata", appid)
        if os.path.exists(compatdata_path):
            break
    if not os.path.exists(compatdata_path):
        raise FileNotFoundError(
            f"Could not find compatdata for '{appid}' in libraries: '{libraries}'"
        )
    return compatdata_path


def get_wine_user_dir(appid, *args):
    game_compat_path = get_game_compat_dir(appid)
    desktop_path = os.path.join(
        game_compat_path, "pfx", "drive_c", "users", "steamuser", *args
    )
    if not os.path.exists(desktop_path):
        raise FileNotFoundError(f"Could not find wine desktop: '{desktop_path}'")
    return desktop_path
