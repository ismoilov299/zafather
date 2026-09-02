"""Zafather CLI.

    python -m zafather new mybot     # yangi loyiha yaratadi
    python -m zafather version
"""
import os
import sys

from . import __version__

TEMPLATE = '''"""{name} — Zafather bilan yozilgan bot."""
import os

from zafather import F, Message, Zafather

TOKEN = os.getenv("BOT_TOKEN", "TOKENNI_SHU_YERGA")

bot = Zafather(TOKEN, parse_mode="HTML")


@bot.command("start")
async def start(m: Message):
    await m.answer(f"Salom, <b>{{m.from_user.first_name}}</b>!")


@bot.message(F.text)
async def echo(m: Message):
    await m.answer(m.text)


if __name__ == "__main__":
    bot.run()
'''

ENV = "BOT_TOKEN=bu_yerga_tokenni_yozing\n"

REQS = "zafather\n"


def create(name: str) -> None:
    if os.path.exists(name):
        print(f"Xato: '{name}' papkasi allaqachon mavjud.")
        sys.exit(1)
    os.makedirs(name)
    with open(os.path.join(name, "bot.py"), "w", encoding="utf-8") as f:
        f.write(TEMPLATE.format(name=name))
    with open(os.path.join(name, ".env"), "w", encoding="utf-8") as f:
        f.write(ENV)
    with open(os.path.join(name, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(REQS)
    print(f"✅ '{name}' loyihasi yaratildi.\n")
    print(f"  cd {name}")
    print("  # .env faylga tokenni yozing")
    print("  python bot.py")


def main(argv=None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = argv[0]
    if cmd in ("version", "-v", "--version"):
        print(f"Zafather {__version__}")
    elif cmd == "new":
        if len(argv) < 2:
            print("Foydalanish: python -m zafather new <loyiha_nomi>")
            sys.exit(1)
        create(argv[1])
    else:
        print(f"Noma'lum buyruq: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
