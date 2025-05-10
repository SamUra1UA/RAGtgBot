import asyncio
import aiohttp
import logging
import os
import json
import time
from dotenv import load_dotenv
from telethon import TelegramClient, events

# Завантажуємо змінні середовища
load_dotenv()


last_user_request_time = {}


# Налаштування логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Ваші облікові дані Telegram API
api_id = int(os.getenv('API_ID'))  # переконайтесь, що це ціле число
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('BOT_TOKEN')

# API ключ і база URL
API_BASE_URL = 'https://ais-rag.geekscode.dev'
API_KEY = os.getenv('API_KEY')


client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)
# === UID кеш ===
UID_CACHE_FILE = "uids.json"

def load_uid_cache():
    if os.path.exists(UID_CACHE_FILE):
        with open(UID_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_uid_cache():
    with open(UID_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(user_chat_uids, f, ensure_ascii=False, indent=2)

user_chat_uids = load_uid_cache()

# === Обробка команд ===
@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond("Привіт! Я бот кафедри СШІ 🤖\nНапиши запитання і я постараюсь на нього відповісти!")
    logger.info(f"Команда /start від користувача {event.sender_id}")
    raise events.StopPropagation

@client.on(events.NewMessage(pattern='/new'))
async def new(event):
    await event.respond("Створюю для тебе новий чат...")
    logger.info(f"Команда /new від користувача {event.sender_id}")

    headers = {
        "xAuth": API_KEY
    }
    sender_id = str(event.sender_id)
    logger.info("Створюємо новий чат...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE_URL}/new-chat", headers=headers) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    uid = data["uid"]
                    user_chat_uids[sender_id] = uid
                    save_uid_cache()
                    logger.info(f"Чат створено, отримано uid: {uid}")
                    await event.respond("Новий чат успішно створено ✅")
                else:
                    logger.error(f"Помилка при створенні чату: статус {resp.status}")
                    await event.respond("Йой, халепа! 😢 Не вдалося створити чат.")
    except Exception as e:
        logger.error(f"Помилка при створенні нового чату: {e}")
        await event.respond("Йой, халепа! 😢 Щось пішло не так.")

    raise events.StopPropagation



@client.on(events.NewMessage)
async def handle_question(event):
    sender_id = str(event.sender_id)
    message = event.message

    current_time = time.time()
    last_time = last_user_request_time.get(sender_id)

    if last_time and current_time - last_time < 10:
        await event.reply("Вибачте, наступний запит можливий через 10 секунд.")
        return

    last_user_request_time[sender_id] = current_time

    if message.media or message.voice or message.audio or message.video or message.document:
        logger.info(f"Отримано медіа повідомлення від користувача {sender_id}")
        await event.reply("Будь ласка, надішліть питання текстом.")
        return

    question = message.message
    logger.info(f"Отримано повідомлення від користувача {sender_id}: {question}")

    headers = {
        "xAuth": API_KEY
    }

    try:
        async with aiohttp.ClientSession() as session:
            uid = user_chat_uids.get(sender_id)
            if not uid:
                logger.info("Створюємо новий чат...")
                async with session.post(f"{API_BASE_URL}/new-chat", headers=headers) as resp:
                    if resp.status == 201:
                        data = await resp.json()
                        uid = data["uid"]
                        user_chat_uids[sender_id] = uid
                        save_uid_cache()
                        logger.info(f"Чат створено, отримано uid: {uid}")
                    else:
                        logger.error(f"Помилка при створенні чату: {resp.status}")
                        await event.reply("Помилка при створенні чату.")
                        return
            else:
                logger.info(f"Використовується збережений uid {uid} для користувача {sender_id}")

            # Паралельна задача затримки
            notify_task = asyncio.create_task(asyncio.sleep(2))

            # Надсилання запиту
            async with session.post(f"{API_BASE_URL}/chat/{uid}", json={"query": question}, headers=headers) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    content = response_data.get("content", "Немає відповіді.")
                    logger.info(f"Отримано відповідь від API: {content}")
                    if not notify_task.done():
                        notify_task.cancel()
                    await event.reply(content)
                else:
                    logger.error(f"Помилка при надсиланні запиту до API: {resp.status}")
                    await event.reply("Помилка при надсиланні запиту до API.")

            # Якщо через 30 секунд ще не було відповіді
            try:
                await notify_task
                await event.reply("Ваш запит все ще в обробці, зачекайте трохи або створіть новий чат і спробуйте знову! 🥲")
            except asyncio.CancelledError:
                pass


    except Exception as e:
        logger.error(f"Сталася помилка: {str(e)}")
        await event.reply(f"Сталася помилка.")

# Запуск
client.run_until_disconnected()

