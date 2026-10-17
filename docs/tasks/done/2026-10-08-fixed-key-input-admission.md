# Fixed key/salt and crypto field admission follow-up

**Date:** 2026-10-08
**Status:** Complete — bounded file reads, early salt shape validation, and fixed crypto envelope admission verified across 164 test cases
**Evidence:** [RS-02 audit](2026-10-08-secure-input-budgets.md)
**Predecessor:** [Completed repairs](2026-10-08-resource-security-repairs.md)

RS-02 measured unbounded read requests on malformed fixed-format key/salt files
using at most 4,096-byte synthetic inputs, and salt admission reaching PBKDF2
before fixed-size rejection. These resource-admission gaps have been addressed:

1. **Bounded key/salt file reading**: `SecureStore._read_private` now accepts an
   explicit `max_bytes: int = 4096` bound (with salt reads bound to `max_bytes=64`).
   Both file `st_size` pre-check and `handle.read(max_bytes + 1)` post-check reject
   oversized files before unbounded allocations.
2. **Early salt validation before PBKDF2**: `SecureStore._derive_key` strictly validates
   that `salt` is bytes of length exactly 16 (`len(salt) == 16`) before constructing
   `PBKDF2HMAC` (avoiding expensive 600,000-iteration KDF runs on invalid salt).
   In passphrase unlock, candidate salts with invalid lengths are skipped before KDF.
3. **Fixed crypto envelope admission**: `secure_crypto.decrypt` validates the exact hex
   lengths of the fixed salt (`SALT_LENGTH * 2`), IV (`IV_LENGTH * 2`), and tag
   (`32` hex characters) fields before unhexing or allocating variable ciphertext payload.
4. **Finite consumed-byte regressions**: Four new regression test cases added to
   `tests/test_secure/test_secure_input_budget_audit.py`, proving oversized file rejection,
   early salt validation before PBKDF2, damaged salt unlock handling, and zero payload
   unhexing on malformed fixed envelope headers. All 164 secure tests pass.
