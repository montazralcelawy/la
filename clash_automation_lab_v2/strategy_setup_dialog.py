"""Guided setup for the reusable visual strategy profile."""
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit, QPushButton,
    QFileDialog, QDialogButtonBox, QMessageBox, QLabel, QDoubleSpinBox,
)


class StrategySetupDialog(QDialog):
    """Collect a small reusable set of screen/button templates, not a task per tap."""

    SCREEN_ROLES = [
        ("home", "قالب شاشة القرية الرئيسية"),
        ("search", "قالب شاشة البحث عن الخصم"),
        ("battle", "قالب شاشة المعركة"),
    ]
    BUTTON_ROLES = [
        ("attack_menu", "زر الهجوم في القرية"),
        ("attack", "زر الهجوم على الخصم"),
        ("next_base", "زر القرية التالية"),
        ("return_home", "زر العودة بعد المعركة"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إعداد محرك الاستراتيجية")
        self.resize(760, 650)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "أنشئ ملف إعدادات واحداً يعيد استخدام القوالب في دورة اللعب. "
            "لا تحتاج إلى إنشاء مهمة منفصلة لكل نقرة. اختر قصاصات واضحة من لقطات الشاشة."
        ))
        form = QFormLayout()
        self.fields = {}
        for key, label in self.SCREEN_ROLES + self.BUTTON_ROLES + [
            ("battle_ended", "قالب علامة انتهاء المعركة (اختياري)"),
            ("troop_slot", "قالب خانة جندي واحدة (مطلوب للنشر)"),
        ]:
            edit = QLineEdit()
            edit.setPlaceholderText("اختر ملف صورة PNG/JPG")
            browse = QPushButton("اختيار…")
            browse.clicked.connect(lambda checked=False, k=key: self.browse_image(k))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(browse)
            holder = QVBoxLayout()
            holder.addLayout(row)
            wrap = __import__("PySide6.QtWidgets", fromlist=["QWidget"]).QWidget()
            wrap.setLayout(holder)
            form.addRow(label + ":", wrap)
            self.fields[key] = edit

        root.addLayout(form)
        root.addWidget(QLabel(
            "نقاط نشر الجنود النسبية (اختياري الآن): اكتب x,y بين 0 و1 وافصل النقاط بفاصلة منقوطة؛ "
            "مثال تنسيقي فقط: 0.25,0.70; 0.75,0.70. لا تستخدمها قبل التأكد من موضع ساحة القتال."
        ))
        self.points = QLineEdit()
        self.points.setPlaceholderText("اتركها فارغة لحين تحديد نقاط آمنة على ساحة القتال")
        root.addWidget(self.points)
        root.addWidget(QLabel(
            "ملاحظة: قراءة الموارد الآلية غير مفعّلة في هذا المعالج؛ لذلك لن يتخذ المحرك قرار تخطي الخصم "
            "حتى تُضبط مناطق قراءة الذهب والإكسير لاحقاً. إذا لم يتعرّف على شاشة، فسيتوقف بأمان."
        ))
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_config)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def browse_image(self, key):
        path, _ = QFileDialog.getOpenFileName(
            self, "اختيار قالب بصري", str(Path.home()),
            "صور PNG/JPEG (*.png *.jpg *.jpeg *.bmp);;كل الملفات (*.*)"
        )
        if path:
            self.fields[key].setText(path)

    def save_config(self):
        missing = [label for key, label in self.SCREEN_ROLES + self.BUTTON_ROLES
                   if not self.fields[key].text().strip()]
        if missing:
            QMessageBox.warning(
                self, "قوالب ناقصة",
                "اختر القوالب الأساسية التالية قبل الحفظ:\n• " + "\n• ".join(missing)
            )
            return
        screen_templates = {key: self.fields[key].text().strip()
                            for key, _ in self.SCREEN_ROLES}
        button_templates = {key: {"template": self.fields[key].text().strip()}
                            for key, _ in self.BUTTON_ROLES}
        status_templates = {}
        if self.fields["battle_ended"].text().strip():
            status_templates["battle_ended"] = self.fields["battle_ended"].text().strip()
        troop_slots = []
        if self.fields["troop_slot"].text().strip():
            troop_slots.append({
                "name": "troop",
                "template": self.fields["troop_slot"].text().strip(),
                "threshold": 0.88,
            })
        points = []
        try:
            raw_points = self.points.text().strip()
            if raw_points:
                for item in raw_points.split(";"):
                    x, y = [float(part.strip()) for part in item.split(",")]
                    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                        raise ValueError("نقاط النشر يجب أن تكون بين 0 و1.")
                    points.append([x, y])
        except (ValueError, TypeError):
            QMessageBox.warning(
                self, "صيغة نقاط غير صحيحة",
                "اكتب النقاط بهذا الشكل: 0.25,0.70; 0.75,0.70"
            )
            return
        config = {
            "min_confidence": 0.88,
            "post_action_delay_seconds": 0.8,
            "tesseract_cmd": "",
            "screen_templates": screen_templates,
            "button_templates": button_templates,
            "status_templates": status_templates,
            "resource_regions": {},
            "troop_slots": troop_slots,
            "deployment_points": points,
            "upgrade_candidates": [],
            "policy": {
                "min_gold": 100000,
                "min_elixir": 100000,
                "min_dark_elixir": 0,
                "min_candidate_confidence": 0.88,
                "attack_when_loot_low": True,
                "collect_resources": False,
                "upgrade_buildings": False,
                "train_army": False,
                "deploy_pattern": "two_sides",
                "max_searches_per_cycle": 30,
            },
        }
        default_path = str(Path.home() / "clash_strategy_config.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "حفظ إعدادات الاستراتيجية", default_path, "JSON (*.json)"
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            Path(path).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "تعذر الحفظ", str(exc))
            return
        self.saved_path = path
        self.accept()
