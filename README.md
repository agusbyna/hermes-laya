# hermes-laya

[Laya](https://github.com/receptron/laya) System-1 typed decisions as a
[Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin.

Laya classifies text against typed questions in **one local CPU forward pass**
with calibrated probabilities. It never generates text — it is the fast,
deterministic first read (triage, routing, urgency, risk flags) before the
LLM does any actual reasoning.

## Tools

### `laya_triage`

Pre-built message triage, one call:

```json
{
  "text": "Pasien pingsan di ruang tunggu, tolong sekarang!"
}
```

Returns:

```json
{
  "success": true,
  "department": "ops",
  "department_confidence": 0.99,
  "department_probabilities": {"billing": 0.0, "ops": 0.99, "clinical": 0.01, "technical": 0.0},
  "urgency_score": 1.95,
  "urgency_label": "emergency",
  "escalation_probability": 0.263,
  "model": "multilingual",
  "latency_ms": 412,
  "usage": {"input_tokens": 210, "truncated": false}
}
```

Custom routing targets via the optional `departments` object
(label -> gloss).

### `laya_predict`

Full typed-decision surface — batch any mix of question types in one pass:

```json
{
  "state": "We were billed twice for March. Refund the duplicate today.",
  "questions": {
    "intent":    {"type": "choice", "instructions": "What does the customer want?",
                  "criteria": {"refund": "money returned or duplicate charge reversed",
                               "technical_help": "a bug or outage",
                               "question": "general question"}},
    "urgency":   {"type": "score", "instructions": "How urgent?",
                  "criteria": ["can wait", "today", "blocking"]},
    "is_threat": {"type": "noul", "instructions": "Does the customer threaten to cancel?"}
  },
  "min_confidence": 0.8
}
```

| type | criteria | returns |
|---|---|---|
| `choice` | dict label -> gloss, or list | `choice` + `probabilities` |
| `score` | ordered list, low -> high | `score` = expected level (float) |
| `noul` | optional `{false, true}` glosses | `noul` = calibrated P(true) |

Options: `model` (`multilingual` default — use it for non-English text),
`max_len` (long documents), `min_confidence` (abstain below threshold).

## Install

```bash
hermes plugins install agusbyna/hermes-laya
hermes plugins enable hermes-laya
```

The install flow asks for consent before pulling the Python dependencies
(`laya`, which brings PyTorch — expect a ~2 GB download on first enable).
On first tool call the checkpoint downloads from Hugging Face (~1.5 GB,
cached afterwards).

Verify:

```bash
hermes plugins doctor hermes-laya --ci
hermes plugins list
```

## Performance & resources (measured)

- First call per process: **~15-30 s** one-time checkpoint load.
  Subsequent calls: **~0.3-0.7 s** per short message on CPU.
- Resident memory: **~2 GB** once the model is loaded.
- Outputs are fully deterministic; question order does not affect results.
- Every Router build does a Hugging Face revision check. With both
  checkpoints cached you can set `HF_HUB_OFFLINE=1` in `~/.hermes/.env` to
  skip it (verified working).

## Config

Set via `hermes config set plugins.entries.hermes-laya.config.<key> <value>`
or the Desktop plugins tab:

| key | default | meaning |
|---|---|---|
| `default_model` | `multilingual` | checkpoint (`multilingual` / `english` / `typed-decisions`) |
| `max_len` | `0` | state token budget; `0` = checkpoint default (1024 multilingual / 512 english) |

## Bundled skill

`hermes-laya:laya-system1` documents the question types, the measured rubric
behavior (over-triage bias, `noul` vs `score`, calibration limits), and the
operational pitfalls. Load it with `skill_view("hermes-laya:laya-system1")`.

## Limits (be honest with yourself)

- This is System 1: right for triage, routing, urgency, yes/no risk flags;
  wrong for anything needing reasoning over the text.
- `score` levels are not calibrated thresholds — the triage rubric is
  example-anchored and deliberately biased toward over-triage (in testing it
  never under-flagged an emergency, but routine items can land at `soon`).
  Read probabilities, not just labels.
- Department routing on Indonesian tickets measured 4/8 correct with gloss
  tuning; the checkpoint is the bottleneck, not the rubric.

## Credits & license

- [Laya](https://github.com/receptron/laya) by Receptron — Apache-2.0.
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research.
- This plugin: Apache-2.0.
