import sqlite3
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import *

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'profiles.db'

SECTIONS = [
    ('عام', [
        ('قرية البناء الرئيسية', [('تفعيل قرية البناء الرئيسية', 'check', True), ('ترقية الجدران', 'check', False), ('إيقاف ترقية الجدران عند المستوى', 'combo', ['15','16','17','18','19','20'], '19')]),
        ('فلتر الهجوم', [('الحد الأدنى للذهب', 'spin', 100000, 0, 100000000), ('الحد الأدنى للإكسير', 'spin', 0, 0, 100000000), ('الحد الأدنى للإكسير الأسود', 'spin', 0, 0, 100000000)]),
        ('التبرعات', [('طلب التبرعات', 'check', False), ('الانتظار 60 ثانية للتعزيزات', 'check', False), ('تفعيل التبرع', 'check', False)]),
        ('شروط إنهاء المعركة', [('إنهاء المعركة عند عدد النجوم', 'check', True), ('عدد النجوم', 'combo', ['1','2','3'], '2'), ('إنهاء المعركة عند النسبة', 'check', False), ('نسبة إنهاء المعركة', 'combo', ['30%','40%','50%','60%','70%','80%','90%'], '50%')]),
        ('إضافات', [('جمع الموارد', 'check', False), ('جمع عربة الغنائم', 'check', False), ('إزالة العوائق', 'check', False), ('جمع غنائم قلعة القبيلة', 'check', False), ('وضع العناصر غير الموضوعة', 'check', False), ('تشغيل المساعدين', 'check', False), ('مسح المقابر', 'check', False), ('جمع الإنجازات', 'check', False), ('مطالبة الصفقة الأسبوعية', 'check', True), ('استخدام التعويذات', 'check', True), ('اختيار التعويذات', 'combo', ['عشوائي','حسب الإعدادات'], 'عشوائي')]),
    ]),
    ('جيش الهجوم', [
        ('تكوين الجيش', [('تفعيل إعداد جيش الهجوم', 'check', False), ('نوع الجيش', 'combo', ['متوازن','جوي','أرضي','مخصص'], 'متوازن'), ('انتظار اكتمال الجيش', 'check', True)]),
        ('الأبطال والتعويذات', [('استخدام الأبطال', 'check', True), ('استخدام آلات الحصار', 'check', False), ('استخدام التعويذات تلقائياً', 'check', True)]),
    ]),
    ('القرى المتعددة', [('إدارة القرى', [('تفعيل القرى المتعددة', 'check', False), ('عدد القرى المستهدف', 'spin', 2, 1, 20), ('الانتقال بين القرى تلقائياً', 'check', False)])]),
    ('قاعدة البناء', [('إعدادات قاعدة البناء', [('تفعيل قاعدة البناء', 'check', False), ('الحد الأدنى للذهب', 'spin', 0, 0, 100000000), ('الحد الأدنى للإكسير', 'spin', 0, 0, 100000000), ('إيقاف الهجوم عند عدد النجوم', 'combo', ['1','2','3','4','5','6'], '3')])]),
    ('عاصمة القبيلة', [('إعدادات العاصمة', [('تفعيل عاصمة القبيلة', 'check', False), ('جمع غنائم العاصمة', 'check', False), ('المساهمة في الترقية', 'check', False)])]),
    ('الترقيات/البحث', [('إدارة الترقيات', [('تفعيل الترقيات', 'check', False), ('ترقية المباني تلقائياً', 'check', False), ('تفعيل البحث في المختبر', 'check', False), ('أولوية الترقية', 'combo', ['المباني','القوات','التوازن'], 'التوازن')])]),
    ('مزارع الخبرة', [('إعدادات الخبرة', [('تفعيل مزارع الخبرة', 'check', False), ('حد المعارك في الجلسة', 'spin', 10, 1, 1000), ('إيقاف عند نسبة تدمير', 'combo', ['50%','70%','90%','100%'], '50%')])]),
    ('أوضاع إضافية', [('الأوضاع', [('تفعيل الأوضاع الإضافية', 'check', False), ('الوضع', 'combo', ['جمع الموارد','تحديات ودية','تدريب','مخصص'], 'جمع الموارد')])]),
    ('تشغيل البوت', [('الجدولة والتحكم', [('تفعيل التشغيل المجدول', 'check', False), ('نمط التشغيل', 'combo', ['مرة واحدة','يومياً','كل 15 دقيقة','كل 30 دقيقة','كل ساعة'], 'يومياً'), ('وقت التشغيل (HH:MM)', 'text', '09:00'), ('إيقاف تلقائي بعد (دقيقة)', 'spin', 60, 1, 1440)])]),
    ('إحصائيات', [('ملخص الجلسة', [('تسجيل إحصائيات الجلسة', 'check', True), ('حفظ سجل المهام', 'check', True)])]),
    ('السجل', [('إعدادات السجل', [('تسجيل الأحداث التفصيلية', 'check', True), ('تسجيل الأخطاء فقط', 'check', False), ('الاحتفاظ بالسجلات (أيام)', 'spin', 30, 1, 3650)])]),
    ('الإعدادات', [('إعدادات التطبيق', [('تشغيل البرنامج عند بدء Windows', 'check', False), ('تقليل البرنامج إلى شريط المهام', 'check', False), ('التأكيد قبل الإيقاف', 'check', True), ('لغة الواجهة', 'combo', ['العربية','English'], 'العربية')])]),
]

class BotConfigPage(QWidget):
    def __init__(self, window=None):
        super().__init__()
        self.window = window
        self.controls = {}
        self.buttons = []
        self.setLayoutDirection(Qt.LeftToRight)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)
        nav = QFrame()
        nav.setObjectName('panel')
        nav.setMinimumWidth(190)
        nav.setMaximumWidth(220)
        nv = QVBoxLayout(nav)
        brand = QLabel('⚙  إعدادات البوت')
        brand.setStyleSheet('font-size:17px;font-weight:700;padding:8px')
        brand.setLayoutDirection(Qt.RightToLeft)
        nv.addWidget(brand)
        for index, (name, _) in enumerate(SECTIONS):
            button = QPushButton(name)
            button.setObjectName('nav')
            button.setCheckable(True)
            button.setMinimumHeight(38)
            button.setLayoutDirection(Qt.RightToLeft)
            button.clicked.connect(lambda checked=False, i=index: self.show_section(i))
            nv.addWidget(button)
            self.buttons.append(button)
        nv.addStretch()
        outer.addWidget(nav)
        self.stack = QStackedWidget()
        self.stack.setLayoutDirection(Qt.RightToLeft)
        outer.addWidget(self.stack, 1)
        self._ensure_db()
        for name, groups in SECTIONS:
            self.stack.addWidget(self._make_section(name, groups))
        self.show_section(0)

    def _ensure_db(self):
        with sqlite3.connect(DB) as con:
            con.execute('CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')

    def _load_value(self, key, default):
        with sqlite3.connect(DB) as con:
            row = con.execute('SELECT value FROM bot_settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else str(default)

    def _save_value(self, key, value):
        with sqlite3.connect(DB) as con:
            con.execute('INSERT INTO bot_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))
        if self.window and hasattr(self.window, 'log'):
            self.window.log('تم حفظ إعداد: ' + key)

    def _make_section(self, section_name, groups):
        page = QWidget()
        page.setLayoutDirection(Qt.RightToLeft)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(8, 4, 8, 4)
        heading = QLabel(section_name)
        heading.setObjectName('title')
        outer.addWidget(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setLayoutDirection(Qt.RightToLeft)

        def make_group(group_name, fields):
            box = QGroupBox(group_name)
            box.setLayoutDirection(Qt.RightToLeft)
            grid = QGridLayout(box)
            grid.setContentsMargins(10, 16, 10, 10)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(10)
            for idx, field in enumerate(fields):
                label, kind, default = field[0], field[1], field[2]
                key = section_name + '.' + label
                if kind == 'check':
                    widget = QCheckBox(label)
                    widget.setChecked(self._load_value(key, default).lower() in ('true', '1', 'yes'))
                    widget.toggled.connect(lambda value, k=key: self._save_value(k, value))
                    grid.addWidget(widget, idx // 2, idx % 2, 1, 2)
                else:
                    caption = QLabel(label)
                    if kind == 'spin':
                        widget = QSpinBox()
                        widget.setRange(field[3], field[4])
                        widget.setGroupSeparatorShown(True)
                        try:
                            widget.setValue(int(self._load_value(key, default)))
                        except ValueError:
                            widget.setValue(int(default))
                        widget.valueChanged.connect(lambda value, k=key: self._save_value(k, value))
                    elif kind == 'combo':
                        widget = QComboBox()
                        widget.addItems(field[2])
                        widget.setCurrentText(self._load_value(key, field[3]))
                        widget.currentTextChanged.connect(lambda value, k=key: self._save_value(k, value))
                    elif kind == 'text':
                        widget = QLineEdit()
                        widget.setText(self._load_value(key, default))
                        widget.editingFinished.connect(lambda w=widget, k=key: self._save_value(k, w.text()))
                    col = (idx % 2) * 2
                    row = idx // 2
                    grid.addWidget(caption, row, col)
                    grid.addWidget(widget, row, col + 1)
                self.controls[key] = widget
            return box

        if section_name == 'عام':
            body_layout = QGridLayout(body)
            body_layout.setContentsMargins(2, 4, 8, 4)
            body_layout.setHorizontalSpacing(10)
            body_layout.setVerticalSpacing(10)
            widgets = [make_group(name, fields) for name, fields in groups]
            positions = [(0, 0, 1, 2), (1, 0, 1, 2), (2, 0, 1, 1), (2, 1, 1, 1), (3, 0, 1, 2)]
            for widget, (row, col, rowspan, colspan) in zip(widgets, positions):
                body_layout.addWidget(widget, row, col, rowspan, colspan)
            body_layout.setColumnStretch(0, 1)
            body_layout.setColumnStretch(1, 1)
            body_layout.setRowStretch(4, 1)
        else:
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(2, 4, 8, 4)
            body_layout.setSpacing(10)
            for group_name, fields in groups:
                body_layout.addWidget(make_group(group_name, fields))
            body_layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        footer = QLabel('تُحفظ الخيارات تلقائياً على هذا الجهاز. ربطها بمحرك تنفيذ اللعبة يتم على مراحل لاحقة.')
        footer.setObjectName('muted')
        outer.addWidget(footer)
        return page

    def show_section(self, index):
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index)
