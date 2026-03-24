import pytest

from app.services.paywall import (
    AUDIO_PROCESSING_QUOTA,
    EXPENSE_REPORT_PDF_QUOTA,
    check_group_member_limit,
    check_admin_group_limit,
    check_media_allowed,
    get_plan_quota,
    MemberLimitExceeded,
    GroupLimitExceeded,
    MediaNotAllowed,
)

@pytest.mark.asyncio
async def test_group_member_limit_free_plan():
    """Test 1: Max 4 members in Free plan."""
    
    # Under limit (4 members allowed)
    try:
        await check_group_member_limit(plan_type="FREE", current_member_count=3)
        await check_group_member_limit(plan_type="FREE", current_member_count=4)
    except MemberLimitExceeded:
        pytest.fail("MemberLimitExceeded raised unexpectedly for valid counts")

    # Over limit
    with pytest.raises(MemberLimitExceeded):
        await check_group_member_limit(plan_type="FREE", current_member_count=5)

@pytest.mark.asyncio
async def test_group_member_limit_premium_plan():
    """Premium plan should have no limit (or a much higher limit)."""
    try:
        await check_group_member_limit(plan_type="PREMIUM", current_member_count=100)
    except MemberLimitExceeded:
        pytest.fail("MemberLimitExceeded raised unexpectedly for PREMIUM plan")

@pytest.mark.asyncio
async def test_admin_group_limit_free_plan():
    """Test 2: Max 1 group per Free admin."""
    
    # Under limit
    try:
        await check_admin_group_limit(plan_type="FREE", current_group_count=0)
        await check_admin_group_limit(plan_type="FREE", current_group_count=1)
    except GroupLimitExceeded:
        pytest.fail("GroupLimitExceeded raised unexpectedly for valid counts")
        
    # Over limit
    with pytest.raises(GroupLimitExceeded):
        await check_admin_group_limit(plan_type="FREE", current_group_count=2)

@pytest.mark.asyncio
async def test_admin_group_limit_premium_plan():
    """Premium plan should allow multiple groups."""
    try:
        await check_admin_group_limit(plan_type="PREMIUM", current_group_count=10)
    except GroupLimitExceeded:
        pytest.fail("GroupLimitExceeded raised unexpectedly for PREMIUM plan")

@pytest.mark.asyncio
async def test_media_allowed_free_plan():
    """Free plan can process audio but not images."""
    
    # Text is allowed
    try:
        await check_media_allowed(plan_type="FREE", message_type="text")
    except MediaNotAllowed:
        pytest.fail("MediaNotAllowed raised unexpectedly for text message")

    try:
        await check_media_allowed(plan_type="FREE", message_type="audio")
    except MediaNotAllowed:
        pytest.fail("MediaNotAllowed raised unexpectedly for audio message")

    with pytest.raises(MediaNotAllowed):
        await check_media_allowed(plan_type="FREE", message_type="image")

@pytest.mark.asyncio
async def test_media_allowed_premium_plan():
    """Premium plan can process audio and images."""
    try:
        await check_media_allowed(plan_type="PREMIUM", message_type="text")
        await check_media_allowed(plan_type="PREMIUM", message_type="audio")
        await check_media_allowed(plan_type="PREMIUM", message_type="image")
    except MediaNotAllowed:
        pytest.fail("MediaNotAllowed raised unexpectedly for PREMIUM plan")


def test_get_plan_quota_returns_free_audio_and_report_limits():
    assert get_plan_quota("FREE", AUDIO_PROCESSING_QUOTA) == {"limit": 5, "period": "weekly"}
    assert get_plan_quota("FREE", EXPENSE_REPORT_PDF_QUOTA) == {"limit": 3, "period": "monthly"}


def test_get_plan_quota_keeps_premium_unlimited():
    assert get_plan_quota("PREMIUM", AUDIO_PROCESSING_QUOTA) is None
    assert get_plan_quota("PREMIUM", EXPENSE_REPORT_PDF_QUOTA) is None
