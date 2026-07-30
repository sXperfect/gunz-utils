# [ACTIVE]: Cleanup obsolete backups and orphan tag

**Date:** 2026-07-16
**Role:** Ops / Repo Hygiene
**Component:** `repo`
**Status:** Pending

## 1. Goal

Remove obsolete files and tags that have accumulated across sessions:

- Local `/tmp/gunz-base-model-wip*` files (5 files, ~20K) — backup of an earlier WIP that has since been properly committed to the repo as `GunzBaseModel` (commit `d2d5153`). Files are obsolete.
- ikarus `/home/adhisant/projects/gunz-utils.bak-pre-clone-20260727-225224/` (14M snapshot directory) — plain directory snapshot from July 15, before some prior git operation. Not a git repo. Contains old files that pre-date current HEAD.
- `pre-history-scrub` orphan tag — still exists on `origin` (a forensic backup from a filter-branch rewrite, points at unreachable commit `2096647`). Need explicit user authorization to push-delete (per AGENTS.md "Never commit without explicit request" — pushing a tag deletion is in the same spirit).

## 2. Scope

### In Scope (no authorization needed)

- Delete local `/tmp/gunz-base-model-wip*` files (5 files: `wip-init.py`, `wip-models.py`, `wip.patch`, `wip-investigation.md`, `wip-README.md`)
- Delete ikarus `gunz-utils.bak-pre-clone-20260727-225224/` directory (14M, plain dir snapshot)

### Out of Scope (requires explicit authorization)

- Push-delete `pre-history-scrub` tag from origin: `git push origin :refs/tags/pre-history-scrub`
  - Per AGENTS.md, "Never commit without explicit request" — pushing a tag deletion is a remote-side mutation
  - Per the original task spec at commit `970f9aa`: "the tag deletion was local-only by design" — the spec explicitly excluded pushing the deletion
  - Will NOT execute this without explicit user `yes`

## 3. Approach

Two parallel local cleanups. No git operations on either node's repo (cleanups are outside the repo).

### Cleanup 1: Local /tmp

```bash
ls /tmp/gunz-base-model-wip*           # confirm 5 files exist
rm -v /tmp/gunz-base-model-wip*        # delete with verbose output for confirmation
ls /tmp/gunz-base-model-wip* 2>&1      # confirm 0 files remain
```

### Cleanup 2: ikarus bak dir

```bash
ssh ikarus 'du -sh /home/adhisant/projects/gunz-utils.bak-pre-clone-20260727-225224/'  # confirm size
ssh ikarus 'rm -rf /home/adhisant/projects/gunz-utils.bak-pre-clone-20260727-225224/'  # delete
ssh ikarus 'ls /home/adhisant/projects/gunz-utils.bak*' 2>&1  # confirm 0 matches
```

## 4. Verification

After cleanups:

1. `ls /tmp/gunz-base-model-wip*` returns "No such file or directory" or empty
2. `ssh ikarus 'ls /home/adhisant/projects/gunz-utils.bak*'` returns no results
3. Repo state on both nodes is unchanged: `git status --short` clean, HEAD same as before

## 5. Definition of Done

- [ ] 5 files deleted from `/tmp/gunz-base-model-wip*`
- [ ] `/home/adhisant/projects/gunz-utils.bak-pre-clone-20260727-225224/` deleted on ikarus
- [ ] No git operations executed (this task is filesystem cleanup only)
- [ ] Repo state on both nodes unchanged

## 6. Deferred (requires explicit user authorization)

- [ ] `git push origin :refs/tags/pre-history-scrub` — DO NOT execute without user "yes"
  - The tag remains on origin by design (forensic backup from a filter-branch rewrite)
  - User explicitly opted for local-only deletion at the time (commit `970f9aa`)
  - Pull/fetch will keep bringing the tag back to local clones
  - If user authorizes, can be done in a separate follow-up task