"""Record inventory inputs without claiming hashes of unobserved distribution archives."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    bom=json.loads((ROOT/"docs/sbom.json").read_text())
    result={"schema_version":1,"application_version":bom["metadata"]["component"]["version"],
        "scope":"Project Python virtual environment including test/build dependencies; excludes OS, Webots, pipx tools, GPU environment and MaleCNS assets (separate inventories)",
        "format":"CycloneDX 1.6 JSON","generator":next(tool["name"]+" "+tool["version"] for tool in bom["metadata"]["tools"]["components"] if tool["name"]=="cyclonedx-py"),
        "command":"scripts/generate_sbom.sh","component_count":len(bom["components"]),
        "inputs_sha256":{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ("requirements.in","requirements.txt","pyproject.toml")},
        "sbom_sha256":hashlib.sha256((ROOT/"docs/sbom.json").read_bytes()).hexdigest(),
        "hash_scope":"Input manifests and SBOM file only. requirements.txt contains allowed artifact hashes; installed package files are not attested."}
    (ROOT/"docs/sbom_provenance.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
