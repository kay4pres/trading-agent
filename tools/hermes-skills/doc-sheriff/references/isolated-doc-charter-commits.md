# Isolated documentation-only charter commits

Use this procedure when a planning or charter package must be copied into a clean worktree, amended, and committed without touching source/runtime files.

## Scope-control sequence

1. Record the required base SHA and branch before any write.
2. Confirm the isolated worktree is clean.
3. Copy only the explicitly authorized artifacts from the protected source location.
4. Hash protected source artifacts and their copies before editing; artifacts designated “copy only” must retain matching hashes.
5. Amend only the authorized document. Keep implementation, deployment, credential access, runtime probing, merge, and push authorization distinct from charter approval.
6. Search the amended charter for every required condition and for stale contradictory wording.
7. Confirm the package contains exactly the authorized paths. If the files are all initially untracked, remember that ordinary `git diff`/`git diff --stat` is empty; inspect filesystem scope first, then stage explicit paths to obtain a cached diff.
8. Stage with explicit path arguments only—never `git add -A` or broad directory staging.
9. Assert the staged path list exactly equals the declared scope before committing.
10. Commit once without amend/rebase/force-push.
11. Report parent SHA, new SHA, exact changed paths, `git diff --stat parent..SHA`, and clean porcelain status.
12. State that independent exact-SHA verification remains outstanding; an author must not claim verifier PASS.

## Markdown hard-break caveat

Copied Markdown may intentionally contain two trailing spaces for hard line breaks. `git diff --cached --check` reports these as trailing whitespace even when the protected copies are byte-identical. Do not silently rewrite protected copy-only artifacts to satisfy the check. Instead:

- preserve their hashes;
- distinguish intentional inherited Markdown hard breaks from newly introduced accidental whitespace;
- report the check result accurately;
- remove accidental whitespace only from the editable artifact when doing so does not alter intended rendering.

## Concurrent-writer and unexpected-commit guard

An isolated worktree can still be changed by another agent/process. Treat every write, staging event, or commit that you did not initiate as a scope-integrity event, not as harmless background activity.

1. Re-read the target immediately before every patch if any tool reports that the file changed since the prior read.
2. Re-run `git rev-parse HEAD`, `git status --porcelain=v2`, staged/unstaged path lists, and target-file hashes immediately before staging and again before committing.
3. If HEAD advances unexpectedly, stop the planned commit and inspect the new commit's parent, subject, changed paths, and aggregate `recorded_base..HEAD` diff. Never assume it is your expected commit merely because the file content looks right.
4. Do not reset, amend, rebase, or force-push to collapse an unexpected commit. If a substantive correction is required, make a new explicit-path fix commit as governance requires, then report the full commit chain and both:
   - final commit's actual `parent..SHA` receipts; and
   - aggregate `recorded_base..final_SHA` changed paths/stat so the verifier can review the complete amendment.
5. If no correction is required, do not create a ceremonial extra commit. Report that the commit landed externally/concurrently and bind verification to its exact SHA.
6. Before final reporting, verify that the worktree/index is clean and that the recorded base is an ancestor of the final SHA.

## Verification receipts

Minimum receipts:

- branch and recorded base SHA;
- pre-write clean status;
- protected-copy hash pairs;
- exact staged path list;
- commit SHA and actual parent SHA;
- complete commit chain when more than one commit exists;
- `git diff --name-only parent..SHA` and `git diff --stat parent..SHA`;
- aggregate `git diff --name-only recorded_base..final_SHA` and stat when HEAD changed unexpectedly or the deliverable spans multiple commits;
- proof that the recorded base is an ancestor of the final SHA;
- post-commit clean `git status --porcelain`.
