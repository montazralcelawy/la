from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget,
)

from .attack import AttackConfig, AttackRunner, TapStep
from .device import AndroidDevice


class ClickableScreenshot(QLabel):
    """Display a device screenshot and report taps in original device pixels."""
    point_selected = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 220)
        self.setText("اضغط «تحديث صورة اللعبة» لعرض الشاشة هنا")
        self.setStyleSheet(
            "background:#0b0e14;border:1px solid #334156;border-radius:8px;padding:6px"
        )
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_screenshot(self, png: bytes) -> None:
        image = QImage()
        if not image.loadFromData(png, "PNG") or image.isNull():
            raise ValueError("الصورة المستلمة من الجهاز ليست PNG صالحة.")
        self._source_pixmap = QPixmap.fromImage(image)
        self._refresh_scaled_pixmap()

    def _refresh_scaled_pixmap(self) -> None:
        if self._source_pixmap is None:
            return
        scaled = self._source_pixmap.scaled(
            self.contentsRect().size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_scaled_pixmap()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._source_pixmap is None or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        source = self._source_pixmap
        area = self.contentsRect()
        scale = min(area.width() / source.width(), area.height() / source.height())
        if scale <= 0:
            return
        shown_width = source.width() * scale
        shown_height = source.height() * scale
        offset_x = area.x() + (area.width() - shown_width) / 2
        offset_y = area.y() + (area.height() - shown_height) / 2
        px = event.position().x()
        py = event.position().y()
        if not (offset_x <= px < offset_x + shown_width and offset_y <= py < offset_y + shown_height):
            return
        x = int((px - offset_x) / scale)
        y = int((py - offset_y) / scale)
        self.point_selected.emit(
            max(0, min(source.width() - 1, x)),
            max(0, min(source.height() - 1, y)),
        )


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
    """Attack task editor with a clickable, live-refreshable device screenshot."""
    def __init__(self, device_factory, parent=None) -> None:
        super().__init__(parent)
        self.device_factory = device_factory
        self.worker: _AttackWorker | None = None
        self.steps: list[TapStep] = []
        self._click_counter = 0

        layout = QVBoxLayout(self)
        intro = QLabel(
            "حدّث صورة اللعبة ثم انقر على موضع الزر داخل الصورة لإضافة خطوة تلقائياً. "
            "الإحداثيات المحفوظة تكون بدقة شاشة الجهاز الأصلية."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        screenshot_row = QHBoxLayout()
        screenshot_col = QVBoxLayout()
        self.screenshot = ClickableScreenshot()
        self.screenshot.point_selected.connect(self.add_step_from_point)
        self.refresh_screenshot_button = QPushButton("تحديث صورة اللعبة")
        self.refresh_screenshot_button.clicked.connect(self.refresh_screenshot)
        screenshot_col.addWidget(self.refresh_screenshot_button)
        screenshot_col.addWidget(self.screenshot, 1)
        self.screen_info = QLabel("لم تُلتقط صورة بعد")
        self.screen_info.setWordWrap(True)
        screenshot_col.addWidget(self.screen_info)
        screenshot_row.addLayout(screenshot_col, 3)

        controls_col = QVBoxLayout()
        form = QFormLayout()
        self.step_name = QLineEdit()
        self.step_name.setPlaceholderText("اسم الخطوة أو الزر")
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
        controls_col.addLayout(form)

        row = QHBoxLayout()
        add_button = QPushButton("إضافة بالإحداثيات")
        remove_button = QPushButton("حذف الخطوة المحددة")
        add_button.clicked.connect(self.add_step)
        remove_button.clicked.connect(self.remove_step)
        row.addWidget(add_button)
        row.addWidget(remove_button)
        controls_col.addLayout(row)

        self.steps_list = QListWidget()
        controls_col.addWidget(QLabel("خطوات التسلسل:"))
        controls_col.addWidget(self.steps_list, 1)
        screenshot_row.addLayout(controls_col, 2)
        layout.addLayout(screenshot_row, 3)

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
        self.log_view.setMaximumHeight(120)
        layout.addWidget(self.log_view)

    def refresh_screenshot(self) -> None:
        try:
            device = self.device_factory()
            png = device.screenshot()
            self.screenshot.set_screenshot(png)
            image = self.screenshot._source_pixmap
            self.screen_info.setText(
                f"دقة الجهاز: {image.width()} × {image.height()} — انقر على الصورة لإضافة خطوة."
            )
            self.append_log("INFO", f"تم تحديث صورة اللعبة بدقة {image.width()}×{image.height()}.")
        except Exception as exc:
            self.append_log("ERROR", f"تعذر تحديث صورة اللعبة: {exc}")
            QMessageBox.warning(self, "تعذر التقاط الشاشة", str(exc))

    def add_step_from_point(self, x: int, y: int) -> None:
        self._click_counter += 1
        name = self.step_name.text().strip() or f"نقرة {self._click_counter}"
        self.x_value.setValue(x)
        self.y_value.setValue(y)
        self.step_name.setText(name)
        self._append_step(name, x, y)
        self.step_name.clear()
        self.append_log("INFO", f"أُضيفت نقطة من الصورة: X={x}, Y={y}.")

    def add_step(self) -> None:
        name = self.step_name.text().strip()
        if not name:
            QMessageBox.warning(self, "اسم الخطوة", "اكتب اسماً للخطوة أو انقر على صورة اللعبة.")
            return
        self._append_step(name, self.x_value.value(), self.y_value.value())
        self.step_name.clear()

    def _append_step(self, name: str, x: int, y: int) -> None:
        step = TapStep(name, x, y, float(self.wait_value.value()))
        try:
            step.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "خطوة غير صالحة", str(exc))
            return
        self.steps.append(step)
        self.steps_list.addItem(
            f"{name} — X:{step.x}, Y:{step.y}, انتظار {step.wait_after:g} ث"
        )

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
