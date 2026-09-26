"""Validate and combine the fixed integration checks into a reviewable report."""
import json
from pathlib import Path
import sys
from pydantic import BaseModel, ConfigDict
from typing import Literal
from reflexguard.simulation.models import Result
from reflexguard.simulation.verify import verify


class ReportArgs(BaseModel):
    model_config=ConfigDict(extra='forbid')
    directory: Path
    profile: Literal['mock','real','local']


def main():
    if len(sys.argv)!=3: raise ValueError('Expected evidence directory and profile')
    args=ReportArgs(directory=sys.argv[1],profile=sys.argv[2])
    def read(name): return json.loads((args.directory/name).read_text())
    worlds=[]
    for name in ('corridor_basic','corridor_side','corridor_static','idle'):
        result=Result.model_validate(read(name+'.json'))
        verify(result)
        worlds.append(result.model_dump())
    control=read('control.json')
    fault=read('disconnect.json')
    if not (control['dashboard_remote_stop'] and control['audit']['valid']
            and control['brain_profile']==args.profile and fault['fault_latched_after_reconnection']):
        raise ValueError('Integration evidence is incomplete')
    report={'status':'passed','profile':args.profile,'worlds':worlds,'disconnect':fault,'control':control}
    if args.profile!='mock':report['contract']=read('contract.json')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
