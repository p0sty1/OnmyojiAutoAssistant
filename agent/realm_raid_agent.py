from __future__ import annotations

import json
from typing import Any

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from maa.event_sink import NotificationType
from maa.tasker import Tasker, TaskerEventSink

from .realm_raid_state import (
    InstanceKey,
    RealmRaidConfig,
    RealmRaidStateStore,
    slot_box,
)


ENTRY = "YYSRealmRaid"
STATE_ACTION = "YYSRealmRaid.State"
SLOT_RECOGNITION = "YYSRealmRaid.NextSlot"

SCAN_NODE = "YYSRealmRaid.Scan"
NINTH_EXIT_NODE = "YYSRealmRaid.NinthExit"
STOP_NODE = "YYSRealmRaid.StopStuck"

STATE_STORE = RealmRaidStateStore()


def _instance_key(context: Context, task_detail: Any) -> InstanceKey:
    return context.tasker.controller.uuid, task_detail.entry, task_detail.task_id


def _tasker_key(tasker: Tasker, entry: str, task_id: int) -> InstanceKey:
    return tasker.controller.uuid, entry, task_id


def _parse_param(raw_param: str) -> dict[str, object]:
    if not raw_param or raw_param == "null":
        return {}
    value = json.loads(raw_param)
    if not isinstance(value, dict):
        raise ValueError("custom action parameter must be a JSON object")
    return value


@AgentServer.custom_recognition(SLOT_RECOGNITION)
class RealmRaidNextSlot(CustomRecognition):
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        key = _instance_key(context, argv.task_detail)
        slot = STATE_STORE.apply(key, lambda state: state.select_slot())
        state = STATE_STORE.snapshot(key)
        return CustomRecognition.AnalyzeResult(
            box=slot_box(slot),
            detail={
                "slot": slot,
                "last_slot": state.last_slot if state else 0,
            },
        )


@AgentServer.custom_action(STATE_ACTION)
class RealmRaidStateAction(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        try:
            param = _parse_param(argv.custom_action_param)
            operation = str(param.get("op", ""))
            key = _instance_key(context, argv.task_detail)

            if operation == "reset":
                STATE_STORE.reset(key, RealmRaidConfig.from_mapping(param))
                return True
            if operation == "leave_page":
                STATE_STORE.apply(key, lambda state: state.leave_page())
                return True
            if operation == "non_start":
                STATE_STORE.apply(key, lambda state: state.mark_non_start())
                return True
            if operation == "advance_slot":
                STATE_STORE.apply(key, lambda state: state.advance_slot())
                return True
            if operation in {"abort_attempt", "idle"}:
                STATE_STORE.apply(key, lambda state: state.abort_attempt())
                return True
            if operation == "record_start":
                decision = STATE_STORE.apply(key, lambda state: state.record_start())
                next_node = SCAN_NODE
                if decision.stop:
                    next_node = STOP_NODE
                elif decision.run_ninth_exit:
                    next_node = NINTH_EXIT_NODE
                return context.override_next(argv.node_name, [next_node])
        except (RuntimeError, TypeError, ValueError):
            return False

        return False


@AgentServer.tasker_sink()
class RealmRaidTaskCleanup(TaskerEventSink):
    def on_tasker_task(
        self,
        tasker: Tasker,
        noti_type: NotificationType,
        detail: TaskerEventSink.TaskerTaskDetail,
    ) -> None:
        if detail.entry != ENTRY:
            return
        if noti_type not in {NotificationType.Succeeded, NotificationType.Failed}:
            return
        try:
            STATE_STORE.discard(_tasker_key(tasker, detail.entry, detail.task_id))
        except RuntimeError:
            return
