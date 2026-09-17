"""UZ: Zafather — Telegram botlar uchun yengil async framework.
RU: Zafather — лёгкий async-фреймворк для Telegram-ботов.
EN: Zafather — a lightweight async framework for Telegram bots.

UZ: Bot API **10.3** imkoniyatlarini qo'llab-quvvatlaydi: rangli tugmalar,
premium emoji, bot yaratadigan botlar, ephemeral xabarlar, guest mode,
reaksiyalar, obunalar va boshqalar.
RU: Поддерживает возможности Bot API **10.3**: цветные кнопки, premium emoji,
боты, создающие ботов, ephemeral-сообщения, guest mode, реакции, подписки.
EN: Supports Bot API **10.3** features: colored buttons, premium emoji,
bots that create bots, ephemeral messages, guest mode, reactions, subscriptions.

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
    MessageGenerationStopped,
    MessageReactionUpdated,
    TelegramObject,
    Update,
    User,
)

__version__ = "0.4.1"
__bot_api__ = BOT_API_VERSION
__author__ = "ismoilov299"
__license__ = "MIT"

__all__ = [
    # UZ: asosiy / RU: основные / EN: core
    "Zafather", "Bot", "Router", "SkipHandler", "F",
    # UZ: tiplar / RU: типы / EN: types
    "Message", "CallbackQuery", "InlineQuery", "User", "Chat", "Update",
    "TelegramObject", "ManagedBotUpdated", "BusinessConnection",
    "MessageReactionUpdated", "ChatBoostUpdated", "BotSubscriptionUpdated",
    "MessageGenerationStopped",
    # UZ: filtrlar / RU: фильтры / EN: filters
    "Filter", "Command", "Text", "Regex", "ChatType", "ContentType", "UserFilter",
    "StateFilter", "Service", "Ephemeral", "Premium", "HasCustomEmoji",
    "IsPrivate", "IsGroup",
    # FSM
    "State", "StatesGroup", "FSMContext", "MemoryStorage", "JSONStorage", "BaseStorage",
    # UZ: klaviaturalar / RU: клавиатуры / EN: keyboards
    "InlineKeyboard", "ReplyKeyboard", "RemoveKeyboard", "ForceReply", "confirm_keyboard",
    # UZ: matn va premium emoji / RU: текст и premium emoji / EN: text and premium emoji
    "emoji", "bold", "italic", "underline", "strike", "spoiler", "code", "pre",
    "link", "mention", "quote", "escape", "TextBuilder", "strip_custom_emoji", "SafeHTML",
    # UZ: boshqariladigan botlar / RU: управляемые боты / EN: managed bots
    "ManagedBots", "BotFarm",
    # UZ: tuzilgan xabarlar / RU: rich-сообщения / EN: rich messages
    "RichMessage", "RichStream", "markdown_rich",
    # Mini App
    "validate", "validate_third_party", "is_valid", "parse_init_data",
    "WebAppInitData", "WebAppAuthError", "WebAppData", "MiniApp", "MiniAppServer",
    "direct_link", "main_app_link", "attach_link",
    # UZ: konstantalar / RU: константы / EN: constants
    "ButtonStyle", "UpdateType", "ContentTypes", "ChatAction", "ParseMode",
    "ChatTypeEnum", "Currency", "DiceEmoji", "PollType", "BOT_API_VERSION",
    # UZ: boshqa / RU: прочее / EN: other
    "InputFile", "TelegramError", "NetworkError",
    "__version__", "__bot_api__",
]
