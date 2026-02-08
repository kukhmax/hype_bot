
import os
import json
import logging
import pandas as pd
import numpy as np
import google.generativeai as genai
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Загружаем переменные окружения
load_dotenv()

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIService:
    """
    Сервис для взаимодействия с AI (Gemini или DeepSeek).
    Отвечает за отправку рыночных данных и получение торгового сигнала в JSON.
    """
    
    def __init__(self):
        """
        Инициализация клиента AI.
        Выбор провайдера зависит от IS_GEMINI в .env.
        """
        self.is_gemini = os.getenv("IS_GEMINI", "True").lower() == "true"
        
        if self.is_gemini:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.error("❌ GEMINI_API_KEY не найден в .env")
                raise ValueError("GEMINI_API_KEY is missing")
                
            genai.configure(api_key=api_key)
            # Конфигурация модели Gemini
            self.gemini_model = genai.GenerativeModel(
                model_name="gemini-2.5-pro",
                generation_config={
                    "temperature": 0.2,
                    "response_mime_type": "application/json"
                }
            )
            logger.info("🤖 Инициализирован Gemini 2.5 Pro")
        else:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                logger.error("❌ DEEPSEEK_API_KEY не найден в .env")
                raise ValueError("DEEPSEEK_API_KEY is missing")
            
            # DeepSeek совместим с OpenAI API
            self.deepseek_client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
            logger.info("🤖 Инициализирован DeepSeek API")

    async def analyze_market(self, symbol: str, df: pd.DataFrame, pivots: list) -> dict:
        """
        Анализирует рынок на основе DataFrame свечей и пивотов.
        """
        
        # 1. Подготовка данных в текстовом виде для промпта
        last_candle = df.iloc[-1]
        market_summary = f"""
        Current Price: {last_candle['close']}
        RSI (14): {last_candle['rsi']:.2f}
        Volume 20SMA: {last_candle['vol_sma']:.2f}
        Current Volume: {last_candle['volume']}
        """
        
        # Формируем CSV строку последних 40 свечей для модели
        csv_data = df.tail(40).to_csv(index=False)
        
        # Helper to convert numpy types to python types for JSON serialization
        def default(o):
            if isinstance(o, (np.int64, np.int32)): return int(o)
            if isinstance(o, (np.float64, np.float32)): return float(o)
            raise TypeError

        # Identified ZigZag Pivots (Local Extrema)
        pivots_json = json.dumps(pivots[-5:], default=default) if pivots else "None"
        
        system_prompt = f"""
        Ты эксперт-трейдер, специализирующийся на Волновой теории Эллиота, методе Вайкоффа и Фибоначчи.
        
        Задача: Проанализируй предоставленные OHLCV данные для {symbol} (1H таймфрейм) и определи, есть ли высоковероятный торговый сетап.
        
        Правила анализа:
        1. **Волны Эллиота**: Определи текущую структуру. Импульс (1,3,5) или Коррекция (A,B,C). Мы ищем вход в начале 3-й или 5-й волны.
        2. **Вайкофф**: Ищи фазы накопления/распределения. Есть ли Spring (пружина) или Upthrust (вынос)? Тест уровней.
        3. **Фибоначчи и Уровни**: Используй уровни Фибоначчи для определения целей (TP) зоны входа.
        4. **Индикаторы**: RSI дивергенция как подтверждение.
        
        Требования к ответу:
        Верни СТРОГО валидный JSON следующей структуры (ключи на английском, значения reason на РУССКОМ):
        {{
            "signal": "LONG" | "SHORT" | "NEUTRAL",
            "confidence": <int 1-10>,
            "setup_name": "<string, например: Пробой 3-й волны>",
            "entry_range": [<float min>, <float max>],
            "stop_loss": <float price>,
            "take_profit_1": <float price>,
            "take_profit_2": <float price>,
            "reasoning": "<ПОДРОБНОЕ объяснение на РУССКОМ языке. Опиши какая сейчас волна Эллиота, что происходит по Вайкоффу (фаза, тесты), есть ли дивергенция RSI. Объясни, почему выбраны именно такие уровни Stop Loss и Take Profit (уровни Фибо, хай/лоу свинга).>"
        }}
        
        Важно:
        - Если уверенность < 7, signal = "NEUTRAL".
        - Stop Loss должен быть логичным (за лоу свинга для лонга).
        - Risk:Reward (RR) минимум 1:2.
        - Ответ "reasoning" должен быть детальным, чтобы пользователь понимал логику входа.
        """

        user_content = f"""
        Контекст рынка:
        {market_summary}
        
        Последние свечи (Last 40):
        {csv_data}
        
        Пивоты ZigZag (Локальные экстремумы):
        {pivots_json}
        """
        
        try:
            logger.info(f"🧠 Отправка данных в {'Gemini' if self.is_gemini else 'DeepSeek'} для {symbol}...")
            
            if self.is_gemini:
                # Gemini требует полный промпт в одном вызове (или chat history, но тут one-shot)
                full_gemini_prompt = system_prompt + "\n\n" + user_content
                response = self.gemini_model.generate_content(full_gemini_prompt)
                response_text = response.text
            else:
                # DeepSeek (OpenAI) использует messages
                response = await self.deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                response_text = response.choices[0].message.content
            
            # Парсинг ответа
            result = json.loads(response_text)
            logger.info(f"✅ Анализ завершен. Сигнал: {result.get('signal')} (Conf: {result.get('confidence')})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запросе к AI: {e}")
            # Возвращаем безопасный нейтральный сигнал при ошибке
            return {"signal": "NEUTRAL", "confidence": 0, "reasoning": "AI Error: " + str(e)}

    async def analyze_setup(self, symbol: str, timeframe: str, setup_info: dict, df: pd.DataFrame) -> dict:
        """
        Валидирует технический сетап.
        """
        last_candle = df.iloc[-1]
        market_summary = f"""
        Price: {last_candle['close']}
        RSI: {last_candle['rsi']:.2f}
        VWAP: {last_candle['vwap']:.2f}
        EMA9: {last_candle['ema9']:.2f}
        EMA21: {last_candle['ema21']:.2f}
        """
        
        system_prompt = f"""
        Ты опытный крипто-трейдер. Твоя задача — подтвердить или отклонить технический сетап от алгоритма.
        
        Алгоритм нашел сетап: {setup_info.get('setup')} 
        Тип: {setup_info.get('signal_type')}
        Цена входа: {setup_info.get('price')}
        
        Посмотри на последние 30 свечей (CSV) и ответь честно:
        1. Видишь ли ты сильные уровни поддержки/сопротивления прямо перед входом? (Если да — опасно).
        2. Есть ли противоречия (например, сильный даунтренд на старшем ТФ, хотя сигнал в лонг)?
        3. Согласен ли ты с сигнал?
        
        Верни JSON:
        {{
            "is_confirmed": true/false,
            "confidence": <int 1-10>,
            "comment": "<Краткое мнение на РУССКОМ>"
        }}
        """
        
        csv_data = df.tail(30).to_csv(index=False)
        user_content = f"Market Context:\n{market_summary}\n\nLast 30 candles:\n{csv_data}"
        
        try:
            if self.is_gemini:
                prompt = system_prompt + "\n\n" + user_content
                response = self.gemini_model.generate_content(prompt)
                text = response.text
            else:
                 response = await self.deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    response_format={"type": "json_object"}
                )
                 text = response.choices[0].message.content
            
            return json.loads(text)
        except Exception as e:
            logger.error(f"AI Validation Error: {e}")
            return {"is_confirmed": True, "confidence": 5, "comment": "AI error, skipping validation"}

if __name__ == "__main__":
    print("Test run requires API Key and Data.")
