"""Three native rounds with cgroup CPU/memory readings after native exit."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

spec=importlib.util.spec_from_file_location('verify',Path(__file__).with_name('verify_image14_debian.py'))
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
out=v.OUT/'resource-smoke'
out.mkdir(exist_ok=False)
real_popen=subprocess.Popen
def wrapped(argv,**kwargs):
    argv=list(argv)
    if argv[:2]==['docker','run']:
        idx=argv.index(v.TAG)
        mode=argv[idx+1]
        wrapper='python3 /app/harness.py '+mode+'; rc=$?; for f in memory.peak memory.max cpu.max cpu.stat; do echo "$f" >> /workspace/cgroup-resources.txt; cat /sys/fs/cgroup/$f >> /workspace/cgroup-resources.txt; done; exit $rc'
        argv=argv[:idx]+['--entrypoint','/bin/sh',v.TAG,'-c',wrapper]
        argv=[('4g' if x=='8g' else x) for x in argv]
    return real_popen(argv,**kwargs)
subprocess.Popen=wrapped
results={}
try:
    for profile,name in v.host.PACKAGES.items():
        p=out/profile
        p.mkdir()
        parent=p/'parent'
        parent.mkdir()
        shutil.copy2(v.OUT/'train-only-projection'/name/'checkpoint.npz',parent/'checkpoint.npz')
        receipt=v.host._artifact_receipt('baseline-'+profile,parent)
        start=time.perf_counter()
        record,candidate,state=v.host._run_round(image=v.TAG,profile=profile,round_index=1,package=v.OUT/'train-only-projection'/name,parent_root=parent,parent=receipt,state_root=None,run_root=p,history=[],artifacts=[receipt])
        resources=(p/'workspace/cgroup-resources.txt').read_text()
        peak=int(resources.split('memory.peak\n')[1].splitlines()[0])
        assert peak<4*1024**3
        assert '4294967296' in resources
        assert '400000 100000' in resources
        results[profile]=dict(wall_seconds=time.perf_counter()-start,peak_cgroup_memory_bytes=peak,cgroup=resources,candidate=candidate is not None,record=record)
finally:
    subprocess.Popen=real_popen
(out/'resources.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({k:{'wall_seconds':r['wall_seconds'],'peak_bytes':r['peak_cgroup_memory_bytes']} for k,r in results.items()}))
