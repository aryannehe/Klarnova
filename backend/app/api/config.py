"""Admin configuration endpoints (Epic G9).

Risk-policy editor and knowledge-base administration. Reads are available to
admin/engineer; writes are admin-only. The risk policy YAML file remains the
single source of truth consumed by ``policy/engine.load_rules``.
"""
import asyncio
import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.database import SessionLocal, get_db
from app.core.rbac import require_roles
from app.models.domain import AuditLog, KnowledgeDoc, Policy
from app.policy.engine import RULES_PATH, SEV_ORDER, WHITELIST, load_rules
from app.rag.ingest import sources_path
from app.rag.store import vector_store

router = APIRouter()
logger = logging.getLogger(__name__)

MODES = ("auto", "require_approval")
SEV_BY_KEY = {f"sev_{n}": f"SEV-{n}" for n in SEV_ORDER.values()}

POLICY_HEADER = (
    "# Klarnova risk policy - declarative, severity-aware.\n"
    "# Maps (action, severity) -> execution mode: auto | require_approval\n"
    "# SEV-1 always requires approval regardless of this table or confidence\n"
    "# (hard rule enforced in policy/engine.py).\n"
)


class PolicyUpdate(BaseModel):
    action: str
    severity: str  # sev_1..sev_4, or "default"
    execution_mode: str


@router.get("/policy")
async def get_policy(
    _: dict = Depends(require_roles("admin", "engineer")),
):
    rules = load_rules()
    return {
        "whitelist": WHITELIST,
        "severity_order": SEV_ORDER,
        "confidence_threshold": rules.get("confidence_threshold", 0.75),
        "actions": rules.get("actions", {}),
    }


@router.put("/policy/rules")
async def update_policy_rule(
    body: PolicyUpdate,
    current_user: dict = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    if body.action not in WHITELIST:
        raise HTTPException(
            status_code=400,
            detail=f"action '{body.action}' is not on the safe-action whitelist",
        )
    if body.severity != "default" and body.severity not in SEV_BY_KEY:
        raise HTTPException(
            status_code=400,
            detail=f"severity must be one of {', '.join(SEV_BY_KEY)} or 'default'",
        )
    if body.execution_mode not in MODES:
        raise HTTPException(
            status_code=400,
            detail="execution_mode must be 'auto' or 'require_approval'",
        )

    rules = load_rules()
    action_rules = rules.setdefault("actions", {}).setdefault(body.action, {})
    action_rules[body.severity] = body.execution_mode
    Path(RULES_PATH).write_text(
        POLICY_HEADER + yaml.safe_dump(rules, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    load_rules.cache_clear()

    severity = SEV_BY_KEY.get(body.severity)
    if severity is not None:
        row = (
            await db.execute(
                select(Policy).where(
                    Policy.action == body.action,
                    Policy.severity == severity,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            db.add(
                Policy(
                    action=body.action,
                    severity=severity,
                    execution_mode=body.execution_mode,
                )
            )
        else:
            row.execution_mode = body.execution_mode
    db.add(
        AuditLog(
            actor=current_user["username"],
            action="policy_updated",
            target=body.action,
            details={"severity": body.severity, "execution_mode": body.execution_mode},
        )
    )
    await db.commit()

    return {
        "whitelist": WHITELIST,
        "severity_order": SEV_ORDER,
        "confidence_threshold": rules.get("confidence_threshold", 0.75),
        "actions": rules.get("actions", {}),
    }


@router.get("/knowledge/sources")
async def knowledge_sources(
    _: dict = Depends(require_roles("admin", "engineer", "viewer")),
):
    path = str(sources_path())
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    collections = {}
    for group, entries in (data.get("collections") or {}).items():
        collections[group] = [
            {
                "id": entry.get("id"),
                "title": entry.get("title", ""),
                "source": entry.get("source", ""),
            }
            for entry in entries
        ]
    return {"path": path, "collections": collections}


@router.post("/knowledge/refresh")
async def refresh_knowledge(
    current_user: dict = Depends(require_roles("admin")),
):
    try:
        from app.rag.ingest import run_ingest

        count = await asyncio.to_thread(run_ingest, True)
    except Exception as exc:
        logger.warning("knowledge refresh failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"knowledge refresh failed: {exc}",
        ) from None

    async with SessionLocal() as session:
        session.add(
            AuditLog(
                actor=current_user["username"],
                action="knowledge_refresh",
                details={"added": count},
            )
        )
        await session.commit()
    return {"added": count}


@router.get("/knowledge/docs")
async def knowledge_docs(
    db=Depends(get_db),
    _: dict = Depends(require_roles("admin", "engineer", "viewer")),
):
    docs = (
        await db.execute(
            select(KnowledgeDoc).order_by(KnowledgeDoc.last_ingested.desc()).limit(200)
        )
    ).scalars().all()
    return {
        "docs": [
            {
                "id": d.id,
                "source_url": d.source_url,
                "doc_type": d.doc_type,
                "content_hash": d.content_hash,
                "last_ingested": d.last_ingested,
            }
            for d in docs
        ],
        "count": len(docs),
        "collections": vector_store.counts(),
    }
