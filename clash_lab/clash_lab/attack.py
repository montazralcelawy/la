from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable

from .device import AndroidDevice, DeviceError


@dataclass(frozen=True)
class TapStep:
    """One explicitly configured screen tap. Coordinates are pixels on the emulator."""
    name: str
    x: int
    y: int
    wait_after: float = 1.0

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("اسم خطوة الهجوم مطلوب.")
        if self.x < 0 or self.y < 0:
            raise ValueError("إحداثيات النقر يجب ألا تكون سالبة.")
        if not 0 <= self.wait_after <= 60:
            raise ValueError("مدة الانتظار يجب أن تكون بين 0 و60 ثانية.")


@dataclass(frozen=True)
class AttackConfig:
    """A user-configured sequence; no guessed coordinates are used by default."""
    steps: tuple[TapStep, ...]
    repeat_count: int = 1
    step_timeout: float = 0.25

    def validate(self) -> None:
        if not self.steps:
            raise ValueError("أضف خطوات الهجوم وإحداثياتها قبل بدء التنفيذ.")
        if not 1 <= self.repeat_count <= 100:
            raise ValueError("عدد التكرارات يجب أن يكون بين 1 و100.")
        if not 0 <= self.step_timeout <= 10:
            raise ValueError("فاصل الاستجابة يجب أن يكون بين 0 و10 ثوانٍ.")
        for step in self.steps:
            step.validate()


LogCallback = Callable[[str, str], None]


class AttackRunner:
    """Cooperative, stoppable attack-step runner.

    It deliberately does not guess game UI coordinates. Supply verified steps for
    the current emulator resolution. The caller owns the worker thread and UI.
    """
    def __init__(
        self,
        device: AndroidDevice,
        config: AttackConfig,
        log: LogCallback | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        config.validate()
        self.device = device
        self.config = config
        self.log_callback = log or (lambda _level, _message: None)
        self._sleep = sleep
        self._stop = threading.Event()
        self._running = False
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def stop(self) -> None:
        self._stop.set()
        self.log_callback("WARNING", "تم طلب إيقاف مهمة الهجوم؛ سيتوقف التنفيذ عند أقرب نقطة آمنة.")

    def _log(self, level: str, message: str) -> None:
        self.log_callback(level, message)

    def run(self) -> bool:
        with self._lock:
            if self._running:
                raise RuntimeError("مهمة الهجوم تعمل بالفعل.")
            self._running = True
        completed = False
        try:
            self._stop.clear()
            devices = AndroidDevice.list_devices(adb_path=self.device.adb_path)
            if not any(d.serial == self.device.serial and d.state == "device" for d in devices):
                raise DeviceError(f"الجهاز {self.device.serial} غير متصل أو ليس في حالة device.")
            self._log("INFO", f"بدأت مهمة الهجوم على الجهاز {self.device.serial}.")
            self._log("INFO", f"عدد الخطوات: {len(self.config.steps)}؛ التكرارات: {self.config.repeat_count}.")
            for cycle in range(1, self.config.repeat_count + 1):
                for index, step in enumerate(self.config.steps, start=1):
                    if self._stop.is_set():
                        self._log("WARNING", "أوقفت المهمة بطلب المستخدم.")
                        return False
                    self._log("INFO", f"الدورة {cycle}/{self.config.repeat_count} — الخطوة {index}/{len(self.config.steps)}: {step.name}.")
                    self.device.tap(step.x, step.y)
                    if self._stop.wait(step.wait_after):
                        self._log("WARNING", "أوقفت المهمة أثناء الانتظار.")
                        return False
                if self._stop.is_set():
                    self._log("WARNING", "أوقفت المهمة بطلب المستخدم.")
                    return False
            completed = True
            self._log("SUCCESS", "انتهت خطوات الهجوم المهيأة بنجاح. تحقق من نتيجة المعركة داخل اللعبة.")
            return True
        except Exception as exc:
            self._log("ERROR", f"فشلت مهمة الهجوم: {exc}")
            raise
        finally:
            with self._lock:
                self._running = False
            if not completed and self._stop.is_set():
                self._log("INFO", "انتهى تنفيذ المهمة بعد الإيقاف.")
