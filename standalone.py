import asyncio
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# --- КОНФИГУРАЦИЯ ---
# Вставьте сюда токен вашего бота
BOT_TOKEN = "8234928556:AAGW43f-WgzsbhVbz_lahKD7DYyopmQgdE4"
# Вставьте ваш Telegram ID (числом, не строкой)
TARGET_USER_ID = 2036883627 

# --- ДАННЫЕ (Эмуляция того, что пришло от AI) ---
summary_data = {
    "session_id": "c2ff764c",
    "duration": "~10 минут",
    "participants": ["Mukhametzhan", "Тимур", "Лена"],
    "key_decisions": [
        "Изменить формат ответа с токенов на JSON (access + refresh)",
        "Сдвинуть дедлайн задач на 13:00"
    ],
    # Сгенерированные задачи (Jira Tasks)
    "tasks": [
        {"id": "DEV-101", "title": "Backend: Обновить схему БД", "assignee": "Mukhametzhan", "deadline": "13:00"},
        {"id": "DEV-102", "title": "Backend: Новый JSON формат {access_token, refresh ..", "assignee": "Тимур", "deadline": "13:00"},
        {"id": "DEV-103", "title": "Frontend: UI Интеграция", "assignee": "Лена", "deadline": "13:30"}
    ],
    "questions": [
        "Сколько времени потребуется на проверку изменений?",
        "Как скоро можно поднять API?"
    ],
    "text_summary": "Команда обсудила изменения в схеме базы данных и формат ответа API. Решено ускорить выполнение к 13:00. Mukhametzhan занимается миграциями, Тимур готовит пример JSON, Лена ждет API для тестов."
}

async def send_scrum_report():
    # Инициализация бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    try:
        # 1. Формируем Текст Сообщения (HTML разметка)
        
        # Блок задач Jira
        jira_block = f"<b>🚀 Создано новых задач: {len(summary_data['tasks'])}</b>\n"
        for task in summary_data['tasks']:
            jira_block += f"• <code>{task['title']}</code> — <b>{task['deadline']}</b> ({task['assignee']})\n"
        
        # Блок Сводки (Красивое оформление)
        report_text = (
            f"{jira_block}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>🤖 AI Scrum Master - Сводка Совещания</b>\n\n"
            f"📅 <b>Сессия:</b> <code>{summary_data['session_id']}</code>\n"
            f"⏱ <b>Длительность:</b> {summary_data['duration']}\n\n"
            
            f"👥 <b>Участники:</b>\n" + 
            "\n".join([f"• {p}" for p in summary_data['participants']]) + "\n\n"
            
            f"🎯 <b>Ключевые Решения:</b>\n" +
            "\n".join([f"• {d}" for d in summary_data['key_decisions']]) + "\n\n"
            
            f"✅ <b>Задачи и Действия:</b>\n" +
            "\n".join([f"• {t['title']} ({t['assignee']})" for t in summary_data['tasks']]) + "\n\n"
            
            f"❓ <b>Обсуждённые Вопросы:</b>\n" +
            "\n".join([f"• {q}" for q in summary_data['questions']]) + "\n\n"
            
            f"📝 <b>Сводка:</b>\n"
            f"<i>{summary_data['text_summary']}</i>"
        )

        # 2. Формируем Кнопки (Inline Keyboard)
        buttons = []
        
        # Генерируем кнопки для каждой задачи
        for task in summary_data['tasks']:
            # Пример ссылки на Jira (заглушка)
            jira_url = f"https://jira.atlassian.net/browse/{task['id']}"
            btn_text = f"📎 {task['id']} ({task['assignee']})"
            buttons.append([InlineKeyboardButton(text=btn_text, url=jira_url)])
        
        # Добавляем общую кнопку "Открыть доску"
        buttons.append([InlineKeyboardButton(text="🔗 Открыть Scrum Board", url="https://jira.atlassian.net/board/1")])

        markup = InlineKeyboardMarkup(inline_keyboard=buttons)

        # 3. Отправка
        print(f"Отправка сообщения пользователю {TARGET_USER_ID}...")
        await bot.send_message(
            chat_id=TARGET_USER_ID,
            text=report_text,
            reply_markup=markup
        )
        print("✅ Сообщение успешно отправлено!")

    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send_scrum_report())