"""Keep the deployed GPU inventory distinct from and consistent with its lock."""
import hashlib
import json
from pathlib import Path
import re
from reflexguard import __version__

ROOT=Path(__file__).resolve().parents[1]


def normalize(name):
    return re.sub(r'[-_.]+','-',name).lower()


def test_gpu_inventory_matches_lock_and_vendor_boundary():
    lock={normalize(name):version for name,version in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s;\\]+)',(ROOT/'brain_server/requirements.txt').read_text(),re.M)}
    bom=json.loads((ROOT/'docs/sbom-gpu.json').read_text())
    inventory=json.loads((ROOT/'docs/logs/gpu-python-inventory.json').read_text())
    packages={normalize(item['name']):item['version'] for item in inventory}
    provenance=json.loads((ROOT/'docs/gpu_provenance.json').read_text())
    assert packages.pop('torch')==provenance['vendor_torch_distribution_version']
    assert packages==lock=={normalize(item['name']):item['version'] for item in bom['components']}
    assert lock['numpy']=='1.26.4'
    assert bom['bomFormat']=='CycloneDX' and bom['specVersion']=='1.6'


def test_gpu_provenance_and_reproduced_model_are_current():
    provenance=json.loads((ROOT/'docs/gpu_provenance.json').read_text())
    manifest=json.loads((ROOT/'brain_server/assets.lock').read_text())
    assert provenance['application_version']==__version__
    assert provenance['weights_sha256']==manifest['weights_sha256']==provenance['conversion_reproduced_weights_sha256']
    for section in ('inputs_sha256','code_sha256'):
        for name,digest in provenance[section].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    assert len(manifest['neurons'])==187
