import sys, sqlite3, subprocess, shutil
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import *

ROOT=Path(__file__).resolve().parent
DB=ROOT/'profiles.db'
STYLE='''
* {font-family:"Segoe UI",Arial; font-size:13px}
QMainWindow,QWidget{background:#0b1722;color:#e6edf5}
QFrame#panel,QGroupBox{background:#122230;border:1px solid #304252;border-radius:9px}
QLabel#title{font-size:22px;font-weight:700;color:#f4f7fb}
QLabel#metric{font-size:27px;font-weight:700}
QLabel#muted{color:#9baaba}
QPushButton{background:#203242;border:1px solid #3b5063;border-radius:6px;padding:8px 12px;color:#edf4fc}
QPushButton:hover{background:#2a4155}
QPushButton#primary{background:#5541b8;border-color:#7663e7;font-weight:600}
QPushButton#green{background:#287d3a;border-color:#3ca753;font-weight:600}
QPushButton#red{background:#a83238;border-color:#d74a4a;font-weight:600}
QPushButton#nav{text-align:right;padding:11px 13px;border:none;background:#142432;border-radius:7px}
QPushButton#nav:hover{background:#1d3041}
QPushButton#nav:checked{background:#443494;border:1px solid #6e5bdf}
QTableWidget{border-radius:7px}
QHeaderView::section{padding:10px}
QFrame#panel{background:#122230;border:1px solid #304252;border-radius:8px}
QLineEdit,QComboBox{background:#0c1a26;border:1px solid #344a5d;border-radius:5px;padding:7px;color:#f0f5fb}
QTableWidget{background:#0f1e2b;alternate-background-color:#142635;border:1px solid #304252;gridline-color:#293c4d;selection-background-color:#3e367f}
QHeaderView::section{background:#1a2b3a;color:#cbd6e2;border:none;padding:9px;font-weight:600}
QPlainTextEdit{background:#0b1823;border:1px solid #304252;border-radius:6px;color:#cbd6e2;padding:7px}
QGroupBox{margin-top:10px;padding-top:10px;font-weight:600}
'''
def db():
 c=sqlite3.connect(DB); c.execute('''CREATE TABLE IF NOT EXISTS profiles(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,serial TEXT DEFAULT '',village TEXT DEFAULT '',task TEXT DEFAULT 'غير نشط',enabled INTEGER DEFAULT 1,notes TEXT DEFAULT '')'''); c.commit(); return c
class Card(QFrame):
 def __init__(self,title,value,note,color):
  super().__init__(); self.setObjectName('panel'); l=QVBoxLayout(self); self.value=QLabel(value); self.value.setObjectName('metric'); self.value.setStyleSheet(f'color:{color}'); l.addWidget(self.value); l.addWidget(QLabel(title)); n=QLabel(note); n.setObjectName('muted'); l.addWidget(n); l.setContentsMargins(14,12,14,12)
class Window(QMainWindow):
 def __init__(self):
  super().__init__(); self.setWindowTitle('Clash Automation Lab'); self.resize(1360,820); self.selected=None; self.running=False; self.pages=QStackedWidget(); self.navs=[]; self.setCentralWidget(QWidget()); root=QHBoxLayout(self.centralWidget()); root.setContentsMargins(8,8,8,8); root.addWidget(self.pages,1)
  self.make_dashboard(); self.make_profiles(); self.make_emulator(); self.make_text_page('المهام',['إدارة مهام عامة ستُضاف في المرحلة التالية.','المشغّل الحالي تجريبي فقط.']); self.make_text_page('الإعدادات',['إعدادات الواجهة والاتصال ستُضاف لاحقاً.','لا تحفظ كلمات المرور أو رموز الدخول.']); self.make_logs()
  self.make_text_page('السكربتات',['هذه الصفحة مخصصة لإدارة السكربتات مستقبلاً.','لا يتم تشغيل سكربتات خارجية في هذه النسخة.'])
  self.make_text_page('حول البرنامج',['Clash Automation Lab','واجهة تجريبية لإدارة ملفات التعريف ومراقبة اتصال ADB.','الإصدار 1.0.0'])
  side=QFrame(); side.setObjectName('panel'); side.setFixedWidth(248); sl=QVBoxLayout(side); sl.setContentsMargins(12,16,12,14); sl.setSpacing(7)
  brand=QLabel('🛡  Clash Automation Lab'); brand.setStyleSheet('font-size:16px;font-weight:700;padding:8px 3px 16px 3px'); brand.setAlignment(Qt.AlignCenter); sl.addWidget(brand)
  for label,i in [('⌂  الرئيسية',0),('♙  ملفات التعريف',1),('☷  المهام',3),('▣  المحاكي و ADB',2),('⚙  الإعدادات',4),('‹›  السكربتات',6),('▤  السجل',5),('ⓘ  حول البرنامج',7)]:
   b=QPushButton(label); b.setObjectName('nav'); b.setCheckable(True); b.setMinimumHeight(42); b.clicked.connect(lambda _,n=i:self.switch(n)); sl.addWidget(b); self.navs.append((b,i))
  sl.addStretch()
  status=QFrame(); status.setObjectName('panel'); st=QVBoxLayout(status); st.setContentsMargins(12,12,12,12)
  st.addWidget(QLabel('●  الحالة العامة')); self.navstatus=QLabel('كل الأنظمة تعمل'); self.navstatus.setStyleSheet('color:#50cf68;font-size:18px;font-weight:bold'); self.navstatus.setAlignment(Qt.AlignCenter); st.addWidget(self.navstatus)
  shield=QLabel('🛡  ✓'); shield.setStyleSheet('color:#50cf68;font-size:38px;padding:10px'); shield.setAlignment(Qt.AlignCenter); st.addWidget(shield)
  st.addWidget(QLabel('الإصدار: 1.0.0'))
  updates=QPushButton('التحقق من التحديثات'); updates.clicked.connect(lambda:self.log('التحقق من التحديثات غير متاح دون إعداد خدمة تحديث.')); st.addWidget(updates)
  sl.addWidget(status); root.addWidget(side); self.switch(0); self.refresh(); self.log('تم تشغيل البرنامج. المشغّل تجريبي ولا ينفذ أوامر اللعبة.')
 def panel(self,title):
  f=QFrame(); f.setObjectName('panel'); l=QVBoxLayout(f); l.setContentsMargins(12,10,12,10); h=QLabel(title); h.setStyleSheet('font-size:15px;font-weight:bold'); l.addWidget(h); return f,l
 def title(self,s):
  x=QLabel(s); x.setObjectName('title'); return x
 def make_dashboard(self):
  p=QWidget(); l=QVBoxLayout(p); l.setContentsMargins(12,10,12,10); l.setSpacing(12)
  header=QHBoxLayout(); header.addWidget(self.title('▦  لوحة التحكم الرئيسية')); header.addStretch()
  refresh=QPushButton('⟳ تحديث البيانات'); refresh.clicked.connect(lambda:(self.refresh(),self.list_devices())); header.addWidget(refresh); l.addLayout(header)
  row=QHBoxLayout(); row.setSpacing(10)
  self.c1=Card('ملفات التعريف','0','0 نشطة','#a78bfa')
  self.c2=Card('المهام قيد التشغيل','0','من أصل 5','#ffad42')
  self.c3=Card('أجهزة متصلة','—','عبر ADB','#70a7ff')
  self.c4=Card('حالة البرنامج','جاهز','المشغّل متوقف','#4ecb74')
  for c in [self.c1,self.c2,self.c3,self.c4]: row.addWidget(c)
  l.addLayout(row)
  mid=QHBoxLayout(); mid.setSpacing(12)
  # Keep device monitoring on the left and the profile table in the main area.
  fdev,fd=self.panel('الأجهزة المتصلة (ADB)  ⟳')
  self.devices=QPlainTextEdit('لم يتم فحص الأجهزة بعد.'); self.devices.setReadOnly(True); self.devices.setMinimumWidth(235); self.devices.setMaximumHeight(245); fd.addWidget(self.devices)
  scan=QPushButton('⟳  تحديث الأجهزة'); scan.setObjectName('primary'); scan.clicked.connect(self.list_devices); fd.addWidget(scan)
  mid.addWidget(fdev,2)
  fp,fl=self.panel('ملفات التعريف')
  top=QHBoxLayout(); showall=QPushButton('عرض الكل'); showall.clicked.connect(lambda:self.switch(1)); top.addWidget(showall); top.addStretch()
  b=QPushButton('＋ جديد'); b.setObjectName('primary'); b.clicked.connect(self.new_and_open); top.addWidget(b); fl.addLayout(top)
  self.dtable=QTableWidget(0,5); self.dtable.setHorizontalHeaderLabels(['الحالة','القرية الرئيسية','الوضع','ADB Serial','اسم ملف التعريف']); self.setup_table(self.dtable); self.dtable.setMinimumHeight(220); fl.addWidget(self.dtable)
  mid.addWidget(fp,5); l.addLayout(mid,4)
  bot=QHBoxLayout(); bot.setSpacing(12)
  cf,cl=self.panel('التحكم السريع')
  rr=QHBoxLayout(); self.start=QPushButton('▶ بدء الكل'); self.start.setObjectName('green'); self.stop=QPushButton('■ إيقاف الكل'); self.stop.setObjectName('red'); self.stop.setEnabled(False); self.start.clicked.connect(self.start_demo); self.stop.clicked.connect(self.stop_demo); rr.addWidget(self.start); rr.addWidget(self.stop); cl.addLayout(rr)
  actions=QGridLayout()
  restart=QPushButton('⟳  إعادة تشغيل ADB'); restart.clicked.connect(self.restart_adb); actions.addWidget(restart,0,0)
  shot=QPushButton('▣  التقاط شاشة'); shot.clicked.connect(self.screenshot); actions.addWidget(shot,0,1)
  folder=QPushButton('▱  فتح مجلد البيانات'); folder.clicked.connect(self.open_data_folder); actions.addWidget(folder,1,0,1,2)
  cl.addLayout(actions)
  note=QLabel('المشغّل تجريبي فقط؛ لا ينفذ أوامر اللعبة.'); note.setObjectName('muted'); cl.addWidget(note)
  # Add the quick-control panel first so RTL places it on the right.
  bot.addWidget(cf,2)
  lf,ll=self.panel('سجل العمليات'); logtop=QHBoxLayout(); clear=QPushButton('مسح السجل'); clear.clicked.connect(self.clear_visible_logs); logtop.addStretch(); logtop.addWidget(clear); ll.addLayout(logtop)
  self.dlog=QPlainTextEdit(); self.dlog.setReadOnly(True); self.dlog.setMinimumHeight(145); ll.addWidget(self.dlog); bot.addWidget(lf,3)
  l.addLayout(bot,3)
  foot=QLabel('Clash Automation Lab 1.0.0   •   © 2026'); foot.setObjectName('muted'); foot.setAlignment(Qt.AlignCenter); l.addWidget(foot)
  self.pages.addWidget(p)

 def setup_table(self,t):
  t.setAlternatingRowColors(True); t.setSelectionBehavior(QTableWidget.SelectRows); t.setEditTriggers(QTableWidget.NoEditTriggers); t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
 def make_profiles(self):
  p=QWidget(); l=QVBoxLayout(p); l.addWidget(self.title('إدارة ملفات التعريف')); sp=QSplitter(); l.addWidget(sp,1); f,fl=self.panel('الملفات المحفوظة'); self.ftable=QTableWidget(0,5); self.ftable.setHorizontalHeaderLabels(['ID','اسم الملف','ADB Serial','القرية','مفعّل']); self.setup_table(self.ftable); self.ftable.itemSelectionChanged.connect(self.load_profile); fl.addWidget(self.ftable); rr=QHBoxLayout()
  for txt,fn in [('جديد',self.clear_form),('حفظ',self.save_profile),('حذف',self.delete_profile)]:
   b=QPushButton(txt); b.clicked.connect(fn); rr.addWidget(b)
  fl.addLayout(rr); sp.addWidget(f); f2,fl2=self.panel('تفاصيل ملف التعريف'); form=QFormLayout(); self.name=QLineEdit(); self.serial=QLineEdit(); self.village=QLineEdit(); self.task=QComboBox(); self.task.addItems(['غير نشط','مراقبة فقط','اختبار اتصال','التقاط لقطة شاشة']); self.notes=QLineEdit(); self.enabled=QCheckBox('ملف التعريف مفعّل'); self.enabled.setChecked(True)
  for label,w in [('اسم الملف:',self.name),('ADB Serial:',self.serial),('القرية / ملاحظة:',self.village),('المهمة الافتراضية:',self.task),('ملاحظات:',self.notes),('',self.enabled)]: form.addRow(label,w)
  fl2.addLayout(form); fl2.addWidget(QLabel('لا تدخل كلمات مرور أو بيانات تسجيل الدخول هنا.')); sp.addWidget(f2); sp.setSizes([600,400]); self.pages.addWidget(p)
 def make_emulator(self):
  p=QWidget(); l=QVBoxLayout(p); l.addWidget(self.title('المحاكي و ADB')); f,fl=self.panel('فحص اتصال Android Debug Bridge'); fl.addWidget(QLabel('اتصل بمحاكي محلي أو جهاز اختبار تملك صلاحية استخدامه.')); rr=QHBoxLayout()
  for txt,fn in [('فحص ADB',self.check_adb),('عرض الأجهزة',self.list_devices),('التقاط شاشة',self.screenshot)]:
   b=QPushButton(txt); b.clicked.connect(fn); rr.addWidget(b)
  fl.addLayout(rr); self.adbout=QPlainTextEdit(); self.adbout.setReadOnly(True); fl.addWidget(self.adbout); l.addWidget(f); l.addStretch(); self.pages.addWidget(p)
 def make_text_page(self,heading,lines):
  p=QWidget(); l=QVBoxLayout(p); l.addWidget(self.title(heading)); f,fl=self.panel(heading)
  for s in lines: fl.addWidget(QLabel(s))
  l.addWidget(f); l.addStretch(); self.pages.addWidget(p)
 def make_logs(self):
  p=QWidget(); l=QVBoxLayout(p); l.addWidget(self.title('سجل العمليات')); self.fulllog=QPlainTextEdit(); self.fulllog.setReadOnly(True); l.addWidget(self.fulllog,1); b=QPushButton('مسح السجل الظاهر'); b.clicked.connect(lambda:(self.fulllog.clear(),self.dlog.clear())); l.addWidget(b); self.pages.addWidget(p)
 def switch(self,i):
  self.pages.setCurrentIndex(i)
  for b,n in self.navs:b.setChecked(n==i)
 def log(self,s):
  line=f'[{datetime.now():%H:%M:%S}] {s}'
  for name in ['dlog','fulllog']:
   if hasattr(self,name):getattr(self,name).appendPlainText(line)
 def refresh(self):
  c=db(); rows=c.execute('SELECT id,name,serial,village,task,enabled,notes FROM profiles ORDER BY id').fetchall(); c.close()
  for table,full in [(getattr(self,'ftable',None),True),(getattr(self,'dtable',None),False)]:
   if table is None:continue
   table.setRowCount(len(rows))
   for r,x in enumerate(rows):
    vals=[x[0],x[1],x[2],x[3],'نعم' if x[5] else 'لا'] if full else [('مفعّل' if x[5] else 'متوقف'),x[3] or '—',x[4],x[2] or '—',x[1]]
    for col,v in enumerate(vals):table.setItem(r,col,QTableWidgetItem(str(v)))
  self.c1.value.setText(str(len(rows))); self.c2.value.setText(str(sum(1 for x in rows if x[5])))
 def new_and_open(self):self.clear_form(); self.switch(1)
 def clear_form(self):
  self.selected=None; self.ftable.clearSelection(); self.name.clear(); self.serial.clear(); self.village.clear(); self.task.setCurrentIndex(0); self.notes.clear(); self.enabled.setChecked(True)
 def load_profile(self):
  items=self.ftable.selectedItems()
  if not items:return
  r=items[0].row(); self.selected=int(self.ftable.item(r,0).text()); c=db(); x=c.execute('SELECT name,serial,village,task,enabled,notes FROM profiles WHERE id=?',(self.selected,)).fetchone(); c.close()
  if x:self.name.setText(x[0]); self.serial.setText(x[1]); self.village.setText(x[2]); self.task.setCurrentText(x[3]); self.enabled.setChecked(bool(x[4])); self.notes.setText(x[5])
 def save_profile(self):
  name=self.name.text().strip()
  if not name:QMessageBox.warning(self,'بيانات ناقصة','اكتب اسم ملف التعريف.'); return
  vals=(name,self.serial.text().strip(),self.village.text().strip(),self.task.currentText(),int(self.enabled.isChecked()),self.notes.text().strip()); c=db()
  try:
   if self.selected is None:c.execute('INSERT INTO profiles(name,serial,village,task,enabled,notes) VALUES(?,?,?,?,?,?)',vals); self.log('تمت إضافة ملف التعريف: '+name)
   else:c.execute('UPDATE profiles SET name=?,serial=?,village=?,task=?,enabled=?,notes=? WHERE id=?',vals+(self.selected,)); self.log('تم حفظ ملف التعريف: '+name)
   c.commit()
  except sqlite3.IntegrityError:QMessageBox.warning(self,'اسم مكرر','استخدم اسماً مختلفاً.')
  finally:c.close()
  self.refresh()
 def delete_profile(self):
  if self.selected is None:QMessageBox.information(self,'اختيار مطلوب','حدد ملفاً أولاً.'); return
  if QMessageBox.question(self,'تأكيد','حذف ملف التعريف المحدد؟')!=QMessageBox.Yes:return
  c=db(); c.execute('DELETE FROM profiles WHERE id=?',(self.selected,)); c.commit(); c.close(); self.log('تم حذف ملف التعريف.'); self.clear_form(); self.refresh()
 def adb(self):
  found=shutil.which('adb')
  if found:return found
  candidates=[Path(r'C:\\platform-tools\\adb.exe'),Path.home()/'AppData'/'Local'/'Android'/'Sdk'/'platform-tools'/'adb.exe']
  for x in candidates:
   if x.exists():return str(x)
  return None
 def runadb(self,args,binary=False):
  exe=self.adb()
  if not exe:QMessageBox.warning(self,'ADB غير موجود','ثبّت Android Platform Tools وأضف platform-tools إلى PATH.'); self.log('لم يتم العثور على ADB.'); return None
  try:
   r=subprocess.run([exe]+args,capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if r.returncode:return None
   return r.stdout if binary else r.stdout.decode(errors='replace').strip()
  except Exception as e:QMessageBox.warning(self,'خطأ ADB',str(e)); return None
 def check_adb(self):
  out=self.runadb(['version'])
  if out:self.log('ADB متاح: '+out.splitlines()[0]); self.adbout.appendPlainText(out) if hasattr(self,'adbout') else None
 def list_devices(self):
  out=self.runadb(['devices'])
  if out is not None:
   self.devices.setPlainText(out or 'لا توجد أجهزة.'); self.adbout.appendPlainText(out) if hasattr(self,'adbout') else None
   n=sum(1 for s in out.splitlines()[1:] if '\tdevice' in s); self.c3.value.setText(str(n)); self.log('تم تحديث قائمة أجهزة ADB.')
 def screenshot(self):
  serial=self.serial.text().strip() if hasattr(self,'serial') else ''; path,_=QFileDialog.getSaveFileName(self,'حفظ لقطة الشاشة',str(ROOT/'screenshot.png'),'PNG Image (*.png)')
  if not path:return
  args=(['-s',serial] if serial else [])+['exec-out','screencap','-p']; data=self.runadb(args,True)
  if data:
   try:Path(path).write_bytes(data); self.log('تم حفظ لقطة الشاشة: '+path); QMessageBox.information(self,'نجاح','تم حفظ لقطة الشاشة.')
   except Exception as e:QMessageBox.warning(self,'خطأ',str(e))
 def restart_adb(self):
  exe=self.adb()
  if not exe:
   QMessageBox.warning(self,'ADB غير موجود','تعذر العثور على adb.exe.'); return
  try:
   stop=subprocess.run([exe,'kill-server'],capture_output=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   start=subprocess.run([exe,'start-server'],capture_output=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if start.returncode==0:
    self.log('تمت إعادة تشغيل خادم ADB.'); self.list_devices()
   else: QMessageBox.warning(self,'خطأ ADB',start.stderr.decode(errors='replace'))
  except Exception as e: QMessageBox.warning(self,'خطأ ADB',str(e))
 def open_data_folder(self):
  try:
   if sys.platform=='win32': subprocess.Popen(['explorer',str(ROOT)])
   else: QMessageBox.information(self,'مجلد البيانات',str(ROOT))
   self.log('تم فتح مجلد بيانات البرنامج.')
  except Exception as e: QMessageBox.warning(self,'خطأ',str(e))
 def clear_visible_logs(self):
  self.dlog.clear()
  if hasattr(self,'fulllog'): self.fulllog.clear()
  self.log('تم مسح السجل الظاهر.')
 def start_demo(self):self.running=True; self.start.setEnabled(False); self.stop.setEnabled(True); self.c4.value.setText('يعمل'); self.navstatus.setText('تشغيل تجريبي'); self.log('بدأ المشغّل التجريبي؛ لا توجد أوامر لعب تُنفّذ.')
 def stop_demo(self):self.running=False; self.start.setEnabled(True); self.stop.setEnabled(False); self.c4.value.setText('جاهز'); self.navstatus.setText('جاهز'); self.log('تم إيقاف المشغّل التجريبي.')
if __name__=='__main__':
 app=QApplication(sys.argv); app.setLayoutDirection(Qt.RightToLeft); app.setStyleSheet(STYLE); w=Window(); w.show(); sys.exit(app.exec())
