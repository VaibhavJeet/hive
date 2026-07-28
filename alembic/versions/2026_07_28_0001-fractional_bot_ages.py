"""Fractional bot ages, and the flag-brigading index deferred from HIVE-008

Revision ID: fractional_bot_ages
Revises: add_community_lifecycle
Create Date: 2026-07-28

HIVE-022 — `bot_lifecycles.virtual_age_days` was an Integer, but aging adds
`(real_hours / 24) * time_scale` days per cycle. At the production `time_scale` of 7,
an hourly cycle adds 0.29 days, and `int(0.29)` is 0. **No bot has ever aged**, so life
stages, vitality-driven death, legacy, and elder reproduction have never run. Widening
to Float is the fix; the truncation itself is removed in `lifecycle.py`.

`death_age` is widened to match, since it is assigned straight from `virtual_age_days`.

HIVE-008 — folds in the partial unique index deferred from the flag-brigading fix.
The service already refuses a second pending flag from the same reporter, but two
concurrent requests can both pass that check. The index makes it airtight, and the
earlier task explicitly deferred it to "the next migration" rather than raising one of
its own.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fractional_bot_ages'
down_revision: Union[str, None] = 'add_community_lifecycle'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # HIVE-022: ages become fractional
    # ------------------------------------------------------------------
    # Existing rows are all 0 (that is the bug), so the cast is lossless.
    op.alter_column(
        'bot_lifecycles',
        'virtual_age_days',
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using='virtual_age_days::double precision',
    )
    op.alter_column(
        'bot_lifecycles',
        'death_age',
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using='death_age::double precision',
    )

    # ------------------------------------------------------------------
    # HIVE-008: one pending flag per (bot, reporter)
    # ------------------------------------------------------------------
    # Partial, so resolved and dismissed flags may accumulate freely — only the
    # *pending* set feeds the auto-pause threshold.
    op.execute(
        """
        DELETE FROM bot_behavior_flags a
        USING bot_behavior_flags b
        WHERE a.status = 'pending'
          AND b.status = 'pending'
          AND a.bot_id = b.bot_id
          AND a.reporter_id = b.reporter_id
          AND a.created_at > b.created_at
        """
    )
    op.create_index(
        'uq_flag_pending_reporter_bot',
        'bot_behavior_flags',
        ['bot_id', 'reporter_id'],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index('uq_flag_pending_reporter_bot', table_name='bot_behavior_flags')

    # Truncating back to Integer loses the fractional part — which is the whole point
    # of the upgrade, so this is lossy by nature.
    op.alter_column(
        'bot_lifecycles',
        'death_age',
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using='death_age::integer',
    )
    op.alter_column(
        'bot_lifecycles',
        'virtual_age_days',
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using='virtual_age_days::integer',
    )
