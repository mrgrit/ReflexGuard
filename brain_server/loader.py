"""Authenticate bounded numeric assets before parsing or allocating a model."""
import hashlib
import io
import os
from pathlib import Path
from typing import Annotated, Literal
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
NeuronID = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,20}$")]
MODEL_VERSION = "malecns-v1.0-lplc2-gf-lif-v1"


class AssetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, allow_inf_nan=False)


class Neuron(AssetModel):
    id: NeuronID
    cell_type: Literal["LPLC2", "DNp01"]
    side: Literal["L", "R"]


class Parameters(AssetModel):
    input_gain: float = Field(default=2.5, ge=1., le=50.)
    synaptic_gain: float = Field(default=25., ge=1., le=100.)
    tau_ms: float = Field(default=10., ge=1., le=100.)
    refractory_ms: int = Field(default=2, ge=0, le=10)
    output_rate_hz: float = Field(default=200., ge=1., le=1000.)


class Manifest(AssetModel):
    source: Literal["MaleCNS"]
    release: Literal["v1.0"]
    model_version: Literal["malecns-v1.0-lplc2-gf-lif-v1"]
    selection: Literal["LPLC2_to_DNp01_feedforward"]
    neurons: list[Neuron] = Field(min_length=4, max_length=2048)
    weights_sha256: Digest
    silence_sha256: Digest
    source_sha256: dict[str, Digest]
    parameters: Parameters

    @model_validator(mode="after")
    def complete_circuit(self):
        if len({n.id for n in self.neurons}) != len(self.neurons):
            raise ValueError("Duplicate neuron ID")
        for side in ("L", "R"):
            if sum(n.cell_type == "DNp01" and n.side == side for n in self.neurons) != 1:
                raise ValueError("One descending output per side is required")
            if not any(n.cell_type == "LPLC2" and n.side == side for n in self.neurons):
                raise ValueError("Bilateral input is required")
        if set(self.source_sha256) != {"annotations", "neurotransmitters", "connectivity"}:
            raise ValueError("Source provenance is incomplete")
        return self


class Allowlist(AssetModel):
    neuron_ids: list[NeuronID] = Field(max_length=2048)


def read_bounded(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as source:
        data = source.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Asset size limit exceeded")
    return data


def load_assets(directory: Path, trusted_key: bytes):
    """Trust comes from deployment configuration, never from the asset directory."""
    key = Ed25519PublicKey.from_public_bytes(trusted_key)
    raw = read_bounded(directory / "assets.lock", 1024 * 1024)
    key.verify(read_bounded(directory / "assets.lock.sig", 64), raw)
    manifest = Manifest.model_validate_json(raw)
    whitelist = read_bounded(directory / "silence.json", 65536)
    key.verify(read_bounded(directory / "silence.json.sig", 64), whitelist)
    if hashlib.sha256(whitelist).hexdigest() != manifest.silence_sha256:
        raise ValueError("Allowlist digest mismatch")
    allowed = Allowlist.model_validate_json(whitelist).neuron_ids
    ids = {neuron.id for neuron in manifest.neurons}
    if len(set(allowed)) != len(allowed) or not set(allowed) <= ids:
        raise ValueError("Invalid silence allowlist")
    raw_weights = read_bounded(directory / "weights.npz", 8 * 1024 * 1024)
    if hashlib.sha256(raw_weights).hexdigest() != manifest.weights_sha256:
        raise ValueError("Weights digest mismatch")
    with zipfile.ZipFile(io.BytesIO(raw_weights)) as archive:
        entries = archive.infolist()
        if len(entries) != 3 or {i.filename for i in entries} != {"pre.npy", "post.npy", "count.npy"}:
            raise ValueError("Unexpected array archive")
        if sum(i.file_size for i in entries) > 8 * 1024 * 1024:
            raise ValueError("Expanded asset size limit exceeded")
        for entry in entries:
            with archive.open(entry) as array_file:
                version = np.lib.format.read_magic(array_file)
                if version == (1, 0):
                    shape, order, dtype = np.lib.format.read_array_header_1_0(array_file, max_header_size=4096)
                elif version == (2, 0):
                    shape, order, dtype = np.lib.format.read_array_header_2_0(array_file, max_header_size=4096)
                else:
                    raise ValueError("Unsupported numeric array format")
                if dtype != np.dtype('int64') or len(shape) != 1 or not 1 <= shape[0] <= 100000 or order:
                    raise ValueError("Unsafe array header")
                if array_file.tell() + shape[0] * dtype.itemsize != entry.file_size:
                    raise ValueError("Array extent mismatch")
    with np.load(io.BytesIO(raw_weights), allow_pickle=False) as arrays:
        pre, post, count = (arrays[name].copy() for name in ("pre", "post", "count"))
    n = len(manifest.neurons)
    if (pre.dtype != np.int64 or post.dtype != np.int64 or count.dtype != np.int64
            or pre.ndim != 1 or pre.shape != post.shape or pre.shape != count.shape
            or not 1 <= pre.size <= 100000):
        raise ValueError("Invalid weight array schema")
    if ((pre < 0).any() or (post < 0).any() or (pre >= n).any() or (post >= n).any()
            or (count <= 0).any() or (count > 1000000).any()):
        raise ValueError("Invalid weight values")
    if len(set(zip(pre.tolist(), post.tolist()))) != pre.size:
        raise ValueError("Duplicate edges")
    for source, target in zip(pre, post):
        if (manifest.neurons[source].cell_type != "LPLC2"
                or manifest.neurons[target].cell_type != "DNp01"):
            raise ValueError("The signed model supports only feedforward visual-to-GF edges")
    if set(pre.tolist()) != {i for i, neuron in enumerate(manifest.neurons) if neuron.cell_type == "LPLC2"}:
        raise ValueError("Disconnected input neuron")
    if set(post.tolist()) != {i for i, neuron in enumerate(manifest.neurons) if neuron.cell_type == "DNp01"}:
        raise ValueError("Disconnected output neuron")
    return manifest, frozenset(allowed), pre, post, count
