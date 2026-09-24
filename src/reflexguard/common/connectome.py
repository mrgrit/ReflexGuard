"""Dataset provenance declaration; this is not an asset-integrity lock."""
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict


class MaleCNSPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    source: Literal["MaleCNS"]
    release: Literal["v1.0"]
    neuprint_dataset: Literal["male-cns:v1.0"]
    neuprint_server: Literal["https://neuprint.janelia.org"]
    documentation: Literal["https://male-cns.janelia.org/download/"]
    bucket: Literal["gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/"]
    annotations: Literal["body-annotations-male-cns-v1.0-minconf-0.5.feather"]
    neurotransmitters: Literal["body-neurotransmitters-male-cns-v1.0.feather"]
    connectivity: Literal["connectome-weights-male-cns-v1.0-minconf-0.5.feather"]
    license: Literal["CC-BY-4.0"]
    state: Literal["planned_not_downloaded"]

    @classmethod
    def load(cls):
        path = Path(__file__).resolve().parents[3] / "config/malecns.json"
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
