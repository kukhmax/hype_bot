
import pandas as pd
import mplfinance as mpf
import io

class ChartGenerator:
    """
    Генератор графиков для отправки в Telegram.
    Использует библиотеку mplfinance для рисования японских свечей.
    """
    
    @staticmethod
    def generate_chart(df: pd.DataFrame, symbol: str, interval: str, pivots: list = None, support_resistance: list = None) -> io.BytesIO:
        """
        Рисует график свечей и наносит разметку.
        
        :param df: DataFrame с данными
        :param symbol: Тикер
        :param interval: Таймфрейм
        :param pivots: (Опционально) Точки ZigZag для отрисовки линий
        :return: Байтовый буфер с картинкой (PNG)
        """
        # mplfinance требует индекс DateTimeIndex
        plot_df = df.copy()
        plot_df.set_index('datetime', inplace=True)
        
        # Настройка стиля
        s = mpf.make_mpf_style(base_mpf_style='charles', rc={'font.size': 8})
        
        # Буфер для сохранения
        buf = io.BytesIO()
        
        title = f"{symbol} Analysis ({interval}) - Hyperliquid Data"
        
        try:
            mpf.plot(
                plot_df,
                type='candle',
                volume=True,
                title=title,
                style=s,
                savefig=dict(fname=buf, dpi=100, bbox_inches='tight'),
                warn_too_much_data=1000  # Suppress warnings
            )
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"❌ Ошибка генерации графика: {e}")
            return None
