---
name: laya-system1
description: Use hermes-laya tools (laya_predict / laya_triage) correctly — question types, measured rubric behavior, and pitfalls.
---

# Laya System-1 via hermes-laya

Two tools, both local CPU inference through the `laya` package. Laya never
generates text: it classifies a `state` against typed `questions` in one
forward pass with calibrated probabilities.

## Which tool

- **`laya_triage`** — inbound message/ticket triage with a fixed rubric:
  department (choice), urgency 0..2 + label (score), human-escalation P (noul).
  Default departments: billing / clinical / ops / technical.
- **`laya_predict`** — anything custom. Pass your own `questions` object.

## Question types (laya_predict)

| type | criteria | returns |
|---|---|---|
| `choice` | dict label -> gloss (or list of labels) | `choice` + `probabilities` |
| `score` | ordered list, low -> high | `score` = expected level, float 0..n-1 |
| `noul` | optional `{false: ..., true: ...}` glosses | `noul` = calibrated P(true) 0..1 |

All three run in the same pass — batch every question about one text into a
single call instead of several.

## Measured behavior (verified against laya 0.3.23)

- Outputs are fully deterministic; wording of `instructions`/`criteria` is the
  only lever. Question order in the dict does not matter.
- `score` absolute levels are NOT calibrated. Abstract 1-3 word rubric levels
  drift to mid-high for neutral text. Example-anchored levels
  ("routine: billing questions, refunds, ...") are the fix — that is what
  `laya_triage` ships. Failure mode is over-triage only: routine items can
  land at "soon", but emergencies were never under-flagged in testing.
- `noul` ranks much better in absolute terms (routine ~0.00-0.02 vs
  non-routine 0.11-0.55). Prefer it for yes/no flags; no fixed threshold
  cleanly splits three tiers, so do not mint graded levels from one noul.
- `choice` with 11+ options has uncalibrated confidence (upstream checkpoint
  warning). Keep option counts small.
- Department routing on Indonesian tickets is mediocre (measured 4/8 with
  gloss tweaks) — read `department_probabilities`, and re-ask with custom
  `departments` glosses if the top probability is close.

## Operational pitfalls

- First call per process loads the checkpoint: ~15-30 s one-time, then
  ~0.3-0.7 s per call. Do not treat the first call as a timeout.
- Checkpoint needs ~2 GB resident. On a small-RAM box avoid holding it next
  to a browser plus other ML processes.
- Long texts: raise `max_len` (checkpoint default 1024 tokens multilingual).
  When truncation happens the `usage` block says so (`truncated: true`,
  `state_tokens_dropped`) — read it, it is not silent.
- Every Router build talks to the Hugging Face hub for a revision check.
  Set `HF_HUB_OFFLINE=1` in `~/.hermes/.env` to skip it once checkpoints
  are cached (verified working).
- Use `min_confidence` when a wrong System-1 call is worse than falling back
  to reading the text yourself: sub-threshold answers return
  `low_confidence: true` plus an `abstention` field.
- Model choice: pass `multilingual` explicitly for non-English text.
  Auto-routing sends Latin-script non-English text to the english
  checkpoint and loses accuracy.
- This is System 1. Right tool for triage, routing, urgency, risk flags.
  Wrong tool for anything needing reasoning over the text.
