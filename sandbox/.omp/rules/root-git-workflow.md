---
description: Root Git workflow — verified commits and pushes through the commit skill
globs:
      - Makefile
      - .omp/skills/commit/SKILL.md
      - .omp/hooks/pre/strict-verified-git.ts
alwaysApply: false
---

# Root Git Workflow

## Verified Commit and Push

- Use the `commit` skill for user-requested commits or pushes.
- Before staging, inspect the complete workspace and keep unrelated user changes
  out of the commit unless the user explicitly approves them.
- `make verify` must pass before a commit or push. Capture its actual status:

  ```bash
  make verify; status=$?; printf 'MAKE_VERIFY_EXIT=%s\n' "$status"
  ```

- `MAKE_VERIFY_EXIT=0` is the pass condition. If a wrapper reports a conflicting
  status, report the harness issue; do not change project code to satisfy it.
- `strict-verified-git.ts` reruns `make verify` immediately before every
  OMP-mediated `git commit` or `git push` and blocks the Git command on failure.
- **The commit must be the verified tree.** `make verify` reads the worktree, so
  a commit with unstaged changes or untracked files publishes a tree that was
  never verified — an untracked new module imported by tracked files is the
  classic case: green verify, broken commit. `strict-verified-git.ts` blocks a
  commit while `git status --porcelain` shows either, naming both ways out:
  `git add -A` (commit what was verified) or `git stash -k` (move the rest out
  first, then re-verify).
- Confirm the remote branch and clean worktree after push.

## Review Judgement (not machine-checked)

- Whether staged work is *related* - only the author knows what the change is.
- Whether a commit message describes the change honestly.

The gate that **is** enforced is narrower and absolute: `strict-verified-git.ts`
runs `make verify` immediately before any commit or push, and a nonzero status
blocks it.

## Never Do These

- Commit or push unverified changes.
- Include unrelated staged work without explicit user approval.
- Commit a partial index after verifying the whole worktree — verify the tree you
  are publishing, not a different one.
- Bypass a failed verification gate.
