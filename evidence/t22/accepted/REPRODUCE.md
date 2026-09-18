Use the accepted T20 installation with issued-update.zip applied, or your existing T22 installation. From that folder, run:

```bash
python scripts/analyze_tranche22_return.py --source-root . --evidence /path/to/owner.zip --output /path/to/new-review
```

The issued candidate and native references are immutable. The independent audit scripts are preserved as run: they expect a workspace with csr22/, upload/t22.zip, and t22-return-review/integrity/ or t22-return-review/findings/ containing the corresponding script. Copy the preserved scripts into that layout to reproduce them. They validate saved evidence and do not run MATLAB.
