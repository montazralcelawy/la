# Clash Automation Lab v2

واجهة عربية داكنة متعددة الصفحات لإدارة ملفات التعريف، سجل العمليات، وفحص ADB والتقاط لقطة شاشة.

## التشغيل على Windows
1. ثبّت Python 3.11 أو أحدث من https://www.python.org/downloads/windows/
2. فك ضغط المشروع وافتح CMD داخل المجلد.
3. نفّذ:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install PySide6
python main.py
```

## ملاحظات
- ملفات التعريف تحفظ محلياً في `profiles.db`.
- ADB اختياري؛ ثبّت Android Platform Tools وأضف مجلد `platform-tools` إلى PATH.
- لا تدخل كلمات مرور أو رموز تسجيل دخول في ملفات التعريف.
- مشغّل المهام تجريبي ولا ينفذ أوامر داخل اللعبة.

## بناء EXE
```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --name ClashAutomationLab main.py
```
سيظهر البرنامج داخل مجلد `dist`.
