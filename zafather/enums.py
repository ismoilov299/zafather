"""Zafather — Bot API 10.2 konstantalari."""
from __future__ import annotations


class ButtonStyle:
    """Tugma rangi (Bot API 9.4+). InlineKeyboardButton va KeyboardButton uchun."""

    PRIMARY = "primary"   # ko'k — asosiy amal
    SUCCESS = "success"   # yashil — ijobiy amal
    DANGER = "danger"     # qizil — xavfli/o'chiruvchi amal

    ALL = (PRIMARY, SUCCESS, DANGER)


class ParseMode:
    HTML = "HTML"
    MARKDOWN_V2 = "MarkdownV2"
    MARKDOWN = "Markdown"


class UpdateType:
    """Bot API 10.2 dagi barcha update turlari."""

    MESSAGE = "message"
    EDITED_MESSAGE = "edited_message"
    CHANNEL_POST = "channel_post"
    EDITED_CHANNEL_POST = "edited_channel_post"
    BUSINESS_CONNECTION = "business_connection"
    BUSINESS_MESSAGE = "business_message"
    EDITED_BUSINESS_MESSAGE = "edited_business_message"
    DELETED_BUSINESS_MESSAGES = "deleted_business_messages"
    MESSAGE_REACTION = "message_reaction"
    MESSAGE_REACTION_COUNT = "message_reaction_count"
    INLINE_QUERY = "inline_query"
    CHOSEN_INLINE_RESULT = "chosen_inline_result"
    CALLBACK_QUERY = "callback_query"
    SHIPPING_QUERY = "shipping_query"
    PRE_CHECKOUT_QUERY = "pre_checkout_query"
    PURCHASED_PAID_MEDIA = "purchased_paid_media"
    POLL = "poll"
    POLL_ANSWER = "poll_answer"
    MY_CHAT_MEMBER = "my_chat_member"
    CHAT_MEMBER = "chat_member"
    CHAT_JOIN_REQUEST = "chat_join_request"
    CHAT_BOOST = "chat_boost"
    REMOVED_CHAT_BOOST = "removed_chat_boost"
    GUEST_MESSAGE = "guest_message"          # 10.0 — guest mode
    MANAGED_BOT = "managed_bot"              # 9.6 — bot yaratadigan botlar
    SUBSCRIPTION = "subscription"            # 10.2 — obuna o'zgarishi

    ALL = (
        MESSAGE,
        EDITED_MESSAGE,
        CHANNEL_POST,
        EDITED_CHANNEL_POST,
        BUSINESS_CONNECTION,
        BUSINESS_MESSAGE,
        EDITED_BUSINESS_MESSAGE,
        DELETED_BUSINESS_MESSAGES,
        MESSAGE_REACTION,
        MESSAGE_REACTION_COUNT,
        INLINE_QUERY,
        CHOSEN_INLINE_RESULT,
        CALLBACK_QUERY,
        SHIPPING_QUERY,
        PRE_CHECKOUT_QUERY,
        PURCHASED_PAID_MEDIA,
        POLL,
        POLL_ANSWER,
        MY_CHAT_MEMBER,
        CHAT_MEMBER,
        CHAT_JOIN_REQUEST,
        CHAT_BOOST,
        REMOVED_CHAT_BOOST,
        GUEST_MESSAGE,
        MANAGED_BOT,
        SUBSCRIPTION,
    )


class ContentType:
    """Message ichidagi kontent maydonlari."""

    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    ANIMATION = "animation"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"
    STICKER = "sticker"
    VIDEO_NOTE = "video_note"
    LOCATION = "location"
    VENUE = "venue"
    CONTACT = "contact"
    POLL = "poll"
    DICE = "dice"
    STORY = "story"
    GAME = "game"
    INVOICE = "invoice"
    SUCCESSFUL_PAYMENT = "successful_payment"
    REFUNDED_PAYMENT = "refunded_payment"
    PAID_MEDIA = "paid_media"
    LIVE_PHOTO = "live_photo"            # 10.0
    CHECKLIST = "checklist"              # 9.1
    RICH_MESSAGE = "rich_message"        # 10.1
    GIFT = "gift"                        # 9.0
    UNIQUE_GIFT = "unique_gift"          # 9.0
    NEW_CHAT_MEMBERS = "new_chat_members"
    LEFT_CHAT_MEMBER = "left_chat_member"
    PINNED_MESSAGE = "pinned_message"
    MANAGED_BOT_CREATED = "managed_bot_created"          # 9.6
    POLL_OPTION_ADDED = "poll_option_added"              # 9.6
    POLL_OPTION_DELETED = "poll_option_deleted"          # 9.6
    SUGGESTED_POST_INFO = "suggested_post_info"          # 9.2
    COMMUNITY_CHAT_ADDED = "community_chat_added"        # 10.2
    COMMUNITY_CHAT_REMOVED = "community_chat_removed"    # 10.2
    CHAT_OWNER_CHANGED = "chat_owner_changed"            # 9.4
    CHAT_OWNER_LEFT = "chat_owner_left"                  # 9.4

    MEDIA = (PHOTO, VIDEO, ANIMATION, AUDIO, VOICE, DOCUMENT, VIDEO_NOTE, LIVE_PHOTO)


class ChatAction:
    TYPING = "typing"
    UPLOAD_PHOTO = "upload_photo"
    RECORD_VIDEO = "record_video"
    UPLOAD_VIDEO = "upload_video"
    RECORD_VOICE = "record_voice"
    UPLOAD_VOICE = "upload_voice"
    UPLOAD_DOCUMENT = "upload_document"
    CHOOSE_STICKER = "choose_sticker"
    FIND_LOCATION = "find_location"
    RECORD_VIDEO_NOTE = "record_video_note"
    UPLOAD_VIDEO_NOTE = "upload_video_note"


class ChatTypeEnum:
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"
    SENDER = "sender"


class DiceEmoji:
    DICE = "🎲"
    DART = "🎯"
    BASKETBALL = "🏀"
    FOOTBALL = "⚽"
    BOWLING = "🎳"
    SLOT_MACHINE = "🎰"


class Currency:
    STARS = "XTR"  # Telegram Stars


class PollType:
    REGULAR = "regular"
    QUIZ = "quiz"


#: Bot API versiyasi, ushbu framework mos keladigan
BOT_API_VERSION = "10.2"
