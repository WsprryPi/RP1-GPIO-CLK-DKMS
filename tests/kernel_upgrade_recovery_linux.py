#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Published v1.0.0 -> kernel update -> current provider, in a restricted container.

Native APT/dpkg/DKMS and filesystem recovery execute. Kernel/boot identity and
systemd observations are fixtures; no host modules, services, GPIO, or RF run.
"""
import argparse
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

sys.dont_write_bytecode = True
sys.path[:0] = ['/source/scripts', '/source/tests']
import package_lifecycle_linux as lifecycle
import provider_lifecycle as provider
import runtime_provider
import runtime_deployment as deployment
import runtime_binding
from version_identity import VERSION, DEBIAN

OLD_COMMIT = 'e17d710499e8c7c630d2eda6adececd7f6b797f5'


class Runner(provider.Runner):
    def run(self, command, **options):
        if len(command) > 2 and command[0] == 'python3' and command[1].endswith('/scripts/runtime_provider.py'):
            output = io.StringIO()
            with mock.patch.object(sys, 'argv', command[1:]), contextlib.redirect_stdout(output):
                code = runtime_provider.main()
            return provider.CommandResult(output.getvalue(), '', code)
        return super().run(command, **options)


def clone(commit, destination):
    subprocess.run(['git', '-c', 'safe.directory=/source/.git', 'clone', '--no-local', '/source', str(destination)], check=True)
    subprocess.run(['git', '-C', str(destination), 'remote', 'set-url', 'origin', provider.REPOSITORY_URL], check=True)
    subprocess.run(['git', '-C', str(destination), 'checkout', '--detach', commit], check=True)


def main():
    output = Path('/results')
    assert output.is_dir() and not any(output.iterdir())
    lifecycle.OLD = Path('/published-100/rp1-gpclk-dkms_1.0.0-1_all.deb')
    lifecycle.setup()  # Refuses network, host system mounts, or hardware capabilities.
    old_kernel, new_kernel = lifecycle.KERNELS
    manifest = json.loads(Path('/candidate', provider.MANIFEST_NAME).read_text())
    previous = json.loads(Path('/published-100', provider.MANIFEST_NAME).read_text())
    assert previous['productVersion'] == '1.0.0' and previous['sourceCommit'] == OLD_COMMIT
    assert provider.sha256_file(lifecycle.OLD) == previous['package']['sha256']
    assert manifest['productVersion'] == VERSION and VERSION != '1.0.0'
    runner = Runner()
    record = provider.DEFAULT_RECORD
    record.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='rp1-kernel-upgrade-') as temporary:
        root = Path(temporary)
        old_source, source = root/'old-source', root/'source'
        clone(OLD_COMMIT, old_source)
        clone(manifest['sourceCommit'], source)
        old_state, state = root/'old-state', root/'state'
        old_state.mkdir(mode=0o700); state.mkdir(mode=0o700)
        old_package = old_state/lifecycle.OLD.name
        shutil.copyfile(lifecycle.OLD, old_package); old_package.chmod(0o600)
        package = state/manifest['package']['filename']
        shutil.copyfile(lifecycle.DEB, package); package.chmod(0o600)
        old_resolved = {'channel': 'release', 'tag': 'v1.0.0', 'commit': OLD_COMMIT,
            'manifest': previous, 'packagePath': str(old_package),
            'checkout': provider.validate_checkout(str(old_source), runner)}
        resolved = {'channel': 'release', 'tag': manifest['releaseTag'], 'commit': manifest['sourceCommit'],
            'manifest': manifest, 'packagePath': str(package),
            'checkout': provider.validate_checkout(str(source), runner)}
        # Install only the initial kernel; then expose the new headers and run
        # native DKMS autoinstall, exactly as a new kernel package does.
        future = Path('/lib/modules', new_kernel)
        shutil.move(str(future), str(root/'future-kernel'))
        with mock.patch.object(provider.platform, 'release', return_value=old_kernel):
            provider.apply_release(old_state, old_resolved, record, Path('/'), runner)
        shutil.move(str(root/'future-kernel'), str(future))
        subprocess.run(['dkms', 'autoinstall', '-k', new_kernel], check=True)
        # A fixed, disabled application companion and systemd adapter model the
        # application/service boundary. Only the listed service operations work.
        companion = Path('/usr/local/lib/wsprrypi/route_application.py')
        companion.parent.mkdir(parents=True, exist_ok=True)
        companion.write_text('import json\nprint(json.dumps({"contract":"wsprrypi-route-application-v1","route":"gpio4","transmit":False,"config":"/usr/local/etc/wsprrypi.ini"}))\n')
        companion.chmod(0o755)
        systemctl = Path('/usr/bin/systemctl')
        systemctl.write_text('''#!/usr/bin/python3
import sys
args=sys.argv[1:]
if args==['daemon-reload']:raise SystemExit(0)
if len(args)==2 and args[0] in ('start','stop') and args[1]=='wsprrypi.service':raise SystemExit(0)
if len(args)>=2 and args[0]=='show':
 unit=args[1]
 if unit not in ('wsprrypi.service','rp1-gpclk-route-manager.socket','rp1-gpclk-route-manager@runtime-inspect.service'):raise SystemExit(98)
 values={'LoadState':'loaded','ActiveState':'inactive','UnitFileState':'disabled' if unit.endswith('.socket') else 'static' if '@' in unit else 'enabled','FragmentPath':'/usr/lib/systemd/system/'+('rp1-gpclk-route-manager@.service' if '@' in unit else unit),'MainPID':'0'}
 fields=[]
 for i,arg in enumerate(args):
  if arg=='-p':fields.extend(args[i+1].split(','))
  elif arg.startswith('--property='):fields.extend(arg.split('=',1)[1].split(','))
 for field in fields:print(values[field] if '--value' in args else field+'='+values[field])
 raise SystemExit(0)
raise SystemExit(99)
''')
        systemctl.chmod(0o755)
        bundle = root/'old-bundle'
        subprocess.run(['python3', '-B', str(old_source/'scripts/build_runtime_bundle.py'),
            '/lib/modules/'+old_kernel+'/updates/dkms', str(bundle),
            '--application-companion', str(companion), '--kernel', old_kernel], check=True)
        binding = runtime_binding.validate_for_removal(json.loads((bundle/'binding.json').read_text()))
        capture = {'version':1,'wasActive':False,'administratorMasked':False,
            'service':{'LoadState':'loaded','ActiveState':'inactive','UnitFileState':'enabled','MainPID':'0'},
            'companion':{'contract':'wsprrypi-route-application-v1','route':'gpio4','transmit':False,'config':'/usr/local/etc/wsprrypi.ini'}}
        values = {path:(bundle/(deployment.admin.digest(path.encode())+'.bin')).read_bytes()
                  for path in deployment.INVENTORY}
        values[deployment.BINDING] = (bundle/'binding.json').read_bytes()
        values.update({path:None for path in deployment.JOURNALS})
        inverse = {'version':1,'application':capture,'previousDeployment':None,'files':{}}
        for path,data in values.items():
            target=Path(path)
            inverse['files'][path]={'before':deployment.encode(target.read_bytes() if target.exists() else None),'after':deployment.encode(data)}
            if data is not None:
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data);target.chmod(0o644)
        deployment.admin.STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
        Path(deployment.LAST_DEPLOYMENT).write_bytes(deployment.journal_bytes(inverse))
        Path(deployment.LAST_DEPLOYMENT).chmod(0o600)
        # Construct exact prior-boot terminal evidence with the old provider's
        # fixture. The incoming provider validates every retained byte/journal.
        evidence = root/'activation.json'
        subprocess.run(['python3','-B','-c', '''import sys,json,pathlib
sys.path[:0]=[sys.argv[1]+'/scripts',sys.argv[1]+'/tests']
import check_runtime_activation as f
import runtime_activation as a
s=f.System(f.captured(False,False));s.binding_value=json.loads(pathlib.Path(sys.argv[2]).read_text());s.raw=pathlib.Path(sys.argv[2]).read_bytes()
s.deployed=json.loads(pathlib.Path(sys.argv[3]).read_text());s.deployment_raw=pathlib.Path(sys.argv[3]).read_bytes()
p=a.activation_plan(s);a.ensure(s,p,a.plan_digest(p),f.lock)
pathlib.Path(sys.argv[4]).write_text(json.dumps(s.journal))
''',str(old_source),str(bundle/'binding.json'),deployment.LAST_DEPLOYMENT,str(evidence)],check=True)
        journal=json.loads(evidence.read_text())
        deployment.admin.STATE.joinpath('activation.json').write_bytes(evidence.read_bytes())
        deployment.admin.STATE.joinpath('activation.json').chmod(0o600)
        owned=json.loads(record.read_text())
        owned['runtime']={'readinessContract':runtime_provider.CONTRACT,
            'bindingSha256':deployment.admin.digest(values[deployment.BINDING]),
            'artifactSetSha256':binding['artifactSetSha256'],'sourceCommit':OLD_COMMIT,
            'productVersion':'1.0.0','targetKernel':old_kernel,
            'compatibilityIdentities':binding['compatibilityIdentities'],
            'deploymentPlanSha256':deployment.plan_hash(inverse),
            'activationPlanSha256':journal['planSha256'],'activationRequestId':journal['requestId'],
            'controllerSession':journal['controller']['session'],'controllerGeneration':0,
            'state':'neutral_ready','route':None,'output':'disabled'}
        provider.atomic_json(record,owned)
        provider.atomic_json(state/'plan.json',{'schema':provider.STATE_SCHEMA,
            'providerRepository':provider.REPOSITORY,'dryRun':False,'decision':{'install':True},
            'resolved':resolved,'createdDirectories':[]})
        uname=os.uname(); updated=os.uname_result((uname.sysname,uname.nodename,new_kernel,uname.version,uname.machine))
        with mock.patch.object(provider.platform,'release',return_value=new_kernel), mock.patch.object(os,'uname',return_value=updated):
            args=argparse.Namespace(command='prepare-runtime-update',state_dir=state,record=record,root=Path('/'))
            provider.prepare_runtime_update(args,runner)
            assert 'runtime' not in json.loads(record.read_text())
            assert runtime_provider.UpdatePreparationHost().update_absent()
            provider.apply(argparse.Namespace(state_dir=state,record=record,root=Path('/')),runner)
            current=json.loads(record.read_text())
            assert current['sourceCommit']==manifest['sourceCommit'] and current['tag']==manifest['releaseTag']
            state_before=lifecycle.snapshot()
            assert all(m['version']==VERSION for m in state_before['modules'])
            assert 'rp1-gpclk-dkms/1.0.0' not in state_before['dkms']
            provider.apply(argparse.Namespace(state_dir=state,record=record,root=Path('/')),runner)
            assert lifecycle.snapshot()['modules']==state_before['modules']
        lifecycle.neutral()
        result={'status':'PASS','predecessor':'1.0.0','successor':VERSION,
            'predecessorSource':OLD_COMMIT,'candidateSource':manifest['sourceCommit'],
            'oldKernel':old_kernel,'newKernel':new_kernel,'nativeDkmsAutoinstall':True,
            'runtimeRemovedThroughNormalUpgrade':True,'idempotentRepeat':True,
            'transmissionAuthorized':False,'kernelBootAndSystemdAreFixtures':True,
            'hardwareQualification':False,'rfQualification':False}
        (output/'kernel-upgrade-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))


if __name__=='__main__': main()
