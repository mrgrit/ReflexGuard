"""Sign an offline conversion on the trusted development host, never the GPU service."""
import base64
import hashlib
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from brain_server.loader import Manifest, load_assets, read_bounded


def main():
    directory = Path(os.environ['REFLEXGUARD_MODEL_DIR'])
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(os.environ['REFLEXGUARD_MODEL_SIGNING_KEY'], validate=True))
    raw = read_bounded(directory/'assets.lock', 1024*1024)
    manifest = Manifest.model_validate_json(raw)
    if len(manifest.neurons) != 187:
        raise ValueError('Unexpected deployment circuit size')
    for name in ('assets.lock','silence.json'):
        (directory/(name+'.sig')).write_bytes(key.sign(read_bounded(directory/name,1024*1024)))
    public_key = key.public_key().public_bytes_raw()
    load_assets(directory,public_key)
    (directory/'public-key.txt').write_text(base64.b64encode(public_key).decode()+'\n')
    print('Model signatures verified; public key SHA-256:',hashlib.sha256(public_key).hexdigest())


if __name__ == '__main__':
    main()
