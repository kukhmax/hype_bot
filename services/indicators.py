
import pandas as pd
import numpy as np

class IndicatorEngine:
    """
    Движок для расчета технических индикаторов (RSI, ZigZag, Volume SMA).
    Необходим для предварительной аналитики перед отправкой данных в AI.
    """

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Расчет индекса относительной силы (RSI).
        
        :param df: DataFrame с колонкой 'close'
        :param period: Период расчета (стандарт 14)
        :return: Series со значениями RSI
        """
        # Вычисляем разницу цен закрытия
        delta = df['close'].diff()
        
        # Разделяем на рост (gain) и падение (loss)
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # Формула RSI
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Заполняем пропуски (первые 14 свечей) значением 50 (нейтрально)
        return rsi.fillna(50)

    @staticmethod
    def calculate_zigzag(df: pd.DataFrame, deviation_percent: float = 1.0) -> list:
        """
        Алгоритм ZigZag для поиска локальных экстремумов (вершин и впадин).
        Помогает ИИ визуально определять волны Эллиотта.
        
        :param df: DataFrame с ценами
        :param deviation_percent: Минимальное отклонение в % для фиксации разворота
        :return: Список словарей [{'index', 'price', 'type', 'time'}]
        """
        closes = df['close'].values
        timestamps = df['timestamp'].values
        
        pivots = [] # Здесь будем хранить найденные точки
        
        last_pivot_price = closes[0]
        last_pivot_idx = 0
        trend = 0 # 0 - не определен, 1 - вверх, -1 - вниз
        
        for i in range(1, len(closes)):
            price = closes[i]
            # Изменение цены в процентах от прошлого пивота
            change = (price - last_pivot_price) / last_pivot_price * 100
            
            if trend == 0:
                # Инициализация первого движения
                if change >= deviation_percent:
                    trend = 1
                    last_pivot_price = price
                    last_pivot_idx = i
                elif change <= -deviation_percent:
                    trend = -1
                    last_pivot_price = price
                    last_pivot_idx = i
            elif trend == 1:
                # Если идем вверх и цена стала еще выше — обновляем хай
                if price > last_pivot_price:
                    last_pivot_price = price
                    last_pivot_idx = i
                # Если цена упала больше чем на deviation — фиксируем вершину и меняем тренд
                elif change <= -deviation_percent:
                    pivots.append({
                        'index': last_pivot_idx, 
                        'price': last_pivot_price, 
                        'type': 'peak', 
                        'time': timestamps[last_pivot_idx]
                    })
                    trend = -1
                    last_pivot_price = price
                    last_pivot_idx = i
            elif trend == -1:
                # Если идем вниз и цена стала еще ниже — обновляем лоу
                if price < last_pivot_price:
                    last_pivot_price = price
                    last_pivot_idx = i
                # Если цена выросла больше чем на deviation — фиксируем дно и меняем тренд
                elif change >= deviation_percent:
                    pivots.append({
                        'index': last_pivot_idx, 
                        'price': last_pivot_price, 
                        'type': 'valley', 
                        'time': timestamps[last_pivot_idx]
                    })
                    trend = 1
                    last_pivot_price = price
                    last_pivot_idx = i
                    
        # Добавляем последнюю известную точку как потенциальный пивот
        pivots.append({
            'index': last_pivot_idx, 
            'price': last_pivot_price, 
            'type': 'peak' if trend == 1 else 'valley', 
            'time': timestamps[last_pivot_idx]
        })
        
        return pivots

    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
        """
        Метод-обертка для расчета всех индикаторов разом.
        """
        df = df.copy()
        
        # 1. RSI
        df['rsi'] = IndicatorEngine.calculate_rsi(df)
        
        # 2. SMA Объема (20 периодов) - чтобы видеть всплески
        df['vol_sma'] = df['volume'].rolling(window=20).mean()
        
        # 3. ZigZag (считаем, но в DataFrame пишем только флаги)
        df['is_pivot'] = 0 # 0 - нет, 1 - пик, -1 - дно
        pivots = IndicatorEngine.calculate_zigzag(df)
        
        # Интегрируем пивоты в DataFrame
        for p in pivots:
            idx = p['index']
            # Проверяем, не выходит ли индекс за границы (на случай ошибок)
            if idx < len(df):
                val = 1 if p['type'] == 'peak' else -1
                # is_pivot колонка, строка idx
                df.iloc[idx, df.columns.get_loc('is_pivot')] = val
                
        return df, pivots
