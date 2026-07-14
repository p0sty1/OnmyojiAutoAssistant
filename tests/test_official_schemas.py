import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "tools" / "schemas"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(instance_path: Path, schema_path: Path) -> None:
    schema = load_json(schema_path)
    schema["$id"] = schema_path.resolve().as_uri()
    validator_class = jsonschema.validators.validator_for(schema)
    validator_class.check_schema(schema)

    registry = Registry()
    for dependency_path in SCHEMA_ROOT.glob("*.json"):
        dependency = load_json(dependency_path)
        dependency["$id"] = dependency_path.resolve().as_uri()
        registry = registry.with_resource(dependency["$id"], Resource.from_contents(dependency))

    validator = validator_class(schema, registry=registry)
    errors = sorted(validator.iter_errors(load_json(instance_path)), key=lambda item: list(item.path))
    assert not errors, "\n".join(f"{instance_path}: {error.json_path}: {error.message}" for error in errors)


def test_project_interface_matches_maaframework_v5_12_1_schema() -> None:
    validate(ROOT / "interface.json", SCHEMA_ROOT / "interface.schema.json")


def test_project_interface_imports_match_maaframework_v5_12_1_schema() -> None:
    schema = SCHEMA_ROOT / "interface_import.schema.json"
    for path in sorted((ROOT / "tasks").glob("*.json")):
        validate(path, schema)


def test_pipelines_match_maaframework_v5_12_1_schema() -> None:
    schema = SCHEMA_ROOT / "pipeline.schema.json"
    for path in sorted((ROOT / "resource_pack" / "base" / "pipeline").rglob("*.json")):
        validate(path, schema)
