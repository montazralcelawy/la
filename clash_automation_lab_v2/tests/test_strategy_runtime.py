import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from strategy_runtime import TemplateVision, _resource_number
from strategy_engine import Screen


class StrategyRuntimeVisionTests(unittest.TestCase):
    def test_resource_number_parses_plain_and_compact_values(self):
        self.assertEqual(_resource_number("123,456"), 123456)
        self.assertEqual(_resource_number("1.2M"), 1200000)
        self.assertEqual(_resource_number("١٢٣"), 123)
        self.assertIsNone(_resource_number("not readable"))

    def test_template_vision_recognizes_screen_and_button(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rng = np.random.default_rng(42)
            screen_template = rng.integers(0, 255, (18, 20, 3), dtype=np.uint8)
            button_template = rng.integers(0, 255, (14, 16, 3), dtype=np.uint8)
            screenshot = rng.integers(0, 255, (120, 160, 3), dtype=np.uint8)
            screenshot[10:28, 12:32] = screen_template
            screenshot[60:74, 100:116] = button_template
            cv2.imwrite(str(root / "home.png"), screen_template)
            cv2.imwrite(str(root / "collect.png"), button_template)
            ok, encoded = cv2.imencode(".png", screenshot)
            self.assertTrue(ok)
            config = {
                "min_confidence": 0.95,
                "screen_templates": {"home": "home.png"},
                "button_templates": {"collect": "collect.png"},
                "resource_regions": {},
                "status_templates": {},
                "troop_slots": [],
                "deployment_points": []
            }
            config_path = root / "vision.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            observation = TemplateVision(str(config_path)).observe(encoded.tobytes())
            self.assertEqual(observation.screen, Screen.HOME)
            self.assertGreaterEqual(observation.confidence, 0.95)
            self.assertIn("collect", observation.buttons)
            self.assertEqual((observation.buttons["collect"].x, observation.buttons["collect"].y), (108, 67))

    def test_missing_config_fails_with_clear_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "غير موجود"):
                TemplateVision(str(Path(folder) / "missing.json"))


if __name__ == "__main__":
    unittest.main()
