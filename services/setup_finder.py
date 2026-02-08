
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SetupFinder:
    """
    Класс для поиска торговых сетапов на основе технического анализа.
    Реализует логику из SETUPS.md: VWAP, EMA 9/21, RSI 9.
    """

    def __init__(self):
        # Параметры индикаторов
        self.rsi_period = 9
        self.ema_fast = 9
        self.ema_slow = 21

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Рассчитывает необходимые индикаторы: VWAP, EMA 9, EMA 21, RSI 9.
        
        :param df: DataFrame с рыночными данными (должен содержать 'close', 'high', 'low', 'volume', 'timestamp')
        :return: DataFrame с добавленными колонками индикаторов
        """
        df = df.copy()
        
        # 1. EMA 9 и 21 (используем pandas ewm)
        df['ema9'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        
        # 2. RSI 9
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50) # Заполняем NaN
        
        # 3. VWAP (Volume Weighted Average Price)
        # Упрощенный расчет для интрадей: кумулятивная сумма (Price * Volume) / кумулятивная сумма Volume
        # Для более точного VWAP с сбросом по всем правилам нужно знать начало сессии, 
        # но для крипты часто используют скользящий или от начала загруженных данных.
        # В данном случае считаем от начала загруженного датафрейма (предполагаем, что загружено достаточно данных, напр. 200 свечей).
        
        # Типичная цена (Typical Price)
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        df['pv'] = df['tp'] * df['volume']
        
        # Кумулятивные суммы
        df['cum_pv'] = df['pv'].cumsum()
        df['cum_vol'] = df['volume'].cumsum()
        
        df['vwap'] = df['cum_pv'] / df['cum_vol']
        
        # Стандартные отклонения для VWAP Bands (опционально, упоминается в SETUPS.md)
        # Вычисляем дисперсию: sum(vol * (tp - vwap)^2) / sum(vol)
        # Но для простоты пока оставим только VWAP линию, так как в условиях входа часто используется просто "выше/ниже VWAP".
        # Добавим Bands если потребуется точное совпадение с "нижняя band VWAP".
        # Упрощенно: bands часто считают как VWAP +/- StDev(Close) * multiplier, но правильный VWAP band сложнее.
        # Пока реализуем без bands, ориентируясь на саму линию VWAP.
        
        return df

    def check_setup_1_pullback(self, row, prev_row, prev2_row) -> str | None:
        """
        Сетап 1: Pullback / Отскок (Трендовый).
        
        Условия ЛОНГ:
        - Цена выше VWAP.
        - EMA 9 > EMA 21 (тренд вверх).
        - Цена откатилась (была коррекция), RSI был не перекуплен.
        - Свеча закрылась выше, отскок.
        - RSI в нормальной зоне (45-55+).
        """
        # Логика:
        # Тренд вверх: Close > VWAP и EMA9 > EMA21
        trend_up = (row['close'] > row['vwap']) and (row['ema9'] > row['ema21'])
        
        # Ищем момент входа "на отскоке".
        # Упрощенно: Предыдущая свеча была "красной" или RSI снижался, а текущая "зеленая" и RSI растет.
        # Или цена коснулась EMA21/VWAP и отскочила.
        
        # Реализуем проверку "зеленая свеча после касания/близости к поддержке"
        is_green = row['close'] > row['open']
        is_bounce = is_green and (row['low'] <= row['ema21'] * 1.002) # Цена опускалась к EMA21 (с небольшим допуском 0.2%)
        
        rsi_ok = 45 <= row['rsi'] <= 65
        
        if trend_up and is_bounce and rsi_ok:
            return "LONG (Pullback)"
            
        # Условия ШОРТ:
        # Цена ниже VWAP.
        # EMA 9 < EMA 21.
        trend_down = (row['close'] < row['vwap']) and (row['ema9'] < row['ema21'])
        is_red = row['close'] < row['open']
        is_bounce_down = is_red and (row['high'] >= row['ema21'] * 0.998) # Цена поднималась к EMA21
        
        rsi_ok_short = 35 <= row['rsi'] <= 55
        
        if trend_down and is_bounce_down and rsi_ok_short:
             return "SHORT (Pullback)"
             
        return None

    def check_setup_2_breakout(self, row, prev_row, prev2_row) -> str | None:
        """
        Сетап 2: Breakout / Пробой (Импульсный).
        
        Условия:
        - Сильный импульс, большая свеча.
        - RSI пробивает 60-70 вверх (для лонга).
        - Volume всплеск (проверяем относительно среднего).
        """
        # Объем выше среднего (например в 1.5 раза больше SMA20 объема, которую мы считаем в indicators.py или здесь)
        # Предположим volume и vol_sma уже есть (или посчитаем локально среднее)
        # Здесь vol_sma нет, используем простое сравнение с пред. свечами
        vol_surge = row['volume'] > (prev_row['volume'] * 1.2) # Объем вырос на 20% по сравнению с прошлой (упрощенно)
        
        # Импульсная свеча
        body_size = abs(row['close'] - row['open'])
        prev_body = abs(prev_row['close'] - prev_row['open'])
        big_candle = body_size > (prev_body * 1.5)
        
        # ЛОНГ
        if (row['close'] > row['vwap']) and (row['rsi'] > 60) and vol_surge and big_candle and (row['close'] > row['open']):
            return "LONG (Breakout)"
            
        # ШОРТ
        if (row['close'] < row['vwap']) and (row['rsi'] < 40) and vol_surge and big_candle and (row['close'] < row['open']):
            return "SHORT (Breakout)"
            
        return None

    def check_setup_3_reversion(self, row, prev_row) -> str | None:
        """
        Сетап 3: Mean Reversion / Возврат к среднему (Контртренд).
        
        Условия ЛОНГ:
        - Цена сильно ниже VWAP (например, на 2-3%).
        - RSI перепродан (<30).
        - Разворотная свеча.
        """
        dist_to_vwap = (row['vwap'] - row['close']) / row['vwap']
        is_far_below = dist_to_vwap > 0.02 # 2% отклонение
        
        if is_far_below and (row['rsi'] < 30) and (row['close'] > row['open']):
             return "LONG (Reversion)"
             
        dist_to_vwap_short = (row['close'] - row['vwap']) / row['vwap']
        is_far_above = dist_to_vwap_short > 0.02
        
        if is_far_above and (row['rsi'] > 70) and (row['close'] < row['open']):
            return "SHORT (Reversion)"
            
        return None

    def find_setup(self, df: pd.DataFrame) -> dict | None:
        """
        Анализирует DataFrame и возвращает найденный сетап на последней закрытой свече.
        
        :return: Словарь с описанием сигнала или None
        """
        if df.empty or len(df) < 30:
            return None
            
        df = self.calculate_indicators(df)
        
        # Анализируем предпоследнюю свечу (last completed), так как последняя еще формируется
        # Или последнюю, если считаем что "закрытие" произошло. 
        # Обычно бот смотрит на последнюю сформированную.
        # df.iloc[-1] - это текущая (активная). df.iloc[-2] - последняя закрытая.
        # Будем смотреть на -1 (текущую) для realtime обнаружения, но нужно понимать риски перерисовки.
        # Либо на -2 для надежности. SETUPS.md говорит "вход на закрытии". -> берем -2.
        
        current = df.iloc[-1] # Текущая цена (для проверки realtime условий, если нужно)
        last_closed = df.iloc[-2]
        prev_closed = df.iloc[-3]
        prev2_closed = df.iloc[-4]
        
        # Проверяем все сетапы по приоритету
        
        # 1. Breakout (самый агрессивный)
        sig = self.check_setup_2_breakout(last_closed, prev_closed, prev2_closed)
        if sig:
            return {
                'setup': 'Breakout',
                'signal_type': sig,
                'price': last_closed['close'],
                'time': last_closed['datetime'],
                'stop_loss': last_closed['close'] * 0.995 if "LONG" in sig else last_closed['close'] * 1.005, # Условный SL
                'take_profit': last_closed['close'] * 1.015 if "LONG" in sig else last_closed['close'] * 0.985
            }
            
        # 2. Pullback (самый надежный)
        sig = self.check_setup_1_pullback(last_closed, prev_closed, prev2_closed)
        if sig:
             return {
                'setup': 'Pullback',
                'signal_type': sig,
                'price': last_closed['close'],
                'time': last_closed['datetime'],
                'stop_loss': last_closed['ema21'], # SL за EMA21
                'take_profit': last_closed['close'] + abs(last_closed['close'] - last_closed['ema21']) * 2 # TP 1:2
            }
            
        # 3. Reversion
        sig = self.check_setup_3_reversion(last_closed, prev_closed)
        if sig:
             return {
                'setup': 'Reversion',
                'signal_type': sig,
                'price': last_closed['close'],
                'time': last_closed['datetime'],
                'stop_loss': last_closed['low'] if "LONG" in sig else last_closed['high'],
                'take_profit': last_closed['vwap'] # TP на возврате к VWAP
            }
            
        return None
