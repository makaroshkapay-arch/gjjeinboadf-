"""P2P Myjot — главный файл. Запуск: python bot.py

Один процесс поднимает сразу две вещи:
  * FastAPI (Mini App + API) на 0.0.0.0:PORT (по умолчанию 3000);
  * Telegram-бота (aiogram 3, long polling).
"""
import asyncio
import logging
import os
import sys

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Message, WebAppInfo,
)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("p2p_myjot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
PORT = int(os.getenv("PORT", "3000"))

START_TEXT = (
    "📊 P2P Myjot\n\n"
    "Удобный калькулятор для P2P-сделок, NFT, гарантированных сделок, обмена и комиссий.\n\n"
    "Здесь можно:\n"
    "• считать прибыль;\n"
    "• учитывать комиссии;\n"
    "• считать NFT;\n"
    "• смотреть курсы криптовалют;\n"
    "• вести историю операций;\n"
    "• смотреть статистику.\n\n"
    "👇 Открой приложение:"
)

dp = Dispatcher()


def open_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📊 Открыть P2P Myjot", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not WEBAPP_URL.startswith("https://"):
        await message.answer("⚠️ WEBAPP_URL не настроен: нужен https-адрес вашего домена Bothost.")
        return
    await message.answer(START_TEXT, reply_markup=open_keyboard())


async def run_api() -> None:
    from api import app  # импорт здесь, чтобы ошибки API были видны в логах

    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_bot() -> None:
    """Бот не должен ронять веб-сервер: при ошибке пишем понятный лог и выходим."""
    bot = Bot(token=BOT_TOKEN)
    try:
        me = await bot.get_me()
        log.info("Бот запущен: @%s", me.username)
        if WEBAPP_URL.startswith("https://"):
            try:  # кнопка меню рядом с полем ввода тоже открывает Mini App
                await bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(text="P2P Myjot", web_app=WebAppInfo(url=WEBAPP_URL))
                )
            except Exception as exc:  # не критично
                log.warning("Не удалось установить кнопку меню: %s", exc)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, handle_signals=False)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.error("Бот остановлен из-за ошибки (проверьте BOT_TOKEN): %r", exc)
    finally:
        await bot.session.close()


async def main() -> None:
    if not WEBAPP_URL:
        log.warning("WEBAPP_URL не задан — кнопка Mini App в боте работать не будет")
    elif not WEBAPP_URL.startswith("https://"):
        log.warning("WEBAPP_URL должен начинаться с https:// (требование Telegram)")

    bot_task = None
    if BOT_TOKEN:
        bot_task = asyncio.create_task(run_bot(), name="bot")
    else:
        log.error("BOT_TOKEN не задан! Запущен только веб-сервер (/health работает), бот выключен.")

    try:
        await run_api()  # возвращается при остановке контейнера или падает при ошибке
    finally:
        if bot_task:
            bot_task.cancel()
            await asyncio.gather(bot_task, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Остановлено")
