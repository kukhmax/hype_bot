
import asyncio
import logging
import os
import html

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
        ai_result = await ai_service.analyze_market(symbol, df, pivots)
        
        # 4. Генерируем график
        chart_buffer = ChartGenerator.generate_chart(df, symbol, "1h", pivots)
        
        # 5. Формируем ответ
        confidence = ai_result.get('confidence', 0)
        confidence_emoji = "🟢" if confidence >= 7 else "🟡"
        if confidence < 5: confidence_emoji = "🔴"
        
        # Экранирование HTML тегов в тексте от ИИ
        reasoning_safe = html.escape(str(ai_result.get('reasoning', '')))
        setup_safe = html.escape(str(ai_result.get('setup_name', '')))
        
        # Перевод сигнала на русский
        raw_signal = str(ai_result.get('signal', '')).upper()
        signal_ru = raw_signal
        if "LONG" in raw_signal:
            signal_ru = "LONG (Покупка) 📈"
        elif "SHORT" in raw_signal:
            signal_ru = "SHORT (Продажа) 📉"
        elif "NEUTRAL" in raw_signal:
            signal_ru = "NEUTRAL (Ждем) 😐"
            
        signal_safe = html.escape(signal_ru)
        
        # Краткая подпись для графика (чтобы не превысить лимит 1024 символа)
        short_caption = (
            f"📊 <b>Анализ {symbol} (1H)</b>\n"
            f"Сигнал: <b>{signal_safe}</b> {confidence_emoji}\n"
            f"Сетап: {setup_safe}\n"
            f"Уверенность: {confidence}/10\n\n"
            f"🎯 Вход: {ai_result.get('entry_range')}\n"
            f"🛑 Стоп: {ai_result.get('stop_loss')}\n"
            f"✅ Тейк: {ai_result.get('take_profit_1')} / {ai_result.get('take_profit_2')}\n\n"
            f"👇 <i>Подробное обоснование ниже</i>"
        )
        
        # Полный текст обоснования отдельным сообщением
        full_text = (
            f"📝 <b>Подробный анализ {symbol}:</b>\n\n"
            f"{reasoning_safe}"
        )
        
        # Удаляем сообщение "думаю" и присылаем результат
        await status_msg.delete()
        
        if chart_buffer:
            input_file = BufferedInputFile(chart_buffer.read(), filename=f"{symbol}_chart.png")
            # Отправляем фото с краткими данными
            await message.answer_photo(photo=input_file, caption=short_caption, parse_mode="HTML")
            # Отправляем подробности следом
            await message.answer(full_text, parse_mode="HTML")
        else:
            await message.answer(short_caption + "\n\n" + full_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in handler: {e}", exc_info=True)
        # Если status_msg уже удален, edit_text вызовет ошибку. Лучше отправить новое сообщение.
        try:
            await message.answer(f"⚠️ Произошла ошибка: {str(e)}")
        except:
            # Если совсем все плохо (например бота заблочили), просто логируем
            logger.error("Failed to send error message to user")
async def main():
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Ошибка: Не задан TG_TOKEN в .env")
    else:
        # На Windows/Linux разное поведение loop policy, но для Linux обычно ок стандарт.
        asyncio.run(main())
