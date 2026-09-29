# Changelog fragments

Every user-visible change should add one small fragment instead of editing the
top of `CHANGELOG.md` directly. This avoids merge conflicts when several
branches or agents work in parallel.

Use the filename form:

```text
<unique-id>.<category>.md
```

The unique ID may be a pull-request number or a descriptive slug. Supported
categories and their minimum Semantic Versioning impact are:

| Category | Minimum bump | Purpose |
|---|---:|---|
| `breaking` | major | incompatible API or behavior change |
| `removed` | major | removal of public API or supported behavior |
| `added` | minor | new backward-compatible functionality |
| `changed` | minor | backward-compatible user-visible behavior change |
| `deprecated` | minor | newly deprecated public behavior |
| `security` | patch | backward-compatible security correction |
| `fixed` | patch | backward-compatible bug fix |
| `performance` | patch | backward-compatible performance improvement |
| `docs` | patch | user-facing documentation correction |
| `internal` | patch | maintenance that is consumed at release time but omitted from published notes |

Each file should contain one concise changelog entry. Plain text is converted to
a bullet automatically; Markdown beginning with `- ` is preserved.

You can create a fragment automatically using the release tool:

```bash
python scripts/release.py new -c <category> -m "<description>"
```

Examples:

```text
changes/184.added.md
changes/ci-cache.fixed.md
changes/remove-legacy-api.breaking.md
```

Before merging, run:

```bash
python scripts/release.py check
```

To inspect the accumulated release impact:

```bash
python scripts/release.py status
```

Only the release preparation step rewrites `CHANGELOG.md` and consumes the
fragment files.
