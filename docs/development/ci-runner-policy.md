# CI Runner Policy

_status: active_

## Current routing

`gunz-utils` is a public reference repository and currently uses hosted GitHub
Actions only. The existing `main` push and pull-request-to-`main` workflow
remains unchanged; this policy does **not** add a self-hosted runner.

## Self-hosted policy for future workflows

If a self-hosted job is added later, it must follow these rules:

- never run `sudo` from the workflow;
- never run `apt-get` from the workflow;
- treat external system executables as pre-provisioned runner dependencies;
- prefer non-root environment provisioning such as Conda/Mamba when a job needs
  an additional executable;
- keep privileged host configuration outside repository CI execution;
- for branch-push self-hosted jobs, explicitly exclude both `main` and `develop`;
- keep `main`/protected-branch verification on hosted runners unless repository policy is deliberately changed;
- make runner routing explicit so protected/default branches do not accidentally depend on a private runner.

Python packages remain normal project dependencies and should be installed via
`pip`/project extras. Wrappers around external executables do not make those
executables pip-managed system dependencies.

## Enforcement

`tests/test_project/test_ci_policy.py` scans every GitHub Actions workflow.
Whenever it finds a job whose `runs-on` contains `self-hosted`, that job must contain neither `sudo` nor `apt-get`, and its branch condition must explicitly exclude `main` and `develop`.

The test also pins the current `gunz-utils` policy: no self-hosted CI jobs are
present today. If the repository intentionally adopts self-hosted CI later,
that assertion should be updated in the same reviewed change while retaining
the no-privilege invariant.
