"""Seed a minimal active knowledge-answer configuration snapshot.

Usage:
  backend/venv/bin/python backend/scripts/seed_knowledge_answer_config.py
  backend/venv/bin/python backend/scripts/seed_knowledge_answer_config.py --version-name rollout-v1
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from common.db.models import (  # noqa: E402
    KnowledgeAnswerabilityProfile,
    KnowledgeConfigVersion,
    KnowledgeEntityAlias,
    KnowledgeIntentRule,
    KnowledgeQueryProfile,
    KnowledgeRankingProfile,
)

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


DEFAULT_VERSION_NAME = "knowledge-answer-default-v1"
_DEFAULT_CREATED_BY = os.getenv("KNOWLEDGE_ANSWER_SEED_CREATED_BY", "seed_script").strip() or "seed_script"


def _to_sync_database_url(database_url: str) -> str:
    return (
        database_url.replace("+asyncpg", "+psycopg2")
        .replace("+aiosqlite", "")
        .strip()
    )


def _build_session_local() -> sessionmaker:
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ai_practice.db").strip()
    sync_database_url = _to_sync_database_url(database_url or "sqlite:///./ai_practice.db")
    sync_engine = create_engine(sync_database_url, poolclass=NullPool)
    return sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


def seed_knowledge_answer_config(
    db_session: Session,
    *,
    version_name: str = DEFAULT_VERSION_NAME,
    notes: str | None = None,
) -> dict[str, Any]:
    existing = db_session.execute(
        select(KnowledgeConfigVersion).where(KnowledgeConfigVersion.version_name == version_name)
    ).scalar_one_or_none()
    if existing is not None:
        _activate_only(db_session, active_version=existing)
        return {
            "created": False,
            "config_version_id": existing.id,
            "version_name": existing.version_name,
        }

    version = KnowledgeConfigVersion(
        version_name=version_name,
        status="active",
        enabled=True,
        notes=notes or "Seeded default knowledge-answer rollout profiles.",
        created_by=_DEFAULT_CREATED_BY,
        updated_by=_DEFAULT_CREATED_BY,
    )
    db_session.add(version)
    db_session.flush()

    _seed_query_profiles(db_session, version.id)
    _seed_intent_rules(db_session, version.id)
    _seed_entity_aliases(db_session, version.id)
    _seed_ranking_profiles(db_session, version.id)
    _seed_answerability_profiles(db_session, version.id)
    _activate_only(db_session, active_version=version)

    return {
        "created": True,
        "config_version_id": version.id,
        "version_name": version.version_name,
    }


def _activate_only(db_session: Session, *, active_version: KnowledgeConfigVersion) -> None:
    versions = db_session.execute(select(KnowledgeConfigVersion)).scalars().all()
    for version in versions:
        version.enabled = True
        version.status = "active" if version.id == active_version.id else "archived"
        version.updated_by = _DEFAULT_CREATED_BY
    db_session.commit()


def _seed_query_profiles(db_session: Session, config_version_id: str) -> None:
    db_session.add_all(
        [
            KnowledgeQueryProfile(
                config_version_id=config_version_id,
                profile_key="product_overview",
                description="产品介绍/是什么/做什么类问答。",
                rewrite_strategy="multi_query",
                max_rewrite_queries=4,
                stop_after_first_success=True,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeQueryProfile(
                config_version_id=config_version_id,
                profile_key="pricing_lookup",
                description="价格/报价/多少钱类问答。",
                rewrite_strategy="single_query",
                max_rewrite_queries=1,
                stop_after_first_success=False,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeQueryProfile(
                config_version_id=config_version_id,
                profile_key="version_compare",
                description="版本区别/对比类问答。",
                rewrite_strategy="multi_query",
                max_rewrite_queries=3,
                stop_after_first_success=False,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeQueryProfile(
                config_version_id=config_version_id,
                profile_key="coaching_guidance",
                description="怎么讲/怎么回答/辅导建议类问答。",
                rewrite_strategy="single_query",
                max_rewrite_queries=1,
                stop_after_first_success=False,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
        ]
    )


def _seed_intent_rules(db_session: Session, config_version_id: str) -> None:
    db_session.add_all(
        [
            KnowledgeIntentRule(
                config_version_id=config_version_id,
                intent_key="company_intro",
                priority=10,
                match_type="regex",
                pattern="介绍一下.*石犀科技",
                profile_key="product_overview",
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeIntentRule(
                config_version_id=config_version_id,
                intent_key="pricing_query",
                priority=20,
                match_type="entity_keyword_contains",
                pattern="价格|报价|多少钱",
                profile_key="pricing_lookup",
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeIntentRule(
                config_version_id=config_version_id,
                intent_key="version_compare",
                priority=30,
                match_type="keyword_contains",
                pattern="区别|对比|版本",
                profile_key="version_compare",
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeIntentRule(
                config_version_id=config_version_id,
                intent_key="coaching_guidance",
                priority=40,
                match_type="keyword_contains",
                pattern="怎么讲|怎么回答|话术|辅导",
                profile_key="coaching_guidance",
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
        ]
    )


def _seed_entity_aliases(db_session: Session, config_version_id: str) -> None:
    db_session.add(
        KnowledgeEntityAlias(
            config_version_id=config_version_id,
            canonical_entity="石犀科技",
            alias="世袭科技",
            entity_type="company",
            confidence=0.96,
            created_by=_DEFAULT_CREATED_BY,
            updated_by=_DEFAULT_CREATED_BY,
        )
    )


def _seed_ranking_profiles(db_session: Session, config_version_id: str) -> None:
    db_session.add_all(
        [
            KnowledgeRankingProfile(
                config_version_id=config_version_id,
                profile_key="product_overview",
                title_exact_boost=0.25,
                entity_match_boost=0.2,
                doc_type_weights_json={"product": 0.18, "faq": 0.05},
                section_weights_json={"overview": 0.14, "pricing": 0.02},
                min_pass_score=0.45,
                min_pass_score_keyword=0.35,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeRankingProfile(
                config_version_id=config_version_id,
                profile_key="pricing_lookup",
                title_exact_boost=0.2,
                entity_match_boost=0.15,
                doc_type_weights_json={"pricing": 0.22},
                section_weights_json={"pricing": 0.14},
                min_pass_score=0.45,
                min_pass_score_keyword=0.35,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeRankingProfile(
                config_version_id=config_version_id,
                profile_key="version_compare",
                title_exact_boost=0.2,
                entity_match_boost=0.15,
                doc_type_weights_json={"comparison": 0.22},
                section_weights_json={"comparison": 0.12},
                min_pass_score=0.45,
                min_pass_score_keyword=0.35,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeRankingProfile(
                config_version_id=config_version_id,
                profile_key="coaching_guidance",
                title_exact_boost=0.15,
                entity_match_boost=0.0,
                doc_type_weights_json={"coach": 0.2},
                section_weights_json={"guidance": 0.15},
                min_pass_score=0.42,
                min_pass_score_keyword=0.3,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
        ]
    )


def _seed_answerability_profiles(db_session: Session, config_version_id: str) -> None:
    db_session.add_all(
        [
            KnowledgeAnswerabilityProfile(
                config_version_id=config_version_id,
                profile_key="product_overview",
                required_slots_json=["definition", "capability"],
                optional_slots_json=["use_case"],
                sufficient_threshold=0.66,
                partial_threshold=0.5,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeAnswerabilityProfile(
                config_version_id=config_version_id,
                profile_key="pricing_lookup",
                required_slots_json=["price"],
                optional_slots_json=["edition"],
                sufficient_threshold=0.5,
                partial_threshold=0.5,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeAnswerabilityProfile(
                config_version_id=config_version_id,
                profile_key="version_compare",
                required_slots_json=["version_a", "version_b"],
                optional_slots_json=["difference"],
                sufficient_threshold=0.66,
                partial_threshold=0.5,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
            KnowledgeAnswerabilityProfile(
                config_version_id=config_version_id,
                profile_key="coaching_guidance",
                required_slots_json=["guidance"],
                optional_slots_json=["example"],
                sufficient_threshold=0.5,
                partial_threshold=0.5,
                created_by=_DEFAULT_CREATED_BY,
                updated_by=_DEFAULT_CREATED_BY,
            ),
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a minimal active knowledge-answer config snapshot")
    parser.add_argument(
        "--version-name",
        default=DEFAULT_VERSION_NAME,
        help="Config version_name to create or reactivate",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Optional notes stored on knowledge_config_versions.notes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_local = _build_session_local()
    with session_local() as session:
        result = seed_knowledge_answer_config(
            session,
            version_name=args.version_name,
            notes=args.notes,
        )
    print(
        f"[seeded] created={result['created']} version_name={result['version_name']} "
        f"config_version_id={result['config_version_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
