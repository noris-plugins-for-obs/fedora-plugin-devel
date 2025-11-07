#! /usr/bin/env python3
'Build RPM files for my OBS Studio plugins'

import argparse
import bz2
import os.path
import subprocess
import shutil
import tempfile
import textwrap
import datetime

_DOCKER_HOME = '/home/user'
_PACKAGER_NAME = 'Norihiro Kamae <fedora-obs-studio-plugins@nagater.net>'

def _default_version():
    res = subprocess.run(['git', 'describe', '--abbrev=0', '--tags'], capture_output=True, check=True)
    return res.stdout.decode('ascii').strip().strip()

def _prepare_rpmbuild(args):
    os.makedirs(args.rpmbuild, exist_ok=True)
    os.makedirs(args.rpmbuild + '/SPECS', exist_ok=True)
    os.makedirs(args.rpmbuild + '/SOURCES', exist_ok=True)

    _prepare_spec_file(args=args)
    _prepare_sources(args=args)

def _prepare_spec_file(args):
    with open(args.spec, 'r', encoding='ascii') as fr:
        spec = fr.read()

    spec = spec.replace('@VERSION@', args.version)
    spec = spec.replace('@RELEASE@', args.release)

    for line in spec.split('\n'):
        if line[0:5] == 'Name:':
            args.name = line.split()[1]

    if args.message:
        msg = args.message
    elif args.old_rpm:
        msg = f'Update to {args.version}'
    else:
        msg = 'Package using script.'

    changelog_date = datetime.datetime.now().strftime('%a %b %d %Y')
    spec += '\n' + textwrap.dedent(f'''\
            %changelog
            * {changelog_date} {_PACKAGER_NAME} - {args.version}-{args.release}
            - {msg}
    ''')

    if args.old_rpm:
        res = subprocess.run(['rpm', '-q', '--changelog', args.old_rpm],
                             capture_output=True, check=True)
        spec = spec.rstrip() + '\n\n' + res.stdout.decode('utf-8')

    with open(f'{args.rpmbuild}/SPECS/{args.name}.spec', 'w', encoding='ascii') as fw:
        fw.write(spec)

    # TODO: Automatically retreive patch files from the spec file
    for patch in args.patch:
        shutil.copy2(patch, f'{args.rpmbuild}/SOURCES')

def _prepare_sources(args):
    ga = subprocess.run([
        'git', 'archive',
        '--format=tar', f'--prefix={args.name}-{args.version}/',
        'HEAD'
        ], capture_output=True, check=True)
    tar_bz2 = bz2.compress(ga.stdout)
    with open(f'{args.rpmbuild}/SOURCES/{args.name}-{args.version}.tar.bz2', 'wb') as fw:
        fw.write(tar_bz2)

def _build_on_docker(image, args):
    with tempfile.TemporaryDirectory() as tmpdir:

        run_sh = tmpdir + '/run.sh'
        with open(run_sh, 'w', encoding='ascii') as fw:
            fw.write(f'''#! /usr/bin/bash
            sudo dnf install -y git createrepo gpg rpm-sign rpm-build
            sudo dnf builddep -y rpmbuild/SPECS/{args.name}.spec
            rpmbuild -ba rpmbuild/SPECS/{args.name}.spec
            ''')
        os.chmod(run_sh, 0o755)

        cmd = [
                'docker', 'run',
                '-v', tmpdir + ':' + tmpdir,
                '-v', os.path.abspath(args.rpmbuild) + ':' + _DOCKER_HOME + '/rpmbuild',
                '--rm',
                image,
                run_sh
        ]
        subprocess.run(cmd, check=True)

def _build_on_native(args):
    rpmbuild_abs = os.path.abspath(args.rpmbuild)
    subprocess.run([
        'rpmbuild',
        '--define', f'_topdir {rpmbuild_abs}',
        '-ba',
        f'{rpmbuild_abs}/SPECS/{args.name}.spec'
        ], check=True)

def _get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', action='store', default=None)
    parser.add_argument('--patch', action='append', default=[])
    parser.add_argument('--docker-image', action='append', default=[])
    parser.add_argument('--native', action='store_true', default=False)
    parser.add_argument('--rpmbuild', action='store', default=None)
    parser.add_argument('--version', action='store', default=None)
    parser.add_argument('--release', action='store', type=str, default='1')
    parser.add_argument('--message', action='store', type=str, default=None)
    parser.add_argument('--old-rpm', action='store', type=str, default=None)

    args = parser.parse_args()

    if not args.version:
        args.version = _default_version()

    return args

def main():
    'Main routine'
    args = _get_args()

    _prepare_rpmbuild(args=args)
    for image in args.docker_image:
        _build_on_docker(image=image, args=args)

    if args.native:
        _build_on_native(args=args)

if __name__ == '__main__':
    main()
