from app.keyboards import kb_main_menu, kb_editor_menu
from app.profile_repo import get_editor_profile
from app.moderation_utils import is_moderator_telegram_id

async def get_menu_markup_for_user(user):
    if is_moderator_telegram_id(user.telegram_id):
        return kb_main_menu("moderator")
    if user.role == "editor":
        p = await get_editor_profile(user.id)
        is_verified = bool(p and p.get("verification_status") == "verified")
        return kb_editor_menu(is_verified)
    return kb_main_menu(user.role)
