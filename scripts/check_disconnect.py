"""Cut a test-owned TLS byte relay and verify a latched gradual stop."""
import asyncio
import json
from reflexguard.brain_client.client import BrainClient
from reflexguard.common.config import ClientSettings
from reflexguard.control.arbiter import Command
from reflexguard.control.config import Calibration
from reflexguard.control.pipeline import Pipeline
from reflexguard.simulation.drive import CameraFrame


async def check():
    settings=ClientSettings.from_env()
    # The relay never terminates TLS, reads credentials or changes production services.
    if settings.base_url.host not in ('localhost','127.0.0.1'):
        raise ValueError('Use the documented local SSH tunnel for this check')
    writers=set()
    tasks=set()
    async def relay(reader,writer):
        task=asyncio.current_task()
        tasks.add(task)
        writers.add(writer)
        peer=None
        async def copy(source,destination):
            while True:
                data=await source.read(65536)
                if not data: break
                destination.write(data)
                await destination.drain()
        try:
            upstream,peer=await asyncio.open_connection('127.0.0.1',settings.base_url.port)
            writers.add(peer)
            await asyncio.gather(copy(reader,peer),copy(upstream,writer))
        except (OSError,asyncio.CancelledError):
            pass
        finally:
            for stream in (writer,peer):
                if stream is not None:
                    stream.close()
                    writers.discard(stream)
            tasks.discard(task)
    server=await asyncio.start_server(relay,'127.0.0.1',0)
    port=server.sockets[0].getsockname()[1]
    values=settings.model_dump()
    values['base_url']=f'https://localhost:{port}'
    pipe=Pipeline(Calibration.load(),BrainClient(ClientSettings.model_validate(values)))
    pixels=bytes([220,220,220,255])*(160*120)
    user=Command(forward=.6,turn=0.)
    try:
        await pipe.start()
        before=await pipe.step(CameraFrame(0,160,120,pixels),user,32)
        if pipe.failed or before.decision.command.forward!=.6:
            raise RuntimeError('Healthy initial motion was not exercised')
        model=pipe.model_version
        server.close()
        await server.wait_closed()
        for stream in tuple(writers): stream.close()
        for task in tuple(tasks): task.cancel()
        await asyncio.gather(*tuple(tasks),return_exceptions=True)
        speeds=[.6]
        for index in range(1,20):
            result=await pipe.step(CameraFrame(index*32,160,120,pixels),user,32)
            speeds.append(result.decision.command.forward)
        if not (pipe.failed and pipe.failures==1 and pipe.brain_steps==1
                and 0<speeds[1]<speeds[0] and speeds[-1]==0
                and all(a>=b for a,b in zip(speeds,speeds[1:]))):
            raise RuntimeError('Disconnect did not cause the required gradual stop')
        # Upstream is still healthy; reconnecting cannot rearm the failed pipeline.
        async with BrainClient(settings) as restored:
            await restored.health()
        idle=Command(forward=0.,turn=0.)
        for index in range(20,40):
            await pipe.step(CameraFrame(index*32,160,120,pixels),idle,32)
        last=await pipe.step(CameraFrame(1280,160,120,pixels),user,32)
        if last.decision.command.forward!=0 or last.decision.reason!='brain_failure':
            raise RuntimeError('Connection restoration incorrectly resumed motion')
        return {'model_version':model,'disconnect_stop':'passed','forward_sequence':speeds,
            'fault_latched_after_reconnection':True,'automatic_mock_downgrade':False}
    finally:
        server.close()
        await server.wait_closed()
        for task in tuple(tasks): task.cancel()
        await asyncio.gather(*tuple(tasks),return_exceptions=True)
        await pipe.close()


if __name__=='__main__':
    print(json.dumps(asyncio.run(check()),indent=2))
