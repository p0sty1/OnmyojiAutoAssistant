import hashlib
import json
import unittest
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = (
    ROOT
    / "resource_pack"
    / "base"
    / "pipeline"
    / "realm_raid"
    / "realm_raid.json"
)
IMAGE_ROOT = ROOT / "resource_pack" / "base" / "image"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "realm_raid"

STATE_NODES = {
    "YYSRealmRaid.Helper": "common/helper.png",
    "YYSRealmRaid.Page": "realm_raid/page.png",
    "YYSRealmRaid.PageStart": "realm_raid/start.png",
    "YYSRealmRaid.PageReward": "realm_raid/reward.png",
    "YYSRealmRaid.ConfirmExit": "realm_raid/confirm.png",
    "YYSRealmRaid.Retry": "realm_raid/retry.png",
    "YYSRealmRaid.ConfirmRetry": "realm_raid/confirm_retry.png",
}


def read_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise AssertionError(f"Unable to decode image: {path}")
    return image


def match_in_roi(
    screen: np.ndarray,
    template: np.ndarray,
    roi: list[int],
) -> tuple[float, tuple[int, int]]:
    x, y, width, height = roi
    cropped = screen[y : y + height, x : x + width]
    result = cv2.matchTemplate(cropped, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    return float(score), (location[0] + x, location[1] + y)


class RealmRaidPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads(
            (FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")
        )

    def test_pipeline_is_v2_and_all_references_resolve(self) -> None:
        self.assertIn("YYSRealmRaid", self.pipeline)
        allowed_actions = {
            "Click",
            "ClickKey",
            "Custom",
            "DoNothing",
            "StopTask",
        }

        for name, node in self.pipeline.items():
            self.assertEqual(set(node["recognition"]), {"type", "param"}, name)
            self.assertEqual(set(node["action"]), {"type", "param"}, name)
            self.assertIn(node["action"]["type"], allowed_actions, name)
            for field in ("next", "on_error"):
                for target in node.get(field, []):
                    self.assertIn(target, self.pipeline, f"{name}.{field} -> {target}")

    def test_custom_nodes_match_the_registered_agent_names(self) -> None:
        reset = self.pipeline["YYSRealmRaid.Reset"]["action"]["param"]
        self.assertEqual(reset["custom_action"], "YYSRealmRaid.State")
        self.assertEqual(
            reset["custom_action_param"],
            {
                "op": "reset",
                "stuck_start_limit": 10,
                "ninth_exit_count": 3,
            },
        )

        slot = self.pipeline["YYSRealmRaid.Slot"]
        self.assertEqual(slot["recognition"]["type"], "Custom")
        self.assertEqual(
            slot["recognition"]["param"]["custom_recognition"],
            "YYSRealmRaid.NextSlot",
        )
        self.assertEqual(slot["action"], {"type": "Click", "param": {"target": True}})

    def test_pipeline_has_finite_waits_and_safe_single_clicks(self) -> None:
        self.assertEqual(
            self.pipeline["YYSRealmRaid.NinthExit"]["action"],
            {"type": "ClickKey", "param": {"key": 111}},
        )
        self.assertEqual(
            self.pipeline["YYSRealmRaid.StopStuck"]["action"]["type"],
            "StopTask",
        )

        for name, node in self.pipeline.items():
            if "next" in node:
                self.assertGreater(node["timeout"], 0, name)
                self.assertLessEqual(node["timeout"], 6000, name)
                self.assertIn("on_error", node, name)
            if node["action"]["type"] == "Click":
                self.assertEqual(node["action"]["param"], {"target": True}, name)
                self.assertNotIn("repeat", node, name)

    def test_scaled_templates_match_manifest(self) -> None:
        self.assertEqual(self.manifest["coordinate_space"], [1280, 720])
        self.assertEqual(self.manifest["scale"], "2/3")
        self.assertEqual(self.manifest["interpolation"], "cv2.INTER_AREA")

        for relative_path, expected in self.manifest["templates"].items():
            path = IMAGE_ROOT / relative_path
            image = read_image(path)
            height, width = image.shape[:2]
            self.assertEqual([width, height], expected["output_size"], relative_path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, expected["output_sha256"], relative_path)

    def test_template_rois_are_inside_the_720p_coordinate_space(self) -> None:
        for node_name, relative_path in STATE_NODES.items():
            params = self.pipeline[node_name]["recognition"]["param"]
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

    def test_positive_fixture_hits_every_template_in_its_roi(self) -> None:
        screen = read_image(FIXTURE_ROOT / "positive_composite.png")
        expected_locations = {
            "YYSRealmRaid.Helper": (1200, 170),
            "YYSRealmRaid.Page": (120, 20),
            "YYSRealmRaid.PageStart": (1100, 600),
            "YYSRealmRaid.PageReward": (500, 300),
            "YYSRealmRaid.ConfirmExit": (360, 600),
            "YYSRealmRaid.Retry": (1100, 300),
            "YYSRealmRaid.ConfirmRetry": (720, 600),
        }

        for node_name, relative_path in STATE_NODES.items():
            params = self.pipeline[node_name]["recognition"]["param"]
            template = read_image(IMAGE_ROOT / relative_path)
            score, location = match_in_roi(screen, template, params["roi"])
            self.assertGreaterEqual(score, params["threshold"], node_name)
            self.assertEqual(location, expected_locations[node_name], node_name)

    def test_current_battle_screen_cannot_be_recognized_as_reward(self) -> None:
        screen = read_image(FIXTURE_ROOT / "battle_negative.png")
        template = read_image(IMAGE_ROOT / "realm_raid" / "reward.png")
        params = self.pipeline["YYSRealmRaid.Reward"]["recognition"]["param"]

        legacy_result = cv2.matchTemplate(
            cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY),
            cv2.cvtColor(template, cv2.COLOR_BGR2GRAY),
            cv2.TM_CCOEFF_NORMED,
        )
        _, legacy_score, _, _ = cv2.minMaxLoc(legacy_result)
        self.assertGreaterEqual(legacy_score, 0.60)

        x, y, width, height = params["roi"]
        configured_result = cv2.matchTemplate(
            cv2.cvtColor(screen[y : y + height, x : x + width], cv2.COLOR_BGR2GRAY),
            cv2.cvtColor(template, cv2.COLOR_BGR2GRAY),
            cv2.TM_CCOEFF_NORMED,
        )
        _, configured_score, _, _ = cv2.minMaxLoc(configured_result)
        self.assertLess(configured_score, params["threshold"] - 0.15)


if __name__ == "__main__":
    unittest.main()
