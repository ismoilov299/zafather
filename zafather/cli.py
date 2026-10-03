"""UZ: Zafather buyruq qatori: loyiha yaratish va versiyani ko'rsatish.
RU: Командная строка Zafather: создание проекта и вывод версии.
EN: Zafather command line: project scaffolding and version output.

    zafather new mybot            # bot loyihasi / проект бота / bot project
    zafather new myuser --userbot # userbot loyihasi / проект userbot / userbot project
    zafather version
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__

_ENV_LOADER = '''

def load_env(path: str = ".env") -> None:
    """UZ: `.env` faylidagi KALIT=QIYMAT qatorlarini muhitga yuklaydi.
    RU: Загружает строки КЛЮЧ=ЗНАЧЕНИЕ из файла `.env` в окружение.
    EN: Loads KEY=VALUE lines from the `.env` file into the environment.
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as env_file:
        for line in env_file:
            key, sep, value = line.strip().partition("=")
            if sep and key and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())
'''

BOT_TEMPLATE = (
    '''"""{name} — Zafather bilan yozilgan bot / бот на Zafather / a bot built with Zafather."""
import os

from zafather import F, Message, Zafather
'''
    + _ENV_LOADER
    + """

load_env()
app = Zafather(os.environ["BOT_TOKEN"])


@app.command("start")
async def start(message: Message) -> None:
    await message.answer(f"Salom, <b>{{message.from_user.first_name}}</b>!")


@app.message(F.text)
async def echo(message: Message) -> None:
    await message.answer(message.text)


if __name__ == "__main__":
    app.run()
"""
)

USERBOT_TEMPLATE = (
    '''"""{name} — Zafather userbot / userbot на Zafather / a Zafather userbot."""
import asyncio
import os

from zafather import UserBot
from zafather.mtproto import events
'''
    + _ENV_LOADER
    + """

load_env()
userbot = UserBot(int(os.environ["API_ID"]), os.environ["API_HASH"], session="{name}")


@userbot.on(events.NewMessage(pattern=r"^\\.ping$", outgoing=True))
async def ping(event: events.NewMessage.Event) -> None:
    await event.edit("pong")


if __name__ == "__main__":
    asyncio.run(userbot.run())
"""
)

BOT_ENV = "BOT_TOKEN=bu_yerga_tokenni_yozing\n"
USERBOT_ENV = "API_ID=12345\nAPI_HASH=bu_yerga_api_hash\n"
GITIGNORE = ".env\n__pycache__/\n*.session.json\nzafather_state.json\n"


def create_project(name: str, *, userbot: bool = False, root: Path | None = None) -> Path:
    """UZ: Yangi loyiha papkasini yaratadi. RU: Создаёт папку нового проекта.
    EN: Creates a new project directory.
    """
    target = (root or Path.cwd()) / name
    if target.exists():
        raise FileExistsError(f"'{target}' already exists")
    target.mkdir(parents=True)
    template = USERBOT_TEMPLATE if userbot else BOT_TEMPLATE
    (target / ("userbot.py" if userbot else "bot.py")).write_text(
        template.format(name=name), encoding="utf-8"
    )
    (target / ".env").write_text(USERBOT_ENV if userbot else BOT_ENV, encoding="utf-8")
    extra = "[userbot]" if userbot else ""
    (target / "requirements.txt").write_text(f"zafather{extra}>={__version__}\n", encoding="utf-8")
    (target / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zafather", description="Zafather CLI")
    commands = parser.add_subparsers(dest="command")
    new = commands.add_parser("new", help="create a project")
    new.add_argument("name")
    new.add_argument("--userbot", action="store_true", help="MTProto userbot template")
    commands.add_parser("version", help="show the version")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        print(f"Zafather {__version__}")
        return 0
    if args.command == "new":
        try:
            target = create_project(args.name, userbot=args.userbot)
        except FileExistsError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        script = "userbot.py" if args.userbot else "bot.py"
        print(f"Created {target}\n\n  cd {args.name}\n  # .env\n  python {script}")
        return 0
    parser.print_help()
    return 0


__all__ = ["build_parser", "create_project", "main"]
