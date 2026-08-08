"""add incident approval + snapshot columns

Revision ID: b3a0a1b2c3d4
Revises: 8294ca90492c
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3a0a1b2c3d4'
down_revision: Union[str, Sequence[str], None] = '8294ca90492c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('incidents', sa.Column('requires_approval', sa.Boolean(), nullable=True))
    op.add_column('incidents', sa.Column('state_snapshot', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('incidents', 'state_snapshot')
    op.drop_column('incidents', 'requires_approval')
