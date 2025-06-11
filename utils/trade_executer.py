import time
import hmac
import hashlib
import requests
import logging 
import os 
from dotenv import load_dotenv

load_dotenv()

class BinanceFuturesTrader:
    BASE_URL = 'https://fapi.binance.com'

    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')

    def _sign(self, params):
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(self.api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        return signature

    def _post(self, endpoint, params):
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._sign(params)
        headers = {"X-MBX-APIKEY": self.api_key}
        response = requests.post(f"{self.BASE_URL}{endpoint}", headers=headers, params=params)
        try:
            response.raise_for_status()
        except Exception as e:
            logging.error("HTTP Error: ", e)
            logging.error("Response body:", response.text)
        return response.json()

    def set_leverage(self, symbol, leverage):
        params = {'symbol': symbol, 'leverage': leverage}
        return self._post('/fapi/v1/leverage', params)

    def place_market_order(self, symbol, side, quantity):
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity
        }
        logging.info(f"Params: {params}")
        try: 
            self.res = self._post('/fapi/v1/order', params)
            logging.info(f"Successfully executed MARKET IN ORDER with ID: {self.res['orderId']}")
            return self.res 
        except Exception as e:
            logging.error(f"An error occurred in BinanceFuturesTrader.place_market_order | Error: {e}")
            raise

    def set_stop_loss(self, symbol, side, stop_price, quantity):
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'STOP_MARKET',
            'stopPrice': stop_price,
            'quantity': quantity,
            'timeInForce': 'GTC'
        }
        try:
            self.res = self._post('/fapi/v1/order', params)
            logging.info(f"Successfully executed STOPLOSS ORDER with ID: {self.res['orderId']}")
            return self.res
        except Exception as e:
            logging.error(f"An error occurred in BinanceFuturesTrader.set_stop_loss | Error: {e}")
            raise

    def set_take_profit_limit(self, symbol, side, stop_price, price, quantity): 
        # stop_price is when the order is triggered, price is the limit price 
        # for faster execution, set price < stop_price so that when the market price hit the stop_price, the order will be filled at limit price 
        # if price > stop_price then there is a chance the order gets stuck due to price pull back
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'TAKE_PROFIT',
            'stopPrice': stop_price,
            'price': price,
            'quantity': quantity,
            'timeInForce': 'GTC'
        }
        try:
            self.res = self._post('/fapi/v1/order', params)
            logging.info(f"Successfully executed TAKEPROFIT ORDER with ID: {self.res['orderId']}")
            return self.res
        except Exception as e:
            logging.error(f"An error occurred in BinanceFuturesTrader.set_take_profit_limit | Error: {e}")
            raise

trade = BinanceFuturesTrader()
trade.place_market_order('SOLUSDT',"BUY",1)

