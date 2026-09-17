"""UZ: Eng oddiy Zafather boti.
RU: Самый простой бот на Zafather.
EN: The simplest Zafather bot.
"""
import os

from zafather import F, Message, Zafather

bot = Zafather(os.getenv("BOT_TOKEN", "TOKENNI_SHU_YERGA"))


@bot.command("start", "help")
async def start(m: Message):
    await m.answer(f"Salom, <b>{m.from_user.first_name}</b>! Menga xohlagan matnni yozing.")


@bot.message(F.text)
async def echo(m: Message):
    await m.answer(m.text)


if __name__ == "__main__":
    bot.run()
