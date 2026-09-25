"""Offline MaleCNS conversion; signing credentials are supplied only through env."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather
from pydantic import BaseModel, ConfigDict, Field

from brain_server.loader import Manifest, Parameters, MODEL_VERSION, Allowlist

SOURCES = {
    'annotations': ('body-annotations-male-cns-v1.0-minconf-0.5.feather', '2177e246113e4cfbf1e7772ec37c6da1955ff22e8063d0b1f833101f99a9a3b2'),
    'neurotransmitters': ('body-neurotransmitters-male-cns-v1.0.feather', '95c9289220663abeb3409f3ad9e5a7f8a53f8093f5139d15502cd08da8879621'),
    'connectivity': ('connectome-weights-male-cns-v1.0-minconf-0.5.feather', 'e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1'),
}


class Transmitter(BaseModel):
    model_config = ConfigDict(extra='ignore', hide_input_in_errors=True)
    body: int = Field(gt=0)
    consensus_nt: str
    predicted_nt: str
    predicted_nt_confidence: float = Field(ge=0., le=1., allow_inf_nan=False)


def canonical(model):
    return json.dumps(model.model_dump(mode='json'), sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def prepare(source_dir, destination):
    if destination.exists():
        raise ValueError('Refusing to replace existing model assets')
    for name, expected in SOURCES.values():
        if sha256(source_dir / name) != expected:
            raise ValueError('Source digest mismatch')
    annotations = feather.read_table(source_dir / SOURCES['annotations'][0], memory_map=True)
    transmitters = feather.read_table(source_dir / SOURCES['neurotransmitters'][0], memory_map=True)
    weights = feather.read_table(source_dir / SOURCES['connectivity'][0], memory_map=True)
    for table, names in ((annotations, ['bodyId','type','somaSide']), (transmitters, ['body','consensus_nt','predicted_nt','predicted_nt_confidence']), (weights, ['body_pre','body_post','weight'])):
        if not set(names) <= set(table.column_names):
            raise ValueError('Source schema mismatch')
    if annotations['bodyId'].null_count or pc.count_distinct(annotations['bodyId']).as_py() != annotations.num_rows:
        raise ValueError('Annotation IDs must be unique')
    if transmitters['body'].null_count or pc.count_distinct(transmitters['body']).as_py() != transmitters.num_rows:
        raise ValueError('Transmitter IDs must be unique')
    chosen = annotations.filter(pc.fill_null(pc.is_in(annotations['type'], value_set=pa.array(['LPLC2','DNp01'])), False))
    rows = sorted(chosen.select(['bodyId','type','somaSide']).to_pylist(), key=lambda r:r['bodyId'])
    neurons = [dict(id=str(row['bodyId']), cell_type=row['type'], side=row['somaSide']) for row in rows]
    nt = transmitters.filter(pc.is_in(transmitters['body'], value_set=chosen['bodyId']))
    checked = [Transmitter.model_validate(row) for row in nt.to_pylist()]
    if {row.body for row in checked} != {row['bodyId'] for row in rows}:
        raise ValueError('Selected neurons lack transmitter evidence')
    if any(row.consensus_nt != 'acetylcholine' or row.predicted_nt != 'acetylcholine' or row.predicted_nt_confidence < 0.5 for row in checked):
        raise ValueError('Selected circuit has uncertain or unsupported transmitter evidence')
    index = {int(neuron['id']): i for i, neuron in enumerate(neurons)}
    visual = pa.array([int(n['id']) for n in neurons if n['cell_type']=='LPLC2'])
    descending = pa.array([int(n['id']) for n in neurons if n['cell_type']=='DNp01'])
    # Validate all original edge values, and record rather than silently discard
    # endpoints outside the curated annotation table. Raw connectome includes fragments.
    selected = []
    outside_annotations = 0
    for batch in weights.to_batches(max_chunksize=1000000):
        table = pa.Table.from_batches([batch])
        for field in ('body_pre','body_post','weight'):
            if table[field].type != pa.int64() or table[field].null_count or pc.min(table[field]).as_py() <= 0:
                raise ValueError('Invalid connectivity values')
        known = pc.and_(pc.is_in(table['body_pre'], value_set=annotations['bodyId']), pc.is_in(table['body_post'], value_set=annotations['bodyId']))
        outside_annotations += table.num_rows - pc.sum(pc.cast(known, pa.int64())).as_py()
        keep = pc.and_(pc.is_in(table['body_pre'], value_set=visual), pc.is_in(table['body_post'], value_set=descending))
        selected.extend(table.filter(keep).to_pylist())
    pre = np.array([index[row['body_pre']] for row in selected], dtype=np.int64)
    post = np.array([index[row['body_post']] for row in selected], dtype=np.int64)
    count = np.array([row['weight'] for row in selected], dtype=np.int64)
    if len(set(zip(pre.tolist(), post.tolist()))) != len(selected):
        raise ValueError('Duplicate selected edges')
    if len(neurons) != 187 or len(selected) != 185 or int(count.sum()) != 4862:
        raise ValueError('Reviewed circuit does not match this source conversion')
    destination.mkdir(mode=0o700, parents=True)
    np.savez(destination/'weights.npz', pre=pre, post=post, count=count)
    allowed = Allowlist(neuron_ids=[n['id'] for n in neurons])
    raw_allow = canonical(allowed)
    manifest = Manifest(source='MaleCNS', release='v1.0', model_version=MODEL_VERSION,
        selection='LPLC2_to_DNp01_feedforward', neurons=neurons, parameters=Parameters(),
        weights_sha256=sha256(destination/'weights.npz'), silence_sha256=hashlib.sha256(raw_allow).hexdigest(),
        source_sha256={role: item[1] for role,item in SOURCES.items()})
    raw_manifest = canonical(manifest)
    for name, raw in (('assets.lock', raw_manifest), ('silence.json', raw_allow)):
        (destination/name).write_bytes(raw)
    report = {'source_rows': weights.num_rows, 'edges_outside_curated_annotations': outside_annotations,
        'selected_neurons': len(neurons), 'selected_edges': len(selected), 'selected_synapses': int(count.sum()),
        'minimum_selected_nt_confidence': min(row.predicted_nt_confidence for row in checked),
        'weight_normalization': 'Each output receives synaptic_gain times its input spike weighted mean',
        'interpretation': 'Reduced circuit; no full-brain or measured physiological parameter claim'}
    (destination/'conversion_report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    result = prepare(Path(os.environ['REFLEXGUARD_SOURCE_DIR']), Path(os.environ['REFLEXGUARD_MODEL_DIR']))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
