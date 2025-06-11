# utils/websocket_handler.py
import asyncio, json, logging, websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from datetime import datetime

async def candle_stream(symbol: str, interval: str = "1m"):
    """
    Async generator that yields a dict every time a candle closes.
    Keeps the WebSocket alive; reconnects only on errors.
    """
    ws_url = f"wss://fstream.binance.com/ws/{symbol.lower()}@kline_{interval}"
    logging.info(f"Connecting to {ws_url}")

    while True:                       # outer reconnect loop
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                logging.info(f"✅ Connected to {symbol.upper()} {interval} stream")
                async for msg in ws:  # keeps reading until socket dies
                    data = json.loads(msg)
                    k = data.get("k", {})
                    if k.get("x"):    # closed candle
                        candle = {
                            "timestamp": datetime.fromtimestamp(k["t"] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                            "open":  float(k["o"]),
                            "high":  float(k["h"]),
                            "low":   float(k["l"]),
                            "close": float(k["c"]),
                            "volume":float(k["v"]),
                        }
                        logging.info(f"📊 Candle Closed - {symbol.upper()} {interval}: {candle}")
                        yield candle
        except (ConnectionClosedError, ConnectionClosedOK) as e:
            logging.warning(f"🔌 WebSocket closed: {e}. Reconnecting…")
        except Exception as e:
            logging.exception("🔥 Unexpected WebSocket error:")

        await asyncio.sleep(2)        # small back-off before reconnect
