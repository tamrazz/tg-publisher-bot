"""Add hashtag_categories table and category_id FK on hashtags

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create hashtag_categories table
    op.create_table(
        "hashtag_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 2. Add category_id column to hashtags (nullable FK)
    op.add_column(
        "hashtags",
        sa.Column("category_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_hashtags_category_id",
        "hashtags",
        "hashtag_categories",
        ["category_id"],
        ["id"],
    )

    # 3. Seed the default "Свободная" category
    op.execute(
        "INSERT INTO hashtag_categories (name, is_required) VALUES ('Свободная', false)"
    )

    # 4. Assign all existing hashtags to the default category
    op.execute(
        "UPDATE hashtags SET category_id = ("
        "SELECT id FROM hashtag_categories WHERE name = 'Свободная'"
        ")"
    )


def downgrade() -> None:
    op.drop_constraint("fk_hashtags_category_id", "hashtags", type_="foreignkey")
    op.drop_column("hashtags", "category_id")
    op.drop_table("hashtag_categories")
