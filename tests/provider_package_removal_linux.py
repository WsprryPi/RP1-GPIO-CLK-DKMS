#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Native provider removal through the real package guard in a disposable container.

Reuse the lifecycle harness's filesystem-only capabilities, exact package
inputs, representative kernel headers, and forbidden module/service operations.
Only the running-kernel identity is substituted; package validation, ownership,
directory retirement, preflight subprocesses, APT, dpkg, and DKMS all execute.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, '/source/scripts')
sys.path.insert(0, '/source/tests')
import package_lifecycle_linux as lifecycle
import provider_lifecycle as provider
import version_identity


def main():
    output = Path('/results')
    assert output.is_dir() and not any(output.iterdir()), 'fresh external results required'
    lifecycle.setup()  # Checks container, capability, mount, network, and input identities.
    manifest = json.loads(Path('/candidate', provider.MANIFEST_NAME).read_text())
    record = provider.DEFAULT_RECORD
    record.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    assert not record.exists()
    directories = [Path(name) for name in sorted(provider.DIRECTORY_SCOPE)]
    assert all(not path.exists() for path in directories)
    with tempfile.TemporaryDirectory(prefix='rp1-real-removal-') as temporary:
        state = Path(temporary)
        source = state/'source'
        # The read-only Actions checkout belongs to the runner UID, while
        # this package-test container runs as root. Trust only this input Git
        # directory; the cloned checkout must still match the candidate commit.
        subprocess.run(['git', 'config', '--global', '--add', 'safe.directory',
                        '/source/.git'], check=True)
        subprocess.run(['git', 'clone', '--no-local', '/source', str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'remote', 'set-url', 'origin',
                        provider.REPOSITORY_URL], check=True)
        runner = provider.Runner()
        checkout = provider.validate_checkout(str(source), runner)
        assert checkout['commit'] == manifest['sourceCommit']
        package = state/manifest['package']['filename']
        shutil.copyfile(Path('/candidate')/package.name, package)
        package.chmod(0o600)
        resolved = {'channel':'release', 'tag':manifest['releaseTag'],
                    'commit':manifest['sourceCommit'], 'manifest':manifest,
                    'packagePath':str(package), 'checkout':checkout}
        provider.ACTIVE_CREATED_DIRECTORIES = [str(path) for path in directories]
        args = argparse.Namespace(remove='true', record=record, root=Path('/'))
        with mock.patch.object(provider.platform, 'release', return_value=lifecycle.KERNELS[0]):
            # Install genuine earlier RC1, discard its package, and exercise
            # the production replacement coordinator without a rollback cache
            # or network. An editable URL need not retain the old bytes.
            previous_commit = '3cfcf234cb068753a98a04ae6a4b991d20620814'
            previous_state = state/'previous'; previous_state.mkdir(mode=0o700)
            previous_source = previous_state/'source'
            subprocess.run(['git', 'clone', '--no-local', '/source', str(previous_source)], check=True)
            subprocess.run(['git', '-C', str(previous_source), 'remote', 'set-url', 'origin',
                            provider.REPOSITORY_URL], check=True)
            subprocess.run(['git', '-C', str(previous_source), 'checkout', '--detach', previous_commit], check=True)
            previous_assets = previous_state/'assets'
            previous_version, previous_debian = version_identity.from_header(
                (previous_source/'include/rp1_gpclk/version.h').read_text())
            subprocess.run([str(previous_source/'scripts/build-release-candidate'),
                            '--version', previous_version, '--source-commit', previous_commit,
                            '--output', str(previous_assets), '--release'], check=True)
            previous_manifest = json.loads((previous_assets/provider.MANIFEST_NAME).read_text())
            assert previous_manifest['productVersion'] == previous_version
            assert previous_manifest['debianVersion'] == previous_debian
            transition = version_identity.transition(previous_version, previous_debian,
                manifest['productVersion'], manifest['debianVersion'])
            assert transition in ('same', 'replace', 'upgrade'), transition
            same_tag = previous_manifest['releaseTag'] == manifest['releaseTag']
            assert same_tag or transition in ('replace', 'upgrade')
            assert previous_commit != manifest['sourceCommit']
            previous_package = previous_state/previous_manifest['package']['filename']
            shutil.copyfile(previous_assets/previous_package.name, previous_package)
            previous_package.chmod(0o600)
            previous_resolved = {'channel':'release', 'tag':previous_manifest['releaseTag'],
                                 'commit':previous_commit, 'manifest':previous_manifest,
                                 'packagePath':str(previous_package),
                                 'checkout':provider.validate_checkout(str(previous_source), runner)}
            provider.apply_release(previous_state, previous_resolved, record, Path('/'), runner)
            previous_receipt = record.read_bytes()
            previous_package.unlink()
            (previous_assets/previous_package.name).unlink()
            assert not list(record.parent.glob('rp1-provider-migration.*'))
            provider.atomic_json(state/'plan.json', {
                'schema':provider.STATE_SCHEMA, 'providerRepository':provider.REPOSITORY,
                'dryRun':False, 'decision':{'install':True}, 'resolved':resolved,
                'createdDirectories':[str(path) for path in directories]})
            provider.apply(argparse.Namespace(state_dir=state, record=record, root=Path('/')), runner)
            assert json.loads(record.read_bytes())['sourceCommit'] == manifest['sourceCommit']
            retained = list(record.parent.glob('rp1-provider-migration.*/previous-installation.json'))
            assert len(retained) == 1 and retained[0].read_bytes() == previous_receipt
            assert not (retained[0].parent/previous_package.name).exists()
            original = record.read_bytes()
            modules = provider.module_artifacts(Path('/'))
            for path in directories:
                path.mkdir(mode=0o755, parents=True, exist_ok=True)
            manager = Path('/etc/systemd/system/rp1-gpclk-route-manager@.service.d')
            foreign = manager/'administrator.conf'
            foreign.write_bytes(b'foreign administrator data\n')
            try:
                provider.remove_owned_provider(args, runner)
            except provider.ContractError as error:
                assert 'preflight refused' in str(error), str(error)
            else:
                raise AssertionError('nonempty administrator directory was removed')
            assert foreign.read_bytes() == b'foreign administrator data\n'
            assert record.read_bytes() == original
            assert not provider.removal_pending_path(record).exists()
            assert provider.module_artifacts(Path('/')) == modules
            foreign.unlink()  # Only this test's deliberately created fixture.
            # These empty directories model the result of reviewed runtime removal.
            # No preflight, ownership, package-manager, or absence checks are mocked.
            provider.remove_owned_provider(args, runner)
            provider.verify_provider_absent(Path('/'), runner)
            assert not record.exists() and not provider.removal_pending_path(record).exists()
            assert all(not path.exists() for path in directories)
    result = {'status':'PASS', 'sourceCommit':manifest['sourceCommit'],
              'sameTagReplacementWithoutOldPackage':same_tag,
              'versionUpgradeWithoutOldPackage':version_identity.compare(
                  previous_version, manifest['productVersion']) < 0,
              'nativeTransition':transition,
              'predecessorProductVersion':previous_version,
              'predecessorSourceCommit':previous_commit,
              'realPreflight':True, 'nativePackageRemoval':True,
              'nonemptyDirectoryPreserved':True, 'ownershipRecoveredOnRefusal':True,
              'hardwareQualification':False, 'rfQualification':False}
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
