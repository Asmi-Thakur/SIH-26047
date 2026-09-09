"""documents: OCR/extraction result columns (Phase 4/2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08

Adds the nullable OCR/extraction result columns to ``documents``. They stay
NULL until a document is processed by ``POST /documents/{id}/reprocess`` —
existing rows remain valid untouched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("documents", sa.Column("extraction", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("ocr_provider", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("ocr_mocked", sa.Boolean(), nullable=True))
    op.add_column("documents", sa.Column("processed_at", TS, nullable=True))
    op.add_column("documents", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "last_error")
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "ocr_mocked")
    op.drop_column("documents", "ocr_provider")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "extraction")
