# Adding a paper to the corpus (onboarding specification)

> Written for #44 from the checks and scripts that exist today. "Enforced" means a test or script fails when the rule is broken; "reviewed" means the maintainer checks it by reading.

A corpus entry is one paper, one public repository at one pinned commit, one script, and the numbers the paper reports. The corpus is the evaluation set, so adding or changing an entry changes what the project measures. Open an issue first and wait for the maintainer to agree.

## 1. Eligibility

| Rule | How it is checked |
|---|---|
| The paper is public (arXiv, or a DOI such as bioRxiv) and its title matches the entry | enforced: `scripts/verify_corpus.py` |
| The repository exists on GitHub | enforced: `scripts/verify_corpus.py` |
| The repository license is open and equals the declared license: `MIT`, `Apache-2.0`, `BSD`, `BSD-2-Clause`, `BSD-3-Clause`, `CC-BY-4.0`, or `ISC` (`ALLOWED_LICENSES` in `src/config.py`) | enforced: `verify_corpus.py` and `tests/test_seed.py` |
| `repo_commit` is a full 40-character commit SHA, and `target_script` exists in the repository at that commit | enforced: `tests/test_seed.py` and `verify_corpus.py` |
| `target_script` is a Python file | enforced: `tests/test_seed.py` |
| Publication year 2020 to 2024 | enforced: `tests/test_seed.py` |
| Tabular machine learning or light NLP, a size and runtime that fit the sandbox limits (Pilot 2 used 2 CPUs, 6 GB of memory, and one hour per phase; the runner default is 8 GB) | reviewed |
| The paper reports at least one number for a model the repository trains | reviewed (see section 4: a paper may end with no accepted claim, but that should be known up front) |

A paper that cannot run in the sandbox at all (data that is not public, code that needs a service) can still be added. The outcome is then reported as it is, with the reason (see `paper_008` in `docs/CORPUS_VERIFICATION.md`). Do not swap in a different repository to make a paper pass.

## 2. The entry (submission template)

One object in the list in `data/seed_papers.json`. Fields marked required are enforced by `src/models.py` (`PaperCreate`) and `tests/test_seed.py`.

```json
{
  "paper_id": "paper_009",
  "title": "Title exactly as on the paper's page",
  "year": 2022,
  "venue": "NeurIPS 2022",
  "repo_url": "https://github.com/<owner>/<repository>",
  "repo_commit": "<40-character commit SHA>",
  "paper_url": "https://arxiv.org/abs/<id>",
  "license": "Apache-2.0",
  "target_script": "path/to/script.py",
  "expected_claims": {},
  "source_table_or_section": {},
  "python_version": "3.8",
  "python_version_source": "Where the repository states it (file and line, or README text)",
  "run_setup": {
    "decision": "fix",
    "reason": "What the repository needs that the sandbox does not give by default",
    "args": [],
    "env": {},
    "data": [],
    "open_items": [],
    "status_note": "Not verified: no run yet."
  }
}
```

Notes:

- `paper_id` is `paper_` and three digits, unique.
- `expected_claims` starts **empty**. It is filled only by `scripts/apply_accepted_claims.py` from claims a person accepted (section 4). A hand-typed value does not belong here. If a paper ends with no accepted claim, `seed_claims_before_extraction` records why.
- `python_version` must be one the sandbox has an image for: 3.8, 3.9, or 3.11 (`SUPPORTED_PYTHON_VERSIONS` in `src/sandbox/runner.py`). Say where you found it.
- `run_setup` is validated by `src/sandbox/run_setup.py`. `decision` is `fix` (we prepare the run) or `report_as_is` (we report that it cannot run). Optional keys: `command`, `working_dir`, `writable_repo`, `data` (URL or OpenML datasets fetched on the host by `scripts/fetch_data.py`, since the sandbox has no network), `build` (source packages built in the sandbox's build phase), `extra_requirements`, `constraints` (with `constraints_source`). The module's docstring describes each key.

## 3. Steps

1. **Issue and branch** as in [`CONTRIBUTING.md`](../CONTRIBUTING.md), one paper per pull request.
2. **Pin the repository** to a commit and add the entry with empty claims (section 2).
3. **Verify the entry:** `python scripts/verify_corpus.py`. Every line must pass; paste the output into the pull request.
4. **Write the questions** in `data/claim_queries/<paper_id>.json`: one question per number you expect the paper to report, naming the metric, dataset, and model, **without the value you expect** (a test, `test_questions_do_not_contain_the_seed_values`, guards this for seed claims). Pin the paper's PDF URL in the same file.
5. **Extract the claims** by the protocol in [`docs/AGENT_EXTRACTION.md`](AGENT_EXTRACTION.md): answer only from the paper text, `not_found` with a reason when it is not there, a verbatim quote and a page for every found value, two passes. The second pass should be independent (`scripts/make_blind_packet.py`, `scripts/import_pass.py`).
6. **Run the quote guard:** `python scripts/check_claims.py`. A claim whose quote or value is not on the cited page stays unverified and is not used.
7. **Compare the passes:** `python scripts/compare_extractions.py`. Every disagreement goes to the maintainer.
8. **Review by a person:** `python scripts/import_claims.py`, then `python cli.py review-claims`. Only the maintainer's accept or reject decides which claims count.
9. **Apply the accepted claims:** `python scripts/apply_accepted_claims.py export`, then `apply`, then `check`.
10. **Prepare the run** (`run_setup`, section 2). Fetch data with `python scripts/fetch_data.py <paper_id>`. Try it with `python scripts/run_pilot.py` (see its docstring for `--pilot2`).
11. **Document the result** in `docs/CORPUS_VERIFICATION.md` (what was checked, with the command output) and `docs/PROGRESS.md`.

## 4. What is not promised

- A paper can end with **no accepted claim** (as `paper_005` did): the paper's numbers are under other names than the repository or the seed list suggest. It stays in the corpus and only the build and run tiers can be measured. Say so in the pull request.
- A run that fails is a result, not a defect to hide. Do not edit a paper's code or settings to make it pass. If the failure is a defect in Repro Radar itself, open an issue for it.
- Pilot 2 ran with the settings frozen in `docs/PILOT_2.md`; a paper added later is not part of that pilot's numbers.

## 5. Review criteria for a new paper

The reviewer reads the pull request and checks:

1. `python scripts/verify_corpus.py` output is present and every line passes.
2. The questions contain no expected values, and each answered claim has a page, a table or figure, and a quote that the guard matched.
3. `expected_claims` was produced by `apply_accepted_claims.py` and `python scripts/apply_accepted_claims.py check` passes.
4. The pass B (second extraction) is independent, or the pull request says plainly that it is not.
5. `python_version`, `python_version_source`, and `run_setup` are filled in, every data source is a public URL with a size or checksum, and nothing in `run_setup` claims a result.
6. The full suite and `ruff check .` pass, with the output pasted.
7. `docs/CORPUS_VERIFICATION.md` and `docs/PROGRESS.md` describe exactly what was checked and what was not.
