Tranche 14 observer repair

The returned run failed while recording a valid ACK. `Frames.base` gives ACK frames an `App` field containing `struct()`; the observer treated field existence as proof of a DATA application identity. The first ACK transmission therefore raised a missing `SourceId` error in all six cases.

The repaired observer exports application identity only for `Kind=DATA`. ACK and terminal observations keep zero application identities. DATA field accesses remain strict, so a malformed DATA packet still fails visibly. No MAC, HOP, NWK, PHY, scheduler, timing input or native reference changes are part of this repair.

The existing real aggregate regression now verifies the actual ACK constructor schema and requires all six boundaries to exist. It checks source 5/app 3 on DATA and zero application identities for every ACK transmission and feedback ingress. The suite remains 18 focused tests plus 88 retained tests (106 total), with 222 structural checks.

Remaining application-field accesses were reviewed: selected-member DATA reads are short-circuit guarded by DATA kind; the delivery callback receives an NWK application; priming and ingress DATA are made by the validated DATA constructor. ACK and settled observations do not need application fields.

MISS_HIT parsed both changed MATLAB files successfully. MATLAB runtime execution is unavailable here and remains pending an owner rerun.

The returned failure also exposed two tests that passed vacuously because they iterated over an empty boundary table. The gateway identity and updated-ACK/queue-drain tests now require all six expected boundary cases before those loops. No test methods were added or removed. Both modified files again pass MISS_HIT after this strengthening.
