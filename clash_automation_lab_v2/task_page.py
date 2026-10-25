import sqlite3
import sys
import json
from pathlib import Path
from datetime import datetime
import subprocess
import threading
import time
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import *

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
DB = ROOT / 'profiles.db'


def latest_screenshot_path(root=None):
    """Return the newest valid screenshot path, or None when none exist."""
    folder = Path(root) / 'screenshots' if root is not None else ROOT / 'screenshots'
    if not folder.is_dir():
        return None
    candidates = [p for p in folder.glob('*.png') if p.is_file()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def db():
    con = sqlite3.connect(DB)
    # Initialize every table needed by the task page. Older packaged databases
    # may contain tasks but not profiles, so this must be safe on every launch.
    con.execute("""CREATE TABLE IF NOT EXISTS profiles(
        id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
        serial TEXT DEFAULT '', village TEXT DEFAULT '',
        task TEXT DEFAULT 'غير نشط', enabled INTEGER DEFAULT 1,
        notes TEXT DEFAULT '')""")
    con.execute("""CREATE TABLE IF NOT EXISTS app_settings(
        key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, profile_id INTEGER,
        serial TEXT DEFAULT '', action TEXT NOT NULL,
        status TEXT DEFAULT 'جاهزة', result TEXT DEFAULT '',
        created TEXT DEFAULT CURRENT_TIMESTAMP)""")
    columns = {row[1] for row in con.execute('PRAGMA table_info(tasks)').fetchall()}
    if 'params' not in columns:
        con.execute("ALTER TABLE tasks ADD COLUMN params TEXT NOT NULL DEFAULT '{}'")
    con.commit()
    return con


class TaskWorker(QThread):
    completed = Signal(int, str, str, str)

    def __init__(self, task_id, name, serial, action, adb_path, params=None):
        super().__init__()
        self.task_id = task_id
        self.task_name = name
        self.serial = serial
        self.action = action
        self.adb_path = adb_path
        self.params = params or {}
        self.cancel_requested = threading.Event()
        self.process = None

    def cancel(self):
        self.cancel_requested.set()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()

    def run(self):
        status, result = 'فشلت', ''
        try:
            if self.action == 'wait':
                duration = max(0, min(int(self.params.get('duration_ms', 1000)), 3600000))
                if self.cancel_requested.wait(duration / 1000):
                    status, result = 'أُلغيت', 'أُوقف الانتظار بطلب المستخدم.'
                else:
                    status, result = 'نجحت', f'انتهى الانتظار لمدة {duration} مللي ثانية.'
            else:
                if not self.adb_path:
                    raise RuntimeError('لم يتم العثور على ADB. تحقق من Android Platform Tools.')
                if not self.serial:
                    raise RuntimeError('لم يتم تحديد جهاز ADB لهذه المهمة.')
                args = [self.adb_path, '-s', self.serial]
                if self.action == 'check':
                    args += ['get-state']
                elif self.action == 'launch_game':
                    args += ['shell', 'monkey', '-p', self.params.get('package', 'com.supercell.clashofclans'),
                             '-c', 'android.intent.category.LAUNCHER', '1']
                elif self.action == 'tap':
                    args += ['shell', 'input', 'tap', str(int(self.params.get('x', 0))),
                             str(int(self.params.get('y', 0)))]
                elif self.action == 'swipe':
                    args += ['shell', 'input', 'swipe',
                             str(int(self.params.get('x', 0))), str(int(self.params.get('y', 0))),
                             str(int(self.params.get('x2', 0))), str(int(self.params.get('y2', 0))),
                             str(int(self.params.get('duration_ms', 500)))]
                elif self.action == 'press_back':
                    args += ['shell', 'input', 'keyevent', '4']
                elif self.action == 'press_home':
                    args += ['shell', 'input', 'keyevent', '3']
                elif self.action == 'screenshot':
                    args += ['exec-out', 'screencap', '-p']
                else:
                    raise RuntimeError('نوع المهمة غير مدعوم: ' + str(self.action))

                self.process = subprocess.Popen(
                    args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                deadline = time.monotonic() + 25
                stdout, stderr = b'', b''
                timed_out = False
                while True:
                    if self.cancel_requested.is_set() and self.process.poll() is None:
                        self.process.terminate()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 and self.process.poll() is None:
                        self.process.kill()
                        stdout, stderr = self.process.communicate()
                        timed_out = True
                        break
                    try:
                        stdout, stderr = self.process.communicate(timeout=min(0.1, max(0.01, remaining)))
                        break
                    except subprocess.TimeoutExpired:
                        continue

                if self.cancel_requested.is_set():
                    status, result = 'أُلغيت', 'أُوقف تنفيذ المهمة بطلب المستخدم.'
                elif timed_out:
                    result = 'انتهت مهلة تنفيذ ADB بعد 25 ثانية.'
                elif self.process.returncode != 0:
                    result = stderr.decode(errors='replace').strip() or 'فشل أمر ADB؛ تحقق من اتصال الجهاز.'
                elif self.action == 'check':
                    state = stdout.decode(errors='replace').strip()
                    if state == 'device':
                        status, result = 'نجحت', 'الجهاز متصل وجاهز.'
                    else:
                        result = 'حالة الجهاز غير متوقعة: ' + (state or 'لا توجد استجابة')
                elif self.action == 'screenshot':
                    if stdout[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10]):
                        folder = ROOT / 'screenshots'
                        folder.mkdir(exist_ok=True)
                        safe = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in self.serial)
                        path = folder / (safe + '_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.png')
                        path.write_bytes(stdout)
                        status, result = 'نجحت', 'حُفظت اللقطة: ' + str(path)
                    else:
                        result = 'تعذر التقاط صورة صالحة؛ تحقق من اتصال الجهاز.'
                else:
                    status = 'نجحت'
                    messages = {
                        'launch_game': 'تم إرسال أمر فتح التطبيق إلى الجهاز.',
                        'tap': f'تم إرسال أمر اللمس إلى الإحداثيات ({self.params.get("x", 0)}, {self.params.get("y", 0)}).',
                        'swipe': 'تم إرسال أمر السحب إلى الجهاز.',
                        'press_back': 'تم إرسال أمر الرجوع إلى الجهاز.',
                        'press_home': 'تم إرسال أمر الشاشة الرئيسية إلى الجهاز.',
                    }
                    result = messages.get(self.action, 'تم تنفيذ أمر ADB.')
        except Exception as exc:
            status, result = 'فشلت', str(exc)
        self.completed.emit(self.task_id, status, result, self.task_name)


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
        self.action.addItem('فتح لعبة Clash of Clans', 'launch_game')
        self.action.addItem('لمس الشاشة عند إحداثيات', 'tap')
        self.action.addItem('سحب الشاشة بين إحداثيات', 'swipe')
        self.action.addItem('انتظار لمدة محددة', 'wait')
        self.action.addItem('زر الرجوع', 'press_back')
        self.action.addItem('زر الشاشة الرئيسية', 'press_home')
        self.x = QSpinBox(); self.x.setRange(0, 10000)
        self.y = QSpinBox(); self.y.setRange(0, 10000)
        self.x2 = QSpinBox(); self.x2.setRange(0, 10000)
        self.y2 = QSpinBox(); self.y2.setRange(0, 10000)
        self.duration = QSpinBox(); self.duration.setRange(0, 3600000); self.duration.setValue(500)
        self.package = QLineEdit('com.supercell.clashofclans')
        form.addRow('X / بداية السحب:', self.x)
        form.addRow('Y / بداية السحب:', self.y)
        form.addRow('X2 / نهاية السحب:', self.x2)
        form.addRow('Y2 / نهاية السحب:', self.y2)
        form.addRow('المدة (مللي ثانية):', self.duration)
        form.addRow('حزمة التطبيق:', self.package)
        self.action.currentIndexChanged.connect(self.action_changed)
        self.action_changed()
        form.addRow('اسم المهمة:', self.name)
        form.addRow('ملف التعريف:', self.profile)
        form.addRow('الجهاز:', self.device)
        form.addRow('نوع المهمة:', self.action)
        pl.addLayout(form)
        buttons = QHBoxLayout()
        for label, fn, obj in [('＋ إنشاء مهمة', self.create_task, 'primary'),
                               ('▣ عرض آخر لقطة', self.show_latest_screenshot, ''),
                               ('⟳ تحديث الأجهزة', self.refresh_devices, ''),
                               ('▶ تشغيل المحددة', self.run_task, 'green'),
                               ('▶ تشغيل كل الجاهزة', self.run_queue, 'green'),
                               ('■ إيقاف المهمة', self.stop_task, 'red'),
                               ('↻ إعادة المحددة', self.reset_selected_task, ''),
                               ('↻ إعادة الكل', self.reset_all_tasks, ''),
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
        note = QLabel('المهام المدعومة: فحص ADB، فتح التطبيق، لقطة شاشة، لمس/سحب بإحداثيات، انتظار، رجوع، والشاشة الرئيسية. نفّذ الإحداثيات بحذر وتأكد من دقة شاشة المحاكي.')
        note.setObjectName('muted')
        layout.addWidget(note)
        self.worker = None
        self.queue_ids = []
        self.queue_running = False
        con = db()
        con.execute("UPDATE tasks SET status='متوقفة',result='أُعيد تشغيل البرنامج قبل اكتمال المهمة.' WHERE status='قيد التشغيل'")
        con.commit()
        con.close()
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
        # Reuse the main window's local BlueStacks port discovery before listing devices.
        self.window.list_devices()
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
        if not serial and self.action.currentData() != 'wait':
            QMessageBox.warning(self, 'الجهاز غير محدد', 'حدد Serial في ملف التعريف أو حدّث قائمة الأجهزة.')
            return
        if profile and not profile[2]:
            QMessageBox.warning(self, 'ملف معطّل', 'فعّل ملف التعريف قبل إنشاء المهمة.')
            return
        params = {'x': self.x.value(), 'y': self.y.value(), 'x2': self.x2.value(),
                  'y2': self.y2.value(), 'duration_ms': self.duration.value(),
                  'package': self.package.text().strip() or 'com.supercell.clashofclans'}
        con = db()
        con.execute('INSERT INTO tasks(name,profile_id,serial,action,status,result,params) VALUES(?,?,?,?,?,?,?)',
                    (name, profile[0] if profile else None, serial, self.action.currentData(), 'جاهزة', '',
                     json.dumps(params, ensure_ascii=False)))
        con.commit()
        con.close()
        self.name.clear()
        self.window.log('تم إنشاء المهمة: ' + name)
        self.reload_tasks()

    def action_changed(self, *_):
        action = self.action.currentData()
        self.x.setEnabled(action in ('tap', 'swipe'))
        self.y.setEnabled(action in ('tap', 'swipe'))
        self.x2.setEnabled(action == 'swipe')
        self.y2.setEnabled(action == 'swipe')
        self.duration.setEnabled(action in ('swipe', 'wait'))
        self.package.setEnabled(action == 'launch_game')

    def reload_tasks(self):
        con = db()
        rows = con.execute("""SELECT t.id,t.name,COALESCE(p.name,''),t.serial,t.action,t.status,t.result
                              FROM tasks t LEFT JOIN profiles p ON p.id=t.profile_id ORDER BY t.id DESC""").fetchall()
        con.close()
        self.table.setRowCount(len(rows))
        names = {
            'check': 'اختبار اتصال', 'screenshot': 'لقطة شاشة',
            'launch_game': 'فتح التطبيق', 'tap': 'لمس الشاشة',
            'swipe': 'سحب الشاشة', 'wait': 'انتظار',
            'press_back': 'زر الرجوع', 'press_home': 'الشاشة الرئيسية'
        }
        for i, row in enumerate(rows):
            vals = [row[0], row[1], row[2] or '—', row[3] or '—',
                    names.get(row[4], row[4]), row[5] + (': ' + row[6] if row[6] else '')]
            for j, value in enumerate(vals):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))

    def run_queue(self, checked=False):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, 'المهمة قيد التنفيذ', 'انتظر انتهاء المهمة الحالية قبل تشغيل قائمة المهام.')
            return
        con = db()
        self.queue_ids = [row[0] for row in con.execute(
            "SELECT id FROM tasks WHERE status='جاهزة' ORDER BY id ASC").fetchall()]
        con.close()
        if not self.queue_ids:
            QMessageBox.information(self, 'لا توجد مهام جاهزة', 'أنشئ مهام أو أعد المهام المطلوبة إلى حالة جاهزة أولاً.')
            return
        self.queue_running = True
        if hasattr(self.window, 'queue_state_changed'):
            self.window.queue_state_changed(True)
        self.window.log('بدأ تنفيذ قائمة من ' + str(len(self.queue_ids)) + ' مهمة.')
        self.run_next_queued_task()

    def run_next_queued_task(self):
        if not self.queue_running:
            return
        if not self.queue_ids:
            self.queue_running = False
            if hasattr(self.window, 'queue_state_changed'):
                self.window.queue_state_changed(False)
            self.window.log('اكتمل تنفيذ قائمة المهام.')
            QMessageBox.information(self, 'اكتملت القائمة', 'انتهى تنفيذ جميع المهام الجاهزة. راجع حالة ونتيجة كل مهمة في الجدول.')
            return
        task_id = self.queue_ids.pop(0)
        # Do not depend on table selection: refreshing the table can clear the selection.
        self.run_task(quiet=True, from_queue=True, task_id=task_id)

    def run_task(self, checked=False, quiet=False, from_queue=False, task_id=None):
        if self.worker is not None and self.worker.isRunning():
            if not quiet:
                QMessageBox.information(self, 'المهمة قيد التنفيذ', 'انتظر انتهاء المهمة الحالية قبل تشغيل مهمة أخرى.')
            return
        if task_id is None:
            row = self.table.currentRow()
            if row < 0:
                if not quiet:
                    QMessageBox.information(self, 'اختر مهمة', 'حدد مهمة من القائمة أولاً.')
                return
            task_id = int(self.table.item(row, 0).text())
        con = db()
        task = con.execute('SELECT name,serial,action,status,params FROM tasks WHERE id=?', (task_id,)).fetchone()
        con.close()
        if not task:
            self.window.log('تعذر العثور على المهمة ' + str(task_id) + '.')
            if from_queue:
                self.run_next_queued_task()
            return
        name, serial, action, old_status, params_text = task
        try:
            params = json.loads(params_text or '{}')
            if not isinstance(params, dict):
                params = {}
        except (TypeError, ValueError):
            params = {}
        if from_queue and old_status != 'جاهزة':
            self.window.log('تم تجاوز المهمة ' + str(task_id) + ' لأن حالتها الحالية هي: ' + old_status)
            self.run_next_queued_task()
            return
        if old_status == 'قيد التشغيل':
            if not quiet:
                QMessageBox.information(self, 'المهمة قيد التنفيذ', 'هذه المهمة مسجلة على أنها قيد التشغيل بالفعل.')
            return
        con = db()
        con.execute("UPDATE tasks SET status='قيد التشغيل',result='' WHERE id=?", (task_id,))
        con.commit()
        con.close()
        self.reload_tasks()
        self.window.log('بدأت المهمة «' + name + '» (ID: ' + str(task_id) + ').')
        self.worker = TaskWorker(task_id, name, serial, action, self.window.adb(), params)
        self.worker.completed.connect(self.task_finished)
        self.worker.start()

    def stop_task(self):
        if self.queue_running:
            self.queue_running = False
            self.queue_ids = []
            if hasattr(self.window, 'queue_state_changed'):
                self.window.queue_state_changed(False)
            self.window.log('تم إيقاف قائمة المهام؛ ستتوقف المهمة الحالية إن كانت قيد التنفيذ.')
        if self.worker is None or not self.worker.isRunning():
            QMessageBox.information(self, 'لا توجد مهمة نشطة', 'لا توجد مهمة قيد التنفيذ حالياً.')
            return
        self.worker.cancel()
        self.window.log('تم طلب إيقاف المهمة الحالية.')

    def task_finished(self, task_id, status, result, name):
        con = db()
        con.execute('UPDATE tasks SET status=?,result=? WHERE id=?', (status, result, task_id))
        con.commit()
        con.close()
        self.window.log('المهمة «' + name + '»: ' + status + ' — ' + result)
        self.reload_tasks()
        self.worker = None
        if self.queue_running:
            self.run_next_queued_task()
            return
        if status == 'نجحت':
            QMessageBox.information(self, 'اكتملت المهمة', result)
        elif status == 'فشلت':
            QMessageBox.warning(self, 'تعذر إكمال المهمة', result or 'لم تنجح المهمة.')

    def show_latest_screenshot(self):
        path = latest_screenshot_path()
        if path is None:
            QMessageBox.information(
                self, 'لا توجد لقطة شاشة',
                'التقط لقطة شاشة أولاً من صفحة المهام أو صفحة المحاكي وADB.'
            )
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            QMessageBox.warning(self, 'تعذر عرض الصورة', 'تعذر فتح ملف الصورة: ' + str(path))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle('معاينة آخر لقطة شاشة')
        dialog.resize(1100, 800)
        layout = QVBoxLayout(dialog)
        info = QLabel(
            f'{path.name} — الأبعاد: {pixmap.width()} × {pixmap.height()} بكسل'
        )
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        image_label = QLabel()
        image_label.setPixmap(pixmap)
        image_label.setFixedSize(pixmap.size())
        scroll.setWidget(image_label)
        layout.addWidget(scroll, 1)

        location = QLabel(str(path))
        location.setTextInteractionFlags(Qt.TextSelectableByMouse)
        location.setWordWrap(True)
        layout.addWidget(location)
        close_button = QPushButton('إغلاق')
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

    def reset_selected_task(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, 'المهمة قيد التنفيذ', 'أوقف المهمة الحالية قبل إعادة تعيين الحالات.')
            return
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, 'اختر مهمة', 'حدد مهمة من القائمة أولاً.')
            return
        task_id = int(self.table.item(row, 0).text())
        con = db()
        cur = con.execute("UPDATE tasks SET status='جاهزة',result='' WHERE id=? AND status!='قيد التشغيل'", (task_id,))
        con.commit()
        con.close()
        if cur.rowcount:
            self.window.log('أُعيدت المهمة ' + str(task_id) + ' إلى حالة جاهزة.')
        self.reload_tasks()

    def reset_all_tasks(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, 'المهمة قيد التنفيذ', 'أوقف المهمة الحالية قبل إعادة تعيين الحالات.')
            return
        answer = QMessageBox.question(
            self, 'إعادة تعيين المهام',
            'إعادة جميع المهام غير النشطة إلى حالة جاهزة؟ ستُمسح نتائجها السابقة من الجدول.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        con = db()
        cur = con.execute("UPDATE tasks SET status='جاهزة',result='' WHERE status!='قيد التشغيل'")
        count = cur.rowcount
        con.commit()
        con.close()
        self.window.log('أُعيدت ' + str(count) + ' مهمة إلى حالة جاهزة.')
        self.reload_tasks()

    def delete_task(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, 'المهمة قيد التنفيذ', 'أوقف المهمة وانتظر انتهائها قبل حذف المهام.')
            return
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
