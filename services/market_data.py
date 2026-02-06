
import pandas as pd
from hyperliquid.info import Info
from hyperliquid.utils import constants

class MarketDataService:
    """
    Сервис для работы с рыночными данными (свечи, цены) через Hyperliquid API.
    """
    
    def __init__(self, base_url=constants.MAINNET_API_URL):
        """
        Инициализация подключения к Info API.
        
        :param base_url: URL API (Mainnet или Testnet)
        """
        # skip_ws=True отключает WebSocket, используем только HTTP для запросов
        self.info = Info(base_url=base_url, skip_ws=True)

    def get_candles(self, symbol: str, interval: str = "1h", limit: int = 100) -> pd.DataFrame:
        """
        Получает исторические свечи (OHLCV) для указанной пары.

        :param symbol: Тикер (например, 'ETH' или 'BTC')
        :param interval: Таймфрейм ('15m', '1h', '4h')
        :param limit: Количество свечей (по умолчанию 100)
        :return: DataFrame с колонками [timestamp, open, high, low, close, volume, datetime]
        """
        print(f"🔄 Загружаю {limit} свечей для {symbol} ({interval})...")
        try:
            import time
            end_time = int(time.time() * 1000)
            # Приблизительный расчет времени старта (с запасом)
            # 1h = 3600*1000, 4h = ...
            # Для простоты берем интервал в миллисекундах
            interval_ms = 3600 * 1000 # default 1h
            if interval == "15m": interval_ms = 15 * 60 * 1000
            elif interval == "4h": interval_ms = 4 * 3600 * 1000
            
            start_time = end_time - (limit * interval_ms)
            
            # Получаем снапшот свечей через SDK
            raw_candles = self.info.candles_snapshot(symbol, interval, start_time, end_time)
            
            if not raw_candles:
                print(f"⚠️ Нет данных для {symbol}")
                return pd.DataFrame()

            # Преобразуем список словарей в DataFrame
            df = pd.DataFrame(raw_candles)
            
            # Hyperliquid возвращает сокращенные ключи:
            # t: timestamp start
            # T: timestamp end
            # s: symbol
            # i: interval
            # o: open price
            # c: close price
            # h: high price
            # l: low price
            # v: volume
            # n: number of trades
            
            # Переименовываем для удобства
            df = df.rename(columns={
                't': 'timestamp',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            })
            
            # Приводим типы данных из строк/чисел в floaf
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)
            
            # Добавляем читаемую дату
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Сортируем по времени (на всякий случай) и берем последние limit
            df = df.sort_values('timestamp').iloc[-limit:]
            
            return df.reset_index(drop=True)

        except Exception as e:
            print(f"❌ Ошибка при получении свечей: {e}")
            return pd.DataFrame()
