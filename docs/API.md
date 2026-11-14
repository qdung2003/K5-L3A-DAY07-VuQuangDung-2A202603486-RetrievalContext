# Model integration

The agent uses the Responses API with a `search` function tool. The model chooses
retrieval, optionally rewrites a follow-up query, then returns answer JSON. The
application validates tool arguments, retrieval limits and final citation IDs.
Semantic support still needs inspection; valid citation IDs alone are insufficient.

Official reference: https://developers.openai.com/api/docs/guides/function-calling

Function calls are sent back as `function_call_output` with the matching `call_id`.
Reasoning and tool-call output items are retained in model input, and the newest
cumulative context replaces older tool-output context. The first retrieval uses
the original question in every configuration; the trace records both the model's
requested arguments and the query actually executed. Filters come only from user
input in the benchmark, never from evidence labels.

The application reads `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` and optional
`OPENAI_REASONING_EFFORT` from the project `.env` or explicit `--env-file`.
Process environment variables take precedence. The agent and AI audit use this same
configuration; experiment templates contain only retrieval settings. Resolved model
and reasoning are recorded with each run. Existing frozen test selections require
the same model and reasoning used on dev. No credentials are written to results,
run metadata or reports.

`--results-root` isolates new experiments, their labels, selection and costs.
Resume validates existing output before requesting the model and does not replace
frozen dev artifacts. Public price estimates are stored separately from frozen
traces, with model/token/group assumptions and data fingerprints.
The user authorized sending the public Python Tutorial context and study questions
to the configured OpenAI API on 2026-11-14, including possible API charges.

Token usage and provider response IDs are recorded. Dollar cost is left unknown
when actual account rates are unavailable; it must not be reported as zero.
AI audit token use is recorded separately in each review and is not agent token use.
