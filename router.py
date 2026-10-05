"""Automatic model routing middleware (ala jev-route, classifier Laya lokal).

Tiap LLM request: ambil teks prompt user terakhir -> Laya noul
"needs_depth" (multilingual) -> p >= threshold berarti advanced.
p < threshold berarti simple -> tulis ulang request["model"].

Semua parameter dari config plugin (ctx.get_config), jadi tanpa edit kode:
  route_enabled (default True), route_threshold (default 0.6),
  route_simple_model (default "" = jangan ganti), route_advanced_model
  (default "" = jangan ganti), route_max_chars (default 4000).

Gagal klasifikasi (paket laya belum terinstal, checkpoint rusak) -> request
dilewatkan apa adanya, tidak pernah menggagalkan turn.
"""
import json

from .tools import _config as _get_config
from .tools import _get_router

NEEDS_DEPTH_QUESTIONS = {
    "needs_depth": {
        "type": "noul",
        "instructions": (
            "Does completing this request correctly require debugging, "
            "investigation, architecture or design judgment, resolving "
            "ambiguity, or multi-step reasoning? Answer yes only if the work "
            "goes beyond applying one clear procedure or fact."
        ),
    }
}

# Diukur 2026-10-05, 16 prompt ID+EN (8 simple / 8 advanced):
# threshold 0.6 -> 14/16 (88%), advanced 8/8, simple 6/8.
# 2 miss keduanya false-advanced (fakta dan typo disangka dalam).
DEFAULT_THRESHOLD = 0.6


def _last_user_text(request):
    messages = request.get("messages") or []
    for msg in reversed(messages):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts = [
                p.get("text", "")
                for p in content
                if isinstance(p, dict) and p.get("type") in ("text", "input_text")
            ]
            text = "".join(parts).strip()
            if text:
                return text
    return ""


def classify(text, ctx=None):
    """Kembalikan (route, probability) atau (None, None) bila gagal."""
    model = _get_config(ctx, "default_model", "multilingual")
    threshold = float(_get_config(ctx, "route_threshold", DEFAULT_THRESHOLD))
    try:
        router = _get_router()
        result = router.predict(text, NEEDS_DEPTH_QUESTIONS, model=model)
        prob = float(result["answers"]["needs_depth"]["noul"])
    except Exception:
        return None, None
    return ("advanced" if prob >= threshold else "simple"), prob


def route_middleware(request=None, **kwargs):
    request = dict(request or {})
    if "model" not in request:
        return {"request": request}
    from . import tools as _tools

    ctx = _tools._route_ctx
    if not _get_config(ctx, "route_enabled", True):
        return {"request": request}
    # Zero-cost bila target model belum diisi: tidak ada yang bisa diganti,
    # jadi lewati klasifikasi sepenuhnya (hemat ~2GB RAM + ~0.5s per turn).
    simple_target = _get_config(ctx, "route_simple_model", "") or ""
    advanced_target = _get_config(ctx, "route_advanced_model", "") or ""
    if not simple_target and not advanced_target:
        return {"request": request}
    text = _last_user_text(request)
    if not text:
        return {"request": request}
    max_chars = int(_get_config(ctx, "route_max_chars", 4000) or 4000)
    route, prob = classify(text[:max_chars], ctx)
    if route is None:
        return {"request": request}
    target = simple_target if route == "simple" else advanced_target
    if not target or target == request.get("model"):
        return {
            "request": request,
            "source": "hermes-laya",
            "reason": f"routed-{route} p={prob:.2f} (keep {request.get('model')})",
        }
    request["model"] = target
    return {
        "request": request,
        "source": "hermes-laya",
        "reason": f"routed-{route} p={prob:.2f} -> {target}",
    }


def route_status(args=None, ctx=None, **kwargs):
    """Tool baca-status: threshold aktif, model target, hasil klasifikasi teks."""
    args = args or {}
    payload = {
        "enabled": bool(_get_config(ctx, "route_enabled", True)),
        "threshold": float(_get_config(ctx, "route_threshold", DEFAULT_THRESHOLD)),
        "simple_model": _get_config(ctx, "route_simple_model", "") or "",
        "advanced_model": _get_config(ctx, "route_advanced_model", "") or "",
        "classifier": "laya-noul needs_depth (multilingual)",
    }
    text = args.get("text") or ""
    if isinstance(text, str) and text.strip():
        route, prob = classify(text[:4000], ctx)
        payload["probe"] = {"route": route, "p_depth": prob}
    return json.dumps({"success": True, **payload}, ensure_ascii=False)


ROUTE_STATUS_SCHEMA = {
    "name": "laya_route_status",
    "description": (
        "Show the automatic model-routing state (enabled, threshold, target "
        "models) and optionally classify a probe text. Routing itself runs "
        "silently as llm_request middleware on every turn; this tool only "
        "inspects it, it never changes routing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Optional probe text to classify (simple/advanced + probability).",
            },
        },
    },
}
