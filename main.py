
import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

from services.market_data import MarketDataService
from services.indicators import IndicatorEngine
from services.ai_analyst import AIService
from services.charts import ChartGenerator
from services.trading import TradingService # Пока не используем для исполнения, но инициализируем

# Загрузка конфига
load_dotenv()
TOKEN = os.getenv("TG_TOKEN")

# Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация сервисов (Global Singletons)
bot = Bot(token=TOKEN)
dp = Dispatcher()

market_data = MarketDataService()
ai_service = AIService()
# trading_service = TradingService() # Раскомментируем когда настроим ключи

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Привет! Я HypeBot.\n"
        "Отправь мне тикер (например, `ETH` или `BTC`), чтобы получить AI-анализ "
        "волн Эллиотта и Вайкоффа на Hyperliquid."
    )

@dp.message(F.text)
async def analyze_ticker(message: types.Message):
    """
    Основной сценарий: Текст -> Анализ -> График + Сигнал.
    """
    symbol = message.text.upper().strip()
    status_msg = await message.answer(f"🔎 Собираю данные для {symbol}...")
    
    try:
        # 1. Получаем данные (1 час)
        df = market_data.get_candles(symbol, interval="1h", limit=200)
        
        if df.empty:
            await status_msg.edit_text(f"❌ Не удалось найти данные по тикеру {symbol}.")
            return

        # 2. Считаем индикаторы
        df, pivots = IndicatorEngine.add_all_indicators(df)
        
        await bot.edit_message_text(f"🧠 Gemini анализирует структуру рынка для {symbol}...", chat_id=message.chat.id, message_id=status_msg.message_id)

        # 3. Спрашиваем ИИ
        # Передаем копию, чтобы не сломать логику если меняется df
        ai_result = ai_service.analyze_market(symbol, df, pivots)
        
        # 4. Генерируем график
        chart_buffer = ChartGenerator.generate_chart(df, symbol, "1h", pivots)
        
        # 5. Формируем ответ
        confidence_emoji = "🟢" if ai_result.get('confidence', 0) >= 7 else "🟡"
        if ai_result.get('confidence', 0) < 5: confidence_emoji = "🔴"
        
        caption = (
            f"📊 **Анализ {symbol} (1H)**\n"
            f"Сигнал: **{ai_result.get('signal')}** {confidence_emoji}\n"
            f"Setup: {ai_result.get('setup_name')}\n"
            f"Confidence: {ai_result.get('confidence')}/10\n\n"
            f"🎯 Entry: {ai_result.get('entry_range')}\n"
            f"🛑 Stop: {ai_result.get('stop_loss')}\n"
            f"✅ TP: {ai_result.get('take_profit_1')} / {ai_result.get('take_profit_2')}\n\n"
            f"📝 _Reasoning:_ {ai_result.get('reasoning')}"
        )
        
        # Удаляем сообщение "думаю" и присылаем результат
        await status_msg.delete()
        
        if chart_buffer:
            input_file = BufferedInputFile(chart_buffer.read(), filename=f"{symbol}_chart.png")
            await message.answer_photo(photo=input_file, caption=caption, parse_mode="Markdown")
        else:
            await message.answer(caption, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in handler: {e}", exc_info=True)
        await status_msg.edit_text(f"⚠️ Произошла ошибка: {str(e)}")

async def main():
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Ошибка: Не задан TG_TOKEN в .env")
    else:
        # На Windows/Linux разное поведение loop policy, но для Linux обычно ок стандарт.
        asyncio.run(main())
