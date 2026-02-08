
import unittest
import pandas as pd
import numpy as np
import sys
import os

# Добавляем корневую директорию в путь, чтобы импортировать services
sys.path.append(os.getcwd())

from services.setup_finder import SetupFinder

class TestSetupFinder(unittest.TestCase):
    def setUp(self):
        self.finder = SetupFinder()
        
        # Создаем тестовый DataFrame (200 свечей)
        # Генерируем данные, похожие на рынок
        self.length = 200
        dates = pd.date_range(start='2024-01-01', periods=self.length, freq='5min')
        
        # Имитация восходящего тренда
        close = np.linspace(100, 150, self.length) + np.random.normal(0, 1, self.length)
        high = close + np.random.uniform(0, 2, self.length)
        low = close - np.random.uniform(0, 2, self.length)
        volume = np.random.uniform(100, 1000, self.length)
        
        self.df = pd.DataFrame({
            'timestamp': dates,
            'open': close, # упрощенно open=close
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'datetime': dates
        })

    def test_indicators_calculation(self):
        df = self.finder.calculate_indicators(self.df)
        
        self.assertIn('ema9', df.columns)
        self.assertIn('ema21', df.columns)
        self.assertIn('rsi', df.columns)
        self.assertIn('vwap', df.columns)
        
        # Проверяем что значения не NaN (кроме начала, где скользящие еще не сформированы)
        self.assertFalse(df['ema21'].iloc[-1] is np.nan)
        self.assertFalse(df['rsi'].iloc[-1] is np.nan)
        self.assertFalse(df['vwap'].iloc[-1] is np.nan)
        
    def test_setup_detection(self):
        # Создаем ситуацию для Pullback Long
        # Тренд вверх: EMA9 > EMA21, Close > VWAP
        # Откат: Low коснулся EMA21
        
        df = self.df.copy()
        
        # Модифицируем последние свечи вручную
        
        # Пред-предпоследняя (trend up)
        idx = -3
        df.loc[df.index[idx], 'close'] = 150
        df.loc[df.index[idx], 'open'] = 149
        df.loc[df.index[idx], 'ema9'] = 148 # Mock indicators for checking logic directly? 
        # Нет, индикаторы пересчитываются внутри find_setup, поэтому надо менять close/volume и пересчитывать
        
        # Так как индикаторы пересчитываются, сложно подогнать цену так, чтобы индикаторы сложились идеально.
        # Поэтому мы будем тестировать методы check_* переопределяя значения в row вручную.
        
        finder = SetupFinder()
        
        # Mock row data matching conditions
        row = pd.Series({
            'close': 105,
            'open': 104,
            'high': 106,
            'low': 100, # touches support
            'vwap': 102,
            'ema9': 103,
            'ema21': 101, # Support
            'rsi': 50,
            'volume': 500,
            'datetime': '2024-01-01 12:00:00'
        })
        
        prev = pd.Series({
             'close': 103,
             'open': 103,
             'ema9': 102,
             'ema21': 100,
             'volume': 100
        })
        
        prev2 = pd.Series({
            'ema9': 101,
            'ema21': 99
        })
        
        # Test Pullback Long
        # Conditions: Close > VWAP, EMA9 > EMA21, Green candle, Low <= EMA21*1.002, RSI 45-65
        result = finder.check_setup_1_pullback(row, prev, prev2)
        # row: Close(105)>VWAP(102) - OK
        # row: EMA9(103)>EMA21(101) - OK
        # row: Green (105>104) - OK
        # row: Low(100) <= EMA21(101)*1.002 (101.2) - OK
        # row: RSI(50) in 45-65 - OK
        self.assertEqual(result, "LONG (Pullback)")
        
    def test_breakout_detection(self):
        finder = SetupFinder()
        
        # Mock for Breakout Long
        # Conditions: Close > VWAP, RSI > 60, Vol > Prev*1.2, Body > Prev*1.5
        row = pd.Series({
            'close': 110, 'open': 100, 'vwap': 105, 'rsi': 65, 'volume': 200
        })
        prev = pd.Series({
            'close': 101, 'open': 100, 'volume': 100
        })
        result = finder.check_setup_2_breakout(row, prev, None)
        self.assertEqual(result, "LONG (Breakout)")

if __name__ == '__main__':
    unittest.main()
