from utils.websocket_handler import candle_stream
from utils.logger import init_logger
from time import sleep
import utils.indicator_cache as indicator 
import utils.binancehelpers as binance
import utils.trade_executer as execute
import asyncio, logging, websockets
from utils.supabase_client import log_into_supabase, get_latest_group_id, get_latest_trades
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
order_table_name = os.getenv("ORDER_TABLE")
supabase_api_key = os.getenv("SUPABASE_API_KEY")
supbase_jwt = os.getenv("SUPABASE_JWT")
strategy = int(os.getenv("STRATEGY_ENV"))

symbol = "SOLUSDT"
interval = "5m"

if strategy == 1: 
    risk_amount = 15
    sl_percentage = 1.1
    fee = 0.1
    portfolio_threshold = 20
    rsi_lower = 30
    rsi_upper = 70
    sma_period = 20
    bb_std_dev = 2
    breakeven_buffer = 0.05
    rsi_period = 14
    max_concurrent_trades = 8
else: 
    risk_amount = 2
    sl_percentage = 0.5
    fee = 0.1
    portfolio_threshold = 20
    rsi_lower = 30
    rsi_upper = 70
    sma_period = 30
    bb_std_dev = 2
    breakeven_buffer = 0.03
    rsi_period = 7
    max_concurrent_trades = 3

usdt_entry_size = risk_amount / ((sl_percentage + fee) / 100)
trade = execute.BinanceFuturesTrader()

async def main():
    init_logger()
    cache = indicator.CandleCache()
    historical_data = cache.fetch_historical_data(symbol=symbol, interval=interval, limit=150)
    cache = indicator.CandleCache(historical_data=historical_data)
    
    async for candle in candle_stream(symbol, interval):   # ← stays connected

        group_id = get_latest_group_id(supabase_url=supabase_url, api_key=supabase_api_key, jwt=supbase_jwt)
        group_id += 1    
        
        cache.add_candle(candle)
        bb = cache.calculate_bollinger_bands(period = sma_period, num_std_dev = bb_std_dev)
        rsi = cache.calculate_rsi(period = rsi_period)

        if bb is not None:
            logging.info(f"BB Upper: {bb['upper']} BB Lower: {bb['lower']} SMA: {bb['sma']}")
        else:
            logging.info("BB: None")
        
        if rsi is not None: 
            logging.info(f"RSI: {rsi}")
        else: 
            logging.info("RSI: None")
        
        percentage_at_risk = binance.percentage_at_risk(risk_amount)
        logging.info(f"Portfolio risk: {percentage_at_risk}")

        recent_trades = get_latest_trades(supabase_url=supabase_url, api_key=supabase_api_key, jwt=supbase_jwt)
        
        #######
        # Cooldown after loss 
        # Ensure no trades made within the next 5 mins after a loss 
        #######
        
        if recent_trades and recent_trades[0]['realized_pnl'] and recent_trades[0]['is_closed'] == True and strategy == 2:
            if recent_trades[0]['realized_pnl'] < 0:
                last_exit_time = datetime.strptime(recent_trades[0]['exit_time'], "%Y-%m-%dT%H:%M:%S.%f")
                now = datetime.utcnow()
                difference_seconds = (now - last_exit_time).total_seconds()
                if difference_seconds < 300: 
                    continue

        #######
        # Max concurrent trades
        #######
        if recent_trades and strategy == 2: 
            open_trades = sum(1 for trade in recent_trades if not trade['is_closed'])
            if open_trades > max_concurrent_trades: 
                continue

        if percentage_at_risk < portfolio_threshold: 
            
            logging.info(f"Portfolio risk: {percentage_at_risk} percent lower than threshold: {portfolio_threshold}, looking for entry")
            last_close = cache.candles[-1]['close']
            prev_close = cache.candles[-2]['close']
            sol_entry_size = round(usdt_entry_size / last_close,2)

            strategy_condition_long  = (prev_close < bb['lower'] and last_close > bb['lower'] and rsi >= rsi_lower ) if strategy == 2 else (last_close <= bb['lower'] and rsi <= rsi_lower)
            strategy_condition_short = (prev_close > bb['upper'] and last_close < bb['upper'] and rsi < rsi_upper) if strategy == 2 else (last_close >= bb['upper'] and rsi >= rsi_upper)

            if strategy_condition_long:                
                logging.info("Close price lower than lower bollinger band ... Entering LONG")
                logging.info(f"Close price: {last_close}")
                logging.info(f"Lower bollinger band: {bb['lower']}")

                try:
                    logging.info(f"Quantity: {sol_entry_size}")
                    market_in = trade.place_market_order(symbol=symbol, side = "BUY", quantity=sol_entry_size)
                    sleep(1)
                    logging.info(market_in)
                    market_in_order_id = market_in['orderId']

                except Exception as e:
                    logging.error(f"Something went wrong executing MARKET IN ORDER, error: {e}")
                    return e
                                
                data = {
                    "group_id": group_id,
                    "order_id": market_in_order_id,
                    "type": "MO",
                    "direction": "LONG",
                    "breakeven_threshold": 0.00,
                    "breakeven_price": 0.00
                }

                try:
                    log_into_supabase(data, supabase_url=supabase_url, api_key=supabase_api_key, jwt=supbase_jwt)
                    logging.info("MARKET IN Trade logged to Supabase")
                
                except Exception as e:
                    logging.error(f"Failed to log MARKET IN trade to Supabase: {e}")
                
                sleep(2)
                actual_entry_price = binance.entry_price(market_in_order_id)

                stoploss_price = round(actual_entry_price - (actual_entry_price * sl_percentage / 100),2)
                # takeprofit_price = round(actual_entry_price + (actual_entry_price * tp_percentage / 100),2)
                takeprofit_price = round(bb['sma'],2)

                try: 
                    stoploss_order = trade.set_stop_loss(symbol=symbol, side="SELL", stop_price=stoploss_price, quantity=sol_entry_size)
                    sleep(1)
                    logging.info(stoploss_order)
                    stoploss_order_id = stoploss_order['orderId']

                except Exception as e:
                    logging.error(f"Something went wrong executing STOPLOSS ORDER, error: {e}")
                    return e
                
                try:
                    takeprofit_order = trade.set_take_profit_limit(symbol=symbol, side="SELL", stop_price=takeprofit_price, price=takeprofit_price, quantity=sol_entry_size)
                    sleep(1)
                    logging.info(takeprofit_order)
                    takeprofit_order_id = takeprofit_order['orderId']

                except Exception as e:
                    logging.error(f"Something went wrong executing TAKEPROFIT ORDER, error: {e}")
                    return e
                
                # Breakeven calculations
                # breakeven_indicator = round(actual_entry_price + (actual_entry_price * breakeven_indicator_percentage / 100),2)
                breakeven_price = round(actual_entry_price + (actual_entry_price * fee / 100),2)
                breakeven_indicator = breakeven_price + breakeven_buffer

                # Log SL into DB 
                data = {
                    "group_id": group_id,
                    "order_id": stoploss_order_id,
                    "type": "SL",
                    "direction": "LONG",
                    "breakeven_threshold": breakeven_indicator,
                    "breakeven_price": breakeven_price
                }
                try:
                    log_into_supabase(data, supabase_url=supabase_url, api_key=supabase_api_key, jwt=supbase_jwt)
                    logging.info("STOPLOSS Trade logged to Supabase")
                
                except Exception as e:
                    logging.error(f"Failed to log STOPLOSS trade to Supabase: {e}")

                # Log TP into DB 

                data = {
                    "group_id": group_id,
                    "order_id": takeprofit_order_id,
                    "type": "TP",
                    "direction": "LONG",
                    "breakeven_threshold": 0.00,
                    "breakeven_price": 0.00
                }
                try:
                    log_into_supabase(data, supabase_url=supabase_url, api_key=supabase_api_key, jwt=supbase_jwt)
                    logging.info("TAKEPROFIT Trade logged to Supabase")
                
                except Exception as e:
                    logging.error(f"Failed to log TAKEPROFIT trade to Supabase: {e}")

            
            elif strategy_condition_short:

                logging.info("Close price higher than upper bollinger band ... Entering SHORT")
                logging.info(f"Close price: {last_close}")
                logging.info(f"Upper bollinger band: {bb['upper']}")

                try: 
                    logging.info(f"Quantity: {sol_entry_size}")
                    market_in = trade.place_market_order(symbol=symbol, side = "SELL", quantity=sol_entry_size)
                    market_in_order_id = market_in['orderId']
                
                except Exception as e:
                    logging.error(f"Something went wrong executing MARKET IN ORDER, error: {e}")
                    return e
                
                # Log into DB 
                data = {
                    "group_id": group_id,
                    "order_id": market_in_order_id,
                    "type": "MO",
                    "direction": "SHORT",
                    "breakeven_threshold": 0.00,
                    "breakeven_price": 0.00
                }
                try:
                    log_into_supabase(data, supabase_url=supabase_url, api_key=supabase_api_key, jwt=supbase_jwt)
                    logging.info("MARKET IN Trade logged to Supabase")
                
                except Exception as e:
                    logging.error(f"Failed to log MARKET IN trade to Supabase: {e}")

                sleep(2)
                actual_entry_price = binance.entry_price(market_in_order_id)
                
                stoploss_price = round(actual_entry_price + (actual_entry_price * sl_percentage / 100),2)
                # takeprofit_price = round(actual_entry_price - (actual_entry_price * sl_percentage / 100),2)
                takeprofit_price = round(bb['sma'],2) 

                try:
                    stoploss_order = trade.set_stop_loss(symbol=symbol, side="BUY", stop_price=stoploss_price, quantity=sol_entry_size)
                    stoploss_order_id = stoploss_order['orderId']

                except Exception as e:
                    logging.error(f"Something went wrong executing STOPLOSS ORDER, error: {e}")
                    return e
                
                try:
                    takeprofit_order = trade.set_take_profit_limit(symbol=symbol, side="BUY", stop_price=takeprofit_price, price=takeprofit_price, quantity=sol_entry_size)
                    takeprofit_order_id = takeprofit_order['orderId']
                
                except Exception as e:
                    logging.error(f"Something went wrong executing TAKEPROFIT ORDER, error: {e}")
                    return e
                
                # Breakeven calculations
                # breakeven_indicator = round(actual_entry_price - (actual_entry_price * breakeven_indicator_percentage / 100),2)
                breakeven_price = round(actual_entry_price - (actual_entry_price * fee / 100),2)
                breakeven_indicator = breakeven_price - breakeven_buffer 

                # Log SL into DB 
                # Log SL into DB 
                data = {
                    "group_id": group_id,
                    "order_id": stoploss_order_id,
                    "type": "SL",
                    "direction": "SHORT",
                    "breakeven_threshold": breakeven_indicator,
                    "breakeven_price": breakeven_price
                }
                try:
                    log_into_supabase(data, supabase_url=supabase_url, api_key=supabase_api_key, jwt=supbase_jwt)
                    logging.info("STOPLOSS Trade logged to Supabase")
                
                except Exception as e:
                    logging.error(f"Failed to log STOPLOSS trade to Supabase: {e}")

                # Log TP into DB 

                data = {
                    "group_id": group_id,
                    "order_id": takeprofit_order_id,
                    "type": "TP",
                    "direction": "SHORT",
                    "breakeven_threshold": 0.00,
                    "breakeven_price": 0.00
                }
                try:
                    log_into_supabase(data, supabase_url=supabase_url, api_key=supabase_api_key, jwt=supbase_jwt)
                    logging.info("TAKEPROFIT Trade logged to Supabase")
                
                except Exception as e:
                    logging.error(f"Failed to log TAKEPROFIT trade to Supabase: {e}")

            else: 
                logging.info('Price within bands no entry')
        
asyncio.run(main())