from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from clash_lab.attack_page import AttackPage
from main import MainWindow, STYLE


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)

    window = MainWindow()

    # Replace the existing placeholder tab instead of adding a duplicate tab.
    tab_index = 1
    old_page = window.tabs.widget(tab_index)
    if old_page is not None:
        window.tabs.removeTab(tab_index)
        old_page.deleteLater()

    attack_page = AttackPage(window.selected_device, window)
    window.tabs.insertTab(tab_index, attack_page, "جيش الهجوم")
    window.tabs.setCurrentWidget(attack_page)
    window.statusBar().showMessage(
        "واجهة جيش الهجوم مفعّلة؛ استخدم إحداثيات تم التحقق منها فقط."
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
