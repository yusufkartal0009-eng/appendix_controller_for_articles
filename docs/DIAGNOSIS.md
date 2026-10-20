# Diagnosis layer

Issues: #31 (input schema and prompt templates), #32 (failure classifier), #33 (rule-based report and `cli.py diagnose`), #34 (backends), #35 (explaining the difference between two runs), #36 (validation of the classifier).

## 1. What this layer is, and is not

The diagnosis layer explains one stored run, or the difference between two, in plain language. It is **rule-based**. It reads the files a run leaves in its folder and writes sentences from templates. It calls no model, uses no network, and needs no key.

An optional language-model step can restate the rule-based report (section 6). It is off by default, it is tested with a mock client only, and it cannot change a number.

The layer does not decide whether a paper is right. A failed run is a statement about one run on one machine with the limits it was given.

## 2. Principles

1. **Every sentence rests on a field.** A report sentence names the file and the key it was read from (`pilot_record.json: run.status`). A sentence without a field is not written.
2. **Unknown is written as unknown.** A value that the files do not hold is `None` in the input, and the report says "unknown" (or "not recorded"); it is never inferred from a neighbouring value.
3. **Neutral language.** Sentences describe what the run did. Words about people or intent are not used (`src/diagnosis/prompts.py: LOADED_WORDS`); a test checks every generated report against the list.
4. **No invented causes.** The category of a failure comes from the classifier (#32) and the quoted log line. Where the log does not say why, the report says that the cause was not investigated.
5. **Numbers come from the run.** Durations, memory, and metrics are copied from the stored files, with the unit of the file.

## 3. The input: `DiagnosisInput` (`src/diagnosis/schema.py`)

`load_diagnosis_input(run_dir)` reads `pilot_record.json`, `run_report.json`, `stderr.log`, and `stdout.log` of one run folder. Each field below is read from exactly one place (`FIELD_SOURCES`); if the key is missing the field is `None`. For a run without a run report, the run block of the pilot record is the fallback for the run fields, and `sources` says which was used.

| Field | Read from | Meaning |
|---|---|---|
| `paper_id`, `protocol`, `started_at`, `finished_at`, `python_version`, `container_command` | `pilot_record.json` | which run it was |
| `stage_status`, `stage_error` | `pilot_record.json: stage.*` | whether the repository was fetched at the pinned commit |
| `build_status` | `pilot_record.json: build.status` | the build phase, for papers that need one |
| `install_status` | `run_report.json: dependency_install_status` | `INSTALLED`, `FAILED`, or `SKIPPED` |
| `run_status`, `exit_code`, `duration_seconds` | `run_report.json` | what the run phase did |
| `timeout_limit_seconds`, `peak_memory_bytes` | `run_report.json: meta.*` | the time limit and the measured peak memory |
| `memory_limit`, `cpus` | `pilot_record.json: limits.*` | the limits the container got |
| `gpu_requested` | `run_report.json: meta.gpu_requested` | whether a GPU was asked for |
| `metrics` | `run_report.json: metrics` | numbers the metric extractor found in the output |
| `seed` | `pilot_record.json: multi_seed.seed` | the seed of a multi-seed run (docs/MULTI_SEED.md) |
| `memory_override`, `cpus_override`, `timeout_override` | `pilot_record.json` | the run is not a protocol run |
| `claims` | given by the caller | the claimed values to compare with, question ID -> number |
| `stderr_tail`, `stdout_tail` | the logs | the last 12 non-empty lines, each with file and line number |
| `files_present`, `sources` | the folder | which files exist, and where each found value came from |

## 4. The output

`src/diagnosis/report.py` (#33) turns a `DiagnosisInput` and the classifier's result (#32, `src/diagnosis/classifier.py`) into a list of statements, each with the text, the field(s) it rests on, and the source. `cli.py diagnose <run_dir>` prints them as Markdown. The sections are: what ran, how it ended, the category of the failure with the quoted log line, the limits, and the comparison with the claims.

## 5. Failure categories (#32)

The categories are those of `scripts/categorize_pilot_failures.py` (`docs/PILOT_WEEK2.md` section 7): `MISSING_DEPENDENCY`, `DATA_NOT_ACCESSIBLE`, `HARDWARE_GPU_REQUIRED`, `TIMEOUT`, `SCRIPT_NOT_FOUND`, `LICENSE_BLOCKED`, `OTHER` (with a name such as `OUT_OF_MEMORY` for a run killed at its memory limit, `WRITE_TO_READ_ONLY_REPOSITORY`, `MISSING_FILE`). The first failure in the order stage, build, install, run decides.

## 6. The optional language-model step (#34)

`docs/prompts/` holds `system.md` and one task template per status (`verified.md`, `partially_verified.md`, `needs_review.md`, `failed.md`). `src/diagnosis/prompts.py` fills them. The rules in `system.md` are: use only the facts of the report; every number must appear in the report character for character (the numbers are listed as locked); neutral wording; no cause that the report does not state.

The prompts are not evidence of anything: they have not been used with a real model.

## 7. What this layer does not do

- It does not read the paper. It knows a run, not the paper's text.
- It does not match a claim to a metric by meaning. A claim is compared with the output only when a metric has the same name; otherwise the report lists both and says that nothing was compared.
- It does not accept or reject claims, and it does not score; scoring is `src/scoring.py`.
