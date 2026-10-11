# Local merge of audited repairs into newer main

**Date:** 2026-10-11
**Status:** Complete — reviewed and verified local merge, not pushed
**Parents:** main `b105e264ed81083b61d8b5d66b93712b6f7095f2` and
audit/native-platforms-20261008 `2fadc30e363176b4d06167c77d69a5e6da10c3ed`

## Reconciliation

Six conflicted paths were resolved with independent source ownership/review.
Newer main process_imap, source documentation/style, cumulative process accounting,
run-directory rollback and cooperating CAS publisher locking are retained.
The audit branch's authentication/recovery, cancellation/task ownership,
exit/drain deadlines, native depth parity and strict regressions are integrated.

CAS process schedules now acknowledge that a second cooperating publisher waits
for the first publication lock; both hard-link and fallback paths preserve the
winning inode. Reader identity-change rejection remains tested using a separate
explicitly noncooperating raw replacement process. Unsafe path and content checks
were not weakened. A dynamic Windows module cast fixes Linux typeshed errors
without changing the inherited locking behavior.

Main's sectioned imports were reconciled with Ruff using explicit isort split
directives. Required gunz-style signature/banner/comment formatting was applied
only after verifying complete Python AST equivalence; import sorting checks
separately verified non-import executable AST equivalence. No checker was disabled.

## Verification

- Final main Python 3.11 suite: 1,635 passed, seven native-host skips.
- Python 3.12 suite: 1,604 passed, 38 skips (31 native-only plus seven host skips).
- Independently built native: 91 passed per interpreter, zero skips.
- Forced fallback: 60 passed per interpreter, 31 exact native-only skips.
- Focused storage: 194 passed per version; lifecycle/concurrency: 141 passed
  plus 21 subtests; serial/two-worker/empty process_imap smoke checks pass.
- Release metadata, Ruff, mypy (97 source files), strict Sphinx and all isolated
  packaging cases pass. Gunz-style scans 231 files with zero violations;
  85 advisory warnings remain and are not errors under main's configuration.

The initial aggregate retained its lint and obsolete CAS-schedule failures in
`tmp/merge-audit-20261011-ci-summary.json`. Corrected primary tests/docs are in
`tmp/merge-audit-20261011-final-ci-summary.json`; the final full lint command
passed separately after formatting reconciliation. Original aggregate packaging
and compatibility gates executed the corrected runtime source and passed.
`tmp/merge-audit-20261011-reviewed-summary.json` records this provenance without
rewriting earlier failed summaries. Formatting after runtime checks preserved AST.

The required local gunz-style package was installed without dependencies into
the task-owned temporary verification environment, not the shared environment.
The current hosted workflow does not install that newly required checker;
hosted dependency setup needs reconciliation before claiming hosted verification.
No workflow runs, remote pushes, release tags or third-party reports were made.
Fixed input admission and actual Windows/macOS proof remain separate follow-ups.
