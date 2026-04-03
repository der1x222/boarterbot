from app.keyboards import kb_main_menu, kb_editor_menu, kb_moderation_menu, kb_with_moderation_button
from app.profile_repo import get_editor_profile
from app.moderation_utils import is_moderator_telegram_id

async def get_menu_markup_for_user(user):
    is_moderator = is_moderator_telegram_id(user.telegram_id)
    if user.role == "editor":
        p = await get_editor_profile(user.id)
        is_verified = bool(p and p.get("verification_status") == "verified")
        base_menu = kb_editor_menu(is_verified)
    elif user.role == "moderator":
        base_menu = kb_moderation_menu()
    else:
        base_menu = kb_main_menu(user.role)

    if is_moderator and user.role != "moderator":
        return kb_with_moderation_button(base_menu)
    return base_menu
