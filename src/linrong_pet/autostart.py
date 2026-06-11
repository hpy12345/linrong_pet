from __future__ import annotations

import subprocess
import sys
import winreg


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "LinRongPet"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable])
    return subprocess.list2cmdline([sys.executable, "-m", "linrong_pet"])


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    return value == launch_command()


def set_enabled(enabled: bool) -> bool:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
    return is_enabled()

