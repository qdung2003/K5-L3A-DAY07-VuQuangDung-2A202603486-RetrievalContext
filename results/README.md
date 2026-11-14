# Evidence for the final Day 7 implementation

- `selection.json`: configuration frozen from dev before test, with artifact hashes.
- `retrieval/dev` and `retrieval/test`: three methods with the same original queries,
  top-1/top-3 cutoff, corpus and labels; raw rankings, source text and timings.
- `baseline`, `dense-wide`, `hybrid`, `hybrid-wide`, `lexical`: actual model traces,
  run configurations, source-based reviews and aggregated summaries. All five have
  dev; baseline and selected hybrid-wide also have held-out test.
- `codex-dev-review.json`, `codex-test-review.json`: direct AI source inspection and
  changes to judge labels. `test_inspection_decisions.json` binds decisions to the
  exact trace files inspected. No human review is claimed.
- `author_review_pending.csv`: blank confirmation fields for the student's review.
- `pretest_corrections.json`: transparent repair of inline citation counting before
  selection; the original answer text and provider output are preserved.
- `ENVIRONMENT.md`, `runtime.json`: actual execution environment and initial failures.
- `verification.json`: source-offset, freeze, vector and evaluation consistency checks.
- `current_validation.json`: current project environment, installed versions, test
  results, rebuilt real Chroma store and neural-embedding agreement. It complements
  the original benchmark runtime record and sends no model API requests.
- `costs.json`: trace-bound retrospective estimates for agent and audit, from the
  dated public ModelAPI pricing snapshot under `data/pricing/`. Group/account
  multipliers and incomplete initial probes prevent treating this as an invoice.

The synthetic heuristic demonstration under `starter/results/` is not this evaluation.
Final artifacts are deliberately tracked under `results/`; source/model caches and
credentials are excluded. See the report and RUNBOOK for reproducible stage commands.
Use `--results-root .runs/replay-01` to repeat all stages without changing these
artifacts. Named reviewers can export/import explicit trace-bound decisions;
the original Codex review markers are not required for new experiments.
