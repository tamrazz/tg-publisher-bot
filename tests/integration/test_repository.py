import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ContentType, PostStatus, UserRole
from src.db.repository import (
    attach_hashtags_to_post,
    create_hashtag,
    create_post,
    delete_hashtag,
    delete_user,
    get_hashtag_by_tag,
    get_or_create_user,
    get_post,
    get_post_by_url,
    get_user,
    is_url_processed,
    list_hashtags,
    update_post_status,
    update_post_text,
    update_user_role,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


async def test_get_or_create_user_creates_new(session: AsyncSession) -> None:
    user, created = await get_or_create_user(
        session, telegram_id=100001, username="testuser", role=UserRole.admin
    )
    assert created is True
    assert user.telegram_id == 100001
    assert user.username == "testuser"
    assert user.role == UserRole.admin


async def test_get_or_create_user_returns_existing(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=100002, username="existing", role=UserRole.owner)
    user, created = await get_or_create_user(
        session, telegram_id=100002, username="existing", role=UserRole.owner
    )
    assert created is False
    assert user.telegram_id == 100002


async def test_get_user_not_found(session: AsyncSession) -> None:
    result = await get_user(session, 999999999)
    assert result is None


async def test_update_user_role(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=100003, username="u3", role=UserRole.admin)
    updated = await update_user_role(session, 100003, UserRole.owner)
    assert updated is not None
    assert updated.role == UserRole.owner


async def test_update_user_role_not_found(session: AsyncSession) -> None:
    result = await update_user_role(session, 999999998, UserRole.owner)
    assert result is None


async def test_delete_user(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=100004, username="u4", role=UserRole.admin)
    deleted = await delete_user(session, 100004)
    assert deleted is True
    assert await get_user(session, 100004) is None


async def test_delete_user_not_found(session: AsyncSession) -> None:
    result = await delete_user(session, 999999997)
    assert result is False


# ---------------------------------------------------------------------------
# Post CRUD
# ---------------------------------------------------------------------------


async def test_is_url_processed_false_for_new_url(session: AsyncSession) -> None:
    result = await is_url_processed(session, "https://new-url.example.com/article")
    assert result is False


async def test_create_and_get_post(session: AsyncSession) -> None:
    owner, _ = await get_or_create_user(
        session, telegram_id=200001, username="poster", role=UserRole.owner
    )
    post = await create_post(
        session,
        url="https://example.com/test-post",
        content_type=ContentType.article,
        created_by=200001,
        raw_content="Raw text",
        post_text="Post text",
    )
    assert post.id is not None
    assert post.url == "https://example.com/test-post"
    assert post.status == PostStatus.pending

    fetched = await get_post(session, post.id)
    assert fetched is not None
    assert fetched.id == post.id


async def test_is_url_processed_true_after_create(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=200002, username="poster2", role=UserRole.owner)
    url = "https://example.com/processed-url"
    await create_post(
        session,
        url=url,
        content_type=ContentType.github,
        created_by=200002,
    )
    assert await is_url_processed(session, url) is True


async def test_get_post_by_url(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=200003, username="poster3", role=UserRole.admin)
    url = "https://example.com/by-url"
    await create_post(session, url=url, content_type=ContentType.youtube, created_by=200003)
    post = await get_post_by_url(session, url)
    assert post is not None
    assert post.url == url


async def test_update_post_status(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=200004, username="poster4", role=UserRole.admin)
    post = await create_post(
        session,
        url="https://example.com/status-test",
        content_type=ContentType.article,
        created_by=200004,
    )
    updated = await update_post_status(session, post.id, PostStatus.published)
    assert updated is not None
    assert updated.status == PostStatus.published
    assert updated.published_at is not None


async def test_update_post_text(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=200005, username="poster5", role=UserRole.admin)
    post = await create_post(
        session,
        url="https://example.com/text-edit",
        content_type=ContentType.article,
        created_by=200005,
        post_text="Original text",
    )
    updated = await update_post_text(session, post.id, "Edited text")
    assert updated is not None
    assert updated.post_text == "Edited text"


# ---------------------------------------------------------------------------
# Hashtag CRUD
# ---------------------------------------------------------------------------


async def test_create_and_list_hashtags(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=300001, username="tagger", role=UserRole.admin)
    h = await create_hashtag(session, tag="#testing", created_by=300001, description="Tests")
    assert h.id is not None
    assert h.tag == "#testing"

    tags = await list_hashtags(session)
    tag_names = [t.tag for t in tags]
    assert "#testing" in tag_names


async def test_get_hashtag_by_tag(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=300002, username="tagger2", role=UserRole.admin)
    await create_hashtag(session, tag="#lookup", created_by=300002)
    result = await get_hashtag_by_tag(session, "#lookup")
    assert result is not None
    assert result.tag == "#lookup"


async def test_get_hashtag_not_found(session: AsyncSession) -> None:
    result = await get_hashtag_by_tag(session, "#nonexistent")
    assert result is None


async def test_delete_hashtag(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=300003, username="tagger3", role=UserRole.admin)
    await create_hashtag(session, tag="#todelete", created_by=300003)
    deleted = await delete_hashtag(session, "#todelete")
    assert deleted is True
    assert await get_hashtag_by_tag(session, "#todelete") is None


async def test_delete_hashtag_not_found(session: AsyncSession) -> None:
    result = await delete_hashtag(session, "#ghosttag")
    assert result is False


# ---------------------------------------------------------------------------
# PostHashtag
# ---------------------------------------------------------------------------


async def test_attach_hashtags_to_post(session: AsyncSession) -> None:
    await get_or_create_user(session, telegram_id=400001, username="rel_user", role=UserRole.admin)
    post = await create_post(
        session,
        url="https://example.com/hashtag-rel",
        content_type=ContentType.article,
        created_by=400001,
    )
    h1 = await create_hashtag(session, tag="#rel1", created_by=400001)
    h2 = await create_hashtag(session, tag="#rel2", created_by=400001)

    await attach_hashtags_to_post(session, post.id, [h1.id, h2.id])

    fetched = await get_post(session, post.id)
    assert fetched is not None
    # Relationship is loaded lazily; verify via post_hashtags count
    await session.refresh(fetched, ["post_hashtags"])
    assert len(fetched.post_hashtags) == 2
