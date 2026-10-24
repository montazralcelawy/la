import sqlite3
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import *

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'profiles.db'


def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, profile_id INTEGER,
        serial TEXT DEFAULT '', action TEXT NOT NULL,
        status TEXT DEFAULT 'جاهزة', result TEXT DEFAULT '',
        created TEXT DEFAULT CURRENT_TIMESTAMP)""")
    con.commit()
    return con


class TasksPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel('إدارة المهام')
        title.setObjectName('title')
        layout.addWidget(title)
        panel = QFrame()
        panel.setObjectName('panel')
        pl = QVBoxLayout(panel)
        pl.addWidget(QLabel('إنشاء مهمة جديدة'))
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText('مثال: فحص اتصال المحاكي')
        self.profile = QComboBox()
        self.profile.currentIndexChanged.connect(self.profile_changed)
        self.device = QComboBox()
        self.action = QComboBox()
        self.action.addItem('اختبار اتصال ADB', 'check')
        self.action.addItem('التقاط لقطة شاشة', 'screenshot')
        form.addRow('اسم المهمة:', self.name)
        form.addRow('ملف التعريف:', self.profile)
        form.addRow('الجهاز:', self.device)
        form.addRow('نوع المهمة:', self.action)
        pl.addLayout(form)
        buttons = QHBoxLayout()
        for label, fn, obj in [('＋ إنشاء مهمة', self.create_task, 'primary'),
                               ('⟳ تحديث الأجهزة', self.refresh_devices, ''),
                               ('▶ تشغيل المحددة', self.run_task, 'green'),
                               ('حذف المهمة', self.delete_task, 'red')]:
            b = QPushButton(label)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            buttons.addWidget(b)
        pl.addLayout(buttons)
        layout.addWidget(panel)
        table_panel = QFrame()
        table_panel.setObjectName('panel')
        tl = QVBoxLayout(table_panel)
        tl.addWidget(QLabel('قائمة المهام المحفوظة'))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['ID', 'اسم المهمة', 'ملف التعريف', 'الجهاز', 'نوع المهمة', 'الحالة / النتيجة'])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tl.addWidget(self.table)
        layout.addWidget(table_panel, 1)
        note = QLabel('تنفذ هذه الصفحة فحص اتصال ADB أو حفظ لقطة شاشة محلية فقط.')
        note.setObjectName('muted')
        layout.addWidget(note)
        self.reload_profiles()
        self.reload_tasks()

    def reload_profiles(self):
        old = self.profile.currentData()
        self.profile.blockSignals(True)
        self.profile.clear()
        con = db()
        rows = con.execute('SELECT id,name,serial,enabled FROM profiles ORDER BY name').fetchall()
        con.close()
        for pid, name, serial, enabled in rows:
            self.profile.addItem(name + ('' if enabled else ' (معطّل)'), (pid, serial or '', enabled))
        if old:
            idx = self.profile.findData(old)
            if idx >= 0:
                self.profile.setCurrentIndex(idx)
        self.profile.blockSignals(False)
        self.profile_changed()

    def profile_changed(self, *_):
        if not hasattr(self, 'device'):
            return
        data = self.profile.currentData()
        serial = data[1] if data else ''
        self.device.clear()
        self.device.addItem(serial or 'حدّث الأجهزة المتصلة لاختيار جهاز', serial)

    def refresh_devices(self):
        output = self.window.runadb(['devices'])
        if output is None:
            return
        devices = [x.split()[0] for x in output.splitlines()[1:]
                   if len(x.split()) >= 2 and x.split()[1] == 'device']
        old = self.device.currentData()
        self.device.clear()
        for serial in devices:
            self.device.addItem(serial, serial)
        if not devices:
            self.device.addItem('لا توجد أجهزة متصلة', '')
        if old:
            idx = self.device.findData(old)
            if idx >= 0:
                self.device.setCurrentIndex(idx)
        self.window.log('تم تحديث أجهزة المهام: ' + str(len(devices)))

    def create_task(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, 'اسم المهمة', 'اكتب اسماً للمهمة أولاً.')
            return
        profile = self.profile.currentData()
        serial = self.device.currentData() or ''
        if not serial:
            QMessageBox.warning(self, 'الجهاز غير محدد', 'حدد Serial في ملف التعريف أو حدّث قائمة الأجهزة.')
            return
        if profile and not profile[2]:
            QMessageBox.warning(self, 'ملف معطّل', 'فعّل ملف التعريف قبل إنشاء المهمة.')
            return
        con = db()
        con.execute('INSERT INTO tasks(name,profile_id,serial,action,status,result) VALUES(?,?,?,?,?,?)',
                    (name, profile[0] if profile else None, serial, self.action.currentData(), 'جاهزة', ''))
        con.commit()
        con.close()
        self.name.clear()
        self.window.log('تم إنشاء المهمة: ' + name)
        self.reload_tasks()

    def reload_tasks(self):
        con = db()
        rows = con.execute("""SELECT t.id,t.name,COALESCE(p.name,''),t.serial,t.action,t.status,t.result
                              FROM tasks t LEFT JOIN profiles p ON p.id=t.profile_id ORDER BY t.id DESC""").fetchall()
        con.close()
        self.table.setRowCount(len(rows))
        names = {'check': 'اختبار اتصال', 'screenshot': 'لقطة شاشة'}
        for i, row in enumerate(rows):
            vals = [row[0], row[1], row[2] or '—', row[3] or '—',
                    names.get(row[4], row[4]), row[5] + (': ' + row[6] if row[6] else '')]
            for j, value in enumerate(vals):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))

    def run_task(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, 'اختر مهمة', 'حدد مهمة من القائمة أولاً.')
            return
        task_id = int(self.table.item(row, 0).text())
        con = db()
        task = con.execute('SELECT name,serial,action FROM tasks WHERE id=?', (task_id,)).fetchone()
        con.close()
        if not task:
            return
        name, serial, action = task
        status, result = 'فشلت', ''
        try:
            if action == 'check':
                output = self.window.runadb(['-s', serial, 'get-state'])
                if output is not None and output.strip() == 'device':
                    status, result = 'نجحت', 'الجهاز متصل وجاهز'
                else:
                    result = 'لم يرجع الجهاز حالة اتصال سليمة'
            else:
                data = self.window.runadb(['-s', serial, 'exec-out', 'screencap', '-p'], True)
                if data and data[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10]):
                    folder = ROOT / 'screenshots'
                    folder.mkdir(exist_ok=True)
                    safe = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in serial)
                    path = folder / (safe + '_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.png')
                    path.write_bytes(data)
                    status, result = 'نجحت', 'حُفظت اللقطة: ' + str(path)
                else:
                    result = 'تعذر التقاط الشاشة؛ تحقق من اتصال الجهاز'
        except Exception as exc:
            result = str(exc)
        con = db()
        con.execute('UPDATE tasks SET status=?,result=? WHERE id=?', (status, result, task_id))
        con.commit()
        con.close()
        self.window.log('المهمة «' + name + '»: ' + status + ' — ' + result)
        self.reload_tasks()
        if status == 'نجحت':
            QMessageBox.information(self, 'اكتملت المهمة', result)
        else:
            QMessageBox.warning(self, 'تعذر إكمال المهمة', result or 'لم تنجح المهمة.')

    def delete_task(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, 'اختر مهمة', 'حدد مهمة من القائمة أولاً.')
            return
        task_id = int(self.table.item(row, 0).text())
        if QMessageBox.question(self, 'تأكيد الحذف', 'هل تريد حذف المهمة المحددة؟') != QMessageBox.Yes:
            return
        con = db()
        con.execute('DELETE FROM tasks WHERE id=?', (task_id,))
        con.commit()
        con.close()
        self.window.log('تم حذف مهمة محفوظة.')
        self.reload_tasks()
