from __future__ import annotations

import sqlite3
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QInputDialog,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget,
)

from clash_lab.database import Database
from clash_lab.device import AndroidDevice, DeviceError
from clash_lab.vision import png_to_pil

STYLE = """
QMainWindow, QWidget { background: #11151d; color: #e6eaf2; font-size: 14px; }
QLabel#title { font-size: 22px; font-weight: 700; color: #f4f7ff; }
QLabel#muted { color: #9ba8bc; }
QPushButton { background: #273449; border: 1px solid #3a4a62; border-radius: 8px; padding: 9px 14px; }
QPushButton:hover { background: #344763; }
QComboBox, QPlainTextEdit, QListWidget { background: #171e2a; border: 1px solid #334156; border-radius: 7px; padding: 7px; }
QTabWidget::pane { border: 1px solid #283446; border-radius: 8px; }
QTabBar::tab { background: #1a2230; padding: 10px 16px; margin: 2px; border-radius: 6px; }
QTabBar::tab:selected { background: #2b4565; }
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.db = Database()
        self.device: AndroidDevice | None = None
        self.setWindowTitle("Clash Automation Lab")
        self.resize(1100, 720)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("Clash Automation Lab")
        title.setObjectName("title")
        subtitle = QLabel("مختبر إدارة المهام والتحكم بأجهزة Android")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        device_row = QHBoxLayout()
        self.devices = QComboBox()
        self.devices.setMinimumWidth(300)
        refresh = QPushButton("تحديث الأجهزة")
        refresh.clicked.connect(self.refresh_devices)
        connect = QPushButton("فحص الاتصال")
        connect.clicked.connect(self.check_device)
        screenshot = QPushButton("التقاط الشاشة")
        screenshot.clicked.connect(self.take_screenshot)
        hierarchy = QPushButton("فحص UiAutomator2")
        hierarchy.clicked.connect(self.check_u2)
        device_row.addWidget(QLabel("الجهاز:"))
        device_row.addWidget(self.devices, 1)
        device_row.addWidget(refresh)
        device_row.addWidget(connect)
        device_row.addWidget(screenshot)
        device_row.addWidget(hierarchy)
        layout.addLayout(device_row)

        self.tabs = QTabWidget()
        for tab_name, description in [
            ("عام", "حالة الاتصال والأدوات الأساسية"),
            ("جيش الهجوم", "إعدادات الهجوم ستضاف بعد اختبار قراءة الشاشة"),
            ("القرى المتعددة", "إدارة ملفات الأجهزة والقرى المحفوظة"),
            ("قاعدة البناء", "إعدادات مستقلة لمهام قاعدة البناء"),
            ("الإعدادات", "مسارات ADB وطرق اكتشاف الواجهة"),
        ]:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            note = QLabel(description)
            note.setWordWrap(True)
            note.setObjectName("muted")
            page_layout.addWidget(note)

            if tab_name == "عام":
                self.preview = QLabel("ستظهر لقطة شاشة الجهاز هنا")
                self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.preview.setMinimumHeight(320)
                self.preview.setStyleSheet(
                    "background:#0b0e14;border:1px solid #29364a;border-radius:8px;padding:8px"
                )
                page_layout.addWidget(self.preview, 2)
                self.log_view = QPlainTextEdit()
                self.log_view.setReadOnly(True)
                self.log_view.setPlaceholderText("سجل التشغيل والأخطاء")
                page_layout.addWidget(self.log_view, 1)
            elif tab_name == "القرى المتعددة":
                self.profiles_list = QListWidget()
                self.profiles_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
                page_layout.addWidget(self.profiles_list, 1)
                profile_buttons = QHBoxLayout()
                add_profile = QPushButton("إضافة قرية للجهاز المحدد")
                add_profile.clicked.connect(self.add_profile)
                remove_profile = QPushButton("حذف القرية المحددة")
                remove_profile.clicked.connect(self.remove_profile)
                reload_profiles = QPushButton("تحديث القائمة")
                reload_profiles.clicked.connect(self.refresh_profiles)
                profile_buttons.addWidget(add_profile)
                profile_buttons.addWidget(remove_profile)
                profile_buttons.addWidget(reload_profiles)
                page_layout.addLayout(profile_buttons)
                help_text = QLabel(
                    "هذه الخطوة تحفظ أسماء القرى وربطها بالجهاز فقط؛ لا تبدأ أي هجوم آلي."
                )
                help_text.setWordWrap(True)
                help_text.setObjectName("muted")
                page_layout.addWidget(help_text)
            else:
                placeholder = QLabel(
                    "قسم تأسيسي — لن تُنفّذ إجراءات لعب آلية قبل بناء وفحص خطواتها."
                )
                placeholder.setWordWrap(True)
                page_layout.addWidget(placeholder)

            page_layout.addStretch(1)
            self.tabs.addTab(page, tab_name)

        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage(f"قاعدة البيانات: {self.db.path}")
        self.log("تم تشغيل التطبيق وتهيئة قاعدة البيانات تلقائياً.")
        self.refresh_devices()
        self.refresh_profiles()

    def log(self, message: str, level: str = "INFO") -> None:
        try:
            self.db.log(level, message)
        except sqlite3.Error:
            pass
        if hasattr(self, "log_view"):
            self.log_view.appendPlainText(f"[{level}] {message}")
        self.statusBar().showMessage(message, 8000)

    def refresh_devices(self) -> None:
        previous_serial = self.devices.currentData()
        self.devices.clear()
        try:
            devices = AndroidDevice.list_devices()
            for device in devices:
                label = f"{device.serial} — {device.state}"
                if device.model:
                    label += f" — {device.model}"
                self.devices.addItem(label, device.serial)
            if previous_serial:
                index = self.devices.findData(previous_serial)
                if index >= 0:
                    self.devices.setCurrentIndex(index)
            if not devices:
                self.log("لم يتم العثور على أجهزة. تحقق من ADB وتشغيل المحاكي.", "WARNING")
            else:
                self.log(f"تم العثور على {len(devices)} جهاز/أجهزة ADB.")
        except DeviceError as exc:
            self.log(str(exc), "ERROR")

    def selected_device(self) -> AndroidDevice:
        serial = self.devices.currentData()
        if not serial:
            raise DeviceError("لا يوجد جهاز محدد. شغّل المحاكي ثم اضغط تحديث الأجهزة.")
        return AndroidDevice(str(serial))

    def check_device(self) -> None:
        try:
            self.device = self.selected_device()
            details = self.device.info()
            self.log(f"الاتصال ناجح: {details}")
            QMessageBox.information(
                self, "فحص الجهاز",
                f"الجهاز: {details['model']}\nAndroid: {details['android_version']}\nالشاشة: {details['display']}",
            )
        except DeviceError as exc:
            self.log(str(exc), "ERROR")
            QMessageBox.warning(self, "تعذر الاتصال", str(exc))

    def take_screenshot(self) -> None:
        try:
            self.device = self.selected_device()
            png = self.device.screenshot()
            image = png_to_pil(png)
            data = image.tobytes("raw", "RGB")
            qimage = QImage(
                data, image.width, image.height, image.width * 3,
                QImage.Format.Format_RGB888,
            ).copy()
            pixmap = QPixmap.fromImage(qimage).scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview.setPixmap(pixmap)
            self.log(f"تم التقاط الشاشة: {image.width}×{image.height}.")
        except Exception as exc:
            self.log(str(exc), "ERROR")
            QMessageBox.warning(self, "فشل التقاط الشاشة", str(exc))

    def check_u2(self) -> None:
        try:
            self.device = self.selected_device()
            info = self.device.connect_uiautomator2().info
            hierarchy = self.device.ui_hierarchy()
            self.log(
                f"UiAutomator2 يعمل. معلومات الجهاز: {info}. "
                f"طول شجرة الواجهة: {len(hierarchy)} حرفاً."
            )
            QMessageBox.information(
                self, "UiAutomator2",
                f"نجح الاتصال بالخادم وقراءة شجرة الواجهة.\nعدد الأحرف: {len(hierarchy)}",
            )
        except DeviceError as exc:
            self.log(str(exc), "ERROR")
            QMessageBox.warning(self, "فحص UiAutomator2", str(exc))

    def refresh_profiles(self) -> None:
        if not hasattr(self, "profiles_list"):
            return
        self.profiles_list.clear()
        for profile in self.db.list_profiles():
            serial = profile["serial"] or "غير مرتبط بجهاز"
            enabled = "مفعّلة" if profile["enabled"] else "معطّلة"
            item = QListWidgetItem(f"{profile['name']}  —  {serial}  —  {enabled}")
            item.setData(Qt.ItemDataRole.UserRole, profile["id"])
            self.profiles_list.addItem(item)

    def add_profile(self) -> None:
        name, accepted = QInputDialog.getText(self, "إضافة قرية", "اسم القرية:")
        if not accepted:
            return
        if not name.strip():
            QMessageBox.warning(self, "اسم غير صالح", "اكتب اسماً للقرية أولاً.")
            return
        serial = str(self.devices.currentData() or "")
        try:
            self.db.add_profile(name, serial)
            self.refresh_profiles()
            self.log(f"تم حفظ القرية «{name.strip()}» وربطها بالجهاز {serial or 'دون جهاز'}.")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "اسم مكرر", "يوجد ملف قرية بهذا الاسم بالفعل.")
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "تعذر حفظ القرية", str(exc))
            self.log(f"تعذر حفظ القرية: {exc}", "ERROR")

    def remove_profile(self) -> None:
        item = self.profiles_list.currentItem()
        if item is None:
            QMessageBox.information(self, "اختيار القرية", "حدد قرية من القائمة أولاً.")
            return
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل تريد حذف ملف القرية «{item.text()}»؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_profile(int(profile_id))
            self.refresh_profiles()
            self.log("تم حذف ملف القرية المحدد.")
        except sqlite3.Error as exc:
            QMessageBox.warning(self, "تعذر الحذف", str(exc))
            self.log(f"تعذر حذف ملف القرية: {exc}", "ERROR")


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
