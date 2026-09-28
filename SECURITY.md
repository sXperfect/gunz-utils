# Security Policy

## Supported versions

Security fixes are developed against the current `main` branch and the latest
tagged release line. Older release lines may receive fixes when practical, but
they are not guaranteed security maintenance.

## Reporting a vulnerability

Do **not** open a public GitHub issue for an undisclosed vulnerability.

Report suspected vulnerabilities privately by email to
`yeremiag@gmail.com` with a subject beginning with `[gunz-utils security]`.
Include, where possible:

- the affected version, tag, or commit;
- the affected module or API;
- reproduction steps or a minimal proof of concept;
- the security impact and realistic attack conditions;
- any mitigations or fixes you have already identified.

Do not include unrelated credentials, production secrets, personal data, or
other sensitive material in a report.

## Security-sensitive areas

Reports are particularly useful for behavior involving path handling,
subprocess execution, secret redaction or storage, serialization, network
boundaries, content-addressed storage, resource limits, and dependency
isolation. This list is not exhaustive.

The repeatable repository review process is documented in
[`docs/design/audit/security-audit-methodology.md`](docs/design/audit/security-audit-methodology.md).
The latest dated audit result is indexed under
[`docs/design/audit/`](docs/design/audit/).

## Disclosure

Please allow time for the issue to be reproduced and a fix to be prepared before
public disclosure. Security fixes should include focused regression tests and,
when user-visible, an appropriate changelog fragment.

For ordinary bugs that do not present a security risk, use the public GitHub
issue tracker instead.
