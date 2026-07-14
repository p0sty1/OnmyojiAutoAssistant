import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_maaframework_loads_the_complete_resource_bundle() -> None:
    # AgentServer and MaaFramework use different native library modes. Pytest
    # imports every test module during collection, so validate the regular
    # MaaFramework resource in a fresh process that has not imported AgentServer.
    script = """
import json
import sys
from maa.resource import Resource

resource = Resource()
job = resource.post_bundle(sys.argv[1])
job.wait()
print(json.dumps({
    "succeeded": job.status.succeeded,
    "loaded": resource.loaded,
    "nodes": resource.node_list,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(ROOT / "resource_pack" / "base")],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    detail = json.loads(result.stdout.strip().splitlines()[-1])

    assert detail["succeeded"]
    assert detail["loaded"]
    assert "Tower.Entry" in detail["nodes"]
    assert "YYSRealmRaid" in detail["nodes"]
    assert len(detail["nodes"]) == 38
