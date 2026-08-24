---
name: commit
description: Create and push Git commits through the verified repository workflow. Use when the user asks to commit, push, publish changes, or prepare a verified commit.
---

# Verified Commit and Push

## Workflow

1. Inspect the complete workspace and separate unrelated user changes before staging.
2. Run and capture the real status of the root quality gate:

   ```bash
   make verify; status=$?; printf 'MAKE_VERIFY_EXIT=%s\n' "$status"
   ```

3. Continue only when `MAKE_VERIFY_EXIT=0`. If a tool wrapper disagrees with the
   captured status, treat the captured Make status as authoritative and report the
   harness discrepancy.
4. Stage the scope so that the index **is** the verified worktree — `git add -A`
   when everything belongs in the commit, otherwise `git stash -k` the rest and
   re-run step 2 before continuing. A commit with unstaged changes or untracked
   files publishes a tree `make verify` never read.
5. Create a descriptive commit and push the intended branch.
6. Confirm the remote branch contains the new commit and the worktree is clean.

## Enforcement

`strict-verified-git.ts` independently runs `make verify` immediately before an
OMP-mediated `git commit` or `git push`. A nonzero verification status blocks the
Git command. This applies even if an earlier verification succeeded, so commits
and pushes are always gated by the current workspace state.

It also blocks a `git commit` while `git status --porcelain` reports unstaged
changes or untracked files, because the verified tree and the committed tree
would then be different trees.

## Never Do These

- Commit or push unrelated staged work without explicit user approval.
- Treat a tool-wrapper status as more authoritative than a captured Make status.
- Bypass a failed verification gate by committing or pushing anyway.
