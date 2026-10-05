"""Handlers for hermes-laya. Every handler returns a JSON string."""
import json
import time

# Module-global Router: one model load per process (matches the laya skill's
# guidance — rebuilding Router per call re-does routing setup).
_router = None
_load_error = None

# Diset oleh register(): ctx plugin agar middleware llm_request (yang tidak
# menerima ctx) bisa membaca config routing. None = pakai default.
_route_ctx = None

URGENCY_INSTRUCTIONS = (
    "How urgent is this? A mentioned date or time never raises urgency by "
    "itself; rate by harm if nothing is done."
)
URGENCY_CRITERIA = [
    "routine: billing questions, refunds, general inquiries, asking about or "
    "booking an appointment for a future time such as tomorrow at 10am",
    "soon: broken facilities, same-day service problems, anything resolved "
    "within today",
    "emergency: a person fainting, not breathing, bleeding, exposed to gas or "
    "fire, or any active danger",
]
URGENCY_LABELS = ["routine", "soon", "emergency"]

DEFAULT_DEPARTMENTS = {
    "billing": "tagihan, invoice, pembayaran, refund",
    "clinical": "keluhan pasien, gejala, obat, janji temu",
    "ops": "antrean, jadwal dokter, reservasi, fasilitas",
    "technical": "aplikasi error, login gagal, sistem down",
}

ESCALATE_INSTRUCTIONS = (
    "Does this describe a life-threatening emergency or active danger "
    "requiring a human responder right now?"
)


def _ok(**fields):
    payload = {"success": True}
    payload.update(fields)
    return json.dumps(payload, ensure_ascii=False)


def _err(message, **extra):
    payload = {"success": False, "error": message}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _get_router():
    """Lazy-load the checkpoint on first call; cache it for the process."""
    global _router, _load_error
    if _router is not None:
        return _router
    if _load_error is not None:
        raise RuntimeError(_load_error)
    try:
        from laya import Router
    except ImportError:
        _load_error = (
            "python package 'laya' is not installed in this Hermes "
            "environment. Re-enable the plugin and accept the dependency "
            "install prompt: hermes plugins enable hermes-laya"
        )
        raise RuntimeError(_load_error)
    _router = Router()
    return _router


def _config(ctx, key, default):
    if ctx is None:
        return default
    try:
        cfg = ctx.get_config() or {}
    except Exception:
        return default
    value = cfg.get(key, default)
    return default if value is None else value


def laya_predict(args, ctx=None, **kwargs):
    """Generic typed decisions: choice / score / noul questions in one pass."""
    state = args.get("state")
    questions = args.get("questions")
    if not isinstance(state, str) or not state.strip():
        return _err("state must be a non-empty string")
    if not isinstance(questions, dict) or not questions:
        return _err(
            "questions must be a non-empty object mapping question ids to "
            "{type, instructions, criteria} definitions"
        )

    model = args.get("model") or _config(ctx, "default_model", "multilingual")
    max_len = args.get("max_len") or _config(ctx, "max_len", 0) or None
    kwargs_predict = {"model": model}
    if max_len:
        kwargs_predict["max_len"] = int(max_len)
    if args.get("min_confidence") is not None:
        kwargs_predict["min_confidence"] = float(args["min_confidence"])

    started = time.time()
    try:
        router = _get_router()
        result = router.predict(state, questions, **kwargs_predict)
    except Exception as exc:  # never let a tool call raise into the dispatcher
        return _err(f"laya predict failed: {exc}")

    return _ok(
        answers=result.get("answers", {}),
        usage=result.get("usage", {}),
        model=(result.get("routing") or {}).get("model", model),
        latency_ms=round((time.time() - started) * 1000),
    )


def laya_triage(args, ctx=None, **kwargs):
    """Pre-built message triage: department, urgency, escalation probability."""
    text = args.get("text")
    if not isinstance(text, str) or not text.strip():
        return _err("text must be a non-empty string")

    departments = args.get("departments") or DEFAULT_DEPARTMENTS
    if not isinstance(departments, dict) or not departments:
        return _err("departments must be an object mapping label -> gloss")

    model = args.get("model") or _config(ctx, "default_model", "multilingual")
    questions = {
        "department": {
            "type": "choice",
            "instructions": "Which department should handle this message?",
            "criteria": departments,
        },
        "urgency": {
            "type": "score",
            "instructions": URGENCY_INSTRUCTIONS,
            "criteria": URGENCY_CRITERIA,
        },
        "escalation": {
            "type": "noul",
            "instructions": ESCALATE_INSTRUCTIONS,
        },
    }

    started = time.time()
    try:
        router = _get_router()
        result = router.predict(text, questions, model=model)
    except Exception as exc:
        return _err(f"laya triage failed: {exc}")

    answers = result.get("answers", {})
    dept = answers.get("department", {})
    urg = answers.get("urgency", {})
    esc = answers.get("escalation", {})
    score = float(urg.get("score", 0.0))
    label_idx = 0 if score < 0.5 else 1 if score < 1.5 else 2

    return _ok(
        department=dept.get("choice"),
        department_confidence=dept.get("confidence"),
        department_probabilities=dept.get("probabilities"),
        urgency_score=round(score, 3),
        urgency_label=URGENCY_LABELS[label_idx],
        escalation_probability=round(float(esc.get("noul", 0.0)), 4),
        usage=result.get("usage", {}),
        model=(result.get("routing") or {}).get("model", model),
        latency_ms=round((time.time() - started) * 1000),
        note=(
            "System-1 output: fast typed decisions, not reasoning. Urgency "
            "tends to over-flag (safe direction); confirm before acting on a "
            "single field."
        ),
    )
