import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SetupFinder:
    """
    Класс для поиска торговых сетапов.
    Строгая логика: VWAP (фильтр) + EMA 9/21 (структура) + RSI (триггер).
    """

    def __init__(self):
        self.rsi_period = 9
        self.ema_fast = 9
        self.ema_slow = 21

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # 1. EMA 9 и 21
        df['ema9'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        
        # 2. RSI 9
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)
        
        # 3. VWAP (Anchored to Day Start - Session VWAP)
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        df['pv'] = df['tp'] * df['volume']
        
        # Группировка по дате для сброса VWAP в начале каждого дня (Anchored VWAP)
        # Это решает проблему "100 свечей мало" - мы берем 1000 свечей в main.py,
        # и VWAP считается честно от 00:00 UTC
        grouped = df.groupby(df['datetime'].dt.date)
        df['cum_pv'] = grouped['pv'].cumsum()
        df['cum_vol'] = grouped['volume'].cumsum()
        
        df['vwap'] = df['cum_pv'] / df['cum_vol']
        
        return df

    def find_setup(self, df: pd.DataFrame) -> tuple[dict | None, pd.DataFrame]:
        """
        Ищет сетап на последних свечах.
        Возвращает (сетап, dataframe_с_индикаторами).
        """
        if df.empty or len(df) < 50:
            return None, df
            
        df = self.calculate_indicators(df)
        
        # Данные: 
        # current (формируется) = iloc[-1]
        # signal_candle (закрытая) = iloc[-2]
        # prev (предыдущая) = iloc[-3]
        
        curr = df.iloc[-2]  # Сигнальная свеча (закрытая)
        prev = df.iloc[-3]  # Для сравнения RSI (было -> стало)
        
        # --- ЛОГИКА LONG ---
        # 1. Цена выше VWAP
        # 2. EMA 9 > EMA 21
        # 3. RSI был в зоне отката (30-40, но >= 25) и развернулся вверх
        
        trend_long = (curr['close'] > curr['vwap']) and (curr['ema9'] > curr['ema21'])
        
        # RSI условия:
        # В предыдущий момент RSI был в зоне покупки (25 < RSI < 40)
        # Сейчас RSI вырос (разворот)
        rsi_was_low = (25 <= prev['rsi'] <= 40)
        rsi_turning_up = (curr['rsi'] > prev['rsi']) and (curr['rsi'] > 30)
        
        # Откат к EMA21 или VWAP
        # Проверяем Low свечи (или предыдущих пары свечей) на касание зоны поддержки
        # Допустим касание было в течение последних 3 свечей
        near_support = False
        for i in range(2, 5):
            row = df.iloc[-i]
            # Цена подошла к EMA21 (снизу или сверху близко)
            dist_ema = abs(row['low'] - row['ema21']) / row['ema21']
            if dist_ema < 0.003: # 0.3% близость
                near_support = True
                break
        
        if trend_long and rsi_was_low and rsi_turning_up and near_support:
            return {
                'signal_type': 'LONG 🟢',
                'setup': 'Trend Pullback',
                'price': curr['close'],
                'time': curr['datetime'],
                'stop_loss': min(curr['ema21'], curr['vwap']) * 0.998,
                'take_profit': curr['close'] + (curr['close'] - min(curr['ema21'], curr['vwap'])) * 2
            }, df

        # --- ЛОГИКА SHORT ---
        # 1. Цена ниже VWAP
        # 2. EMA 9 < EMA 21
        # 3. RSI был в зоне 60-70 (но <= 75) и развернулся вниз
        
        trend_short = (curr['close'] < curr['vwap']) and (curr['ema9'] < curr['ema21'])
        
        rsi_was_high = (60 <= prev['rsi'] <= 75)
        rsi_turning_down = (curr['rsi'] < prev['rsi']) and (curr['rsi'] < 70)
        
        near_resistance = False
        for i in range(2, 5):
            row = df.iloc[-i]
            dist_ema = abs(row['high'] - row['ema21']) / row['ema21']
            if dist_ema < 0.003:
                near_resistance = True
                break

        if trend_short and rsi_was_high and rsi_turning_down and near_resistance:
             return {
                'signal_type': 'SHORT 🔴',
                'setup': 'Trend Pullback',
                'price': curr['close'],
                'time': curr['datetime'],
                'stop_loss': max(curr['ema21'], curr['vwap']) * 1.002,
                'take_profit': curr['close'] - (max(curr['ema21'], curr['vwap']) - curr['close']) * 2
            }, df
            
        return None, df
