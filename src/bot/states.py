from aiogram.fsm.state import State, StatesGroup


class ModerationStates(StatesGroup):
    """FSM states for the post moderation flow."""

    waiting_for_action = State()  # Showing preview + action buttons
    editing_post = State()  # Admin is typing new post text (moderation flow → publishes)
    editing_announce = State()  # Admin is typing new text (announce flow → shows preview)


class HashtagMgmtStates(StatesGroup):
    """FSM states for the hashtag management flow (settings → hashtags)."""

    entering_tag = State()
    selecting_category = State()
    entering_category_name = State()
    entering_description = State()
    confirming = State()
