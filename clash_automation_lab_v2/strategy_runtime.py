"""ADB-backed, template/OCR-driven runtime for the strategy engine.

All image coordinates are normalized to the current screenshot size in the
JSON profile. No game action is taken unless the screen and target templates
meet configured confidence thresholds.
"""
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from strategy_engine import (
    ActionType, Candidate, GameObservation, PolicyConfig, Screen, StrategyEngine
)


DEFAULT_PACKAGE = "com.supercell.clashofclans"


def _resource_number(text: str) -> Optional[int]:
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    cleaned = text.upper().replace(",", "").replace(" ", "").replace(".", ".")
    match = re.search(r"\d+(?:\.\d+)?\s*[KMB]?", cleaned)
    if not match:
        return None
    token = match.group(0).replace(" ", "")
    multiplier = 1
    if token.endswith("K"):
        multiplier, token = 1_000, token[:-1]
    elif token.endswith("M"):
        multiplier, token = 1_000_000, token[:-1]
    elif token.endswith("B"):
        multiplier, token = 1_000_000_000, token[:-1]
    try:
        return int(float(token) * multiplier)
    except ValueError:
        return None


class TemplateVision:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path).expanduser().resolve()
        if not self.config_path.is_file():
            raise RuntimeError("ملف إعدادات الرؤية غير موجود: " + str(self.config_path))
        try:
            self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError("تعذر قراءة ملف إعدادات الرؤية JSON: " + str(exc)) from exc
        if not isinstance(self.config, dict):
            raise RuntimeError("ملف إعدادات الرؤية يجب أن يحتوي كائن JSON.")
        if not self.config.get("screen_templates"):
            raise RuntimeError("إعدادات الرؤية فارغة: أضف صورة قالب واحدة على الأقل لكل شاشة تريد تشغيلها داخل screen_templates.")
        if not self.config.get("button_templates"):
            raise RuntimeError("إعدادات الرؤية لا تحتوي قوالب أزرار؛ أضف قوالب الأزرار داخل button_templates قبل التشغيل.")
        self.base = self.config_path.parent
        self.threshold = float(self.config.get("min_confidence", 0.88))
        self.threshold = max(0.5, min(self.threshold, 0.999))
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("يلزم تثبيت opencv-python-headless لتشغيل الرؤية.") from exc
        self.cv2, self.np = cv2, np
        self._template_cache = {}

    def _path(self, value):
        path = Path(str(value)).expanduser()
        return path if path.is_absolute() else (self.base / path).resolve()

    def _template(self, value):
        path = self._path(value)
        key = str(path)
        if key not in self._template_cache:
            image = self.cv2.imread(key, self.cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError("تعذر قراءة قالب الصورة: " + key)
            self._template_cache[key] = image
        return self._template_cache[key]

    def _match(self, screenshot, template_path, threshold=None):
        template = self._template(template_path)
        sh, sw = screenshot.shape[:2]
        th, tw = template.shape[:2]
        if th > sh or tw > sw:
            return None
        score = self.cv2.matchTemplate(screenshot, template, self.cv2.TM_CCOEFF_NORMED)
        _, confidence, _, location = self.cv2.minMaxLoc(score)
        required = self.threshold if threshold is None else max(0.5, min(float(threshold), 0.999))
        if confidence < required:
            return None
        return Candidate(
            name=str(template_path),
            x=int(location[0] + tw // 2),
            y=int(location[1] + th // 2),
            confidence=float(confidence),
        )

    def _ocr_region(self, screenshot, region):
        try:
            import pytesseract
        except ImportError:
            return None
        command = self.config.get("tesseract_cmd")
        if command:
            pytesseract.pytesseract.tesseract_cmd = str(self._path(command))
        height, width = screenshot.shape[:2]
        x, y, w, h = [float(v) for v in region]
        # Config regions are normalized fractions from 0 to 1.
        if max(abs(x), abs(y), abs(w), abs(h)) <= 1.0:
            x, y, w, h = x * width, y * height, w * width, h * height
        x, y, w, h = int(x), int(y), int(w), int(h)
        x, y = max(0, x), max(0, y)
        crop = screenshot[y:min(height, y + h), x:min(width, x + w)]
        if crop.size == 0:
            return None
        gray = self.cv2.cvtColor(crop, self.cv2.COLOR_BGR2GRAY)
        gray = self.cv2.resize(gray, None, fx=2, fy=2, interpolation=self.cv2.INTER_CUBIC)
        text = pytesseract.image_to_string(gray, config="--psm 7")
        return _resource_number(text)

    def observe(self, screenshot_bytes: bytes) -> GameObservation:
        image = self.cv2.imdecode(self.np.frombuffer(screenshot_bytes, dtype=self.np.uint8), self.cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("تعذر فك لقطة شاشة ADB.")
        screens = self.config.get("screen_templates", {})
        best_screen, best_candidate = Screen.UNKNOWN, None
        for screen_name, path in screens.items():
            try:
                screen = Screen(screen_name)
            except ValueError:
                continue
            candidate = self._match(image, path)
            if candidate and (best_candidate is None or candidate.confidence > best_candidate.confidence):
                best_screen, best_candidate = screen, candidate
        screen_confidence = best_candidate.confidence if best_candidate else 0.0

        buttons = {}
        for name, spec in self.config.get("button_templates", {}).items():
            path = spec.get("template") if isinstance(spec, dict) else spec
            threshold = spec.get("threshold", self.threshold) if isinstance(spec, dict) else self.threshold
            candidate = self._match(image, path, threshold)
            if candidate:
                buttons[name] = Candidate(name, candidate.x, candidate.y, confidence=candidate.confidence)

        resources = {}
        for name, region in self.config.get("resource_regions", {}).items():
            resources[name] = self._ocr_region(image, region)

        troop_slots = []
        for spec in self.config.get("troop_slots", []):
            candidate = self._match(image, spec["template"], spec.get("threshold", self.threshold))
            if candidate:
                troop_slots.append(Candidate(
                    str(spec.get("name", "troop")), candidate.x, candidate.y,
                    confidence=candidate.confidence
                ))

        upgrades = []
        for spec in self.config.get("upgrade_candidates", []):
            candidate = self._match(image, spec["template"], spec.get("threshold", self.threshold))
            if candidate:
                upgrades.append(Candidate(
                    str(spec.get("name", "upgrade")), candidate.x, candidate.y,
                    cost_gold=int(spec.get("cost_gold", 0)),
                    cost_elixir=int(spec.get("cost_elixir", 0)),
                    cost_dark=int(spec.get("cost_dark", 0)),
                    category=str(spec.get("category", "other")),
                    confidence=candidate.confidence,
                ))

        height, width = image.shape[:2]
        points = []
        for point in self.config.get("deployment_points", []):
            x, y = float(point[0]), float(point[1])
            if 0 <= x <= 1 and 0 <= y <= 1:
                points.append((int(x * width), int(y * height)))
            else:
                points.append((int(x), int(y)))

        status = self.config.get("status_templates", {})
        def status_visible(name):
            path = status.get(name)
            return bool(path and self._match(image, path))

        return GameObservation(
            screen=best_screen,
            confidence=screen_confidence,
            gold=resources.get("gold"),
            elixir=resources.get("elixir"),
            dark_elixir=resources.get("dark_elixir"),
            army_ready=True if status_visible("army_ready") else (
                False if status_visible("army_not_ready") else None),
            camp_full=True if status_visible("camp_full") else (
                False if status_visible("camp_not_full") else None),
            builders_available=(1 if "builders" in buttons else None),
            shield_active=True if status_visible("shield_active") else (
                False if status_visible("shield_inactive") else None),
            buttons=buttons,
            upgrade_candidates=tuple(upgrades),
            troop_slots=tuple(troop_slots),
            deployment_points=tuple(points),
            battle_ended=True if status_visible("battle_ended") else None,
        )


class ADBStrategyRuntime:
    def __init__(self, adb_path: str, serial: str, config_path: str,
                 package: str = DEFAULT_PACKAGE, max_steps: int = 500):
        if not adb_path or not serial:
            raise RuntimeError("حدد مسار ADB والجهاز قبل تشغيل محرك الاستراتيجية.")
        self.adb_path, self.serial = adb_path, serial
        self.package = package or DEFAULT_PACKAGE
        self.vision = TemplateVision(config_path)
        cfg = self.vision.config.get("policy", {})
        self.engine = StrategyEngine(PolicyConfig(
            min_gold=int(cfg.get("min_gold", 100_000)),
            min_elixir=int(cfg.get("min_elixir", 100_000)),
            min_dark_elixir=int(cfg.get("min_dark_elixir", 0)),
            min_candidate_confidence=float(cfg.get("min_candidate_confidence", 0.88)),
            attack_when_loot_low=bool(cfg.get("attack_when_loot_low", True)),
            collect_resources=bool(cfg.get("collect_resources", True)),
            upgrade_buildings=bool(cfg.get("upgrade_buildings", True)),
            train_army=bool(cfg.get("train_army", True)),
            deploy_pattern=str(cfg.get("deploy_pattern", "two_sides")),
            max_searches_per_cycle=int(cfg.get("max_searches_per_cycle", 30)),
        ))
        self.max_steps = max(1, min(int(max_steps), 5000))
        self.last_observation = None
        self._deploy_index = 0

    def _run(self, args, timeout=15):
        result = subprocess.run(
            [self.adb_path, "-s", self.serial] + list(args),
            capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace").strip() or "فشل أمر ADB.")
        return result.stdout

    def _game_is_foreground(self):
        output = self._run(["shell", "dumpsys", "window", "windows"], timeout=8)
        lines = [line for line in output.decode(errors="replace").splitlines()
                 if "mCurrentFocus" in line or "mFocusedApp" in line]
        return any(self.package in line for line in lines)

    def _ensure_game_foreground(self):
        if not self._game_is_foreground():
            raise RuntimeError("توقفت الأتمتة لأن اللعبة ليست في المقدمة.")

    def _launch_game_if_needed(self, cancelled):
        if self._game_is_foreground():
            return
        package_path = self._run(["shell", "pm", "path", self.package], timeout=10)
        if not package_path.decode(errors="replace").strip().startswith("package:"):
            raise RuntimeError("لعبة Clash of Clans غير مثبتة على الجهاز المحدد.")
        self._run(["shell", "monkey", "-p", self.package,
                   "-c", "android.intent.category.LAUNCHER", "1"], timeout=15)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if cancelled():
                raise RuntimeError("أوقف المستخدم التشغيل أثناء فتح اللعبة.")
            if self._game_is_foreground():
                return
            time.sleep(0.75)
        raise RuntimeError("أُرسل أمر فتح اللعبة لكن لم تظهر في المقدمة خلال 45 ثانية.")

    def _screenshot(self):
        return self._run(["exec-out", "screencap", "-p"], timeout=20)

    def _tap(self, x, y):
        self._ensure_game_foreground()
        self._run(["shell", "input", "tap", str(int(x)), str(int(y))], timeout=10)

    def _execute(self, decision, cancelled):
        if cancelled():
            return False
        if decision.action == ActionType.DEPLOY:
            obs = self.last_observation
            if not obs or not obs.troop_slots or not obs.deployment_points:
                return False
            # Rotate through detected troop slots and configured perimeter points.
            slot = obs.troop_slots[self._deploy_index % len(obs.troop_slots)]
            point = obs.deployment_points[self._deploy_index % len(obs.deployment_points)]
            self._tap(slot.x, slot.y)
            if cancelled():
                return False
            time.sleep(0.15)
            self._tap(point[0], point[1])
            self._deploy_index += 1
            return True
        if decision.target is None:
            return False
        self._tap(decision.target.x, decision.target.y)
        return True

    def run(self, cancelled: Callable[[], bool] = lambda: False,
            on_decision: Callable[[str], None] = lambda message: None) -> str:
        try:
            on_decision("التحقق من تشغيل اللعبة...")
            self._launch_game_if_needed(cancelled)
        except Exception as exc:
            return "تعذر بدء محرك الأتمتة: " + str(exc)
        for step in range(self.max_steps):
            if cancelled():
                return "أوقف المستخدم محرك الأتمتة."
            try:
                screenshot = self._screenshot()
                self.last_observation = self.vision.observe(screenshot)
                decision = self.engine.decide(self.last_observation)
                on_decision(f"الخطوة {step + 1}: {decision.action.value} — {decision.reason}")
                if decision.action == ActionType.STOP:
                    return decision.reason
                if decision.action == ActionType.WAIT:
                    # OCR is optional; missing OCR is surfaced instead of guessed.
                    if self.last_observation.screen in (Screen.HOME, Screen.SEARCH) and (
                        self.last_observation.gold is None or self.last_observation.elixir is None
                    ) and self.vision.config.get("resource_regions"):
                        try:
                            import pytesseract  # noqa: F401
                        except ImportError:
                            return "قراءة الموارد تحتاج تثبيت pytesseract وTesseract OCR؛ لم تُنفذ أي خطوة تعتمد على موارد غير مقروءة."
                    time.sleep(0.6)
                    continue
                if not self._execute(decision, cancelled):
                    return "تعذر تنفيذ الإجراء بأمان؛ أوقف المحرك."
                # Always recapture and recognize the screen before the next action.
                time.sleep(float(self.vision.config.get("post_action_delay_seconds", 0.8)))
            except Exception as exc:
                return "توقف المحرك لحماية الحساب: " + str(exc)
        return "بلغ المحرك حد الخطوات الآمن؛ أوقف الدورة."
