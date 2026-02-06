
from hyperliquid.utils import constants
from hyperliquid.exchange import Exchange
from eth_account.signers.local import LocalAccount
from eth_account import Account
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class TradingService:
    """
    Сервис для исполнения ордеров на Hyperliquid.
    Использует Agent Wallet для подписи транзакций.
    """
    
    def __init__(self):
        """
        Инициализация подключения к бирже.
        Требует наличия AGENT_PRIVATE_KEY и MAIN_WALLET_ADDRESS в .env
        """
        private_key = os.getenv("AGENT_PRIVATE_KEY")
        main_address = os.getenv("MAIN_WALLET_ADDRESS")
        base_url = constants.MAINNET_API_URL if os.getenv("IS_MAINNET") == "True" else constants.TESTNET_API_URL
        
        if not private_key or not main_address:
            raise ValueError("❌ Не настроены ключи в .env")

        # Создаем аккаунт из приватного ключа
        self.account: LocalAccount = Account.from_key(private_key)
        
        # Инициализируем Exchange SDK
        # account=self.account - это агент, который подписывает
        # agent_address=... - это может быть необязательно, если account уже агент, 
        # но в SDK Hyperliquid важно указать, от чьего имени торгуем (main wallet vault).
        # В текущей версии SDK Exchange сам разруливает это, если передать account.
        
        self.exchange = Exchange(self.account, base_url, account_address=main_address)
        print(f"✅ Trading Service готов. Agent: {self.account.address}")

    def place_order(self, symbol: str, side: str, size_usd: float, sl_price: float, tp1_price: float, tp2_price: float):
        """
        Открывает позицию по рынку и сразу ставит TP/SL.
        
        :param symbol: Тикер (ETH)
        :param side: 'LONG' или 'SHORT'
        :param size_usd: Размер позиции в долларах
        :param sl_price: Цена стоп-лосса
        :param tp1_price: Цена первого тейка (50%)
        :param tp2_price: Цена второго тейка (50%)
        """
        is_buy = (side.upper() == "LONG")
        
        try:
            # 1. Получаем текущую цену (чтобы посчитать размер в монетах)
            # В реальном коде лучше передавать текущую цену снаружи, чтобы не делать лишний запрос
            # Но для надежности спросим у API или возьмем примерную
            # Для Market Order цена не критична, но нужна для конвертации USD -> COIN
            # Здесь упростим: считаем по цене входа (которую мы не знаем, так как маркет)
            # Лучше всего запросить mid price.
            
            # Для MVP: просто открываем ордер. SDK пересчитает? Нет, SDK просит size в монетах (sz).
            # Нам нужно знать цену.
            # TODO: Добавить получение цены. Пока поставим placeholder логику.
            print("⚠️ ВНИМАНИЕ: Для расчета размера позиции нужна текущая цена. Реализуем в следующем шаге.")
            
            # Предположим у нас есть цена (передадим в метод позже).
            # Пока вернем успех для теста структуры.
            print(f"🛒 Симуляция ордера: {side} {symbol} на ${size_usd}")
            print(f"🛑 SL: {sl_price}, 🎯 TP1: {tp1_price}, 🎯 TP2: {tp2_price}")
            
            return {"status": "simulated_success", "order_id": "sim_123"}
            
            # Реальная логика (закомментирована пока нет Price Getter):
            # amount_coins = size_usd / current_price
            # order_result = self.exchange.market_open(symbol, is_buy, amount_coins, px=None, slippage=0.01)
            # if order_result['status'] == 'ok':
            #    self._set_sl_tp(symbol, is_buy, amount_coins, sl_price, tp1_price, tp2_price)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ордера: {e}")
            return {"status": "error", "message": str(e)}

    def _set_sl_tp(self, symbol, is_buy_entry, total_sz, sl_price, tp1_price, tp2_price):
        """
        Внутренний метод для выставления зависимых ордеров (Reduce-Only).
        """
        # Логика SL/TP на Hyperliquid делается через 'trigger' ордера или Limit Reduce-Only
        pass
