"""GPU-local timing and NumPy parity on the authenticated deployed circuit."""
import base64
import json
import os
from pathlib import Path
import statistics
import time
import numpy as np
from brain_server.loader import load_assets
from brain_server.model import Circuit
from reflexguard.common.schemas import StepRequest


def main():
    assets=load_assets(Path(os.environ['REFLEXGUARD_MODEL_DIR']),base64.b64decode(os.environ['REFLEXGUARD_MODEL_PUBLIC_KEY'],validate=True))
    gpu=Circuit(assets,backend='cuda')
    cpu=Circuit(assets)
    gs,cs=gpu.state(),cpu.state()
    timings=[]
    pattern=[(0.,0.),(.2,.1),(.5,0.),(.8,0.),(0.,.8),(1.,1.)]
    # Warm up CUDA before taking timings; discard its state.
    gpu.step(gpu.state(),StepRequest(t_ms=0,dt_ms=50,left_looming=0.,right_looming=0.),set(),time.monotonic()+30)
    for index in range(120):
        left,right=pattern[index%len(pattern)]
        request=StepRequest(t_ms=index*50,dt_ms=50,left_looming=left,right_looming=right)
        silence=set() if index<100 else {'10001','10010'}
        started=time.perf_counter()
        gs,gr=gpu.step(gs,request,silence,time.monotonic()+.15)
        timings.append((time.perf_counter()-started)*1000)
        cs,cr=cpu.step(cs,request,silence,time.monotonic()+1)
        if gr.model_dump()!=cr.model_dump():
            raise RuntimeError('GPU and reference spike outputs differ')
        if not np.allclose(gs.voltage.cpu().numpy(),cs.voltage,atol=1e-5,rtol=1e-5):
            raise RuntimeError('GPU and reference state differs')
    print(json.dumps({'model_version':assets[0].model_version,'weights_sha256':assets[0].weights_sha256,
        'neurons':gpu.size,'edges':len(assets[2]),'steps':len(timings),'dt_ms':50,
        'parameters':assets[0].parameters.model_dump(),'numpy_cuda_parity':'passed',
        'compute_ms':{'min':min(timings),'median':statistics.median(timings),'p95':sorted(timings)[113],'max':max(timings)}},indent=2))


if __name__=='__main__':
    main()
