"""Run the public contract over real mTLS and measure actual end-to-end latency."""
import asyncio
import json
import os
import statistics
import ssl
import time
import httpx

from reflexguard.brain_client.client import BrainClient
from reflexguard.common.config import ClientSettings
from reflexguard.common.schemas import StepRequest


async def check():
    settings=ClientSettings.from_env()
    bare=ssl.create_default_context(cafile=str(settings.ca_cert))
    url=str(settings.base_url).rstrip('/')
    denied=False
    async with httpx.AsyncClient(verify=bare,trust_env=False,timeout=2) as client:
        try:
            await client.get(url+'/v1/health',headers={'Authorization':'Bearer '+settings.token.get_secret_value()})
        except httpx.TransportError:
            denied=True
    if not denied:
        raise RuntimeError('Missing client certificate was accepted')
    tls=ssl.create_default_context(cafile=str(settings.ca_cert))
    tls.load_cert_chain(str(settings.client_cert),str(settings.client_key))
    async with httpx.AsyncClient(verify=tls,trust_env=False,timeout=2) as client:
        response=await client.get(url+'/v1/health')
        if response.status_code!=401:
            raise RuntimeError('Missing bearer token was accepted')
    timings=[]
    async with BrainClient(settings) as client:
        health=await client.health()
        if not health.model_version.startswith('malecns-'):
            raise RuntimeError('The target is not the real model')
        session=await client.create_session()
        responses=[]
        for index in range(100):
            started=time.perf_counter()
            response=await client.step(session.session_id,StepRequest(t_ms=index*50,dt_ms=50,left_looming=.8,right_looming=.0))
            timings.append((time.perf_counter()-started)*1000)
            responses.append(response)
        if not all(r.escape>0 and r.turn_right>r.turn_left for r in responses):
            raise RuntimeError('Lateral input did not activate the expected output')
        await client.silence(session.session_id,['10001','10010'])
        quiet=await client.step(session.session_id,StepRequest(t_ms=5000,dt_ms=50,left_looming=1.,right_looming=1.))
        if quiet.escape!=0:
            raise RuntimeError('Signed allowlist silencing did not suppress the outputs')
    ordered=sorted(timings)
    return {'health':health.model_dump(),'steps':len(timings),'dt_ms':50,
        'client_deadline_ms':200,'end_to_end_ms':{'min':min(timings),'median':statistics.median(timings),'p95':ordered[94],'max':max(timings)},
        'missing_client_certificate_rejected':True,'missing_bearer_rejected':True,'directional_response':'passed','output_silencing':'passed'}


if __name__=='__main__':
    print(json.dumps(asyncio.run(check()),indent=2))
