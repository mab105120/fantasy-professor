"""Pydantic models that define every structured artifact the agent writes:
report envelopes (schemas.report), shared building blocks (schemas.common),
and season memory (schemas.memory). These classes are the single source of
truth: `fp` validates against them, JSON Schema is exported from them, and the
frontend types are generated from that schema."""


def json_schemas() -> dict[str, dict]:
    """File stem -> JSON Schema for every exported model, as written to
    schemas/json/<stem>.schema.json by `fp report schema`."""
    from .memory import Proposals, SeasonMemory
    from .report import Report

    models = {"report": Report, "season-memory": SeasonMemory, "proposals": Proposals}
    return {name: model.model_json_schema() for name, model in models.items()}
