"""UZ: Zafather — Bot API 10.3 konstantalari.
RU: Zafather — константы Bot API 10.3.
EN: Zafather — Bot API 10.3 constants.
"""
from __future__ import annotations


class ButtonStyle:
    """UZ: Tugma rangi (Bot API 9.4+). InlineKeyboardButton va KeyboardButton uchun.
    RU: Цвет кнопки (Bot API 9.4+). Для InlineKeyboardButton и KeyboardButton.
    EN: Button color (Bot API 9.4+). For InlineKeyboardButton and KeyboardButton.
    """

    PRIMARY = "primary"   # UZ: ko'k — asosiy amal / RU: синий — основное действие / EN: blue — primary action
    SUCCESS = "success"   # UZ: yashil — ijobiy amal / RU: зелёный — положительное действие / EN: green — positive action
    DANGER = "danger"     # UZ: qizil — xavfli/o'chiruvchi amal / RU: красный — опасное/удаляющее действие / EN: red — destructive action

    ALL = (PRIMARY, SUCCESS, DANGER)


class ParseMode:
    """UZ: Xabar parse_mode qiymatlari.
    RU: Значения parse_mode для сообщений.
    EN: Message parse_mode values.
    """

    HTML = "HTML"
    MARKDOWN_V2 = "MarkdownV2"
    MARKDOWN = "Markdown"


class UpdateType:
    """UZ: Bot API 10.3 dagi barcha update turlari.
    RU: Все типы update из Bot API 10.3.
    EN: All update types from Bot API 10.3.
    """

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
    GUEST_MESSAGE = "guest_message"          # UZ: 10.0 — mehmon rejimi / RU: 10.0 — гостевой режим / EN: 10.0 — guest mode
    MANAGED_BOT = "managed_bot"              # UZ: 9.6 — bot yaratadigan botlar / RU: 9.6 — боты, создающие ботов / EN: 9.6 — bots that create bots
    SUBSCRIPTION = "subscription"            # UZ: 10.2 — obuna o'zgarishi / RU: 10.2 — изменение подписки / EN: 10.2 — subscription change
    # UZ: foydalanuvchi rich/message generatsiyasini to'xtatdi.
    # RU: пользователь остановил генерацию rich/message.
    # EN: the user stopped rich/message generation.
    STOPPED_MESSAGE_GENERATION = "stopped_message_generation"

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
        STOPPED_MESSAGE_GENERATION,
    )


class ContentType:
    """
    UZ: Message ichidagi kontent maydonlari.
    RU: Поля контента внутри Message.
    EN: Content fields inside a Message.
    """

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
    COMMUNITY_CHAT_JOINED = "community_chat_joined"      # 10.3
    CHAT_OWNER_CHANGED = "chat_owner_changed"            # 9.4
    CHAT_OWNER_LEFT = "chat_owner_left"                  # 9.4

    MEDIA = (PHOTO, VIDEO, ANIMATION, AUDIO, VOICE, DOCUMENT, VIDEO_NOTE, LIVE_PHOTO)


class ChatAction:
    """UZ: sendChatAction uchun harakat turlari.
    RU: Типы действий для sendChatAction.
    EN: Action types for sendChatAction.
    """

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
    """UZ: Chat turlari.
    RU: Типы чатов.
    EN: Chat types.
    """

    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"
    SENDER = "sender"


class DiceEmoji:
    """UZ: sendDice uchun emoji qiymatlari.
    RU: Значения emoji для sendDice.
    EN: Emoji values for sendDice.
    """

    DICE = "🎲"
    DART = "🎯"
    BASKETBALL = "🏀"
    FOOTBALL = "⚽"
    BOWLING = "🎳"
    SLOT_MACHINE = "🎰"


class Currency:
    """UZ: To'lov valyutalari.
    RU: Валюты платежей.
    EN: Payment currencies.
    """

    STARS = "XTR"  # Telegram Stars


class PollType:
    """UZ: So'rovnoma turlari.
    RU: Типы опросов.
    EN: Poll types.
    """

    REGULAR = "regular"
    QUIZ = "quiz"


#: UZ: Ushbu framework mos keladigan Bot API versiyasi.
#: RU: Версия Bot API, которую поддерживает этот фреймворк.
#: EN: Bot API version supported by this framework.
BOT_API_VERSION = "10.3"
