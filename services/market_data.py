
import pandas as pd
from hyperliquid.info import Info
from hyperliquid.utils import constants

class MarketDataService:
    def __init__(self, base_url=constants.MAINNET_API_URL):
        self.info = Info(base_url=base_url, skip_ws=True)

    def get_candles(self, symbol: str, interval: str = "1h", limit: int = 100) -> pd.DataFrame:
        """
        Fetch candles from Hyperliquid and return as DataFrame.
        Intervals: 15m, 1h, 4h, etc.
        """
        # Mapping common intervals to Hyperliquid format if needed, 
        # but usually they match (15m, 1h).
        
        print(f"Fetching {limit} candles for {symbol} on {interval}...")
        try:
            # Note: Hyperliquid SDK typically returns raw lists.
            # info.candles_snapshot(coin, interval, startTime, endTime)
            # We usually just get the latest snapshot.
            raw_candles = self.info.candles_snapshot(symbol, interval)
            
            if not raw_candles:
                print(f"No candles returned for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(raw_candles)
            
            # Hyperliquid returns columns: ['t', 'T', 's', 'i', 'o', 'c', 'h', 'l', 'v', 'n']
            # t: start time, o: open, c: close, h: high, l: low, v: volume
            
            # Rename for clarity
            df = df.rename(columns={
                't': 'timestamp',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            })
            
            # Type conversion
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)
            
            # Parse timestamp (ms to datetime)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Sort and slice
            df = df.sort_values('timestamp').iloc[-limit:]
            
            return df.reset_index(drop=True)

        except Exception as e:
            print(f"Error fetching candles: {e}")
            return pd.DataFrame()
