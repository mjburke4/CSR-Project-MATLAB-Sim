#!/usr/bin/env python3
"""Audit the fresh, unchanged native control build and repeat the T9 ACK contract."""
import csv
import hashlib
import importlib.util
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent / 'csr11'
ENGINE = ROOT / 'engine'
SOURCE = ROOT / 'ns'
BUILD = ENGINE / 'build'
OUT = ROOT / 'smoke'
ENV = os.environ.copy()
ENV['PYTHONPATH'] = str(ROOT/'tools') + os.pathsep + ENV.get('PYTHONPATH', '')
ENV['PATH'] = str(ROOT/'tools/bin') + os.pathsep + ENV['PATH']

def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def dump(path, obj):
    pathlib.Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')

def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()

def run(command, name):
    start = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, env=ENV)
    log = OUT / (name + '.log')
    log.write_text(result.stdout + result.stderr)
    record = dict(command=command, exit_code=result.returncode,
                  elapsed_seconds=time.monotonic()-start,
                  log=str(log.relative_to(ROOT)), log_sha256=digest(log),
                  output_captured_after_process_closed=True)
    dump(OUT / (name + '.json'), record)
    if result.returncode:
        raise RuntimeError(f'{name} failed, see {log}')
    return record

def main():
    OUT.mkdir(exist_ok=True)
    assert git(SOURCE, 'rev-parse', 'HEAD') == '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
    assert git(ENGINE, 'rev-parse', 'HEAD') == '6b5cd24ea80713ce16d88575869aedd6f432bdae'
    assert not git(SOURCE, 'status', '--porcelain', '--untracked-files=no')
    assert not git(ENGINE, 'status', '--porcelain', '--untracked-files=no')
    module = json.loads((ROOT/'module-copy.json').read_text())
    for row in module['files']:
        assert digest(SOURCE/row['path']) == row['sha256']
        assert digest(ENGINE/'contrib/csr'/row['path']) == row['sha256']
    for stem in ['build', 'configure']:
        record = json.loads((ROOT/(stem+'.json')).read_text())
        assert record['exit_code'] == 0
        record['log_sha256'] = digest(ROOT/(stem+'.log'))
        dump(ROOT/(stem+'.json'), record)
    spec = importlib.util.spec_from_file_location('base', REPO/'scripts/run_tranche4_ns3_reference.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    if not (OUT/'pending.json').exists():
        run([str(ROOT/'tools/bin/cmake'), '--build', str(ENGINE/'cmake-cache'),
             '--parallel', '4', '--target', *base.MODULES], 'pending')
    base.check_source(SOURCE, BUILD)
    before = base.input_snapshot(SOURCE, BUILD)
    contract = REPO/'scripts/ns3/tranche9_ack_contract.cc'
    binary = OUT/'ack-contract'
    command = base.compile_runner(SOURCE, BUILD, binary, '/usr/bin/g++')
    command[command.index(str(SOURCE/'csr-opnet-scenario-runner.cc'))] = str(contract)
    compile_record = run(command, 'compile')
    run_record = run([str(binary), str(OUT/'checkpoints.csv')], 'run')
    assert before == base.input_snapshot(SOURCE, BUILD)
    reference = REPO/'evidence/tranche-9-contract-reference/checkpoints.csv'
    assert (OUT/'checkpoints.csv').read_bytes() == reference.read_bytes()
    with (OUT/'checkpoints.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 101 and len({r['case'] for r in rows}) == 6
    assert all(r['pass'] == '1' for r in rows)
    linked = run(['ldd', str(binary)], 'linked-libraries')
    assert 'not found' not in (OUT/'linked-libraries.log').read_text()
    # Retain the successful follow-up build with stdout written only after exit.
    # The first build returned success but the workspace retained only its log
    # prefix. The follow-up rebuilt 225 steps; it is not a no-work assertion.
    pending = json.loads((OUT/'pending.json').read_text())
    assert pending['exit_code'] == 0
    assert pending['log_sha256'] == digest(OUT/'pending.log')
    pending['nothing_pending_claimed'] = False
    pending['reason'] = ('The first build succeeded but retained only a stdout prefix. '
                         'This follow-up build completed with stdout captured after process exit; '
                         'the ACK smoke was then repeated against these libraries.')
    toolchain = {}
    for name, command in {
        'compiler': ['/usr/bin/g++', '--version'],
        'linker': ['/usr/bin/ld', '--version'],
        'cmake': [str(ROOT/'tools/bin/cmake'), '--version'],
        'ninja': [str(ROOT/'tools/bin/ninja'), '--version'],
        'python': [sys.executable, '--version'],
    }.items():
        toolchain[name] = dict(command=command, executable=str(pathlib.Path(command[0]).resolve()),
                               sha256=digest(pathlib.Path(command[0]).resolve()),
                               version=subprocess.check_output(command, text=True, env=ENV).strip())
    libraries = [dict(path=str(BUILD/'lib'/f'libns3-dev-{n}-debug.so'),
                      sha256=digest(BUILD/'lib'/f'libns3-dev-{n}-debug.so'),
                      bytes=(BUILD/'lib'/f'libns3-dev-{n}-debug.so').stat().st_size) for n in base.MODULES]
    manifest = dict(
        schema='csr-tranche11-native-control-build-v1', status='passed',
        generated_utc=datetime.now(timezone.utc).isoformat(),
        source_commit=git(SOURCE, 'rev-parse', 'HEAD'), source_tree=git(SOURCE, 'rev-parse', 'HEAD^{tree}'),
        engine_commit=git(ENGINE, 'rev-parse', 'HEAD'), engine_tree=git(ENGINE, 'rev-parse', 'HEAD^{tree}'),
        source_repository='https://github.com/mjburke4/CSR-Project-NS3-part2.git',
        engine_repository='https://github.com/nsnam/ns-3-dev-git.git',
        engine_rebuilt=True, reused_historical_libraries=False,
        historical_libraries_byte_identity_claimed=False,
        csr_tracked_sources_unchanged=True, engine_tracked_sources_unchanged=True,
        module_files_verified=len(module['files']), source_path=str(SOURCE), build_path=str(BUILD),
        build_profile='Debug', cpp_standard=23, assertions=True, logging=True,
        enabled_modules=list(base.MODULES), toolchain=toolchain, platform=platform.platform(),
        fetch_records={n:json.loads((ROOT/(n+'-fetch.json')).read_text()) for n in ['ns','engine']},
        configure_record=json.loads((ROOT/'configure.json').read_text()),
        initial_build_record={**json.loads((ROOT/'build.json').read_text()),
                              'retained_stdout_complete':False},
        build_record=pending, libraries=libraries,
        cmake_cache_sha256=digest(ENGINE/'cmake-cache/CMakeCache.txt'),
        smoke_contract=dict(source=str(contract), source_sha256=digest(contract),
                            compile=compile_record, run=run_record, checkpoint_count=101,
                            case_count=6, checkpoint_sha256=digest(OUT/'checkpoints.csv'),
                            historical_reference_sha256=digest(reference), historical_reference_bytes_equal=True,
                            binary_sha256=digest(binary), inputs_unchanged=True),
        matlab_executed=False, full_engine_test_suite_executed=False, historical_benchmarks_rerun=False,
        scope='Fresh unmodified nine-module native control build plus unchanged six-case ACK contract. Separate T11 fixture instrumentation and test execution are not included in this record.',
        input_sha256=before, artifacts=[])
    target = REPO/'evidence/tranche-11-native-build'
    target.mkdir(exist_ok=True)
    for path in [*sorted(ROOT.glob('*.py')), *sorted(ROOT.glob('*.md')), *sorted(ROOT.glob('*.json')), *sorted(ROOT.glob('*.log')), *sorted(OUT.iterdir())]:
        if path.is_file() and path.name != 'manifest.json':
            rel = path.relative_to(ROOT)
            dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
            manifest['artifacts'].append(dict(path=rel.as_posix(), sha256=digest(path), bytes=path.stat().st_size))
    dump(target/'manifest.json', manifest)
    dump(REPO/'evidence/tranche-11-native-build.json', manifest)
    print(json.dumps(dict(status='passed', libraries=len(libraries), checkpoints=len(rows),
                          source_path=str(SOURCE), build_path=str(BUILD), record=str(target/'manifest.json'))))

if __name__ == '__main__':
    main()
