# Dangling task-id references — pointer note (WS3-S8 sweep, 2026-07-11)

The `guardkit task audit` reports three **dangling references** in this repo — task ids
named by first-party source that no task file in `tasks/` declares:

| Referenced id  | Referenced by                | Disposition |
|----------------|------------------------------|-------------|
| `TASK-QAV-005` | `src/qav/gold_negatives.py`  | **Intentional external-incident label — NOT a local task.** |
| `TASK-SMP2-07` | `src/qav/gold_negatives.py`  | **Intentional external-incident label — NOT a local task.** |
| `TASK-SMP3-06` | `src/qav/gold_negatives.py`  | **Intentional external-incident label — NOT a local task.** |

## Why these are not tracker rot

`src/qav/gold_negatives.py` is the QAV (QA-verifier) **gold-negative fixture set**. Each
fixture carries a `task=` field that records the *originating autobuild defect incident* the
gold negative is drawn from — these ids belong to **other repos' autobuild runs** (guardkit
`10AC`/`TASK-QAV-005`, study-tutor `SMP2`/`SMP3` composition-seam escapes), embedded here as
data labels, not as work items to be executed in agentic-dataset-factory.

They therefore **correctly have no declaring task file** in this repo, and the audit's
dangling-reference flag on them is expected and permanent. Do not file phantom
`TASK-QAV-005` / `TASK-SMP2-07` / `TASK-SMP3-06` task files to silence the audit — that would
invent local work that does not exist. If a future audit gains a per-repo reference-ignore
list, these three source-embedded labels are the entries to exclude.

_Filed by the WS3-S8 tracker sweep, 2026-07-11 (see ai-transition WS3 §6 S8 STATUS row)._
