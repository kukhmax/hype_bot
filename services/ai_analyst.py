
import os
import json
import logging
import pandas as pd
import numpy as np
import google.generativeai as genai
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIService:
    """
    Сервис для взаимодействия с Gemini 1.5 Pro.
    Отвечает за отправку рыночных данных и получение торгового сигнала в JSON.
    """
    
    def __init__(self):
        """
        Инициализация клиента Gemini.
        Ключ берется из переменной окружения GEMINI_API_KEY.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("❌ GEMINI_API_KEY не найден в .env")
            raise ValueError("GEMINI_API_KEY is missing")
            
        genai.configure(api_key=api_key)
        
        # Конфигурация модели
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-pro",
            generation_config={
                "temperature": 0.2, # Низкая температура для более детерминированных ответов (JSON)
                "response_mime_type": "application/json" # Принудительный JSON режим
            }
        )

    def analyze_market(self, symbol: str, df: pd.DataFrame, pivots: list) -> dict:
        """
        Анализирует рынок на основе DataFrame свечей и пивотов.
        
        :param symbol: Тикер (ETH)
        :param df: DataFrame с индикаторами (RSI, и т.д.)
        :param pivots: Список точек ZigZag
        :return: Словарь с торговым сигналом (парсится из JSON ответа)
        """
        
        # 1. Подготовка данных в текстовом виде для промпта
        # Берем последние 30 свечей для детального контекста, но summary по 100
        last_candle = df.iloc[-1]
        market_summary = f"""
        Current Price: {last_candle['close']}
        RSI (14): {last_candle['rsi']:.2f}
        Volume 20SMA: {last_candle['vol_sma']:.2f}
        Current Volume: {last_candle['volume']}
        """
        
        # Формируем CSV строку последних 40 свечей для модели
        csv_data = df.tail(40).to_csv(index=False)
        
        # 2. Сборка системного промпта
        # Helper to convert numpy types to python types for JSON serialization
        def default(o):
            if isinstance(o, (np.int64, np.int32)): return int(o)
            if isinstance(o, (np.float64, np.float32)): return float(o)
            raise TypeError

        # Identified ZigZag Pivots (Local Extrema)
        pivots_json = json.dumps(pivots[-5:], default=default) if pivots else "None"
        
        prompt = f"""
        You are an expert Crypto Trader algorithm specializing in Elliott Wave Theory and Wyckoff Analysis.
        
        Task: Analyze the provided OHLCV data for {symbol} (1H timeframe) and decide if there is a high-probability trade setup.
        
        Data Context:
        {market_summary}
        
        Recent Candles (Last 40):
        {csv_data}
        
        Identified ZigZag Pivots (Local Extrema):
        {pivots_json}
        
        Analysis Rules:
        1. **Elliott Wave**: Identify if we are in an Impulse (1,3,5) or Correction (A,B,C). Prefer trades in direction of Wave 3 or 5.
        2. **Wyckoff**: Look for Spring/Upthrust tests near Support/Resistance.
        3. **Indicators**: Use RSI divergence as confirmation.
        
        Output Requirements:
        Return ONLY valid JSON with this structure:
        {{
            "signal": "LONG" | "SHORT" | "NEUTRAL",
            "confidence": <int 1-10>,
            "setup_name": "<string, e.g. Wave 3 Breakout>",
            "entry_range": [<float min>, <float max>],
            "stop_loss": <float price>,
            "take_profit_1": <float price>,
            "take_profit_2": <float price>,
            "reasoning": "<concise explanation, max 2 sentences>"
        }}
        
        Important:
        - If confidence is < 7, set signal to "NEUTRAL".
        - Stop Loss must be logical (under swing low for Long).
        - RR (Risk:Reward) must be at least 1:2.
        """
        
        try:
            logger.info(f"🧠 Отправка данных в Gemini для {symbol}...")
            response = self.model.generate_content(prompt)
            
            # Парсинг ответа
            result = json.loads(response.text)
            logger.info(f"✅ Анализ завершен. Сигнал: {result.get('signal')} (Conf: {result.get('confidence')})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запросе к AI: {e}")
            # Возвращаем безопасный нейтральный сигнал при ошибке
            return {"signal": "NEUTRAL", "confidence": 0, "reasoning": "AI Error"}

if __name__ == "__main__":
    # Простой тест (можно запустить файл напрямую)
    print("Test run requires API Key and Data.")
