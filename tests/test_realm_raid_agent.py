import json
import unittest
from types import SimpleNamespace

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition

from agent.realm_raid_agent import (
    SLOT_RECOGNITION,
    STATE_ACTION,
    STATE_STORE,
    RealmRaidNextSlot,
    RealmRaidStateAction,
)


class FakeContext:
    def __init__(self, device_uuid: str = "test-device") -> None:
        self.tasker = SimpleNamespace(
            controller=SimpleNamespace(uuid=device_uuid),
        )
        self.next_override = None

    def override_next(self, name: str, next_list: list[str]) -> bool:
        self.next_override = (name, next_list)
        return True


def action_arg(task_id: int, operation: str, **extra: object) -> SimpleNamespace:
    param = {"op": operation, **extra}
    return SimpleNamespace(
        task_detail=SimpleNamespace(task_id=task_id, entry="YYSRealmRaid"),
        node_name="YYSRealmRaid.RecordStart",
        custom_action_param=json.dumps(param),
    )


class RealmRaidAgentApiTests(unittest.TestCase):
    def tearDown(self) -> None:
        for task_id in range(1, 4):
            STATE_STORE.discard(("test-device", "YYSRealmRaid", task_id))

    def test_extensions_use_the_official_agent_base_classes(self) -> None:
        self.assertTrue(issubclass(RealmRaidStateAction, CustomAction))
        self.assertTrue(issubclass(RealmRaidNextSlot, CustomRecognition))
        self.assertIn(STATE_ACTION, AgentServer._custom_action_holder)
        self.assertIn(SLOT_RECOGNITION, AgentServer._custom_recognition_holder)

    def test_custom_recognition_returns_the_instance_next_slot(self) -> None:
        context = FakeContext()
        action = RealmRaidStateAction()
        self.assertTrue(action.run(context, action_arg(1, "reset")))

        recognition = RealmRaidNextSlot()
        argv = SimpleNamespace(
            task_detail=SimpleNamespace(task_id=1, entry="YYSRealmRaid"),
        )
        result = recognition.analyze(context, argv)
        self.assertEqual(result.box, (288, 180, 72, 48))
        self.assertEqual(result.detail, {"slot": 1, "last_slot": 0})

    def test_record_start_overrides_only_the_current_task_flow(self) -> None:
        context = FakeContext()
        action = RealmRaidStateAction()
        self.assertTrue(
            action.run(
                context,
                action_arg(2, "reset", stuck_start_limit=2, ninth_exit_count=3),
            )
        )

        self.assertTrue(action.run(context, action_arg(2, "record_start")))
        self.assertEqual(
            context.next_override,
            ("YYSRealmRaid.RecordStart", ["YYSRealmRaid.Scan"]),
        )

        self.assertTrue(action.run(context, action_arg(2, "record_start")))
        self.assertEqual(
            context.next_override,
            ("YYSRealmRaid.RecordStart", ["YYSRealmRaid.StopStuck"]),
        )


if __name__ == "__main__":
    unittest.main()
