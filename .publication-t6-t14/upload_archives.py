#!/usr/bin/env python3
"""Verify and create exactly three authorized evidence archive Git blobs.

This temporary transport helper never creates or changes Git refs, commits,
trees, pull requests, repository settings, or permissions. The default mode
verifies local bytes only; --upload is restricted to the authorized push event.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.request


REPOSITORY = "mjburke4/CSR-Project-MATLAB-Sim"
BRANCH = "agent/t6-t14-checkpoint"
REF = "refs/heads/" + BRANCH
MARKER = "T6_T14_TRANSPORT_READY"
ENDPOINT = "https://api.github.com/repos/" + REPOSITORY + "/git/blobs"
PART_BYTES = 8 * 1024 * 1024
TRANSPORT = ".publication-t6-t14"
ARCHIVES = {
    "t8": {
        "repository_path": "evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip",
        "bytes": 17925128,
        "sha256": "bfc4f7f05f0800316b371df3ec316f309f14e3482ef259c3f9c7bd7eea025d77",
        "git_blob_sha": "26e0e3c30f085b3b7a3fa62f24304ffcc8ce51b2",
    },
    "t7": {
        "repository_path": "evidence/tranche-7-r2025a-accepted/tranche7_evidence.zip",
        "bytes": 23627006,
        "sha256": "ea39b86ef68f91a551e4e22d176e2e96dc5305f33673741eee0adc6039599655",
        "git_blob_sha": "29cedae53292f2479872c6d5e6262c59171af5c3",
    },
    "t10": {
        "repository_path": "evidence/tranche-10-r2025a-accepted/tranche10_evidence.zip",
        "bytes": 28810179,
        "sha256": "066c180f31c44412b617e1cc0f6197711ac50daaac9cbbbcbefbc6a59f1916f8",
        "git_blob_sha": "3ccac99c10e2b7a5e209923cf0e4ab61bd76692e",
    },
}


def require(condition, message):
    if not condition:
        raise SystemExit("Archive transport stopped: " + message)


def reconstruct_all(manifest, root, output_dir):
    require(manifest.get("schema") == "csr-t6-t14-archive-transport-v1",
            "manifest schema differs")
    require(manifest.get("repository") == REPOSITORY, "manifest repository differs")
    require(manifest.get("branch") == BRANCH, "manifest branch differs")
    archives = manifest.get("archives", [])
    require(len(archives) == len(ARCHIVES), "unexpected archive count")
    require({archive.get("key") for archive in archives} == set(ARCHIVES),
            "unexpected archive keys")
    outputs = []
    for archive in archives:
        key = archive["key"]
        expected = ARCHIVES[key]
        for field, value in expected.items():
            require(archive.get(field) == value, key + ": metadata differs: " + field)
        part_count = (expected["bytes"] + PART_BYTES - 1) // PART_BYTES
        parts = archive.get("parts", [])
        require(len(parts) == part_count, key + ": unexpected part count")
        sha256 = hashlib.sha256()
        git_sha1 = hashlib.sha1(f'blob {expected["bytes"]}\0'.encode("ascii"))
        output = output_dir / (key + ".zip")
        total = 0
        with output.open("wb") as assembled:
            for index, part in enumerate(parts):
                relative = f"{TRANSPORT}/parts/{key}/part-{index:03d}.bin"
                require(part.get("path") == relative, key + ": unexpected part path")
                path = root / relative
                require(path.is_file() and not path.is_symlink()
                        and path.resolve().is_relative_to(root.resolve()),
                        "part is missing or points outside checkout: " + relative)
                data = path.read_bytes()
                expected_size = min(PART_BYTES, expected["bytes"] - PART_BYTES * index)
                require(len(data) == part.get("bytes") == expected_size,
                        "part size differs: " + relative)
                require(hashlib.sha256(data).hexdigest() == part.get("sha256"),
                        "part SHA256 differs: " + relative)
                assembled.write(data)
                sha256.update(data)
                git_sha1.update(data)
                total += len(data)
        require(total == expected["bytes"], key + ": assembled size differs")
        require(sha256.hexdigest() == expected["sha256"], key + ": assembled SHA256 differs")
        require(git_sha1.hexdigest() == expected["git_blob_sha"],
                key + ": assembled Git blob SHA differs")
        outputs.append((key, output))
        print("Verified " + expected["repository_path"] + " (" + str(total) + " bytes)", flush=True)
    return outputs


def verify_upload_context(root):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "not a GitHub Actions run")
    require(os.environ.get("GITHUB_EVENT_NAME") == "push", "not a push event")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY,
            "event repository differs")
    require(os.environ.get("GITHUB_REF") == REF, "event branch differs")
    sha = os.environ.get("GITHUB_SHA", "")
    require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None, "invalid event commit SHA")
    actual_sha = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         cwd=root, text=True).strip()
    require(actual_sha == sha, "checkout is not the exact event commit")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    require(event.get("ref") == REF and event.get("after") == sha,
            "push payload does not identify this commit and branch")
    require(event.get("repository", {}).get("full_name") == REPOSITORY,
            "push payload repository differs")
    require(not event.get("deleted", False), "branch deletion event")
    require(MARKER in event.get("head_commit", {}).get("message", ""),
            "push message does not contain the transport-ready marker")
    require(bool(os.environ.get("GITHUB_TOKEN")), "workflow token is unavailable")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        raise SystemExit("Archive transport stopped: API redirect refused")


def upload(key, path):
    expected = ARCHIVES[key]
    data = path.read_bytes()
    # Verify again immediately before sending the immutable archive bytes.
    require(len(data) == expected["bytes"]
            and hashlib.sha256(data).hexdigest() == expected["sha256"],
            key + ": reconstructed archive changed before upload")
    body = json.dumps({"content": base64.b64encode(data).decode("ascii"),
                       "encoding": "base64"}, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Content-Type": "application/json",
                 "User-Agent": "CSR-T6-T14-authorized-archive-transport",
                 "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=180) as response:
            require(response.status == 201, key + ": unexpected API status")
            response_bytes = response.read(1024 * 1024 + 1)
            require(len(response_bytes) <= 1024 * 1024, key + ": API response too large")
            result = json.loads(response_bytes)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Archive transport stopped: {key} GitHub API returned HTTP {error.code}") from None
    except urllib.error.URLError:
        raise SystemExit("Archive transport stopped: " + key + " GitHub API connection failed") from None
    require(result.get("sha") == expected["git_blob_sha"], key + ": API blob SHA differs")
    require(result.get("url") == ENDPOINT + "/" + expected["git_blob_sha"],
            key + ": API blob URL differs")
    record = {"key": key, "repository_path": expected["repository_path"],
              "sha": result["sha"], "bytes": expected["bytes"], "status": "created"}
    print(json.dumps(record, sort_keys=True), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true",
                        help="Create the three blobs in the authorized GitHub push context.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / TRANSPORT / "manifest.json").read_text())
    if args.upload:
        verify_upload_context(root)
    with tempfile.TemporaryDirectory(prefix="t6-t14-archives-",
                                     dir=os.environ.get("RUNNER_TEMP")) as directory:
        # Every part and archive is verified before the first API write.
        archives = reconstruct_all(manifest, root, Path(directory))
        if not args.upload:
            print("Verification only; no remote mutation requested.")
            return
        results = [upload(key, path) for key, path in archives]
        print(json.dumps({"repository": REPOSITORY, "blobs": results,
                          "refs_modified": False, "pull_requests_created": False},
                         sort_keys=True), flush=True)
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with Path(summary_path).open("a") as summary:
                summary.write("Verified and created the three authorized original evidence archive blobs.\n\n")
                for result in results:
                    summary.write(f'- `{result["repository_path"]}`: `{result["sha"]}`\n')
                summary.write("\nNo Git ref, tree, commit, PR, merge, or repository setting was changed by this job.\n")


if __name__ == "__main__":
    main()
