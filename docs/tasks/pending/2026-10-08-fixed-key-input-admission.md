# Fixed key/salt and crypto field admission follow-up

**Date:** 2026-10-08
**Status:** Pending — compatibility contract and bounded regression design first
**Evidence:** [RS-02 audit](../done/2026-10-08-secure-input-budgets.md)
**Predecessor:** [Completed repairs](../done/2026-10-08-resource-security-repairs.md)

RS-02 measured unbounded read requests on malformed fixed-format key/salt files
using at most 4,096-byte synthetic inputs, and salt admission reaching PBKDF2
before fixed-size rejection. These are resource-admission gaps; no memory
exhaustion was demonstrated. Arbitrary valid ciphertext/plaintext budgets remain
caller-owned unless separately specified.

1. Establish persisted key whitespace compatibility and exact salt shape from
   maintained writing/reading contracts and legacy tests before choosing limits.
2. Bound fixed-format reads before allocation and reject malformed salt before
   KDF while retaining opened-object safety, authenticated recovery and rejected
   unlock preservation.
3. Validate fixed crypto envelope fields before decoding variable ciphertext;
   retain independent known-answer/component proofs and compatible errors.
4. Add finite consumed-byte/KDF-admission regressions, test Python 3.11/3.12,
   run canonical gates and update GAP-008 with the actual executed evidence.

No implementation or new API cap is implied by this task. Use synthetic tmp
fixtures only; preserve user edits and follow AGENTS.md/SECURITY.md.
