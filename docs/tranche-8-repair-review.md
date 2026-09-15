# Independent review of the Tranche 8 input repair

**Disposition: ready for owner MATLAB retry.** The reported startup defect is
corrected in the inputs. No further immediate import or reference-preflight
blocker was found. MATLAB execution and Tranche 8 acceptance remain pending.

The review compared the repair with candidate
`010793b402cc63c1bd434328d80d0b6b53c39ebf`, read the actual MATLAB importer and
factory, and checked the corrected inputs independently of the derivation
verifier. All ten CSVs preserve the parent header, row order and field values
except the run row's declared scenario, seed and provenance hash. All 25 node
rows and 15 flow rows match the accepted parent fields exactly. Removing
their 40 populated `scenario` cells resolves the specific rejection at
`importNs3:77`; the importer remains strict and unchanged.

All input, recipe and parent hashes pass. The corrected plan is
`ed648ee4f54ebf14e14b98d6fcecce224590727139db83f0f4d23161ddfc7a09`.
The fresh ns-3 reference suite is
`5ea5a39c7751c856e710d2eaa09b5d71d4a23c543bafa894c605052f1ded9d5a`.
Independent file reads and decompression verified:

- 130 reference artifact hashes and sizes, and 32 full gzip roundtrips.
- All 74 old/new application trace, admission, feedback, aggregate and
  summary artifact pairs are byte-identical.
- Ten observer on/off comparisons and both pristine-runner controls pass;
  both seed-128 T7 anchors retain their passing comparisons.
- The only 21 changed build inputs are the plan, ten CSVs and ten recipes.
  The source, observer and preserved engine-library bindings are unchanged.

These comparisons cover the recorded application/statistics and feedback
evidence. They do not establish complete protocol/PHY trace equivalence or
MATLAB runtime success. The unchanged ACK observations support no new policy
modification from this repair.

The [repair checks](../evidence/tranche-8-repair-checks.json) record 203 passing
Python tests. Their log, the four supporting artifact hashes, and all 189
current source-snapshot hashes were verified. The new regressions reject
rehashed node/flow contamination and independently read MATLAB's allowed-field
declarations; they no longer rely solely on reconstructing the derivation.
All 112 tracked `.m` files, including 108 executable source/test files, and
all 22 protected PHY/HOP/MAC/NWK/data files match `010793b` byte-for-byte.
Reusing the original 108-file static lint result is therefore appropriate;
that result is explicitly not a MATLAB execution claim.

The repair documentation accurately explains why the earlier passing Python
tests and static lint missed this input-consumer incompatibility. Original
checks remain historical, and the current candidate points to the repaired
plan, fresh reference and new checks. Compact run and case paths are retained.
Final committed ZIP integrity and path verification belong to the packaging
gate; the owner's returned MATLAB tests, ten cases and two controls remain
the execution gate.
