"""add application table

Revision ID: 27b21766a2f2
Revises: 78d31e7951d7
Create Date: 2026-07-01 23:01:29.119290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27b21766a2f2'
down_revision: Union[str, Sequence[str], None] = '78d31e7951d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("company", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("vacancy_text", sa.Text, nullable=False),
        sa.Column("cover_letter_md", sa.Text, nullable=True),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("cv_variant_id", sa.Uuid, sa.ForeignKey("cv_variant.id"), nullable=True),
        sa.Column("short_link_code", sa.Text, sa.ForeignKey("short_link.code"), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "archived", name="applicationstatus"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_application_slug", "application", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_application_slug", table_name="application")
    op.drop_table("application")
    op.execute("DROP TYPE IF EXISTS applicationstatus")
