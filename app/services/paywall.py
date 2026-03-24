from typing import Optional

class PaywallException(Exception):
    """Base exception for paywall-related limits."""
    pass

class MemberLimitExceeded(PaywallException):
    """Raised when a group exceeds the allowed number of members for the current plan."""
    pass

class GroupLimitExceeded(PaywallException):
    """Raised when an admin tries to create more groups than allowed for the current plan."""
    pass

class MediaNotAllowed(PaywallException):
    """Raised when a user tries to process media that is blocked by the current plan."""
    pass


AUDIO_PROCESSING_QUOTA = "audio_processing"
EXPENSE_REPORT_PDF_QUOTA = "expense_report_pdf"


# Config for plan limits
PLAN_LIMITS = {
    "FREE": {
        "max_members_per_group": 4,
        "max_groups_per_admin": 1,
        "allowed_media_types": ["text", "audio"],
        "quotas": {
            AUDIO_PROCESSING_QUOTA: {"limit": 5, "period": "weekly"},
            EXPENSE_REPORT_PDF_QUOTA: {"limit": 3, "period": "monthly"},
        },
    },
    "PREMIUM": {
        "max_members_per_group": float("inf"),
        "max_groups_per_admin": float("inf"),
        "allowed_media_types": ["text", "audio", "image", "document", "video"],
        "quotas": {},
    },
}


def get_plan_quota(plan_type: str, quota_key: str) -> dict | None:
    plan = plan_type.upper()
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["FREE"])
    quotas = limits.get("quotas") or {}
    return quotas.get(quota_key)


def build_quota_limit_message(quota_key: str) -> str:
    if quota_key == AUDIO_PROCESSING_QUOTA:
        return (
            "🚀 Tu plan FREE ya llegó al máximo de 5 audios por semana. "
            "Pasate a PREMIUM para seguir enviando audios sin límite."
        )
    if quota_key == EXPENSE_REPORT_PDF_QUOTA:
        return (
            "🚀 Tu plan FREE ya llegó al máximo de 3 reportes por mes. "
            "Pasate a PREMIUM para generar reportes sin límite."
        )
    return "🚀 Alcanzaste un límite de tu plan. ¡Actualizá a PREMIUM para más beneficios!"


async def check_group_member_limit(plan_type: str, current_member_count: int) -> None:
    """
    Check if adding a new member exceeds the plan limit.
    """
    plan = plan_type.upper()
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["FREE"])
    
    # We are checking if current members + 1 > limit? Or just if current_members > limit?
    # The prompt tests max 4 members. If they already have 4, adding 1 more makes it 5.
    if current_member_count > limits["max_members_per_group"]:
        raise MemberLimitExceeded(
            f"The group has {current_member_count} members, "
            f"but the {plan} plan only allows up to {limits['max_members_per_group']}."
        )

async def check_admin_group_limit(plan_type: str, current_group_count: int) -> None:
    """
    Check if an admin creating a new group exceeds their plan limit.
    """
    plan = plan_type.upper()
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["FREE"])
    
    # If the admin already has current_group_count groups, and tries to create a new one, 
    # the check fails if current_group_count > max_groups_per_admin? 
    # No, usually if current_group_count >= max_groups_per_admin, they can't create one more.
    # Wait, my test says: 
    # check_admin_group_limit(plan_type="FREE", current_group_count=1) -> passes?
    # No, wait. 
    # The test in test_paywall.py says:
    # check_admin_group_limit(plan_type="FREE", current_group_count=1) -> PASS
    # check_admin_group_limit(plan_type="FREE", current_group_count=2) -> EXCEPTION
    # Which means we are validating the STATE after creation.
    
    if current_group_count > limits["max_groups_per_admin"]:
        raise GroupLimitExceeded(
            f"The admin has {current_group_count} groups, "
            f"but the {plan} plan only allows up to {limits['max_groups_per_admin']}."
        )

async def check_media_allowed(plan_type: str, message_type: str) -> None:
    """
    Check if the specific media type is allowed in the user's plan.
    """
    plan = plan_type.upper()
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["FREE"])
    
    if message_type.lower() not in limits["allowed_media_types"]:
        raise MediaNotAllowed(
            f"Media type '{message_type}' is not allowed in the {plan} plan."
        )
