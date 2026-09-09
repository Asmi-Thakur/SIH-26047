"""initial schema: 12 foundational tables

Revision ID: 0001
Revises:
Create Date: 2026-09-06

The 12 Phase-1 tables per docs/PROTOTYPE_BUILD_SPEC.md section 26 and
docs/DATA_MODEL.md:

patients, users, sessions, consents, answers, documents, triage_alerts,
case_summaries, case_versions, audit_logs, fhir_exports, sync_queue
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSON on every dialect; JSONB on PostgreSQL (mirrors app.db.base.JSONB).
JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

TS = sa.DateTime(timezone=True)
NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    # --- patients ---------------------------------------------------------
    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_token", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("sex", sa.String(length=16), nullable=True),
        sa.Column("preferred_language", sa.String(length=8), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="pk_patients"),
        sa.UniqueConstraint("external_token", name="uq_patients_external_token"),
    )

    # --- users ------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default=sa.text("'doctor'")),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    # --- sessions ---------------------------------------------------------
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False, server_default=sa.text("'welcome'")),
        sa.Column("mode", sa.String(length=16), nullable=True),
        sa.Column("department", sa.String(length=64), nullable=True),
        sa.Column("started_at", TS, nullable=False, server_default=NOW),
        sa.Column("completed_at", TS, nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], name="fk_sessions_patient_id_patients"),
    )
    op.create_index("ix_sessions_patient_id", "sessions", ["patient_id"])

    # --- consents ---------------------------------------------------------
    op.create_table(
        "consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("purposes", JSON, nullable=True),
        sa.Column("consent_text_version", sa.String(length=32), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("revoked_at", TS, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_consents"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name="fk_consents_session_id_sessions"),
        sa.UniqueConstraint("session_id", name="uq_consents_session_id"),
    )

    # --- answers ----------------------------------------------------------
    op.create_table(
        "answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("input_mode", sa.String(length=16), nullable=True),
        sa.Column("raw_answer", sa.Text(), nullable=True),
        sa.Column("structured_value", JSON, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="pk_answers"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name="fk_answers_session_id_sessions"),
    )
    op.create_index("ix_answers_session_id_question_id", "answers", ["session_id", "question_id"])

    # --- documents --------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("document_type", sa.String(length=32), nullable=True),
        sa.Column("storage_path", sa.String(length=512), nullable=True),
        sa.Column("processing_status", sa.String(length=16), nullable=False, server_default=sa.text("'uploaded'")),
        sa.Column("uploaded_at", TS, nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name="fk_documents_session_id_sessions"),
    )
    op.create_index("ix_documents_session_id", "documents", ["session_id"])

    # --- triage_alerts ----------------------------------------------------
    op.create_table(
        "triage_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("rules_triggered", JSON, nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("acknowledged_at", TS, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_triage_alerts"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name="fk_triage_alerts_session_id_sessions"),
    )
    op.create_index("ix_triage_alerts_status", "triage_alerts", ["status"])
    op.create_index("ix_triage_alerts_session_id", "triage_alerts", ["session_id"])

    # --- case_summaries ---------------------------------------------------
    op.create_table(
        "case_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("content", JSON, nullable=True),
        sa.Column("draft_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", TS, nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="pk_case_summaries"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name="fk_case_summaries_session_id_sessions"),
        sa.UniqueConstraint("session_id", name="uq_case_summaries_session_id"),
    )

    # --- case_versions ----------------------------------------------------
    op.create_table(
        "case_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_summary_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("content", JSON, nullable=False),
        sa.Column("edited_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="pk_case_versions"),
        sa.ForeignKeyConstraint(
            ["case_summary_id"], ["case_summaries.id"], name="fk_case_versions_case_summary_id_case_summaries"
        ),
        sa.UniqueConstraint(
            "case_summary_id", "version_number", name="uq_case_versions_case_summary_id_version_number"
        ),
    )

    # --- audit_logs -------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("details", JSON, nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])

    # --- fhir_exports -----------------------------------------------------
    op.create_table(
        "fhir_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("bundle", JSON, nullable=True),
        sa.Column("destination", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempted_at", TS, nullable=True),
        sa.Column("succeeded_at", TS, nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="pk_fhir_exports"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name="fk_fhir_exports_session_id_sessions"),
    )
    op.create_index("ix_fhir_exports_session_id", "fhir_exports", ["session_id"])

    # --- sync_queue -------------------------------------------------------
    op.create_table(
        "sync_queue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("payload", JSON, nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="pk_sync_queue"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name="fk_sync_queue_session_id_sessions"),
    )


def downgrade() -> None:
    op.drop_table("sync_queue")
    op.drop_table("fhir_exports")
    op.drop_table("audit_logs")
    op.drop_table("case_versions")
    op.drop_table("case_summaries")
    op.drop_table("triage_alerts")
    op.drop_table("documents")
    op.drop_table("answers")
    op.drop_table("consents")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("patients")
