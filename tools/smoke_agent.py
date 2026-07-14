from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from maa.agent_client import AgentClient
from maa.resource import Resource


EXPECTED_ACTIONS = {"YYSRealmRaid.State"}
EXPECTED_RECOGNITIONS = {"YYSRealmRaid.NextSlot"}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: smoke_agent.py <agent-executable>", file=sys.stderr)
        return 2

    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)

    resource = Resource()
    client = AgentClient()
    if not client.bind(resource):
        raise RuntimeError("Failed to bind AgentClient to Resource")
    if not client.set_timeout(10_000):
        raise RuntimeError("Failed to set AgentClient timeout")

    identifier = client.identifier
    if not identifier:
        raise RuntimeError("AgentClient did not provide an identifier")

    process = subprocess.Popen(
        [str(executable), identifier],
        cwd=executable.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        if not client.connect():
            stdout, stderr = process.communicate(timeout=2)
            raise RuntimeError(f"AgentClient connection failed\nstdout: {stdout}\nstderr: {stderr}")

        actions = set(client.custom_action_list)
        recognitions = set(client.custom_recognition_list)
        if not EXPECTED_ACTIONS.issubset(actions):
            raise RuntimeError(f"Missing custom actions: {sorted(EXPECTED_ACTIONS - actions)}")
        if not EXPECTED_RECOGNITIONS.issubset(recognitions):
            raise RuntimeError(
                f"Missing custom recognitions: {sorted(EXPECTED_RECOGNITIONS - recognitions)}"
            )

        print(json.dumps({"actions": sorted(actions), "recognitions": sorted(recognitions)}))
    finally:
        if client.connected:
            client.disconnect()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
