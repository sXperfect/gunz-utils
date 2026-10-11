Add a guarded local platform verifier with actual host/interpreter/source identity,
source fingerprints, bounded commands, JUnit skip/failure evidence and independent
native/fallback activation. Linux runs remain preparation evidence; native platform
acceptance requires both Python 3.11 and 3.12 with no unexplained coverage skips.
Reject malformed or all-skipped JUnit proof packets, preserve xfail disposition,
validate interpreter identity domains, and isolate verification from inherited
pytest selection plugins; require exact native-helper activation receipt lines.
