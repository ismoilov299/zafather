# HTML widgetlar (Bot API 10.4)

Zafather Telegram xabaridagi widgetlarni yuboradi, ma'lumot va wallet
so'rovlarini qabul qiladi. Yuborilgan HTML o'zgarmaydi; bot holatni alohida
yangilaydi. Widget Telegram ichida, internet va matn kiritishsiz ishlaydi.
JavaScript `TelegramWidget` ushbu Python paketiga emas, Telegram klientiga tegishli.

## Yuborish va javob berish

```python
from zafather import WidgetQuery, Zafather

app = Zafather("TOKEN")

@app.command("start")
async def start(message):
    await message.answer_widget(
        "<button onclick=\"TelegramWidget.request('refresh')\">Refresh</button>",
        allow_queries=True,
        chat_data='{"n":0}',
        caption="Refresh the counter",
    )

@app.widget_query()
async def refresh(query: WidgetQuery):
    await query.answer('{"ok":true}')

app.run()
```

Har bir so'rovga, xatoda ham, 15 soniya ichida javob bering. `query.answer()`
natija ma'lumotini yubormaydi; `query.answer("")` bo'sh natija yuboradi. Ikkalasi
ham holatni o'zgartirmaydi. `examples/widget_bot.py` ishga tushiriladigan namuna:
bot hisoblagichni saqlaydi, amallarni tekshiradi, holatni yangilaydi va tahrir
xatolarini qayta ishlaydi. Uning xotiradagi hisoblagichlari restartda yo'qoladi;
haqiqiy botda doimiy storage ishlating.

## API va yorliqlar

| Metod | Vazifasi |
|---|---|
| `Bot.send_widget(chat_id, html, **params)` | Oddiy yoki shared widget yaratish |
| `Bot.send_shared_widget(chat_id, widget_id, **params)` | Mavjud shared widgetni yuborish |
| `Bot.answer_widget_query(widget_query_id, data=None)` | Original yoki forward so'roviga javob |
| `Bot.edit_message_widget_data(chat_id=..., message_id=..., chat_data=...)` | Xabar holatini tahrirlash |
| `Bot.edit_message_widget_data(inline_message_id=..., public_data=...)` | Inline xabar holatini tahrirlash |
| `Bot.edit_shared_widget_data(widget_id, public_data, cache_time=...)` | Umumiy holatni tahrirlash |

Yuborish metodlari `Message` qaytaradi; `message.widget` — `Widget`. Caption,
entity, klaviatura va boshqa rasmiy parametrlar `**params` orqali o'tadi. Botning
standart parse mode'i HTML kodga emas, caption'ga qo'llanadi. `parse_mode=None`
yoki `caption_entities` standart parse mode'ni o'chiradi.

Xabar yorliqlari: `answer_widget(html)`, `reply_widget(html)`,
`answer_shared_widget(widget_id)`, `edit_widget_data(...)`. Forum mavzusi va
aniq berilgan parametrlar saqlanadi, biznes ulanishi meros olinmaydi: Bot API
10.4 widget yuborish metodlarida bunday parametr yo'q.
`message.external_reply.widget` ham `Widget` sifatida o'raladi.

`@app.widget_query(...)` original va inline `WidgetQuery` uchun;
`@app.shared_widget_query(...)` forward qilingan shared widgetning
`SharedWidgetQuery` so'rovi uchun. Odatiy filtr, middleware, DI, `state=` va ichki
routerlar ishlaydi. Polling va webhook standart holatda ikkala update turini
so'raydi; o'z `allowed_updates` ro'yxatingizda `widget_query` hamda
`shared_widget_query` bo'lsin.

Original so'rovda `answer(data)`, `edit_data(chat_data=..., public_data=...)`,
`edit_shared_data(public_data, cache_time=...)` bor. Forward so'rovda faqat
`answer` va `edit_shared_data` bor: Telegram chat/xabar koordinatalarini bermaydi.
Inline yoki forward so'rovining DI kontekstida `chat_id=None`; foydalanuvchining
shaxsiy chat ID si o'rniga qo'yilmaydi. Inline tahrirda `inline_message_id`
avtomatik ishlatiladi. Oddiy widgetda shared holatni tahrirlash `ValueError` beradi.

## Holat va chegaralar

Holat va natijalar satr bo'lishi kerak; JSON uchun `json.dumps` ishlating.
`None` maydonni yubormaydi va eski holatni saqlaydi; `""` tozalaydi. `chat_data`
bitta xabarga, shared `public_data` esa `widget_id` ga tegishli. Asosiy holatni
faqat bot o'zgartiradi. Ishonchsiz `query.data` ni backend yozuvlariga solishtiring;
ovoz, egalik va to'lovlar uchun localStorage'ga ishonmang.

Tekshiruv HTTP'dan oldin ishlaydi, jumladan `Bot.call`/`request` va xom inline
lug'atlar uchun: HTML 1–32768 UTF-8 bayt, zlib-9 bilan ko'pi bilan 4096 bayt;
har bir holat va javob ko'pi bilan 1024 UTF-8 bayt. HTML/holatda NUL va noto'g'ri
UTF-8 rad etiladi. `widget_size(html)` oddiy va siqilgan hajmni qaytaradi. HTML'ni
siqmasdan yuboring. Eni va bo'yi butun son; nol avtomatik o'lcham, qolgan butun
o'lchamlarni Telegram chegaralaydi.

Xabar tahririda `chat_id` va `message_id` yoki `inline_message_id` kerak;
ikkalasini birga bermang. Shared cache vaqti kamida 5 soniya bo'lgan butun son;
3600 dan kattasini Telegram 3600 ga tushiradi. Berilmasa eski davr saqlanadi
(boshlanishida 30 soniya). Noto'g'ri kirish `TypeError`/`ValueError` beradi;
API/tarmoq xatolari frameworkning tiplangan xatolari bo'lib qoladi. Javobi
yo'qolgan yozuvchi so'rov standart holatda qaytarilmaydi. “message is not
modified” xatosini ilova muvaffaqiyat deb qabul qilishi mumkin; so'rovga baribir
javob berish kerak.

Shared holatni jonli olish uchun klient `TelegramWidget.watchPublicData()`
chaqiradi. Eski polling natijasini tashlash uchun holat/javobda o'suvchi revision
saqlang. Shared tahrirlarni soniyasiga bittagacha birlashtiring. So'rov limiti
foydalanuvchi/bot uchun 5 soniyada 5 ta; widgetda bittasi bajarilayotgan bo'ladi.

## Inline rejim va wallet

```python
from zafather import InputSharedWidgetMessageContent, InputWidgetMessageContent

content = InputWidgetMessageContent("<b>Price</b>", public_data='{"p":1}')
existing = InputSharedWidgetMessageContent("WIDGET_ID", caption="Live price")
await app.bot.answer_inline_query(inline_query_id="QUERY_ID", results=[{
    "type": "article", "id": "price", "title": "Price",
    "input_message_content": existing,
}])
```

Quruvchilar `to_dict()` bilan serializatsiya qilinadi. Yangi inline natijadagi
`is_shared=True` har yuborishda alohida shared widget yaratadi. Bitta holatni
ulashish uchun avval `send_widget(..., is_shared=True)` bilan yarating va
`sent.widget.id` ni qayta ishlating.

`query.type` avtomatik `WidgetQueryTypeData`, `WidgetQueryTypeSignData` yoki
`WidgetQueryTypeSentTransaction` bo'ladi; kelajakdagi noma'lum turlar maydonlari
yo'qolmasdan `WidgetQueryType` bo'lib qoladi. `wallet_card` — `TonWalletCard`,
`wallet` — `WidgetQueryWallet`. Wallet manzili va balans satr bo'lib qoladi;
`sign_data` asl JSON satridir. Filtr: `F.type.type == "data"` yoki boshqa tur nomi.
Backend imzolarni va tranzaksiyalarni zanjirda tekshirishi kerak. Tranzaksiya
xabari to'lov isboti emas; timeoutdan keyin qayta to'lashdan oldin buyurtma
holatini tekshiring. Paket TON tekshiruvchisini amalga oshirmaydi.

## Mavjudlik va sinash

2026-yil 11-noyabrdagi hujjatga ko'ra production'da faqat bot bilan shaxsiy
chat mavjud; widget xabarlari himoyalanadi va forward qilinmaydi. Guruhlar,
inline yuborish va forwarding test serverida. Test botlar uchun
`Zafather(..., api_url=TelegramAPIServer(test_environment=True))` ishlating.
Widgetni kanalga bevosita yuborish yoki nusxalash mumkin emas.

Oflayn testlar serializatsiya, routing va chegaralarni tekshiradi, Telegram
chizishini emas. Deploydan oldin klientlar, yorug'/qorong'i tema, tor ekran,
caption joylashuvi, restart, so'rov xatolari va shared yangilanishni sinang.

Manbalar: [widget qo'llanmasi](https://core.telegram.org/bots/widgets),
[Bot API](https://core.telegram.org/bots/api#sendwidget).
