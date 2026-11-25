"""Verify frozen image14 source in Debian; never read public validation."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/image14-debian'
SOURCE = OUT / 'source'
sys.path.insert(0, str(SOURCE / 'src'))
spec = importlib.util.spec_from_file_location('image14_host', SOURCE / 'scripts/verify_workspace_v2_image.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)
TAG = 'brace-msi:0.10.6rc1-debian1'


def run():
    receipts = []
    def command(argv):
        start = time.perf_counter()
        p = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        receipts.append(dict(argv=argv, exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr, wall_seconds=time.perf_counter()-start))
        return p
    for tag in ('brace-msi:0.10.6rc1', TAG):
        for entry, args in [('/bin/true', []), ('/bin/sh', ['-c','echo shell-ok; id; pwd']), ('python3',['-c','import numpy; print(numpy.__version__)'])]:
            p=command(['docker','run','--rm','--network','none','--read-only','--cpus','4','--memory','4g','--entrypoint',entry,tag,*args])
            assert p.returncode==0, receipts[-1]
        p=command(['docker','run','--rm','--network','none','--read-only',tag])
        assert p.returncode==0, receipts[-1]
        p=command(['docker','run','--rm','--network','none','--read-only',tag,'describe'])
        assert json.loads(p.stdout)['sdk_version']=='1.0.2'
    p=command(['docker','run','--rm','--entrypoint','python3',TAG,'-c',"import json,sys,importlib.metadata as m; print(json.dumps({'python':sys.version,'dependencies':{d.metadata['Name']:d.version for d in m.distributions()}}))"])
    dependencies=json.loads(p.stdout)
    assert dependencies['dependencies']['numpy']=='1.26.4'
    assert not {'pytrio','swanlab','torch','scipy','scikit-learn'} & set(dependencies['dependencies'])
    p=command(['docker','run','--rm','--entrypoint','python3',TAG,'-m','pip','check'])
    assert p.returncode==0
    p=command(['docker','run','--rm','--entrypoint','/bin/sh',TAG,'-c','dpkg-query -W; find /app -type f | sort'])
    # Compare every shipped Python source to the exact frozen Git tree.
    code_hashes={}
    for subtree in ('brace_formal','contest_harness'):
        for path in sorted((SOURCE/'src'/subtree).glob('*.py')):
            inside='/app/src/'+subtree+'/'+path.name
            p=command(['docker','run','--rm','--entrypoint','sha256sum',TAG,inside])
            expected=hashlib.sha256(path.read_bytes()).hexdigest()
            assert p.stdout.split()[0]==expected, inside
            code_hashes[inside]=expected
    packages=OUT/'train-only-projection'
    packages.mkdir(exist_ok=False)
    official=Path(r'C:/Users/Administrator/Desktop/人工智能创新大赛/训练包')
    for name in host.PACKAGES.values():
        target=packages/name
        (target/'public').mkdir(parents=True)
        shutil.copy2(official/name/'checkpoint.npz',target/'checkpoint.npz')
        shutil.copy2(official/name/'public/train.jsonl',target/'public/train.jsonl')
        # Existing host expects a prediction path named validation. It contains
        # only the first five training inputs; never official validation data.
        with (target/'public/train.jsonl').open(encoding='utf-8') as f:
            rows=[next(f) for _ in range(5)]
        (target/'public/validation.jsonl').write_text(''.join(rows),encoding='utf-8')
    real_popen=subprocess.Popen
    real_run=subprocess.run
    def limit(argv):
        argv=list(argv)
        if argv[:2]==['docker','run']:
            argv=[('4g' if x=='8g' else x) for x in argv]
        return argv
    def popen(argv,**kwargs):
        return real_popen(limit(argv),**kwargs)
    def limited_run(argv,**kwargs):
        return real_run(limit(argv),**kwargs)
    subprocess.Popen=popen
    subprocess.run=limited_run
    start=time.perf_counter()
    try:
        acceptance=host.run(TAG,packages,OUT/'container-acceptance')
    finally:
        subprocess.Popen=real_popen
        subprocess.run=real_run
    assert acceptance['valid']
    for profile in acceptance['profiles'].values():
        assert profile['round_count']==10
        assert all(r['candidate_submitted'] for r in profile['rounds'])
        assert profile['model_call_count']==20
    report=dict(scope='local_protocol_not_official_performance', tag=TAG, dependencies=dependencies, startup_checks=receipts, source_hashes=code_hashes, acceptance=acceptance, container_limits=dict(cpus=4,memory_bytes=4*1024**3,network='none',read_only=True), wall_seconds=time.perf_counter()-start, online_pytrio='NOT_RUN_HOST_PROTOCOL_STANDIN', swanlab='EXTERNAL_RECORDING_NOT_SHIPPED')
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(valid=True,rounds=30,candidates=30,model_protocol_calls=60,wall_seconds=report['wall_seconds'])))

if __name__=='__main__':
    run()
