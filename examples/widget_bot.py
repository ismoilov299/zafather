"""UZ: Shaxsiy chatdagi widget hisoblagichi; BOT_TOKEN bilan ishga tushiring.
RU: Виджет-счётчик в личном чате; запускайте с BOT_TOKEN.
EN: A private-chat widget counter; run with BOT_TOKEN.
"""

from __future__ import annotations

import asyncio
import json
import os

from zafather import Message, TelegramAPIError, WidgetQuery, Zafather

bot = Zafather(os.getenv("BOT_TOKEN", "TOKENNI_SHU_YERGA"))
counters: dict[tuple[int, int], int] = {}
lock = asyncio.Lock()

HTML = """<h3>Counter</h3><p id="count"></p><button id="add">+1</button><p id="status"></p>
<script>
const W = TelegramWidget, button = document.getElementById('add');
const status = document.getElementById('status');
function draw() {
  let data = {}; try { data = JSON.parse(W.chatData) || {}; } catch (_) {}
  document.getElementById('count').textContent = data.n || 0;
}
button.onclick = () => {
  button.disabled = true; status.textContent = 'Sending...';
  W.request('inc').then(answer => {
    let result = {}; try { result = JSON.parse(answer.result) || {}; } catch (_) {}
    status.textContent = result.error || '';
    button.disabled = false;
  }, error => {
    status.textContent = error.code; button.disabled = false;
  });
};
W.onEvent('chatDataChanged', draw); draw(); W.ready();
</script>"""


@bot.command("start")
async def start(message: Message) -> None:
    if message.chat.type != "private":
        await message.answer("Open this bot in a private chat.")
        return
    sent = await message.answer_widget(
        HTML, chat_data='{"n":0}', allow_queries=True, caption="Counter: tap +1 to increment."
    )
    counters[(message.chat_id, sent.message_id)] = 0


@bot.widget_query()
async def increment(query: WidgetQuery) -> None:
    key = (query.chat_id, query.message_id)
    if query.data != "inc" or query.type.type != "data" or key not in counters:
        await query.answer('{"error":"Unknown widget or action; send /start."}')
        return
    if query.chat_id != query.user_id:
        await query.answer('{"error":"This counter belongs to another user."}')
        return
    async with lock:
        value = counters[key] + 1
        data = json.dumps({"n": value}, separators=(",", ":"))
        try:
            await query.edit_data(chat_data=data)
        except TelegramAPIError:
            await query.answer('{"error":"Update failed; try again."}')
            return
        counters[key] = value
    await query.answer(data)


if __name__ == "__main__":
    bot.run()
