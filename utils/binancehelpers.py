from binance.client import Client
import logging
import requests
import time
import os 
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

client = Client(api_key, api_secret)

def get_usdt_balance():
    while True:
        try:
            futures_account = client.futures_account()  # USDT-margined futures
            assets = futures_account['assets']
            for asset in assets:
                if asset['asset'] == 'USDT':
                    marginBalance = asset['marginBalance']

            return float(marginBalance)

        except requests.exceptions.RequestException as e:
            logging.warning(f"⚠️ Error fetching positions: {e}. Retrying")
            time.sleep(0.1)

def percentage_at_risk(risk_amount):
    while True:
        try:
            positions = client.futures_account()['positions']

            open_positions = [
                pos for pos in positions
                if float(pos['positionAmt']) != 0.0
            ]
            if len(open_positions) != 0:
                amount_at_risk = risk_amount*len(open_positions)
                percentage_at_risk = round((amount_at_risk / get_usdt_balance() * 100) ,2)
            else:
                print("No open positions")
                percentage_at_risk = 0

            return percentage_at_risk

        except requests.exceptions.RequestException as e:
            logging.warning(f"⚠️ Error fetching positions: {e}. Retrying")
            time.sleep(0.1)

def entry_price(order_id):
    while True:
        try:
            trades = client.futures_account_trades(symbol="SOLUSDT")

            matching_trades = [t for t in trades if t['orderId'] == order_id]

            if not matching_trades:
                print("❌ No trades found for that order ID.")
            else:
                total_qty = sum(float(t['qty']) for t in matching_trades)
                weighted_sum = sum(float(t['price']) * float(t['qty']) for t in matching_trades)
                avg_entry_price = weighted_sum / total_qty

            return avg_entry_price

        except requests.exceptions.RequestException as e:
            logging.warning(f"⚠️ Error fetching positions: {e}. Retrying")
            time.sleep(0.1)

def get_total_open_order():
    while True: 
        try: 
            open_orders = client.futures_get_open_orders()
            return len(open_orders)
        except Exception as e: 
            logging.warning(f"⚠️ Error fetching open orders: {e}. Retrying")
            time.sleep(0.1)


if __name__ == '__main__':
    print(get_total_open_order())