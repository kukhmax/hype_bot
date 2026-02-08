import unittest
import pandas as pd
import numpy as np
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.getcwd())

from services.setup_finder import SetupFinder

class TestSetupFinder(unittest.TestCase):
    def setUp(self):
        self.finder = SetupFinder()
        # Генерируем 1000 свечей (несколько дней) для проверки Anchored VWAP
        dates = pd.date_range(start='2024-01-01', periods=1000, freq='5min')
        self.df = pd.DataFrame({
            'timestamp': dates,
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.0,
            'volume': 1000.0,
            'datetime': dates
        })
        
    def test_indicators_calculation(self):
        df = self.finder.calculate_indicators(self.df)
        self.assertIn('ema9', df.columns)
        self.assertIn('vwap', df.columns)
        self.assertIn('rsi', df.columns)

    def test_long_pullback_setup(self):
        """
        Тест нахождения ЛОНГ сетапа (Pullback).
        Условия:
        1. Trend: Close > VWAP, EMA9 > EMA21
        2. RSI: был 30-40, развернулся вверх
        3. Support: Цена была у EMA21
        """
        # Сначала прогоняем расчет индикаторов, чтобы получить структуру
        df = self.finder.calculate_indicators(self.df)
        
        # Модифицируем последние строки для имитации сетапа
        # Нам нужны iloc[-2] (сигнальная), iloc[-3] (предыдущая) и история для EMA/VWAP
        
        # Индексы (последние)
        curr_idx = 998 # iloc[-2]
        prev_idx = 997 # iloc[-3]
        
        # Настраиваем EMA и VWAP "вручную" в DataFrame, 
        # НО find_setup пересчитывает индикаторы!
        # Поэтому мы должны переопределить calculate_indicators или подделать цены так, чтобы индикаторы сложились.
        # Подделывать цены сложно. Проще замокать метод calculate_indicators или просто подать уже готовый DF с индикаторами,
        # если изменить find_setup, чтобы он не пересчитывал если уже есть.
        # Но код find_setup вызывает calculate_indicators безусловно.
        
        # В таком случае, давайте просто пропатчим данные ПОСЛЕ расчета в find_setup?
        # Нет, find_setup - это черный ящик.
        
        # Ок, тогда наследуемся и переопределяем calculate_indicators для теста, чтобы он возвращал то что нам надо.
        
        class MockSetupFinder(SetupFinder):
            def calculate_indicators(self, df):
                # Возвращаем DF как есть (предполагаем индикаторы там уже проставлены нами)
                return df

        mock_finder = MockSetupFinder()
        df_mock = df.copy()
        
        # Устанавливаем тренд вверх
        df_mock['vwap'] = 100
        df_mock['ema21'] = 101
        df_mock['ema9'] = 102 # EMA9 > EMA21
        
        # Сигнальная свеча (curr, -2)
        df_mock.loc[curr_idx, 'close'] = 103 # > VWAP
        df_mock.loc[curr_idx, 'ema9'] = 102
        df_mock.loc[curr_idx, 'ema21'] = 101
        df_mock.loc[curr_idx, 'vwap'] = 100
        
        # RSI разворот
        df_mock.loc[prev_idx, 'rsi'] = 35 # Был в зоне 25-40
        df_mock.loc[curr_idx, 'rsi'] = 36 # Стал выше (разворот)
        
        # Касание поддержки (в -2, -3 или -4)
        df_mock.loc[curr_idx, 'low'] = 101.05 # Почти 101 (ema21) -> разница < 0.3%
        
        # Проверяем
        result, _ = mock_finder.find_setup(df_mock)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['signal_type'], 'LONG 🟢')
        self.assertEqual(result['setup'], 'Trend Pullback')

    def test_short_pullback_setup(self):
        class MockSetupFinder(SetupFinder):
            def calculate_indicators(self, df):
                return df
                
        mock_finder = MockSetupFinder()
        df_mock = self.df.copy()
        
        curr_idx = 998
        prev_idx = 997
        
        # Тренд вниз
        df_mock['vwap'] = 100
        df_mock['ema21'] = 99
        df_mock['ema9'] = 98 # EMA9 < EMA21
        
        # Сигнальная свеча
        df_mock.loc[curr_idx, 'close'] = 97 # < VWAP
        df_mock.loc[curr_idx, 'ema9'] = 98
        df_mock.loc[curr_idx, 'ema21'] = 99
        df_mock.loc[curr_idx, 'vwap'] = 100
        
        # RSI разворот вниз
        df_mock.loc[prev_idx, 'rsi'] = 65 # Был в зоне 60-75
        df_mock.loc[curr_idx, 'rsi'] = 64 # Стал ниже
        
        # Касание сопротивления
        df_mock.loc[curr_idx, 'high'] = 98.9 # Почти 99 (ema21)
        
        result, _ = mock_finder.find_setup(df_mock)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['signal_type'], 'SHORT 🔴')

if __name__ == '__main__':
    unittest.main()
