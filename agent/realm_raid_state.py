from __future__ import annotations

from dataclasses import dataclass, replace
from threading import RLock
from typing import Callable, Mapping, TypeVar


GRID_CENTERS_1080P = (
    (486, 306),
    (1014, 306),
    (1542, 306),
    (486, 479),
    (1014, 479),
    (1542, 479),
    (486, 651),
    (1014, 651),
    (1542, 651),
)
SCALE_TO_720P = 2 / 3
SLOT_BOX_SIZE = (72, 48)


def slot_box(slot: int) -> tuple[int, int, int, int]:
    """Return a safe 720p click box for a one-based realm-raid slot."""
    if not 1 <= slot <= 9:
        raise ValueError(f"slot must be in [1, 9], got {slot}")

    source_x, source_y = GRID_CENTERS_1080P[slot - 1]
    center_x = round(source_x * SCALE_TO_720P)
    center_y = round(source_y * SCALE_TO_720P)
    width, height = SLOT_BOX_SIZE
    return center_x - width // 2, center_y - height // 2, width, height


@dataclass(frozen=True)
class RealmRaidConfig:
    stuck_start_limit: int = 10
    ninth_exit_count: int = 3

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "RealmRaidConfig":
        stuck_start_limit = int(value.get("stuck_start_limit", cls.stuck_start_limit))
        ninth_exit_count = int(value.get("ninth_exit_count", cls.ninth_exit_count))
        if stuck_start_limit < 1:
            raise ValueError("stuck_start_limit must be at least 1")
        if ninth_exit_count < 0:
            raise ValueError("ninth_exit_count cannot be negative")
        return cls(
            stuck_start_limit=stuck_start_limit,
            ninth_exit_count=ninth_exit_count,
        )


@dataclass(frozen=True)
class StartDecision:
    stop: bool
    run_ninth_exit: bool
    slot: int | None
    consecutive_start_taps: int
    ninth_slot_page_count: int


@dataclass
class RealmRaidState:
    config: RealmRaidConfig = RealmRaidConfig()
    last_slot: int = 0
    slot_cursor: int = 1
    pending_slot: int | None = None
    ninth_slot_page_count: int = 0
    consecutive_start_taps: int = 0
    on_page: bool = False
    stopped: bool = False

    def enter_page(self) -> None:
        if self.on_page:
            return
        self.on_page = True
        self.ninth_slot_page_count = 0
        self.pending_slot = None
        self.slot_cursor = self.last_slot % 9 + 1

    def leave_page(self) -> None:
        self.on_page = False
        self.ninth_slot_page_count = 0
        self.pending_slot = None
        self.slot_cursor = self.last_slot % 9 + 1

    def select_slot(self) -> int:
        self.enter_page()
        if self.pending_slot is None:
            self.pending_slot = self.slot_cursor
        return self.pending_slot

    def advance_slot(self) -> None:
        attempted_slot = self.pending_slot or self.slot_cursor
        self.slot_cursor = attempted_slot % 9 + 1
        self.pending_slot = None
        self.consecutive_start_taps = 0

    def mark_non_start(self) -> None:
        self.consecutive_start_taps = 0

    def abort_attempt(self) -> None:
        self.mark_non_start()
        self.pending_slot = None
        self.slot_cursor = self.last_slot % 9 + 1

    def record_start(self) -> StartDecision:
        self.consecutive_start_taps += 1
        slot = self.pending_slot
        run_ninth_exit = False

        if slot is not None:
            self.last_slot = slot
            self.slot_cursor = slot % 9 + 1
            self.pending_slot = None
            if slot == 9:
                self.ninth_slot_page_count += 1
                run_ninth_exit = (
                    self.ninth_slot_page_count <= self.config.ninth_exit_count
                )

        stop = self.consecutive_start_taps >= self.config.stuck_start_limit
        self.stopped = self.stopped or stop
        return StartDecision(
            stop=stop,
            run_ninth_exit=run_ninth_exit,
            slot=slot,
            consecutive_start_taps=self.consecutive_start_taps,
            ninth_slot_page_count=self.ninth_slot_page_count,
        )


InstanceKey = tuple[str, str, int]
ResultT = TypeVar("ResultT")


class RealmRaidStateStore:
    """Thread-safe state storage keyed by a concrete Maa task instance."""

    def __init__(self) -> None:
        self._states: dict[InstanceKey, RealmRaidState] = {}
        self._lock = RLock()

    def reset(
        self,
        key: InstanceKey,
        config: RealmRaidConfig | None = None,
    ) -> None:
        with self._lock:
            self._states[key] = RealmRaidState(config=config or RealmRaidConfig())

    def apply(
        self,
        key: InstanceKey,
        operation: Callable[[RealmRaidState], ResultT],
    ) -> ResultT:
        with self._lock:
            state = self._states.setdefault(key, RealmRaidState())
            return operation(state)

    def snapshot(self, key: InstanceKey) -> RealmRaidState | None:
        with self._lock:
            state = self._states.get(key)
            return replace(state) if state is not None else None

    def discard(self, key: InstanceKey) -> None:
        with self._lock:
            self._states.pop(key, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._states)
