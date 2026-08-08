"""Seed the Klarnova database with a bootstrap admin user, policy rules, and KB docs."""
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.domain import KnowledgeDoc, Policy, User
import yaml


SEV_BY_KEY = {
    "sev_1": "SEV-1",
    "sev_2": "SEV-2",
    "sev_3": "SEV-3",
    "sev_4": "SEV-4",
}


def load_policy_rules() -> list[dict]:
    rules_path = BACKEND_DIR / "app" / "policy" / "rules" / "default.yaml"
    with open(rules_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    rules = []
    for action, sev_map in (data.get("actions") or {}).items():
        if "default" in sev_map:
            sev_map = {**sev_map, **{k: sev_map["default"] for k in SEV_BY_KEY}}
        for sev_key, mode in sev_map.items():
            severity = SEV_BY_KEY.get(sev_key)
            if severity and mode in ("auto", "require_approval"):
                rules.append({"action": action, "severity": severity, "mode": mode})
    return rules


SAMPLE_KB_DOCS = [
    {
        "source_url": "kb://runbooks/oomkilled",
        "doc_type": "runbook",
        "content": "OOMKilled: increase memory limits, move stateful load, restart pod.",
    },
    {
        "source_url": "kb://runbooks/crashloop",
        "doc_type": "runbook",
        "content": "CrashLoopBackOff: check config, previous logs, rollback deployment.",
    },
    {
        "source_url": "kb://runbooks/imagenotfound",
        "doc_type": "runbook",
        "content": "ImagePullBackOff: verify image tag, check registry credentials, update deployment.",
    },
]


async def main() -> None:
    async with SessionLocal() as session:
        existing = (await session.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if existing is None:
            session.add(
                User(
                    username="admin",
                    hashed_password=hash_password("admin-password"),
                    role="Admin",
                )
            )
            print("Seeded admin user (admin / admin-password)")
        else:
            print("Admin user already exists")

        rules = load_policy_rules()
        for rule in rules:
            exists = (
                await session.execute(
                    select(Policy).where(
                        Policy.action == rule["action"],
                        Policy.severity == rule["severity"],
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    Policy(
                        action=rule["action"],
                        severity=rule["severity"],
                        execution_mode=rule["mode"],
                    )
                )
        print(f"Seeded {len(rules)} policy action rules")

        for doc in SAMPLE_KB_DOCS:
            exists = (
                await session.execute(
                    select(KnowledgeDoc).where(KnowledgeDoc.source_url == doc["source_url"])
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    KnowledgeDoc(
                        source_url=doc["source_url"],
                        doc_type=doc["doc_type"],
                        content_hash=str(hash(doc["content"])),
                    )
                )
        print("Seeded sample KB docs")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
