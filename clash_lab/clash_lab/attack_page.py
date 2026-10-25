from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget,
)

from .attack import AttackConfig, AttackRunner, TapStep
from .device import AndroidDevice


class _AttackWorker(QThread):
    log_line = Signal(str, str)
    finished_result = Signal(bool, str)

    def __init__(self, device: AndroidDevice, config: AttackConfig) -> None:
        super().__init__()
        self.runner = AttackRunner(device, config, self._relay_log)

    def _relay_log(self, level: str, message: str) -> None:
        self.log_line.emit(level, message)

    def run(self) -> None:
        try:
            result = self.runner.run()
            self.finished_result.emit(result, "")
        except Exception as exc:
            self.finished_result.emit(False, str(exc))

    def request_stop(self) -> None:
        self.runner.stop()


class AttackPage(QWidget):
    """Reusable attack UI page; instantiate and add to a tab without changing main.py."""
    def __init__(self, device_factory, parent=None) -> None:
        super().__init__(parent)
        self.device_factory = device_factory
        self.worker: _AttackWorker | None = None
        self.steps: list[TapStep] = []

        layout = QVBoxLayout(self)
        intro = QLabel(
            "مهمة الهجوم التجريبية: أضف إحداثيات تم التحقق منها على دقة المحاكي الحالية. "
            "لا توجد إحداثيات افتراضية حتى لا ينقر البرنامج عشوائياً."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.step_name = QLineEdit()
        self.step_name.setPlaceholderText("مثال: زر البحث عن خصم")
        self.x_value = QSpinBox()
        self.x_value.setRange(0, 10000)
        self.y_value = QSpinBox()
        self.y_value.setRange(0, 10000)
        self.wait_value = QSpinBox()
        self.wait_value.setRange(0, 60)
        self.wait_value.setValue(2)
        self.repeat_value = QSpinBox()
        self.repeat_value.setRange(1, 100)
        self.repeat_value.setValue(1)
        form.addRow("اسم الخطوة:", self.step_name)
        form.addRow("الإحداثي X:", self.x_value)
        form.addRow("الإحداثي Y:", self.y_value)
        form.addRow("انتظار بعد النقر (ثانية):", self.wait_value)
        form.addRow("عدد تكرار التسلسل:", self.repeat_value)
        layout.addLayout(form)

        row = QHBoxLayout()
        add_button = QPushButton("إضافة خطوة")
        remove_button = QPushButton("حذف الخطوة المحددة")
        add_button.clicked.connect(self.add_step)
        remove_button.clicked.connect(self.remove_step)
        row.addWidget(add_button)
        row.addWidget(remove_button)
        layout.addLayout(row)

        self.steps_list = QListWidget()
        layout.addWidget(self.steps_list, 1)

        controls = QHBoxLayout()
        self.start_button = QPushButton("بدء الهجوم")
        self.stop_button = QPushButton("إيقاف")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_attack)
        self.stop_button.clicked.connect(self.stop_attack)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("سجل تنفيذ مهمة الهجوم")
        layout.addWidget(self.log_view, 1)

    def add_step(self) -> None:
        name = self.step_name.text().strip()
        if not name:
            QMessageBox.warning(self, "اسم الخطوة", "اكتب اسماً واضحاً للخطوة.")
            return
        step = TapStep(name, self.x_value.value(), self.y_value.value(), float(self.wait_value.value()))
        try:
            step.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "خطوة غير صالحة", str(exc))
            return
        self.steps.append(step)
        self.steps_list.addItem(f"{name} — X:{step.x}, Y:{step.y}, انتظار {step.wait_after:g} ث")
        self.step_name.clear()

    def remove_step(self) -> None:
        index = self.steps_list.currentRow()
        if index < 0:
            return
        self.steps_list.takeItem(index)
        del self.steps[index]

    def start_attack(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        try:
            config = AttackConfig(tuple(self.steps), self.repeat_value.value())
            config.validate()
            device = self.device_factory()
        except Exception as exc:
            QMessageBox.warning(self, "تعذر بدء المهمة", str(exc))
            return
        self.worker = _AttackWorker(device, config)
        self.worker.log_line.connect(self.append_log)
        self.worker.finished_result.connect(self.on_finished)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.append_log("INFO", "تم بدء عامل التنفيذ.")
        self.worker.start()

    def stop_attack(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.stop_button.setEnabled(False)

    def append_log(self, level: str, message: str) -> None:
        self.log_view.appendPlainText(f"[{level}] {message}")

    def on_finished(self, success: bool, error: str) -> None:
        if error:
            self.append_log("ERROR", error)
        self.append_log("INFO", "اكتمل العامل." if success else "توقفت المهمة أو لم تكتمل.")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
