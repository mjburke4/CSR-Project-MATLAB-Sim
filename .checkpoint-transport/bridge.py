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
import sys
import urllib.error
import urllib.request

REPOSITORY = 'mjburke4/CSR-Project-MATLAB-Sim'
BRANCH = 'agent/t15-t21-checkpoint'
BASE_COMMIT = 'ec829f04f4ab8c8af4f6e9a53e07c1273cab2590'
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

    def create_blob(self, data, expected):
        result = self.request('POST', 'git/blobs', {
            'encoding': 'base64', 'content': base64.b64encode(data).decode('ascii')})
        require(result.get('sha') == expected, 'Created Git blob SHA mismatch')
        return result['sha']

    def head(self):
        result = self.request('GET', 'git/ref/heads/' + BRANCH)
        require(result.get('ref') == 'refs/heads/' + BRANCH, 'Unexpected branch response')
        return result['object']['sha']


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
    require([p['sha'] for p in commit.get('parents', [])] == [BASE_COMMIT], 'Staging parent is not the approved main checkpoint')
    manifest_bytes = api.blob(manifest_sha, 256 * 1024)
    require(digest(manifest_bytes) == manifest_digest, 'Manifest SHA-256 mismatch')
    manifest = json.loads(manifest_bytes)
    records = validate_manifest(manifest)
    receipts = []
    for record in records:
        require(api.head() == staging_head, 'Checkpoint branch advanced during upload')
        original = reconstruct(record, lambda chunk: api.blob(chunk['sha'], CHUNK_BYTES))
        sha = api.create_blob(original, record['sha'])
        receipts.append({k: record[k] for k in ('path', 'bytes', 'sha', 'sha256')})
        print(json.dumps({'verified_blob': record['path'], 'bytes': len(original), 'sha': sha}), flush=True)
        del original
    status = {
        'schema': 'csr-checkpoint-oversized-blob-transport-status-v1', 'passed': True,
        'repository': REPOSITORY, 'branch': BRANCH, 'base_commit': BASE_COMMIT,
        'staging_commit': staging_head, 'transport_manifest_sha256': manifest_digest,
        'verified_blobs': receipts, 'production_simulations_executed': 0,
        'main_modified': False}
    status_bytes = compact_json(status) + b'\n'
    status_sha = api.create_blob(status_bytes, git_blob_sha(status_bytes))
    entries = [{'path': r['path'], 'mode': '100644', 'type': 'blob', 'sha': r['sha']} for r in receipts]
    entries.append({'path': STATUS_PATH, 'mode': '100644', 'type': 'blob', 'sha': status_sha})
    tree = api.request('POST', 'git/trees', {'base_tree': commit['tree']['sha'], 'tree': entries})
    require(re.fullmatch('[0-9a-f]{40}', tree.get('sha', '')) is not None, 'Invalid new tree SHA')
    new_commit = api.request('POST', 'git/commits', {
        'message': 'Stage verified oversized Tranches 15–21 checkpoint blobs',
        'tree': tree['sha'], 'parents': [staging_head]})
    require(re.fullmatch('[0-9a-f]{40}', new_commit.get('sha', '')) is not None, 'Invalid new commit SHA')
    require(api.head() == staging_head, 'Checkpoint branch advanced before attachment')
    updated = api.request('PATCH', 'git/refs/heads/' + BRANCH, {'sha': new_commit['sha'], 'force': False})
    require(updated.get('ref') == 'refs/heads/' + BRANCH and updated['object']['sha'] == new_commit['sha'], 'Wrong updated ref')
    require(api.head() == new_commit['sha'], 'Final branch verification failed')
    print(json.dumps({'passed': True, 'branch': BRANCH, 'commit': new_commit['sha'], 'tree': tree['sha'], 'blobs': len(receipts)}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BridgeError as exc:
        print('Checkpoint transport failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
