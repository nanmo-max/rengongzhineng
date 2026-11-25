"""Freeze a Debian candidate only after native container and Linux tests pass."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/image14-debian'
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    log=(OUT/'linux-regression5.log').read_text(encoding='utf-8')
    if '470 passed, 1 skipped' not in log and '471 passed' not in log:
        raise SystemExit('Linux full-regression gate has not passed; refusing release')
    acceptance=json.loads((OUT/'verification.json').read_text(encoding='utf-8'))
    assert acceptance['acceptance']['valid']
    image=json.loads(subprocess.check_output(['docker','image','inspect','brace-msi:0.10.6rc1-debian1'],text=True))[0]
    assert image['Architecture']=='amd64' and image['Os']=='linux'
    assert image['Size']<2*1024**3
    for relative,inside in [('submission/harness.py','/app/harness.py'),('submission/contest_submission.py','/app/contest_submission.py')]:
        actual=subprocess.check_output(['docker','run','--rm','--entrypoint','sha256sum','brace-msi:0.10.6rc1-debian1',inside],text=True).split()[0]
        assert actual==sha(OUT/'source'/relative)
    archive=OUT/'harness-debian.tar'
    manifest=dict(format='brace.image14-debian.release.v1',status='LOCAL_READY_PENDING_PLATFORM',base_source_commit='c653e0e04297b655b93e28a90abd9f36e2ff761d',tag='brace-msi:0.10.6rc1-debian1',image_id=image['Id'],base_image='python:3.12-slim-bookworm@sha256:44cf1793efa7c7a476bb0f2cff81443f4a072c90c1cb127e2924933daa3e8c64',archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),image_bytes=image['Size'],dockerfile_sha256=sha(ROOT/'Dockerfile.image14-debian'),verification_sha256=sha(OUT/'verification.json'),linux_regression_sha256=sha(OUT/'linux-regression4.log'),resources_sha256=sha(OUT/'resource-smoke/resources.json'),official_platform_test_consumed=False,real_model_calls=False,cloud_sync=False)
    manifest['linux_regression_sha256']=sha(OUT/'linux-regression5.log')
    (OUT/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'source-debian.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted((OUT/'source/src').rglob('*.py')):
            rel=path.relative_to(OUT/'source')
            if rel.parts[1] in {'brace_formal','contest_harness'}:
                z.write(path,str(rel))
        for f in ['submission/harness.py','submission/contest_submission.py','requirements.formal.lock']:
            z.write(OUT/'source'/f,f)
        z.write(ROOT/'Dockerfile.image14-debian','Dockerfile.formal')
    with zipfile.ZipFile(OUT/'DEBIAN-兼容性验收与源码.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['release-manifest.json','source-debian.zip','verification.json','resource-smoke/resources.json','linux-regression5.log','swanlab-interface.json']:
            z.write(OUT/name,name)
        z.write(ROOT/'docs/results/IMAGE14-DEBIAN-001.md','IMAGE14-DEBIAN-001.md')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    main()
