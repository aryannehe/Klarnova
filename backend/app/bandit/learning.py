"""Bandit learning loop: reward remediation outcomes and persist them.

Runs after every remediation attempt (auto path and approval path). Only
actions that actually executed and were whitelisted produce training signal.
"""
import logging

from sqlalchemy import select

from app.bandit.model import bandit, build_context
from app.core.database import SessionLocal
from app.models.domain import BanditPolicy
from app.policy.engine import WHITELIST

logger = logging.getLogger(__name__)

_DEFAULT_CONTEXT = {
    "severity": "SEV-3",
    "metrics": {},
    "resource_kind": "pod",
}


def selected_action(state) -> str | None:
    action = (state.get("selected_action") or {}).get("action_type")
    return action if action in WHITELIST else None


def reward_for(state) -> float | None:
    """1.0 resolved, 0.0 attempted-but-failed, None if nothing executed."""
    if not state.get("remediation_success"):
        return None
    return 1.0 if state.get("is_resolved") else 0.0


async def record_learning(state) -> None:
    action = selected_action(state)
    reward = reward_for(state)
    if action is None or reward is None:
        return

    await bandit.partial_fit(action, reward, build_context(state))

    labels = (state.get("incident_data") or {}).get("labels") or {}
    category = labels.get("alertname", "unknown")
    try:
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(BanditPolicy).where(
                        BanditPolicy.action == action,
                        BanditPolicy.incident_category == category,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                session.add(
                    BanditPolicy(
                        incident_category=category,
                        action=action,
                        reward=reward,
                        update_count=1,
                    )
                )
            else:
                total = (row.reward or 0.0) * (row.update_count or 0) + reward
                row.update_count = (row.update_count or 0) + 1
                row.reward = total / row.update_count
            await session.commit()
    except Exception as exc:
        logger.warning("bandit learning persistence failed: %s", exc)


async def seed_bandit_from_db() -> None:
    """Replay persisted rewards so learned policy survives restarts."""
    try:
        async with SessionLocal() as session:
            rows = (await session.execute(select(BanditPolicy))).scalars().all()
    except Exception as exc:
        logger.warning("bandit seed from db failed: %s", exc)
        return
    for row in rows:
        await bandit.partial_fit(
            row.action,
            float(row.reward or 0.0),
            build_context(dict(_DEFAULT_CONTEXT)),
        )
    if rows:
        logger.info("bandit seeded from %d persisted policy rows", len(rows))
