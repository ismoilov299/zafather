"""
Zafather — Telegram botlar uchun yengil async framework.

Bot API **10.2** (14-iyul, 2026) imkoniyatlarini qo'llab-quvvatlaydi:
rangli tugmalar, premium emoji, bot yaratadigan botlar, ephemeral xabarlar,
guest mode, reaksiyalar, obunalar va boshqalar.

    from zafather import Zafather, Message, InlineKeyboard, emoji, F

    bot = Zafather("TOKEN")

    @bot.command("start")
    async def start(m: Message):
        kb = InlineKeyboard().success("✅ Ha", "yes").danger("❌ Yo'q", "no")
        await m.answer(f"{emoji('5368324170671202286', '🔥')} Salom!", reply_markup=kb)

    bot.run()
"""

from .app import Zafather
from .bot import Bot, InputFile, NetworkError, TelegramError
from .enums import (
    BOT_API_VERSION,
    ButtonStyle,
    ChatAction,
    ChatTypeEnum,
    ContentType as ContentTypes,
    Currency,
    DiceEmoji,
    ParseMode,
    PollType,
    UpdateType,
)
from .filters import (
    ChatType,
    Command,
    ContentType,
    Ephemeral,
    Filter,
    HasCustomEmoji,
    IsGroup,
    IsPrivate,
    Premium,
    Regex,
    Service,
    StateFilter,
    Text,
    UserFilter,
)
from .fsm import BaseStorage, FSMContext, JSONStorage, MemoryStorage, State, StatesGroup
from .keyboards import (
    ForceReply,
    InlineKeyboard,
    RemoveKeyboard,
    ReplyKeyboard,
    confirm_keyboard,
)
from .magic import F
from .managed import BotFarm, ManagedBots
from .rich import RichMessage, RichStream, markdown_rich
from .router import Router, SkipHandler
from .text import (
    SafeHTML,
    TextBuilder,
    bold,
    code,
    emoji,
    escape,
    italic,
    link,
    mention,
    pre,
    quote,
    spoiler,
    strike,
    strip_custom_emoji,
    underline,
)
from .webapp import (
    MiniApp,
    WebAppAuthError,
    WebAppData,
    WebAppInitData,
    attach_link,
    direct_link,
    is_valid,
    main_app_link,
    parse_init_data,
    validate,
    validate_third_party,
)
from .webserver import MiniAppServer
from .types import (
    BotSubscriptionUpdated,
    BusinessConnection,
    CallbackQuery,
    Chat,
    ChatBoostUpdated,
    InlineQuery,
    ManagedBotUpdated,
    Message,
    MessageReactionUpdated,
    TelegramObject,
    Update,
    User,
)

__version__ = "0.4.1"
__bot_api__ = BOT_API_VERSION
__author__ = "Zafather"

__all__ = [
    # asosiy
    "Zafather", "Bot", "Router", "SkipHandler", "F",
    # tiplar
    "Message", "CallbackQuery", "InlineQuery", "User", "Chat", "Update",
    "TelegramObject", "ManagedBotUpdated", "BusinessConnection",
    "MessageReactionUpdated", "ChatBoostUpdated", "BotSubscriptionUpdated",
    # filtrlar
    "Filter", "Command", "Text", "Regex", "ChatType", "ContentType", "UserFilter",
    "StateFilter", "Service", "Ephemeral", "Premium", "HasCustomEmoji",
    "IsPrivate", "IsGroup",
    # FSM
    "State", "StatesGroup", "FSMContext", "MemoryStorage", "JSONStorage", "BaseStorage",
    # klaviaturalar
    "InlineKeyboard", "ReplyKeyboard", "RemoveKeyboard", "ForceReply", "confirm_keyboard",
    # matn va premium emoji
    "emoji", "bold", "italic", "underline", "strike", "spoiler", "code", "pre",
    "link", "mention", "quote", "escape", "TextBuilder", "strip_custom_emoji", "SafeHTML",
    # managed bots
    "ManagedBots", "BotFarm",
    # rich messages
    "RichMessage", "RichStream", "markdown_rich",
    # Mini App
    "validate", "validate_third_party", "is_valid", "parse_init_data",
    "WebAppInitData", "WebAppAuthError", "WebAppData", "MiniApp", "MiniAppServer",
    "direct_link", "main_app_link", "attach_link",
    # konstantalar
    "ButtonStyle", "UpdateType", "ContentTypes", "ChatAction", "ParseMode",
    "ChatTypeEnum", "Currency", "DiceEmoji", "PollType", "BOT_API_VERSION",
    # boshqa
    "InputFile", "TelegramError", "NetworkError",
    "__version__", "__bot_api__",
]
