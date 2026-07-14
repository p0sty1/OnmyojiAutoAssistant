import unittest

from agent.realm_raid_state import (
    RealmRaidConfig,
    RealmRaidState,
    RealmRaidStateStore,
    slot_box,
)


def advance_to_slot(state: RealmRaidState, target: int) -> None:
    for _ in range(9):
        if state.select_slot() == target:
            return
        state.advance_slot()
    raise AssertionError(f"slot {target} was not reached")


class RealmRaidStateTests(unittest.TestCase):
    def test_slot_boxes_are_scaled_from_the_old_1080p_grid(self) -> None:
        self.assertEqual(slot_box(1), (288, 180, 72, 48))
        self.assertEqual(slot_box(5), (640, 295, 72, 48))
        self.assertEqual(slot_box(9), (992, 410, 72, 48))
        for slot in range(1, 10):
            x, y, width, height = slot_box(slot)
            self.assertGreaterEqual(x, 148)
            self.assertGreaterEqual(y, 147)
            self.assertLessEqual(x + width, 1204)
            self.assertLessEqual(y + height, 492)

    def test_next_scan_starts_after_the_last_successful_slot(self) -> None:
        state = RealmRaidState()
        self.assertEqual(state.select_slot(), 1)
        state.advance_slot()
        self.assertEqual(state.select_slot(), 2)

        decision = state.record_start()
        self.assertEqual(decision.slot, 2)
        self.assertEqual(state.last_slot, 2)
        self.assertEqual(state.select_slot(), 3)

        state.leave_page()
        self.assertEqual(state.select_slot(), 3)

    def test_ninth_slot_exits_three_times_but_not_the_fourth(self) -> None:
        state = RealmRaidState(last_slot=8, slot_cursor=9)
        decisions = []
        for _ in range(4):
            advance_to_slot(state, 9)
            decisions.append(state.record_start())

        self.assertEqual([item.slot for item in decisions], [9, 9, 9, 9])
        self.assertEqual(
            [item.run_ninth_exit for item in decisions],
            [True, True, True, False],
        )
        self.assertEqual(state.ninth_slot_page_count, 4)

        state.leave_page()
        self.assertEqual(state.ninth_slot_page_count, 0)
        self.assertEqual(state.last_slot, 9)

    def test_non_start_resets_stuck_counter_and_tenth_start_stops(self) -> None:
        state = RealmRaidState(config=RealmRaidConfig(stuck_start_limit=10))
        for expected in range(1, 10):
            decision = state.record_start()
            self.assertEqual(decision.consecutive_start_taps, expected)
            self.assertFalse(decision.stop)

        decision = state.record_start()
        self.assertTrue(decision.stop)
        self.assertTrue(state.stopped)

        state.mark_non_start()
        self.assertEqual(state.record_start().consecutive_start_taps, 1)

    def test_store_isolates_instances_and_reset_replaces_state(self) -> None:
        store = RealmRaidStateStore()
        first = ("device-a", "YYSRealmRaid", 1)
        second = ("device-b", "YYSRealmRaid", 1)
        store.reset(first)
        store.reset(second)

        store.apply(first, lambda state: state.select_slot())
        store.apply(first, lambda state: state.record_start())
        self.assertEqual(store.snapshot(first).last_slot, 1)
        self.assertEqual(store.snapshot(second).last_slot, 0)

        store.reset(first, RealmRaidConfig(stuck_start_limit=4, ninth_exit_count=0))
        reset_state = store.snapshot(first)
        self.assertEqual(reset_state.last_slot, 0)
        self.assertEqual(reset_state.config.stuck_start_limit, 4)
        self.assertEqual(reset_state.config.ninth_exit_count, 0)

        store.discard(first)
        self.assertIsNone(store.snapshot(first))
        self.assertEqual(len(store), 1)


if __name__ == "__main__":
    unittest.main()
