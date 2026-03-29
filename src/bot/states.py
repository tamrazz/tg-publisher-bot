from aiogram.fsm.state import State, StatesGroup


class ModerationStates(StatesGroup):
    """FSM states for the post moderation flow."""

    waiting_for_action = State()  # Showing preview + action buttons
    editing_post = State()  # Admin is typing new post text


class HashtagCreationStates(StatesGroup):
    """FSM states for hashtag creation."""

    waiting_for_tag = State()
    waiting_for_description = State()
