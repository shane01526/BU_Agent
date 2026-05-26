"""add llm_model to sessions

Revision ID: 20260525_0002
Revises: 20260512_0001
Create Date: 2026-05-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0002"
down_revision: Union[str, None] = "20260512_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("llm_model", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "llm_model")
