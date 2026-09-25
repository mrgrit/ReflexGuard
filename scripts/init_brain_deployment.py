"""Create local deployment credentials without emitting or committing secrets."""
import base64
import json
import os
from pathlib import Path
import secrets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main():
    root=Path(__file__).resolve().parents[1]
    targets=[root/'.env.model-signing',root/'.env.brain-client',root/'certs/brain/server.env']
    if any(path.exists() for path in targets):
        raise ValueError('Deployment files already exist; refusing to overwrite credentials')
    certs=root/'certs/brain'
    if not all((certs/name).is_file() for name in ('ca.crt','client.crt','client.key','server.crt','server.key')):
        raise ValueError('Generate dedicated brain certificates first')
    key=Ed25519PrivateKey.generate()
    private=base64.b64encode(key.private_bytes_raw()).decode()
    public=base64.b64encode(key.public_key().public_bytes_raw()).decode()
    token=secrets.token_urlsafe(32)
    content=[
        'REFLEXGUARD_MODEL_SIGNING_KEY='+private+'\n',
        '\n'.join([
            'REFLEXGUARD_BRAIN_URL=https://localhost:18443',
            'REFLEXGUARD_BRAIN_TOKEN='+token,
            'REFLEXGUARD_TLS_CA='+str(certs/'ca.crt'),
            'REFLEXGUARD_TLS_CLIENT_CERT='+str(certs/'client.crt'),
            'REFLEXGUARD_TLS_CLIENT_KEY='+str(certs/'client.key'),
        ])+'\n',
        '\n'.join([
            'REFLEXGUARD_API_TOKENS='+json.dumps([{'token':token,'subject':'wheelchair-1','role':'operator'}],separators=(',',':')),
            'REFLEXGUARD_MODEL_PUBLIC_KEY='+public,
            'REFLEXGUARD_MODEL_DIR=/model',
            'REFLEXGUARD_TLS_CA=/run/reflexguard/ca.crt',
            'REFLEXGUARD_TLS_SERVER_CERT=/run/reflexguard/server.crt',
            'REFLEXGUARD_TLS_SERVER_KEY=/run/reflexguard/server.key',
            'REFLEXGUARD_BRAIN_PORT=8443',
        ])+'\n',
    ]
    for path,text in zip(targets,content):
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'w') as target:
            target.write(text)
    print('Dedicated brain deployment files created with mode 0600')


if __name__=='__main__':
    main()
