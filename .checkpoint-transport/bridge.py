#!/usr/bin/env python3
"""Publish exact oversized checkpoint blobs from same-repository chunks.

Executed only by the temporary, pinned checkpoint-branch workflow. No shell,
external URL, checkout action, archive extraction, main-branch write, or secret
output is used. Standard-library implementation; all remote mutations are
sequential. See README for the REST fast-forward concurrency guarantee.
"""
import base64
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

REPOSITORY = 'mjburke4/CSR-Project-MATLAB-Sim'
BRANCH = 'agent/t15-t21-checkpoint'
BASE_COMMIT = 'ec829f04f4ab8c8af4f6e9a53e07c1273cab2590'
STAGING_PARENT = 'fca38e97ab2a2758f3c2f1fc1119ecd56fcd24bb'
REMOTE_URL = 'https://github.com/mjburke4/CSR-Project-MATLAB-Sim.git'
CHUNK_BYTES = 8 * 1024 * 1024
STATUS_PATH = '.checkpoint-transport/status.json'
EXPECTED = {'evidence/t16/owner.zip': {'bytes': 23215583,
                            'sha': 'db0a587434b2324bd1931351331fc0bdacb1b169',
                            'sha256': '4fbfb17ba654bee0a137f1fc2d3ac3f65a091bf936d6c44589b1db9db1f4be60'},
 'evidence/t17/owner.zip': {'bytes': 15449392,
                            'sha': '3b8cfdde66684699c2d35dc0f2d53dc3e4a56e77',
                            'sha256': '19921afa83c57db2779e4302e5b39afef5120afb129a87fddb1f6d1bdbec2bd1'},
 'evidence/t18/owner.zip': {'bytes': 19931065,
                            'sha': '16ec34a2fadff2a6e68af4e3dbabbd0326949f3a',
                            'sha256': '85d63854fff84e8aaf62b5c9814603cbc277cffa6c67c648ba3892d90107965d'},
 'evidence/t18/review.json': {'bytes': 74024793,
                              'sha': '0112b1bbff35ca544395d0151429f091ef245c3c',
                              'sha256': '8843564d80a30ff55b4989c5481c223fb63dab14b6d9356d0a57533def82e61b'},
 'evidence/t19/owner.zip': {'bytes': 30906014,
                            'sha': '5c45398767124acbd048d7527cda1409ca7af62f',
                            'sha256': '525758669b8f84fa5dada46e293b8482980ef389efc5408ff056aac0e804ee30'},
 'evidence/t20/owner.zip': {'bytes': 31229812,
                            'sha': '6ae536f332ca2ae067d1b2287dfd4e94f237412b',
                            'sha256': '41ee42fd72d3246b005cffa6eb0731aef1f465ac19747be82feb481571a72861'},
 'evidence/t20/review.zip': {'bytes': 38609993,
                             'sha': 'b916839fb786050a4036010780ec2b4acf691465',
                             'sha256': '6862eed78a45a505dfb8e2b570970d5e86a71a195ee7cd848235a00205deeda8'},
 'evidence/tranche-18-ns3-reference/p128/ns3-service.csv.gz': {'bytes': 12869678,
                                                               'sha': 'a2a1fefb336a1f6edeed0e145e69a2f6dad33b10',
                                                               'sha256': 'feace5f105d5c4e6d076867a8c858f3e99d7868c21dcb849f68855cef2764086'},
 'evidence/tranche-20-ns3-reference/s129/ns3-trace.csv.gz': {'bytes': 66208697,
                                                             'sha': 'ec3d34796659ec9ab9d1fd2bdc61e8ef0373d2d2',
                                                             'sha256': 'aa4ae4e40309ef956d5e89d20040828c3fab47062747eaa51a637506764c2643'},
 'evidence/tranche-20-ns3-reference/s130/ns3-trace.csv.gz': {'bytes': 77193119,
                                                             'sha': '0f1f5e5e2832628e05386590baca378c3d3f9103',
                                                             'sha256': '404b719dcb8c2762cb60a2f60eb2489b0b5c41f198baa25b3fe93630c1b07930'}}


class BridgeError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise BridgeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


def compact_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def validate_manifest(manifest):
    require(manifest.get('schema') == 'csr-checkpoint-oversized-blob-transport-v1', 'Wrong manifest schema')
    require(manifest.get('repository') == REPOSITORY, 'Wrong repository')
    require(manifest.get('branch') == BRANCH, 'Wrong branch')
    require(manifest.get('base_commit') == BASE_COMMIT, 'Wrong base commit')
    records = manifest.get('files')
    require(isinstance(records, list) and len(records) == len(EXPECTED), 'Wrong approved blob count')
    require({r.get('path') for r in records} == set(EXPECTED), 'Unexpected target paths')
    chunk_paths = set()
    for record in records:
        require(all(record.get(k) == v for k, v in EXPECTED[record['path']].items()), 'Unapproved target identity')
        require(record.get('transport_encoding') in ('raw', 'gzip'), 'Unsupported transport encoding')
        require(isinstance(record.get('transport_bytes'), int) and 0 < record['transport_bytes'] <= record['bytes'], 'Invalid transport size')
        require(re.fullmatch('[0-9a-f]{64}', record.get('transport_sha256', '')) is not None, 'Invalid transport digest')
        chunks = record.get('chunks')
        require(isinstance(chunks, list) and 0 < len(chunks) <= 10, 'Invalid chunk count')
        require(sum(c.get('bytes', -1) for c in chunks) == record['transport_bytes'], 'Chunk sizes do not sum')
        for index, chunk in enumerate(chunks):
            require(chunk.get('index') == index, 'Chunks are not ordered')
            require(isinstance(chunk.get('bytes'), int) and 0 < chunk['bytes'] <= CHUNK_BYTES, 'Invalid chunk size')
            require(index == len(chunks) - 1 or chunk['bytes'] == CHUNK_BYTES, 'Short nonfinal chunk')
            require(re.fullmatch('[0-9a-f]{40}', chunk.get('sha', '')) is not None, 'Invalid chunk Git SHA')
            require(re.fullmatch('[0-9a-f]{64}', chunk.get('sha256', '')) is not None, 'Invalid chunk SHA-256')
            path = chunk.get('path', '')
            require(re.fullmatch(r'\.checkpoint-transport/chunks/[0-9a-f]{40}/[0-9]{3}\.bin', path) is not None, 'Invalid chunk path')
            require(path not in chunk_paths, 'Duplicate chunk path')
            chunk_paths.add(path)
    return records


def reconstruct(record, read_chunk):
    parts = []
    for chunk in record['chunks']:
        data = read_chunk(chunk)
        require(len(data) == chunk['bytes'], 'Chunk byte size mismatch')
        require(digest(data) == chunk['sha256'], 'Chunk SHA-256 mismatch')
        require(git_blob_sha(data) == chunk['sha'], 'Chunk Git SHA mismatch')
        parts.append(data)
    transported = b''.join(parts)
    require(len(transported) == record['transport_bytes'], 'Transport byte size mismatch')
    require(digest(transported) == record['transport_sha256'], 'Transport SHA-256 mismatch')
    if record['transport_encoding'] == 'gzip':
        with gzip.GzipFile(fileobj=io.BytesIO(transported)) as stream:
            data = stream.read(record['bytes'] + 1)
            require(len(data) == record['bytes'] and stream.read(1) == b'', 'Inflated byte size mismatch')
    else:
        data = transported
    require(len(data) == record['bytes'], 'Original byte size mismatch')
    require(digest(data) == record['sha256'], 'Original SHA-256 mismatch')
    require(git_blob_sha(data) == record['sha'], 'Original Git SHA mismatch')
    return data


class GitHub:
    def __init__(self, token):
        require(bool(token), 'Missing job token')
        self.token = token

    def request(self, method, suffix, payload=None):
        require(method == 'GET' and payload is None, 'Bridge REST access is read-only')
        require(suffix.startswith('git/'), 'Unexpected API path')
        url = f'https://api.github.com/repos/{REPOSITORY}/{suffix}'
        data = None if payload is None else compact_json(payload)
        request = urllib.request.Request(url, data=data, method=method, headers={
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'CSR-checkpoint-bounded-transport',
            'Content-Type': 'application/json'})
        # The API endpoint and request suffix are controlled in this script.
        # Disable redirects to avoid forwarding the job token to another host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=180) as response:
                require(response.status in (200, 201), 'Unexpected API success status')
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise BridgeError(f'GitHub HTTP {exc.code} during {method} {suffix.split("/")[0:2]}') from None
        except (urllib.error.URLError, TimeoutError):
            raise BridgeError(f'GitHub transport error during {method}') from None

    def blob(self, sha, maximum):
        result = self.request('GET', 'git/blobs/' + sha)
        require(result.get('sha') == sha and result.get('encoding') == 'base64', 'Unexpected blob response')
        require(isinstance(result.get('size'), int) and 0 <= result['size'] <= maximum, 'Blob response too large')
        encoded = ''.join(result.get('content', '').split())
        require(len(encoded) <= 4 * ((maximum + 2) // 3), 'Encoded response too large')
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise BridgeError('Invalid blob base64') from None
        require(len(data) == result['size'] and git_blob_sha(data) == sha, 'Downloaded Git blob mismatch')
        return data

    def head(self):
        result = self.request('GET', 'git/ref/heads/' + BRANCH)
        require(result.get('ref') == 'refs/heads/' + BRANCH, 'Unexpected branch response')
        return result['object']['sha']


class NativeGit:
    """Write exact Git objects and push one child commit using the normal job token."""
    def __init__(self, token, staging_head):
        self.temp = tempfile.TemporaryDirectory(prefix='csr-checkpoint-git-')
        self.directory = self.temp.name
        # No credential is written to config, argv, URL, filesystem, or output.
        # Remove inherited Git tracing/config variables before installing this
        # one fixed authentication context for the child Git processes.
        self.environment = {k: v for k, v in os.environ.items()
                            if not k.startswith('GIT_') and k != 'GH_TOKEN'}
        self.environment.update({
            'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_CONFIG_SYSTEM': os.devnull,
            'GIT_AUTHOR_NAME': 'github-actions[bot]',
            'GIT_AUTHOR_EMAIL': '41898282+github-actions[bot]@users.noreply.github.com',
            'GIT_COMMITTER_NAME': 'github-actions[bot]',
            'GIT_COMMITTER_EMAIL': '41898282+github-actions[bot]@users.noreply.github.com'})
        header = 'AUTHORIZATION: basic ' + base64.b64encode(('x-access-token:' + token).encode()).decode()
        settings = [('http.' + REMOTE_URL + '.extraheader', header),
                    ('http.followRedirects', 'false'), ('credential.helper', ''),
                    ('core.hooksPath', os.devnull), ('gc.auto', '0'),
                    ('commit.gpgSign', 'false')]
        self.environment['GIT_CONFIG_COUNT'] = str(len(settings))
        for index, (key, value) in enumerate(settings):
            self.environment[f'GIT_CONFIG_KEY_{index}'] = key
            self.environment[f'GIT_CONFIG_VALUE_{index}'] = value
        self.run(['init', '--bare', self.directory], 'initialize temporary object store')
        self.run(['remote', 'add', 'origin', REMOTE_URL], 'set fixed repository remote')
        self.run(['config', 'remote.origin.promisor', 'true'], 'set partial-fetch metadata')
        self.run(['config', 'remote.origin.partialclonefilter', 'blob:none'], 'set partial-fetch filter')
        self.run(['fetch', '--no-tags', '--depth=1', '--filter=blob:none', 'origin',
                  'refs/heads/' + BRANCH], 'fetch checkpoint parent', timeout=400)
        require(self.run(['rev-parse', 'FETCH_HEAD'], 'verify fetched checkpoint') == staging_head,
                'Git fetched a different checkpoint head')
        self.run(['read-tree', 'FETCH_HEAD^{tree}'], 'initialize checkpoint index')

    def run(self, arguments, label, data=None, timeout=180):
        try:
            result = subprocess.run(['git', '-C', self.directory, *arguments], input=data,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    env=self.environment, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise BridgeError('Native Git failed to ' + label) from None
        # Never include raw stderr, Git configuration, or environment in errors.
        require(result.returncode == 0, 'Native Git failed to ' + label)
        return result.stdout.decode('utf-8', errors='strict').strip()

    def add_blob(self, path, data, expected_sha):
        require(path in EXPECTED or path == STATUS_PATH, 'Unapproved native Git target path')
        sha = self.run(['hash-object', '-w', '--stdin'], 'write a verified blob', data)
        require(sha == expected_sha, 'Native Git blob SHA mismatch')
        self.run(['update-index', '--add', '--cacheinfo', '100644,' + sha + ',' + path],
                 'attach verified blob to checkpoint index')
        return sha

    def attach(self, api, staging_head):
        # Existing promisor blobs are already on the remote parent. The ten new
        # blobs and status were locally written and individually hash-verified.
        tree = self.run(['write-tree', '--missing-ok'], 'write checkpoint tree')
        require(re.fullmatch('[0-9a-f]{40}', tree) is not None, 'Invalid native Git tree SHA')
        commit = self.run(['commit-tree', tree, '-p', staging_head], 'write checkpoint commit',
                          b'Stage verified oversized Tranches 15-21 checkpoint blobs\n')
        require(re.fullmatch('[0-9a-f]{40}', commit) is not None, 'Invalid native Git commit SHA')
        require(api.head() == staging_head, 'Checkpoint branch advanced before native Git push')
        advertised = self.run(['ls-remote', '--refs', 'origin', 'refs/heads/' + BRANCH],
                              'verify remote checkpoint immediately before push')
        require(advertised == staging_head + '\trefs/heads/' + BRANCH, 'Remote checkpoint head changed')
        # Explicit single-branch refspec. No --force, leading +, wildcard, tag,
        # main ref, credential in URL, or shell evaluation is used.
        self.run(['push', '--porcelain', 'origin', commit + ':refs/heads/' + BRANCH],
                 'push checkpoint child commit', timeout=400)
        require(api.head() == commit, 'Native Git branch verification failed')
        remote = api.request('GET', 'git/commits/' + commit)
        require(remote.get('sha') == commit and remote['tree']['sha'] == tree and
                [p['sha'] for p in remote.get('parents', [])] == [staging_head],
                'Native Git remote commit identity mismatch')
        return commit, tree

    def close(self):
        self.environment.clear()
        self.temp.cleanup()


def main():
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'Wrong execution repository')
    require(os.environ.get('GITHUB_REF') == 'refs/heads/' + BRANCH, 'Wrong execution branch')
    require(os.environ.get('GITHUB_EVENT_NAME') == 'push', 'Wrong execution event')
    staging_head = os.environ.get('GITHUB_SHA', '')
    require(re.fullmatch('[0-9a-f]{40}', staging_head) is not None, 'Invalid staging SHA')
    manifest_sha = os.environ.get('TRANSPORT_MANIFEST_GIT_SHA', '')
    manifest_digest = os.environ.get('TRANSPORT_MANIFEST_SHA256', '')
    require(re.fullmatch('[0-9a-f]{40}', manifest_sha) is not None, 'Invalid manifest Git SHA')
    require(re.fullmatch('[0-9a-f]{64}', manifest_digest) is not None, 'Invalid manifest SHA-256')
    api = GitHub(os.environ.get('GH_TOKEN'))
    require(api.head() == staging_head, 'Checkpoint branch advanced before job started')
    commit = api.request('GET', 'git/commits/' + staging_head)
    require(commit.get('sha') == staging_head, 'Wrong staging commit')
    require([p['sha'] for p in commit.get('parents', [])] == [STAGING_PARENT], 'Staging parent is not the approved transport repair parent')
    prior = api.request('GET', 'git/commits/' + STAGING_PARENT)
    require(prior.get('sha') == STAGING_PARENT and [p['sha'] for p in prior.get('parents', [])] == [BASE_COMMIT],
            'Transport repair parent does not descend directly from the approved main checkpoint')
    manifest_bytes = api.blob(manifest_sha, 256 * 1024)
    require(digest(manifest_bytes) == manifest_digest, 'Manifest SHA-256 mismatch')
    manifest = json.loads(manifest_bytes)
    records = validate_manifest(manifest)
    native = NativeGit(os.environ['GH_TOKEN'], staging_head)
    try:
        receipts = []
        for record in records:
            require(api.head() == staging_head, 'Checkpoint branch advanced during upload')
            original = reconstruct(record, lambda chunk: api.blob(chunk['sha'], CHUNK_BYTES))
            sha = native.add_blob(record['path'], original, record['sha'])
            receipts.append({k: record[k] for k in ('path', 'bytes', 'sha', 'sha256')})
            print(json.dumps({'verified_blob': record['path'], 'bytes': len(original), 'sha': sha}), flush=True)
            del original
        status = {
            'schema': 'csr-checkpoint-oversized-blob-transport-status-v1', 'passed': True,
            'repository': REPOSITORY, 'branch': BRANCH, 'base_commit': BASE_COMMIT,
            'staging_parent': STAGING_PARENT, 'staging_commit': staging_head,
            'transport_manifest_sha256': manifest_digest, 'transport_method': 'git_https_pack',
            'verified_blobs': receipts, 'production_simulations_executed': 0,
            'main_modified': False}
        status_bytes = compact_json(status) + b'\n'
        native.add_blob(STATUS_PATH, status_bytes, git_blob_sha(status_bytes))
        new_commit, tree = native.attach(api, staging_head)
        print(json.dumps({'passed': True, 'branch': BRANCH, 'commit': new_commit,
                          'tree': tree, 'blobs': len(receipts), 'transport_method': 'git_https_pack'}), flush=True)
    finally:
        native.close()


if __name__ == '__main__':
    try:
        main()
    except BridgeError as exc:
        print('Checkpoint transport failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
