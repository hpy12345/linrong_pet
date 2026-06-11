from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import win32api
import win32con
import win32gui
import win32process


WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_APPWINDOW = 0x00040000


def windows_for_pid(pid: int) -> list[dict[str, object]]:
    windows: list[dict[str, object]] = []

    def collect(hwnd: int, _extra: object) -> None:
        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
        if window_pid != pid:
            return
        rect = win32gui.GetWindowRect(hwnd)
        windows.append(
            {
                "hwnd": hwnd,
                "title": win32gui.GetWindowText(hwnd),
                "class_name": win32gui.GetClassName(hwnd),
                "rect": rect,
                "visible": bool(win32gui.IsWindowVisible(hwnd)),
            }
        )

    win32gui.EnumWindows(collect, None)
    return windows


def find_pet_window(pid: int) -> dict[str, object] | None:
    candidates = []
    for window in windows_for_pid(pid):
        left, top, right, bottom = window["rect"]
        if window["visible"] and right - left > 200 and bottom - top > 200:
            candidates.append(window)
    return max(
        candidates,
        key=lambda item: (
            item["rect"][2] - item["rect"][0]
        )
        * (
            item["rect"][3] - item["rect"][1]
        ),
        default=None,
    )


def wait_for_pet_window(pid: int, timeout: float = 5.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window = find_pet_window(pid)
        if window is not None:
            return window
        time.sleep(0.05)
    raise RuntimeError("desktop pet window did not appear")


def post_click(hwnd: int, width: int, height: int) -> None:
    x = width // 2
    y = height // 2
    lparam = (y << 16) | (x & 0xFFFF)
    win32gui.PostMessage(
        hwnd,
        win32con.WM_LBUTTONDOWN,
        win32con.MK_LBUTTON,
        lparam,
    )
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)


def post_drag(hwnd: int, width: int, height: int) -> None:
    start_x = width // 2
    start_y = height // 2
    end_x = max(10, start_x - 60)
    end_y = max(10, start_y - 20)
    start_lparam = (start_y << 16) | (start_x & 0xFFFF)
    end_lparam = (end_y << 16) | (end_x & 0xFFFF)
    win32gui.PostMessage(
        hwnd,
        win32con.WM_LBUTTONDOWN,
        win32con.MK_LBUTTON,
        start_lparam,
    )
    time.sleep(0.05)
    win32gui.PostMessage(
        hwnd,
        win32con.WM_MOUSEMOVE,
        win32con.MK_LBUTTON,
        end_lparam,
    )
    time.sleep(0.1)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, end_lparam)


def process_cpu_seconds(handle: int) -> float:
    times = win32process.GetProcessTimes(handle)
    return float(times["UserTime"] + times["KernelTime"]) / 10_000_000


def measure_resources(pid: int, duration: float = 5.0) -> dict[str, float]:
    handle = win32api.OpenProcess(
        win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
        False,
        pid,
    )
    try:
        start_cpu = process_cpu_seconds(handle)
        start = time.monotonic()
        time.sleep(duration)
        elapsed = time.monotonic() - start
        end_cpu = process_cpu_seconds(handle)
        memory = win32process.GetProcessMemoryInfo(handle)
    finally:
        win32api.CloseHandle(handle)
    total_cpu_percent = (
        (end_cpu - start_cpu) / elapsed / max(os.cpu_count() or 1, 1) * 100
    )
    return {
        "total_cpu_percent": round(total_cpu_percent, 3),
        "private_memory_mb": round(
            memory.get("PrivateUsage", memory["PagefileUsage"])
            / 1024
            / 1024,
            2,
        ),
        "working_set_mb": round(memory["WorkingSetSize"] / 1024 / 1024, 2),
    }


def run(executable: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="linrong-pet-smoke-") as appdata:
        environment = os.environ.copy()
        environment["APPDATA"] = appdata
        started = time.monotonic()
        primary = subprocess.Popen([str(executable)], env=environment)
        try:
            pet = wait_for_pet_window(primary.pid)
            startup_seconds = time.monotonic() - started
            hwnd = int(pet["hwnd"])
            rect = tuple(int(value) for value in pet["rect"])
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top

            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            monitor = win32api.MonitorFromWindow(
                hwnd, win32con.MONITOR_DEFAULTTONEAREST
            )
            work_area = tuple(
                int(value) for value in win32api.GetMonitorInfo(monitor)["Work"]
            )
            work_left, work_top, work_right, work_bottom = work_area
            inside_work_area = (
                left >= work_left
                and top >= work_top
                and right <= work_right
                and bottom <= work_bottom
            )

            before_windows = {
                int(item["hwnd"]) for item in windows_for_pid(primary.pid)
            }
            post_click(hwnd, width, height)
            time.sleep(0.4)
            after = windows_for_pid(primary.pid)
            bubble_visible = any(
                item["visible"]
                and int(item["hwnd"]) not in before_windows
                and 20 < item["rect"][2] - item["rect"][0] < 400
                and 20 < item["rect"][3] - item["rect"][1] < 200
                for item in after
            )

            before_drag = win32gui.GetWindowRect(hwnd)
            post_drag(hwnd, width, height)
            time.sleep(0.3)
            after_drag = win32gui.GetWindowRect(hwnd)
            drag_moved_window = after_drag != before_drag
            drag_inside_work_area = (
                after_drag[0] >= work_left
                and after_drag[1] >= work_top
                and after_drag[2] <= work_right
                and after_drag[3] <= work_bottom
            )

            roaming_observed = False
            roaming_start = after_drag
            roaming_deadline = time.monotonic() + 4.0
            while time.monotonic() < roaming_deadline:
                time.sleep(0.1)
                if win32gui.GetWindowRect(hwnd) != roaming_start:
                    roaming_observed = True
                    break

            secondary = subprocess.Popen([str(executable)], env=environment)
            try:
                secondary_exit = secondary.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                secondary.terminate()
                secondary_exit = secondary.wait(timeout=3.0)

            resources = measure_resources(primary.pid)
            result: dict[str, object] = {
                "ok": True,
                "startup_seconds": round(startup_seconds, 3),
                "window_rect": rect,
                "work_area": work_area,
                "inside_work_area": inside_work_area,
                "window_style": {
                    "topmost": bool(ex_style & WS_EX_TOPMOST),
                    "tool_window": bool(ex_style & WS_EX_TOOLWINDOW),
                    "layered_transparency": bool(ex_style & WS_EX_LAYERED),
                    "taskbar_app_window": bool(ex_style & WS_EX_APPWINDOW),
                },
                "click_bubble_visible": bubble_visible,
                "drag_moved_window": drag_moved_window,
                "drag_inside_work_area": drag_inside_work_area,
                "roaming_observed": roaming_observed,
                "single_instance_secondary_exit_code": secondary_exit,
                "tray_message_window_present": any(
                    "TrayIconMessageWindowClass" in item["class_name"]
                    for item in after
                ),
                "resources": resources,
            }
            checks = [
                startup_seconds <= 3.0,
                inside_work_area,
                result["window_style"]["topmost"],
                result["window_style"]["tool_window"],
                result["window_style"]["layered_transparency"],
                not result["window_style"]["taskbar_app_window"],
                bubble_visible,
                drag_moved_window,
                drag_inside_work_area,
                roaming_observed,
                secondary_exit == 0,
                result["tray_message_window_present"],
                resources["private_memory_mb"] < 100,
                resources["total_cpu_percent"] < 1,
            ]
            result["ok"] = all(checks)
            return result
        finally:
            primary.terminate()
            try:
                primary.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                primary.kill()
                primary.wait(timeout=3.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = run(args.executable.resolve())
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
