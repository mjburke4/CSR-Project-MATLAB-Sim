#!/usr/bin/env python3
"""Create a deterministic, unfiltered canonical ns-3 trace prefix.

Usage: extract_exact_prefix.py PARENT.csv.gz PREFIX.csv.gz CUTOFF_SECONDS
Unlike a diagnostic-window extractor, this retains *every* canonical row
strictly before the stop time, in original event order and CSV fields.
"""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):
            h.update(chunk)
    return h.hexdigest()


if __name__=='__main__':
    # Preserve predictable gzip metadata so the prefix digest is reproducible.
    if len(sys.argv)!=4:
        raise SystemExit(__doc__)
    parent=Path(sys.argv[1]);out=Path(sys.argv[2]);cutoff=int(sys.argv[3]);n=0
    with gzip.open(parent,'rt',newline='') as src,out.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0,compresslevel=9) as gz:
            with io.TextIOWrapper(gz,encoding='utf-8',newline='') as dst:
                reader=csv.DictReader(src)
                writer=csv.DictWriter(dst,fieldnames=reader.fieldnames,lineterminator='\n')
                writer.writeheader()
                for row in reader:
                    if float(row['time_s'])>=cutoff:
                        break
                    writer.writerow(row);n+=1
    print(json.dumps(dict(parent_sha256=digest(parent),prefix_sha256=digest(out),
                          cutoff_seconds=cutoff,rows=n,bytes=out.stat().st_size),indent=2))
