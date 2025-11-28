import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

BOT_TOKEN = "8234928556:AAGW43f-WgzsbhVbz_lahKD7DYyopmQgdE4"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_command(message: types.Message):
    # Create Web App button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Open AI Scrum Master",
            web_app=WebAppInfo(url="https://aiscrummaster64.lovable.app")  # Replace with your deployed URL
        )
    ]])
    
    await message.answer(
        "Welcome! 👋\n\nOpen the AI Scrum Master app to manage your tasks.",
        reply_markup=keyboard
    )

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
