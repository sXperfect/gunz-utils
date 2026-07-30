# [ACTIVE]: Push-delete orphan `pre-history-scrub` tag from origin

**Date:** 2026-07-16
**Role:** Ops / Repo Hygiene
**Component:** `git`
**Status:** Pending (authorized)

## 1. Goal

Remove the orphan `pre-history-scrub` tag from `origin`. The tag was originally cut during a filter-branch rewrite session as a forensic backup, pointing at unreachable commit `2096647`. It was deleted locally in commit `970f9aa` (tier-1 cleanup), but the tag was never pushed-deleted from origin — by explicit design at the time.

The user's 2026-07-16 instruction authorizes pushing the deletion.

## 2. Scope

### In Scope
- `git push origin :refs/tags/pre-history-scrub` from the local repo
- Verify the tag is gone from `origin` after push
- Verify the local repo is unchanged

### Out of Scope
- Re-creating the tag on origin (irreversible; do not re-create)
- Any other remote-side operations
- Any local git operations besides the single push

## 3. Background

The tag has the following characteristics:
- **Subject on creation**: "Pre-history-scrub backup tag (d8c702d + new content)"
- **Commit**: `2096647` (unreachable from main; was deleted locally but exists on origin)
- **Last local deletion**: commit `970f9aa` chore: delete dead duplicates left over from v1.3.0 ext.* split
- **Original task spec**: explicitly excluded pushing the deletion ("`git push origin :refs/tags/pre-history-scrub` is OUT OF SCOPE")
- **Current authorization**: 2026-07-16 user explicitly authorized push-delete

The original lessons-learned guide says tags are immutable from the time of cut. This push-delete is a one-time exception, authorized by the user to clean up the orphan. No re-creation will happen.

## 4. Approach

```bash
cd /home/sxperfect/projects/gunz-utils
git push origin :refs/tags/pre-history-scrub
```

The `:refs/tags/<name>` syntax on the remote side of `git push` deletes the tag. This is the standard, safe way to remove a remote tag — no force-push, no history rewrite.

### Why this is safe (not a force-push)

- It does not rewrite any commits
- It does not delete or modify any branches
- It does not affect any reachable history
- It only removes a single ref that points at a single commit
- That commit still exists on origin (untouched); only the tag pointing at it is removed

## 5. Verification

After push:

1. `git ls-remote --tags origin | grep pre-history-scrub` → must return no results
2. `git ls-remote origin | grep pre-history-scrub` → must return no results (refs/heads and refs/tags)
3. Local repo unchanged: `git status --short` clean, HEAD `bcf638c`
4. Local tag list unchanged: `git tag -l` does NOT include `pre-history-scrub` (already deleted locally)
5. `git log --oneline -1 origin/main` → still `bcf638c` (push didn't move main)
6. `pytest tests/ -q` → still 99 + 4
7. Sync ikarus:
   - `ssh ikarus 'cd /home/adhisant/projects/gunz-utils && git fetch origin 2>&1 | tail -3'` — should NOT bring the tag back (it's gone)
   - `ssh ikarus 'cd /home/adhisant/projects/gunz-utils && git reset --hard origin/main 2>&1'` — HEAD matches local
   - `ssh ikarus 'cd /home/adhisant/projects/gunz-utils && git tag -l | grep pre-history-scrub; echo "exit=$?"'` — should print nothing and exit 1 (grep no-match)

## 6. Definition of Done

- [ ] `git push origin :refs/tags/pre-history-scrub` executed successfully
- [ ] `git ls-remote --tags origin | grep pre-history-scrub` returns no results
- [ ] `git ls-remote origin | grep pre-history-scrub` returns no results (covers both refs/heads and refs/tags)
- [ ] Local repo unchanged: clean working tree, HEAD `bcf638c`
- [ ] Tests still pass (99 + 4) — they should since no code changed
- [ ] ikarus sync'd to `bcf638c`; `git tag -l` on ikarus does NOT include `pre-history-scrub`
- [ ] No re-creation of the tag (irreversible)

## 7. Rollback

If the push fails (network error, auth issue, etc.), the tag remains on origin unchanged. No rollback needed.

If the push succeeds but you regret it: you can re-create the tag locally and push it back:
```bash
git tag pre-history-scrub 2096647e88986765eaa47e851e7d6acd90617790
git push origin refs/tags/pre-history-scrub
```
But this should NOT be done — the user authorized deletion, not re-creation.