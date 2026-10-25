import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import task_page


class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def communicate(self, timeout=None):
        return self._stdout, self._stderr

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9


class TaskWorkerTests(unittest.TestCase):
    def run_worker(self, action, params=None, serial="emulator-5554", adb_path="adb", stdout=b""):
        result = []
        worker = task_page.TaskWorker(7, "اختبار", serial, action, adb_path, params or {})
        worker.completed.connect(lambda *args: result.append(args))
        with patch.object(task_page.subprocess, "Popen", return_value=FakeProcess(stdout=stdout)) as popen:
            worker.run()
        self.assertEqual(len(result), 1)
        return result[0], popen

    def test_check_reports_connected_device(self):
        result, popen = self.run_worker("check", stdout=b"device")
        self.assertEqual(result[1], "نجحت")
        self.assertIn("جاهز", result[2])
        self.assertEqual(popen.call_args.args[0], ["adb", "-s", "emulator-5554", "get-state"])

    def test_launch_game_uses_configured_package(self):
        result, popen = self.run_worker("launch_game", {"package": "com.example.game"})
        self.assertEqual(result[1], "نجحت")
        self.assertIn("تم إرسال أمر فتح التطبيق", result[2])
        self.assertEqual(popen.call_args.args[0][-5:], ["-p", "com.example.game", "-c", "android.intent.category.LAUNCHER", "1"])

    def test_check_game_installed_reports_installed_package(self):
        result, popen = self.run_worker(
            "check_game_installed", {"package": "com.example.game"},
            stdout=b"package:/data/app/com.example.game/base.apk"
        )
        self.assertEqual(result[1], "نجحت")
        self.assertIn("التطبيق مثبت", result[2])
        self.assertEqual(
            popen.call_args.args[0][-3:],
            ["pm", "path", "com.example.game"]
        )

    def test_check_game_installed_reports_missing_package(self):
        result, _ = self.run_worker("check_game_installed", stdout=b"")
        self.assertEqual(result[1], "فشلت")
        self.assertIn("لم يتم العثور", result[2])

    def test_current_app_reports_focused_window(self):
        result, popen = self.run_worker(
            "current_app", stdout=b"  mCurrentFocus=Window{123 u0 com.example.game/.MainActivity}\n"
        )
        self.assertEqual(result[1], "نجحت")
        self.assertIn("com.example.game", result[2])
        self.assertEqual(
            popen.call_args.args[0][-3:],
            ["dumpsys", "window", "windows"]
        )

    def test_assert_foreground_app_passes_when_expected_package_is_visible(self):
        result, popen = self.run_worker(
            "assert_foreground_app", {"package": "com.example.game"},
            stdout=b"  mCurrentFocus=Window{123 u0 com.example.game/.MainActivity}\\n"
        )
        self.assertEqual(result[1], "نجحت")
        self.assertIn("تم التحقق", result[2])
        self.assertEqual(popen.call_args.args[0][-3:], ["dumpsys", "window", "windows"])

    def test_assert_foreground_app_fails_when_another_app_is_visible(self):
        result, _ = self.run_worker(
            "assert_foreground_app", {"package": "com.example.game"},
            stdout=b"  mCurrentFocus=Window{123 u0 com.android.launcher/.MainActivity}\\n"
        )
        self.assertEqual(result[1], "فشلت")
        self.assertIn("فشل شرط التطبيق", result[2])

    def test_tap_uses_saved_coordinates(self):
        result, popen = self.run_worker("tap", {"x": 123, "y": 456})
        self.assertEqual(result[1], "نجحت")
        self.assertEqual(popen.call_args.args[0][-3:], ["tap", "123", "456"])

    def test_swipe_uses_all_coordinates_and_duration(self):
        result, popen = self.run_worker(
            "swipe",
            {"x": 10, "y": 20, "x2": 300, "y2": 400, "duration_ms": 750}
        )
        self.assertEqual(result[1], "نجحت")
        self.assertEqual(
            popen.call_args.args[0][-6:],
            ["swipe", "10", "20", "300", "400", "750"]
        )

    def test_back_and_home_use_android_keyevents(self):
        back_result, back_popen = self.run_worker("press_back")
        home_result, home_popen = self.run_worker("press_home")
        self.assertEqual(back_result[1], "نجحت")
        self.assertEqual(home_result[1], "نجحت")
        self.assertEqual(back_popen.call_args.args[0][-3:], ["input", "keyevent", "4"])
        self.assertEqual(home_popen.call_args.args[0][-3:], ["input", "keyevent", "3"])

    def test_wait_does_not_require_adb(self):
        result, popen = self.run_worker("wait", {"duration_ms": 0}, serial="", adb_path=None)
        self.assertEqual(result[1], "نجحت")
        popen.assert_not_called()

    def test_missing_adb_returns_clear_failure(self):
        result, popen = self.run_worker("check", adb_path=None)
        self.assertEqual(result[1], "فشلت")
        self.assertIn("ADB", result[2])
        popen.assert_not_called()

    def test_latest_screenshot_path_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNone(task_page.latest_screenshot_path(temp))

    def test_latest_screenshot_path_finds_png(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "screenshots"
            folder.mkdir()
            screenshot = folder / "emulator-5554_test.png"
            screenshot.write_bytes(b"png")
            self.assertEqual(task_page.latest_screenshot_path(temp), screenshot)

    def test_screenshot_saves_png(self):
        png = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + b"test"
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(task_page, "ROOT", Path(temp)):
                result, popen = self.run_worker("screenshot", stdout=png)
            self.assertEqual(result[1], "نجحت")
            saved = list((Path(temp) / "screenshots").glob("*.png"))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_bytes(), png)


if __name__ == "__main__":
    unittest.main()
