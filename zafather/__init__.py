"""UZ: Zafather — Telegram botlar va userbotlar uchun yengil async framework.
RU: Zafather — лёгкий async-фреймворк для Telegram-ботов и userbot.
EN: Zafather — a lightweight async framework for Telegram bots and userbots.

UZ: Bot API **10.3** imkoniyatlari: rangli tugmalar, premium emoji, bot yaratadigan
botlar, ephemeral xabarlar, guest mode, reaksiyalar, obunalar, rich xabarlar.
RU: Возможности Bot API **10.3**: цветные кнопки, premium emoji, боты, создающие
ботов, ephemeral-сообщения, guest mode, реакции, подписки, rich-сообщения.
EN: Bot API **10.3** features: colored buttons, premium emoji, bots that create bots,
ephemeral messages, guest mode, reactions, subscriptions and rich messages.

::

    from zafather import F, InlineKeyboard, Message, Zafather, emoji

    app = Zafather("TOKEN")

    @app.command("start")
    async def start(message: Message):
        kb = InlineKeyboard().success("✅ Ha", "yes").danger("❌ Yo'q", "no")
        await message.answer(f"{emoji('5368324170671202286', '🔥')} Salom!", reply_markup=kb)

    app.run()
"""

__version__ = "0.5.0"
__author__ = "ismoilov299"
__license__ = "MIT"

from .api import AiohttpSession, BaseSession, RetryPolicy, TelegramAPIServer
from .app import Zafather
from .bot import Bot
from .callback_data import CallbackData
from .dispatcher import Dispatcher
from .enums import (
    BOT_API_VERSION,
    ButtonStyle,
    ChatAction,
    ChatTypeEnum,
    Currency,
    DiceEmoji,
    ParseMode,
    PollType,
    UpdateType,
)
from .enums import ContentType as ContentTypes
from .exceptions import (
    BadRequest,
    Conflict,
    Forbidden,
    MigrateToChat,
    NetworkError,
    NotFound,
    OptionalDependencyError,
    RetryAfter,
    ServerError,
    TelegramAPIError,
    TelegramError,
    Unauthorized,
    ZafatherError,
)
from .files import InputFile
from .filters import (
    ChatType,
    Command,
    ContentType,
    Ephemeral,
    ExceptionTypeFilter,
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
from .fsm import (
    BaseStorage,
    FSMContext,
    FSMStrategy,
    JSONStorage,
    MemoryStorage,
    RedisStorage,
    State,
    StatesGroup,
    StorageKey,
)
from .i18n import I18n
from .keyboards import ForceReply, InlineKeyboard, RemoveKeyboard, ReplyKeyboard, confirm_keyboard
from .magic import F
from .managed import BotFarm, ManagedBots
from .middlewares import (
    AlbumMiddleware,
    BaseMiddleware,
    ChatActionMiddleware,
    ThrottlingMiddleware,
)
from .mtproto import EventBuilder, Events, MTProtoClient
from .payments import Invoice, LabeledPrice, StarsAPI
from .polling import LongPolling
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
from .types import (
    BotSubscriptionUpdated,
    BusinessConnection,
    CallbackQuery,
    Chat,
    ChatBoostUpdated,
    InlineQuery,
    ManagedBotUpdated,
    Message,
    MessageGenerationStopped,
    MessageReactionUpdated,
    PreCheckoutQuery,
    TelegramObject,
    Update,
    User,
)
from .userbot import UserBot
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
from .webhook import WebhookServer
from .webserver import MiniAppServer

__bot_api__ = BOT_API_VERSION

__all__ = [
    "BOT_API_VERSION",
    "AiohttpSession",
    "AlbumMiddleware",
    "BadRequest",
    "BaseMiddleware",
    "BaseSession",
    "BaseStorage",
    "Bot",
    "BotFarm",
    "BotSubscriptionUpdated",
    "BusinessConnection",
    "ButtonStyle",
    "CallbackData",
    "CallbackQuery",
    "Chat",
    "ChatAction",
    "ChatActionMiddleware",
    "ChatBoostUpdated",
    "ChatType",
    "ChatTypeEnum",
    "Command",
    "Conflict",
    "ContentType",
    "ContentTypes",
    "Currency",
    "DiceEmoji",
    "Dispatcher",
    "Ephemeral",
    "EventBuilder",
    "Events",
    "ExceptionTypeFilter",
    "F",
    "FSMContext",
    "FSMStrategy",
    "Filter",
    "Forbidden",
    "ForceReply",
    "HasCustomEmoji",
    "I18n",
    "InlineKeyboard",
    "InlineQuery",
    "InputFile",
    "Invoice",
    "IsGroup",
    "IsPrivate",
    "JSONStorage",
    "LabeledPrice",
    "LongPolling",
    "MTProtoClient",
    "ManagedBotUpdated",
    "ManagedBots",
    "MemoryStorage",
    "Message",
    "MessageGenerationStopped",
    "MessageReactionUpdated",
    "MigrateToChat",
    "MiniApp",
    "MiniAppServer",
    "NetworkError",
    "NotFound",
    "OptionalDependencyError",
    "ParseMode",
    "PollType",
    "PreCheckoutQuery",
    "Premium",
    "RedisStorage",
    "Regex",
    "RemoveKeyboard",
    "ReplyKeyboard",
    "RetryAfter",
    "RetryPolicy",
    "RichMessage",
    "RichStream",
    "Router",
    "SafeHTML",
    "ServerError",
    "Service",
    "SkipHandler",
    "StarsAPI",
    "State",
    "StateFilter",
    "StatesGroup",
    "StorageKey",
    "TelegramAPIError",
    "TelegramAPIServer",
    "TelegramError",
    "TelegramObject",
    "Text",
    "TextBuilder",
    "ThrottlingMiddleware",
    "Unauthorized",
    "Update",
    "UpdateType",
    "User",
    "UserBot",
    "UserFilter",
    "WebAppAuthError",
    "WebAppData",
    "WebAppInitData",
    "WebhookServer",
    "Zafather",
    "ZafatherError",
    "__bot_api__",
    "__version__",
    "attach_link",
    "bold",
    "code",
    "confirm_keyboard",
    "direct_link",
    "emoji",
    "escape",
    "is_valid",
    "italic",
    "link",
    "main_app_link",
    "markdown_rich",
    "mention",
    "parse_init_data",
    "pre",
    "quote",
    "spoiler",
    "strike",
    "strip_custom_emoji",
    "underline",
    "validate",
    "validate_third_party",
]
