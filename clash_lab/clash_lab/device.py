from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any

@dataclass
class DeviceInfo:
    serial: str
    state: str
    model: str = ""
    android_version: str = ""

class DeviceError(RuntimeError):
    pass

class AndroidDevice:
    """ADB-backed device adapter with optional UiAutomator2 capabilities."""
    def __init__(self, serial: str, adb_path: str | None = None) -> None:
        self.serial = serial
        self.adb_path = adb_path or shutil.which("adb") or "adb"
        self._u2 = None

    def _run(self, *args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
        cmd = [self.adb_path, "-s", self.serial, *args]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        except FileNotFoundError as exc:
            raise DeviceError("لم يتم العثور على adb. ثبّت Android Platform Tools أو حدّد مسار adb.exe.") from exc
        except subprocess.TimeoutExpired as exc:
            raise DeviceError(f"انتهت مهلة تنفيذ أمر الجهاز: {' '.join(args)}") from exc
        if proc.returncode != 0:
            raise DeviceError((proc.stderr or proc.stdout or "فشل أمر ADB").strip())
        return proc

    @staticmethod
    def list_devices(adb_path: str | None = None) -> list[DeviceInfo]:
        adb = adb_path or shutil.which("adb") or "adb"
        try:
            proc = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise DeviceError("ADB غير موجود أو لم يستجب. ثبّت Android Platform Tools وأعد المحاولة.") from exc
        if proc.returncode != 0:
            raise DeviceError((proc.stderr or "تعذر قراءة الأجهزة").strip())
        devices: list[DeviceInfo] = []
        for line in proc.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            model = ""
            for token in parts[2:]:
                if token.startswith("model:"):
                    model = token.split(":", 1)[1].replace("_", " ")
            devices.append(DeviceInfo(serial=serial, state=state, model=model))
        return devices

    def info(self) -> dict[str, Any]:
        model = self._run("shell", "getprop", "ro.product.model").stdout.strip()
        version = self._run("shell", "getprop", "ro.build.version.release").stdout.strip()
        size = self._run("shell", "wm", "size").stdout.strip()
        return {"serial": self.serial, "model": model, "android_version": version, "display": size}

    def screenshot(self) -> bytes:
        try:
            proc = subprocess.run([self.adb_path, "-s", self.serial, "exec-out", "screencap", "-p"], capture_output=True, timeout=25)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise DeviceError("فشل التقاط الشاشة عبر ADB") from exc
        if proc.returncode != 0 or not proc.stdout.startswith(b"\x89PNG"):
            raise DeviceError((proc.stderr or b"تعذر التقاط الشاشة").decode("utf-8", "replace"))
        return proc.stdout

    def tap(self, x: int, y: int) -> None:
        self._run("shell", "input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 350) -> None:
        self._run("shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms)))

    def connect_uiautomator2(self) -> Any:
        try:
            import uiautomator2 as u2
        except ImportError as exc:
            raise DeviceError("مكتبة UiAutomator2 غير مثبتة. نفّذ: pip install uiautomator2") from exc
        try:
            self._u2 = u2.connect(self.serial)
            _ = self._u2.info
            return self._u2
        except Exception as exc:
            self._u2 = None
            raise DeviceError(f"تعذر تهيئة UiAutomator2 على {self.serial}: {exc}") from exc

    def ui_hierarchy(self) -> str:
        if self._u2 is None:
            self.connect_uiautomator2()
        try:
            return self._u2.dump_hierarchy(compressed=False)
        except Exception as exc:
            raise DeviceError(f"تعذر قراءة شجرة عناصر الواجهة: {exc}") from exc

    def click_text(self, text: str, timeout: float = 3.0) -> bool:
        if self._u2 is None:
            self.connect_uiautomator2()
        selector = self._u2(text=text)
        if selector.wait(timeout=timeout):
            selector.click()
            return True
        return False
