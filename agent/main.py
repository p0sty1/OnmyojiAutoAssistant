from __future__ import annotations

import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    # Packaged layout: <project>/agent/runtime/onmyoji_auto_assistant_agent.exe
    PROJECT_ROOT = Path(sys.executable).resolve().parents[2]
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from maa.agent.agent_server import AgentServer  # noqa: E402
from maa.tasker import Tasker  # noqa: E402

from agent import realm_raid_agent  # noqa: E402, F401


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Usage: onmyoji_auto_assistant_agent <socket_id>")
        return 2

    Tasker.set_log_dir(str(PROJECT_ROOT / "debug"))
    socket_id = args[-1]
    if not AgentServer.start_up(socket_id):
        raise RuntimeError("Failed to start MaaFramework AgentServer")

    try:
        AgentServer.join()
    finally:
        AgentServer.shut_down()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
