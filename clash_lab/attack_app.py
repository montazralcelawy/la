from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from clash_lab.attack_page import AttackPage
from main import MainWindow, STYLE


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)

    window = MainWindow()
    attack_page = AttackPage(window.selected_device, window)
    index = window.tabs.indexOf(window.tabs.widget(1))
    window.tabs.insertTab(index if index >= 0 else 1, attack_page, "جيش الهجوم")
    window.tabs.setCurrentWidget(attack_page)
    window.statusBar().showMessage(
        "واجهة جيش الهجوم التجريبية مفعّلة؛ استخدم إحداثيات تم التحقق منها فقط."
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
