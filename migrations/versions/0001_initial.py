"""Initial schema: users, hashtags, posts, post_hashtags

Revision ID: 0001
Revises:
Create Date: 2026-03-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            sa.Enum("owner", "admin", name="user_role"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("telegram_id"),
    )

    op.create_table(
        "hashtags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tag", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tag"),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "content_type",
            sa.Enum("article", "youtube", "github", "audio", name="content_type"),
            nullable=False,
        ),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("post_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "published", "rejected", name="post_status"),
            nullable=False,
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )

    op.create_table(
        "post_hashtags",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("hashtag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["hashtag_id"], ["hashtags.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.PrimaryKeyConstraint("post_id", "hashtag_id"),
    )


def downgrade() -> None:
    op.drop_table("post_hashtags")
    op.drop_table("posts")
    op.drop_table("hashtags")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS post_status")
    op.execute("DROP TYPE IF EXISTS content_type")
    op.execute("DROP TYPE IF EXISTS user_role")
