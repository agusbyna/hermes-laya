"""hermes-laya — Laya System-1 typed decisions for Hermes Agent.

Layout per the Hermes plugin guide: plugin.yaml declares what the plugin is,
schemas.py describes the tools for the LLM, tools.py implements the handlers,
and register(ctx) wires everything together.
"""
from pathlib import Path


def register(ctx):
    from . import schemas, tools

    ctx.register_tool(
        name="laya_predict",
        toolset="laya",
        schema=schemas.LAYA_PREDICT,
        handler=lambda args, **kw: tools.laya_predict(args, ctx=ctx, **kw),
    )
    ctx.register_tool(
        name="laya_triage",
        toolset="laya",
        schema=schemas.LAYA_TRIAGE,
        handler=lambda args, **kw: tools.laya_triage(args, ctx=ctx, **kw),
    )

    # Bundle skills: read-only, loaded later via skill_view("<plugin>:<dir>").
    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)
