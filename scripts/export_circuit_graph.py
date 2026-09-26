"""Regenerate public visual metadata only after authenticating signed model assets."""
import base64
import json
import os
from pathlib import Path
from pydantic import BaseModel, DirectoryPath, Field
from brain_server.loader import load_assets


class ExportSettings(BaseModel):
    model_dir: DirectoryPath
    public_key: str = Field(min_length=44, max_length=44)


def export(settings):
    key = base64.b64decode(settings.public_key, validate=True)
    manifest, _, pre, post, count = load_assets(settings.model_dir, key)
    return {
        "source": manifest.source, "release": manifest.release,
        "model_version": manifest.model_version, "weights_sha256": manifest.weights_sha256,
        "source_url": "https://male-cns.janelia.org/download/", "license": "CC-BY-4.0",
        "nodes": [neuron.model_dump() for neuron in manifest.neurons],
        "edges": [{"source": manifest.neurons[int(a)].id, "target": manifest.neurons[int(b)].id,
                   "synapses": int(c)} for a, b, c in zip(pre, post, count)],
    }


def main():
    settings = ExportSettings(model_dir=os.environ["REFLEXGUARD_MODEL_DIR"],
                              public_key=os.environ["REFLEXGUARD_MODEL_PUBLIC_KEY"])
    graph = export(settings)
    target = Path(__file__).resolve().parents[1] / "src/reflexguard/control_server/static/malecns-circuit.json"
    target.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
