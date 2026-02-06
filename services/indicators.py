
import pandas as pd
import numpy as np

class IndicatorEngine:
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50) # Fill NaN with neutral

    @staticmethod
    def calculate_zigzag(df: pd.DataFrame, deviation_percent: float = 1.0) -> list:
        """
        Identify local Highs and Lows for Wave Analysis.
        Simple ZigZag algorithm implementation.
        """
        closes = df['close'].values
        timestamps = df['timestamp'].values
        
        pivots = [] # List of (index, price, type) where type is 'peak' or 'valley'
        
        # Simple implementation: Look for percentage deviation
        last_pivot_price = closes[0]
        last_pivot_idx = 0
        trend = 0 # 1 for up, -1 for down, 0 for init
        
        for i in range(1, len(closes)):
            price = closes[i]
            change = (price - last_pivot_price) / last_pivot_price * 100
            
            if trend == 0:
                if change >= deviation_percent:
                    trend = 1
                    last_pivot_price = price
                    last_pivot_idx = i
                elif change <= -deviation_percent:
                    trend = -1
                    last_pivot_price = price
                    last_pivot_idx = i
            elif trend == 1:
                if price > last_pivot_price:
                    last_pivot_price = price
                    last_pivot_idx = i
                elif change <= -deviation_percent:
                    pivots.append({'index': last_pivot_idx, 'price': last_pivot_price, 'type': 'peak', 'time': timestamps[last_pivot_idx]})
                    trend = -1
                    last_pivot_price = price
                    last_pivot_idx = i
            elif trend == -1:
                if price < last_pivot_price:
                    last_pivot_price = price
                    last_pivot_idx = i
                elif change >= deviation_percent:
                    pivots.append({'index': last_pivot_idx, 'price': last_pivot_price, 'type': 'valley', 'time': timestamps[last_pivot_idx]})
                    trend = 1
                    last_pivot_price = price
                    last_pivot_idx = i
                    
        # Add the potential last point
        pivots.append({'index': last_pivot_idx, 'price': last_pivot_price, 'type': 'peak' if trend == 1 else 'valley', 'time': timestamps[last_pivot_idx]})
        
        return pivots

    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # RSI
        df['rsi'] = IndicatorEngine.calculate_rsi(df)
        
        # Volume SMA
        df['vol_sma'] = df['volume'].rolling(window=20).mean()
        
        # ZigZag (Just storing as a separate object usually, but can mark in DF)
        # For DataFrame augmentation, we might just flag is_pivot
        df['is_pivot'] = 0
        pivots = IndicatorEngine.calculate_zigzag(df)
        for p in pivots:
            idx = p['index']
            if idx < len(df):
                df.iloc[idx, df.columns.get_loc('is_pivot')] = 1 if p['type'] == 'peak' else -1
                
        return df, pivots
