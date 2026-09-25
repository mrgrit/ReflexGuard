"""Signed asset, LIF and authenticated real-service regression tests."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from fastapi.testclient import TestClient
import numpy as np
import pytest

from brain_server.loader import load_assets, Manifest, Parameters, MODEL_VERSION
from brain_server.model import Circuit
from brain_server.app import create_app
from brain_server.service import SimulationService
from reflexguard.common.schemas import StepRequest


@pytest.fixture
def signed_assets(tmp_path):
    key = Ed25519PrivateKey.generate()
    directory = tmp_path/'assets'
    directory.mkdir()
    np.savez(directory/'weights.npz', pre=np.array([0,1], dtype=np.int64), post=np.array([2,3], dtype=np.int64), count=np.array([10,20], dtype=np.int64))
    allowed = json.dumps({'neuron_ids':['1','2','3','4']}).encode()
    (directory/'silence.json').write_bytes(allowed)
    (directory/'silence.json.sig').write_bytes(key.sign(allowed))
    manifest = Manifest(source='MaleCNS', release='v1.0', model_version=MODEL_VERSION,
        selection='LPLC2_to_DNp01_feedforward',
        neurons=[{'id':str(i+1),'cell_type':'LPLC2' if i<2 else 'DNp01','side':'L' if i%2==0 else 'R'} for i in range(4)],
        weights_sha256=hashlib.sha256((directory/'weights.npz').read_bytes()).hexdigest(),
        silence_sha256=hashlib.sha256(allowed).hexdigest(),
        source_sha256={role:hashlib.sha256(b'synthetic test fixture').hexdigest() for role in ('annotations','neurotransmitters','connectivity')}, parameters=Parameters())
    raw=manifest.model_dump_json().encode()
    (directory/'assets.lock').write_bytes(raw)
    (directory/'assets.lock.sig').write_bytes(key.sign(raw))
    return directory,key


def load_fixture(fixture):
    directory,key=fixture
    return load_assets(directory,key.public_key().public_bytes_raw())


def resign(fixture, updates):
    directory,key=fixture
    manifest=json.loads((directory/'assets.lock').read_text())
    manifest.update(updates)
    raw=json.dumps(manifest).encode()
    (directory/'assets.lock').write_bytes(raw)
    (directory/'assets.lock.sig').write_bytes(key.sign(raw))


@pytest.mark.parametrize('name', ['assets.lock','assets.lock.sig','silence.json','silence.json.sig','weights.npz'])
def test_asset_tampering_is_rejected_before_simulation(signed_assets,name):
    path=signed_assets[0]/name
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises((ValueError,InvalidSignature)):
        load_fixture(signed_assets)


def test_signer_must_match_independent_trust_key(signed_assets):
    with pytest.raises(InvalidSignature):
        load_assets(signed_assets[0],Ed25519PrivateKey.generate().public_key().public_bytes_raw())


@pytest.mark.parametrize('change', ['negative','foreign_index','duplicate','float','reversed','disconnected'])
def test_signed_but_invalid_graph_is_rejected(signed_assets,change):
    arrays={'pre':np.array([0,1],dtype=np.int64),'post':np.array([2,3],dtype=np.int64),'count':np.array([10,20],dtype=np.int64)}
    if change=='negative': arrays['count'][0]=-1
    elif change=='foreign_index': arrays['pre'][0]=9000
    elif change=='duplicate':
        arrays['pre'][1]=0
        arrays['post'][1]=2
    elif change=='float': arrays['count']=arrays['count'].astype(np.float32)
    elif change=='reversed': arrays['pre'],arrays['post']=arrays['post'],arrays['pre']
    else: arrays['pre'][1]=0
    path=signed_assets[0]/'weights.npz'
    np.savez(path,**arrays)
    resign(signed_assets,{'weights_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    with pytest.raises(ValueError): load_fixture(signed_assets)


def test_array_header_cannot_request_unbounded_allocation(signed_assets):
    header=io.BytesIO()
    np.lib.format.write_array_header_1_0(header,{'descr':'<i8','fortran_order':False,'shape':(10**12,)})
    path=signed_assets[0]/'weights.npz'
    with zipfile.ZipFile(path,'w') as archive:
        for name in ('pre','post','count'): archive.writestr(name+'.npy',header.getvalue())
    resign(signed_assets,{'weights_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    with pytest.raises(ValueError,match='header'): load_fixture(signed_assets)


def test_symlink_assets_are_not_followed(signed_assets):
    path=signed_assets[0]/'weights.npz'
    saved=path.read_bytes()
    path.unlink()
    target=signed_assets[0]/'elsewhere'
    target.write_bytes(saved)
    path.symlink_to(target)
    with pytest.raises(OSError): load_fixture(signed_assets)


def test_signed_allowlist_cannot_name_foreign_neurons(signed_assets):
    directory,key=signed_assets
    raw=json.dumps({'neuron_ids':['999']}).encode()
    (directory/'silence.json').write_bytes(raw)
    (directory/'silence.json.sig').write_bytes(key.sign(raw))
    resign(signed_assets,{'silence_sha256':hashlib.sha256(raw).hexdigest()})
    with pytest.raises(ValueError): load_fixture(signed_assets)


def test_lif_has_directional_activity_silencing_and_quiet_baseline(signed_assets):
    circuit=Circuit(load_fixture(signed_assets))
    initial=circuit.state()
    request=StepRequest(t_ms=0,dt_ms=50,left_looming=0.,right_looming=0.)
    _,baseline=circuit.step(initial,request,set(),time.monotonic()+1)
    assert baseline.escape==baseline.turn_left==baseline.turn_right==0
    request=StepRequest(t_ms=0,dt_ms=50,left_looming=1.,right_looming=0.)
    state,active=circuit.step(initial,request,set(),time.monotonic()+1)
    assert active.escape>0 and active.turn_right>active.turn_left
    assert not initial.voltage.any() and not initial.spikes.any()
    _,silenced=circuit.step(state,request,{'3','4'},time.monotonic()+1)
    assert silenced.escape==0
    assert any(n.id=='3' and n.rate_hz>0 for n in active.top_neurons)
    with pytest.raises(TimeoutError): circuit.step(initial,request,set(),time.monotonic()-1)
    assert not initial.voltage.any()


def test_signed_parameter_ranges_are_enforced(signed_assets):
    resign(signed_assets,{'parameters':{'input_gain':float('inf')}})
    with pytest.raises(ValueError): load_fixture(signed_assets)


def test_real_api_contract_auth_owner_replay_silence(signed_assets,mock_settings,credentials):
    app=create_app(mock_settings,Circuit(load_fixture(signed_assets)))
    headers=lambda who:{'Authorization':'Bearer '+credentials[who]['token']}
    with TestClient(app,base_url='https://localhost',raise_server_exceptions=False) as client:
        assert client.get('/v1/health').status_code==401
        assert client.get('/v1/health',headers=headers('operator')).json()['model_version']==MODEL_VERSION
        session=client.post('/v1/sessions',headers=headers('operator'),json={}).json()['session_id']
        body={'t_ms':0,'dt_ms':50,'left_looming':1.,'right_looming':0.}
        path='/v1/sessions/'+session
        assert client.post(path+'/step',json=body,headers=headers('outsider')).status_code==404
        assert client.post(path+'/step',json={**body,'dt_ms':101},headers=headers('operator')).status_code==422
        first=client.post(path+'/step',json=body,headers=headers('operator'))
        assert first.status_code==200 and first.json()['escape']>0
        assert client.post(path+'/step',json=body,headers=headers('operator')).status_code==409
        assert client.post(path+'/silence',json={'neuron_ids':['3']},headers=headers('guardian')).status_code==403
        assert client.post(path+'/silence',json={'neuron_ids':['999']},headers=headers('operator')).status_code==422
        assert client.post(path+'/silence',json={'neuron_ids':[str(i) for i in range(11)]},headers=headers('operator')).status_code==422
        assert client.post(path+'/silence',json={'neuron_ids':['3','4']},headers=headers('operator')).status_code==200
        final=client.post(path+'/step',json={**body,'t_ms':50},headers=headers('operator'))
        assert final.status_code==200 and final.json()['escape']==0


def test_simulation_timeout_disables_service_without_committing(signed_assets):
    circuit=Circuit(load_fixture(signed_assets))
    service=SimulationService(circuit,max_sessions=1,ttl=10)
    sid=service.create('owner')
    with pytest.raises(HTTPException) as error: service.create('owner')
    assert error.value.status_code==503
    original=service.sessions[sid].state
    def stall(*args):
        time.sleep(.18)
        raise TimeoutError('test simulated worker overrun')
    circuit.step=stall
    async def run():
        with pytest.raises(HTTPException) as error:
            await service.step(sid,'owner',StepRequest(t_ms=0,dt_ms=50,left_looming=1.,right_looming=0.))
        assert error.value.status_code==503
        assert service.failed and sid not in service.sessions
        assert not original.voltage.any()
        with pytest.raises(HTTPException): service.create('owner')
        await asyncio.sleep(.05)
    try: asyncio.run(run())
    finally: service.close()


def test_session_expiration_and_queue_bound(signed_assets):
    service=SimulationService(Circuit(load_fixture(signed_assets)),max_sessions=1,ttl=1)
    first=service.create('owner')
    service.sessions[first].touched-=2
    second=service.create('owner')
    assert first not in service.sessions
    service.pending=4
    async def run():
        with pytest.raises(HTTPException) as error:
            await service.step(second,'owner',StepRequest(t_ms=0,dt_ms=1,left_looming=0.,right_looming=0.))
        assert error.value.status_code==503
        assert service.sessions[second].last_t_ms==-1
    try: asyncio.run(run())
    finally: service.close()


@pytest.fixture(params=['mock','real'])
def contract_api(request,signed_assets,mock_settings,credentials):
    if request.param=='mock':
        from reflexguard.mock_brain.app import create_app as mock_app
        app=mock_app(mock_settings)
        outputs=['mock-escape']
    else:
        app=create_app(mock_settings,Circuit(load_fixture(signed_assets)))
        outputs=['3','4']
    with TestClient(app,base_url='https://localhost',raise_server_exceptions=False) as client:
        client.headers['Authorization']='Bearer '+credentials['operator']['token']
        yield client,outputs


def test_shared_contract_health_direction_replay_and_silence(contract_api):
    from reflexguard.common.schemas import HealthResponse, SessionResponse, StepResponse
    api,outputs=contract_api
    health=HealthResponse.model_validate(api.get('/v1/health').json())
    assert health.status=='ok'
    sid=SessionResponse.model_validate(api.post('/v1/sessions').json()).session_id
    path='/v1/sessions/'+sid
    body={'t_ms':0,'dt_ms':50,'left_looming':1.,'right_looming':0.}
    response=api.post(path+'/step',json=body)
    assert response.status_code==200
    signal=StepResponse.model_validate(response.json())
    assert signal.model_version==health.model_version and signal.escape>0
    assert signal.turn_right>signal.turn_left
    assert api.post(path+'/step',json=body).status_code==409
    assert api.post(path+'/silence',json={'neuron_ids':outputs}).status_code==200
    quiet=StepResponse.model_validate(api.post(path+'/step',json={**body,'t_ms':50}).json())
    assert quiet.escape==0


def test_shared_contract_boundaries_and_owner_isolation(contract_api,credentials):
    api,_=contract_api
    sid=api.post('/v1/sessions').json()['session_id']
    path='/v1/sessions/'+sid
    assert api.post(path+'/step',json={'t_ms':0,'dt_ms':101,'left_looming':0.,'right_looming':0.}).status_code==422
    assert api.post(path+'/silence',json={'neuron_ids':['foreign-neuron']}).status_code==422
    assert api.post('/v1/sessions',content=b'x'*16385).status_code==413
    assert api.get('http://localhost/v1/health',headers={'X-Forwarded-Proto':'https'}).status_code==400
    assert api.get('/docs').status_code==404 and api.get('/openapi.json').status_code==404
    api.headers['Authorization']='Bearer '+credentials['guardian']['token']
    assert api.post(path+'/silence',json={'neuron_ids':[]}).status_code==403
    api.headers['Authorization']='Bearer '+credentials['outsider']['token']
    body={'t_ms':0,'dt_ms':50,'left_looming':0.,'right_looming':0.}
    assert api.post(path+'/step',json=body).status_code==404
    api.headers.pop('Authorization')
    for method,url in [('GET','/v1/health'),('POST','/v1/sessions'),('POST',path+'/step'),('POST',path+'/silence')]:
        assert api.request(method,url).status_code==401


def test_control_ca_stays_separate_from_brain_ca(monkeypatch,certificates,untrusted_certificates,credentials):
    from reflexguard.control_server.device_client import DeviceSettings
    values={'REFLEXGUARD_CONTROL_URL':'https://localhost:8444','REFLEXGUARD_CHAIR_ID':'seat-a',
        'REFLEXGUARD_DEVICE_TOKEN':credentials['operator']['token'],
        'REFLEXGUARD_REMOTE_KEY':credentials['admin']['token'],
        'REFLEXGUARD_CONTROL_TLS_CA':str(certificates/'ca.crt'),
        'REFLEXGUARD_TLS_CA':str(untrusted_certificates/'ca.crt')}
    for name,value in values.items(): monkeypatch.setenv(name,value)
    assert DeviceSettings.from_env().ca_cert==certificates/'ca.crt'
    monkeypatch.delenv('REFLEXGUARD_CONTROL_TLS_CA')
    assert DeviceSettings.from_env().ca_cert==untrusted_certificates/'ca.crt'
