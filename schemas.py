"""Tool schemas — what the LLM reads to decide when to call these tools."""

LAYA_PREDICT = {
    "name": "laya_predict",
    "description": (
        "Run Laya System-1 typed decisions over a piece of text: classify it "
        "(choice), rate an ordinal level (score), or get a calibrated yes/no "
        "probability (noul) — all in one fast local forward pass with "
        "per-option probabilities. Use for triage, routing, intent, urgency, "
        "or risk flags (spam/phishing/churn/danger) where a quick typed answer "
        "beats reading the text again. Do NOT use it for anything needing "
        "reasoning, comparison, summarization, or generated text — that is "
        "your job as the LLM; Laya never generates text. First call pays a "
        "one-time model load (~15-30 s), later calls are sub-second on CPU."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "description": "The text to classify (message, ticket, document, ...).",
            },
            "questions": {
                "type": "object",
                "description": (
                    "Object mapping question ids to question definitions. Each "
                    "question is {type, instructions, criteria} where type is "
                    "'choice' (criteria: object of label -> gloss, or list of "
                    "labels; returns choice + probabilities), 'score' (criteria: "
                    "ordered list of level descriptions, low -> high; returns "
                    "expected level as a float), or 'noul' (criteria optional; "
                    "returns calibrated P(true) 0..1). Example: "
                    '{"dept": {"type": "choice", "instructions": "Which department?", '
                    '"criteria": {"billing": "invoices, refunds", "tech": "bugs, outages"}}}'
                ),
                "additionalProperties": True,
            },
            "model": {
                "type": "string",
                "enum": ["multilingual", "english", "typed-decisions"],
                "description": (
                    "Checkpoint override. Default from plugin config "
                    "(multilingual). Always use multilingual for non-English "
                    "text: auto-routing sends Latin-script non-English text to "
                    "the english checkpoint and loses accuracy."
                ),
            },
            "max_len": {
                "type": "integer",
                "description": (
                    "Token budget for the state. 0/omitted = checkpoint "
                    "default (1024 multilingual / 512 english). Raise it for "
                    "long texts — otherwise usage.truncated comes back true "
                    "and state_tokens_dropped tells you how much was cut."
                ),
            },
            "min_confidence": {
                "type": "number",
                "description": (
                    "Gate answers below this confidence: they come back with "
                    "low_confidence=true and an abstention field instead of a "
                    "clean answer. Use when a wrong System-1 call is worse "
                    "than falling back to reading the text yourself."
                ),
            },
        },
        "required": ["state", "questions"],
    },
}

LAYA_TRIAGE = {
    "name": "laya_triage",
    "description": (
        "Triage an inbound message with Laya's pre-built rubric: routing "
        "department (with probabilities), urgency as an ordinal level "
        "(routine / soon / emergency, 0..2 with expected-value score), and a "
        "calibrated human-escalation probability. Convenience wrapper over "
        "laya_predict for the common ticket/message triage case — use "
        "laya_predict instead when you need custom questions. The urgency "
        "rubric is example-anchored and biased toward over-triage (it never "
        "under-flagged emergencies in testing, but may label routine "
        "appointments 'soon'); read the probabilities, not just the labels."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The message or ticket to triage.",
            },
            "departments": {
                "type": "object",
                "description": (
                    "Optional override of routing targets: object mapping "
                    "department label -> short gloss describing what belongs "
                    "there. Defaults to billing / clinical / ops / technical."
                ),
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["text"],
    },
}
