"""Prevent stale or untraceable security claims and dependency inventories."""
import ast
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import re
import importlib.util
import pytest
import tomli
from reflexguard import __version__

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/"docs/security_controls.json").read_text())


def symbol_exists(path,qualified):
    node=ast.parse(path.read_text())
    for name in qualified.split("."):
        matches=[child for child in node.body if isinstance(child,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and child.name==name]
        if len(matches)!=1:return False
        node=matches[0]
    return True


@pytest.mark.parametrize("row",DATA["controls"],ids=lambda row:row["id"])
def test_every_control_points_to_real_code_and_tests(row):
    assert row["status"] in ("implemented","partial")
    assert row["item"] and row["approach"] and row["printed_page"]>0
    assert row["code"] and row["tests"]
    if row["status"]=="partial":assert row["limit"]
    for reference in row["code"]:
        name,symbol=reference.split(":",1)
        path=ROOT/name
        assert path.is_file(),reference
        if path.suffix==".py":assert symbol_exists(path,symbol),reference
        else:assert path.suffix==".sh" and symbol=="(script)"
    for reference in row["tests"]:
        name,test=reference.split("::",1)
        assert name.startswith("tests/test_") and test.startswith("test_")
        assert symbol_exists(ROOT/name,test),reference


def test_mapping_has_one_row_per_item_and_markdown_is_current():
    assert len({row["id"] for row in DATA["controls"]})==len(DATA["controls"])
    assert len({row["item"] for row in DATA["controls"]})==len(DATA["controls"])
    # Import the local renderer without changing sys.path or launching a subprocess.
    spec=importlib.util.spec_from_file_location("render_security_docs",ROOT/"scripts/render_security_docs.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (ROOT/"docs/kisa_mapping.md").read_text()==module.render(DATA)


def normalize(name):
    return re.sub(r"[-_.]+","-",name).lower()


def test_sbom_matches_locked_and_installed_packages():
    bom=json.loads((ROOT/"docs/sbom.json").read_text())
    lock=(ROOT/"requirements.txt").read_text()
    locked={normalize(name):version for name,version in re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)",lock,re.M)}
    components={normalize(component["name"]):component["version"] for component in bom["components"]}
    installed={normalize(dist.metadata["Name"]):dist.version for dist in distributions()}
    assert components==locked==installed
    assert len(components)==len(bom["components"])
    assert bom["bomFormat"]=="CycloneDX" and bom["specVersion"]=="1.6"
    assert all(component.get("purl") for component in bom["components"])
    refs={component["bom-ref"] for component in bom["components"]}|{bom["metadata"]["component"]["bom-ref"]}
    for dependency in bom["dependencies"]:
        assert dependency["ref"] in refs
        assert set(dependency.get("dependsOn",[]))<=refs


def test_sbom_provenance_and_application_versions_match():
    bom=json.loads((ROOT/"docs/sbom.json").read_text())
    provenance=json.loads((ROOT/"docs/sbom_provenance.json").read_text())
    project=tomli.loads((ROOT/"pyproject.toml").read_text())["project"]
    assert DATA["application_version"]==project["version"]==bom["metadata"]["component"]["version"]==provenance["application_version"]==__version__
    assert __version__ in (ROOT/"README.md").read_text()
    assert "## "+__version__+" —" in (ROOT/"CHANGELOG.md").read_text()
    assert provenance["component_count"]==len(bom["components"])
    for name,digest in provenance["inputs_sha256"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    assert hashlib.sha256((ROOT/"docs/sbom.json").read_bytes()).hexdigest()==provenance["sbom_sha256"]


def test_all_python_components_have_license_notices():
    bom=json.loads((ROOT/"docs/sbom.json").read_text())
    notices=(ROOT/"THIRD_PARTY_NOTICES.md").read_text()
    for component in bom["components"]:
        assert "| "+component["name"]+" | "+component["version"]+" |" in notices
