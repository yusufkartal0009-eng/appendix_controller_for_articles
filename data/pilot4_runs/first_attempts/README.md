# Pilot 4: earlier attempts kept as evidence

Each folder is the unchanged output of an earlier attempt of a paper (`docs/PILOT_4.md` section 7).

- `paper_106_attempt1/`: the **first attempt** of `paper_106` (the README command as written). It ended with
  `ModuleNotFoundError: No module named 'torch'`. This is the strict result of the paper.
- `paper_106_attempt2_tool_defect/`: the first run of the **correction round** (extra requirement `torch`). It did not install
  `torch` because `RepoStager.bundle_dependencies` ignored the extra requirements of a repository without a requirements
  file (`bundle.status: SKIPPED`); the same `ModuleNotFoundError` followed. This was a defect of Repro Radar, not a result about
  the paper. It was fixed (issue #372) and the corrected run was made again; section 8 of the protocol says that this does not use
  up the correction round. This folder is not counted in any rate.

The final record of the paper, with `correction.json`, is `data/pilot4_runs/paper_106/`.
