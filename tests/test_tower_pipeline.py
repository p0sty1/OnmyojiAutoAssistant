import hashlib
import json
import unittest
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "resource_pack" / "base" / "pipeline" / "tower" / "tower.json"
IMAGE_ROOT = ROOT / "resource_pack" / "base" / "image"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "tower"

STATE_NODES = {
    "Tower.Helper": "common/helper.png",
    "Tower.Challenge": "tower/start.png",
    "Tower.Continue": "tower/continue.png",
    "Tower.Gold": "tower/gold.png",
}


def read_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise AssertionError(f"Unable to decode image: {path}")
    return image


def match_in_roi(screen: np.ndarray, template: np.ndarray, roi: list[int]) -> tuple[float, tuple[int, int]]:
    x, y, width, height = roi
    cropped = screen[y : y + height, x : x + width]
    result = cv2.matchTemplate(cropped, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    return float(score), (location[0] + x, location[1] + y)


class TowerPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_pipeline_is_v2_and_all_references_resolve(self) -> None:
        self.assertIn("Tower.Entry", self.pipeline)
        allowed_actions = {"Click", "DoNothing", "StopTask"}

        for name, node in self.pipeline.items():
            self.assertEqual(set(node["recognition"]), {"type", "param"}, name)
            self.assertEqual(set(node["action"]), {"type", "param"}, name)
            self.assertIn(node["action"]["type"], allowed_actions, name)

            for field in ("next", "on_error"):
                for target in node.get(field, []):
                    self.assertIn(target, self.pipeline, f"{name}.{field} -> {target}")

    def test_pipeline_has_finite_timeouts_and_single_click_actions(self) -> None:
        self.assertEqual(self.pipeline["Tower.Challenge"]["max_hit"], 1)
        self.assertEqual(self.pipeline["Tower.StopAtChallenge"]["action"]["type"], "StopTask")

        for name, node in self.pipeline.items():
            if "next" in node:
                self.assertGreater(node["timeout"], 0, name)
                self.assertLessEqual(node["timeout"], 300_000, name)
                self.assertEqual(node.get("on_error"), ["Tower.Timeout"], name)

            if node["action"]["type"] == "Click":
                self.assertEqual(node["action"]["param"], {"target": True}, name)
                self.assertNotIn("repeat", node, name)

    def test_each_click_waits_for_its_template_to_disappear(self) -> None:
        pairs = {
            "Tower.Helper": "Tower.HelperGone",
            "Tower.Challenge": "Tower.ChallengeGone",
            "Tower.Continue": "Tower.ContinueGone",
            "Tower.Gold": "Tower.GoldGone",
        }
        for click_name, gone_name in pairs.items():
            click = self.pipeline[click_name]
            gone = self.pipeline[gone_name]
            self.assertEqual(click["next"], [gone_name], click_name)
            self.assertTrue(gone["inverse"], gone_name)
            self.assertEqual(gone["recognition"], click["recognition"], gone_name)
            self.assertEqual(gone["action"]["type"], "DoNothing", gone_name)

    def test_scaled_templates_match_manifest(self) -> None:
        self.assertEqual(self.manifest["coordinate_space"], [1280, 720])
        self.assertEqual(self.manifest["scale"], "2/3")
        self.assertEqual(self.manifest["interpolation"], "cv2.INTER_AREA")

        for relative_path, expected in self.manifest["templates"].items():
            path = IMAGE_ROOT / relative_path
            image = read_image(path)
            height, width = image.shape[:2]
            self.assertEqual([width, height], expected["output_size"], relative_path)
            self.assertGreater(float(image.std()), 8.0, relative_path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, expected["output_sha256"].lower(), relative_path)

    def test_rois_are_inside_720p_coordinate_space(self) -> None:
        for node_name, relative_path in STATE_NODES.items():
            recognition = self.pipeline[node_name]["recognition"]
            self.assertEqual(recognition["type"], "TemplateMatch")
            params = recognition["param"]
            self.assertEqual(params["template"], relative_path)
            x, y, width, height = params["roi"]
            template = read_image(IMAGE_ROOT / relative_path)
            template_height, template_width = template.shape[:2]
            self.assertGreaterEqual(x, 0, node_name)
            self.assertGreaterEqual(y, 0, node_name)
            self.assertLessEqual(x + width, 1280, node_name)
            self.assertLessEqual(y + height, 720, node_name)
            self.assertGreaterEqual(width, template_width, node_name)
            self.assertGreaterEqual(height, template_height, node_name)

    def test_positive_fixture_hits_every_state_inside_its_roi(self) -> None:
        screen = read_image(FIXTURE_ROOT / "positive_composite.png")
        self.assertEqual(screen.shape[:2], (720, 1280))

        expected_locations = {
            "Tower.Helper": (1140, 70),
            "Tower.Challenge": (1080, 550),
            "Tower.Continue": (330, 610),
            "Tower.Gold": (120, 120),
        }
        for node_name, relative_path in STATE_NODES.items():
            params = self.pipeline[node_name]["recognition"]["param"]
            template = read_image(IMAGE_ROOT / relative_path)
            score, location = match_in_roi(screen, template, params["roi"])
            self.assertGreaterEqual(score, params["threshold"], node_name)
            self.assertEqual(location, expected_locations[node_name], node_name)

    def test_real_negative_fixture_stays_below_every_threshold(self) -> None:
        screen = read_image(FIXTURE_ROOT / "negative_non_tower.png")
        self.assertEqual(screen.shape[:2], (720, 1280))

        for node_name, relative_path in STATE_NODES.items():
            params = self.pipeline[node_name]["recognition"]["param"]
            template = read_image(IMAGE_ROOT / relative_path)
            score, _ = match_in_roi(screen, template, params["roi"])
            self.assertLess(score, params["threshold"] - 0.2, node_name)


if __name__ == "__main__":
    unittest.main()
