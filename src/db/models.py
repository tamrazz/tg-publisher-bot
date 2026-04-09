import logging
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class UserRole(StrEnum):
    owner = "owner"
    admin = "admin"


class ContentType(StrEnum):
    article = "article"
    youtube = "youtube"
    github = "github"
    audio = "audio"


class PostStatus(StrEnum):
    pending = "pending"
    published = "published"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    posts: Mapped[list["Post"]] = relationship("Post", back_populates="created_by_user")
    hashtags: Mapped[list["Hashtag"]] = relationship("Hashtag", back_populates="created_by_user")

    def __repr__(self) -> str:
        return f"<User telegram_id={self.telegram_id} role={self.role}>"


class HashtagCategory(Base):
    __tablename__ = "hashtag_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    hashtags: Mapped[list["Hashtag"]] = relationship("Hashtag", back_populates="category")

    def __repr__(self) -> str:
        return f"<HashtagCategory id={self.id} name={self.name!r} is_required={self.is_required}>"


class Hashtag(Base):
    __tablename__ = "hashtags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=False
    )
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("hashtag_categories.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    created_by_user: Mapped["User"] = relationship("User", back_populates="hashtags")
    category: Mapped["HashtagCategory | None"] = relationship(
        "HashtagCategory", back_populates="hashtags"
    )
    post_hashtags: Mapped[list["PostHashtag"]] = relationship(
        "PostHashtag", back_populates="hashtag"
    )

    def __repr__(self) -> str:
        return f"<Hashtag id={self.id} tag={self.tag!r} category_id={self.category_id}>"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type"), nullable=False
    )
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="post_status"), nullable=False, default=PostStatus.pending
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    created_by_user: Mapped["User"] = relationship("User", back_populates="posts")
    post_hashtags: Mapped[list["PostHashtag"]] = relationship("PostHashtag", back_populates="post")

    def __repr__(self) -> str:
        return f"<Post id={self.id} url={self.url!r} status={self.status}>"


class PostHashtag(Base):
    __tablename__ = "post_hashtags"

    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), primary_key=True)
    hashtag_id: Mapped[int] = mapped_column(Integer, ForeignKey("hashtags.id"), primary_key=True)

    post: Mapped["Post"] = relationship("Post", back_populates="post_hashtags")
    hashtag: Mapped["Hashtag"] = relationship("Hashtag", back_populates="post_hashtags")

    def __repr__(self) -> str:
        return f"<PostHashtag post_id={self.post_id} hashtag_id={self.hashtag_id}>"
