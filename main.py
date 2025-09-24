import ccxt
import pandas as pd
import ta
import time
from datetime import datetime

# ======================
# CONFIG
# ======================
SYMBOL = "BTC/USDT"
TIMEFRAME = "4h"        # intervalle bougie
LIMIT = 50              # nombre de bougies à récupérer
INITIAL_BALANCE = 1000
TRADING_FEES = 0.001
MIN_BTC_TO_SELL = 0.0001

RSI_PERIOD = 14
RSI_BUY = 30
RSI_SELL = 70
SELL_FRACTION = 0.5
TRAILING_STOP_BASE = 0.03
SMA_PERIOD = 50

# Délai entre chaque vérification en secondes
SLEEP_TIME = 60

# ======================
# Connexion Testnet Binance
# ======================
exchange = ccxt.binance({
    'apiKey': 'hPd9FbJLObt0jG0r5ZdQrtbX9BirMiaokX3WRrB1rbZtVeWLfQSwOGuvf2d13agE',
    'secret': 'EP1LjU7unlRTNoRlcdl2VvkDBCypD7HCKDKWDOtZaN0LvRqjSBhMVSUUdcT0mCUv',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})
exchange.set_sandbox_mode(True)

# ======================
# PORTFOLIO PAPER TRADING
# ======================
usdt_balance = INITIAL_BALANCE
btc_balance = 0
entry_price = None
peak_price = None
last_trade_time = None

# ======================
# FONCTION DE RÉCUP BOUCLES
# ======================
def get_latest_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)
    df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# ======================
# BOUCLE PRINCIPALE
# ======================
while True:
    try:
        df = get_latest_data()
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=RSI_PERIOD).rsi()
        df['sma'] = df['close'].rolling(SMA_PERIOD).mean()

        latest = df.iloc[-1]
        price = latest['close']
        rsi = latest['rsi']
        sma = latest['sma']
        date = latest['timestamp']

        if pd.isna(rsi) or pd.isna(sma):
            print(f"{datetime.now()} → Waiting for enough data...")
            time.sleep(SLEEP_TIME)
            continue

        last_trade_time
        # ===== ACHAT =====
        if rsi < RSI_BUY and price < sma and usdt_balance > 0:
            btc_balance = (usdt_balance * (1 - TRADING_FEES)) / price
            entry_price = price
            peak_price = price
            usdt_balance = 0
            last_trade_time = date  # <-- pas besoin de global
            print(f"{date} → BUY {btc_balance:.6f} BTC @ {price:.2f} (RSI+SMA)")

        # Mettre à jour peak si BTC détenu
        if btc_balance > 0 and price > peak_price:
            peak_price = price

        # ===== TRAILING STOP =====
        trailing_stop_price = None
        if btc_balance > 0:
            recent_volatility = df['close'].iloc[-20:].pct_change().std() or 0
            trailing_stop_price = peak_price * (1 - max(TRAILING_STOP_BASE, recent_volatility*2))

        # ===== VENTE =====
        sell_signal = False
        reason = ""
        if btc_balance > 0:
            if rsi > RSI_SELL:
                sell_signal = True
                reason = "RSI SELL"
            elif trailing_stop_price and price <= trailing_stop_price:
                sell_signal = True
                reason = "Trailing stop"

        if sell_signal:
            btc_to_sell = btc_balance * SELL_FRACTION
            if btc_to_sell >= MIN_BTC_TO_SELL:
                usdt_balance += btc_to_sell * price * (1 - TRADING_FEES)
                btc_balance -= btc_to_sell
                last_trade_time = date
                print(f"{date} → SELL {btc_to_sell:.6f} BTC @ {price:.2f} ({reason})")
            if btc_balance < MIN_BTC_TO_SELL:
                usdt_balance += btc_balance * price * (1 - TRADING_FEES)
                print(f"{date} → SELL {btc_balance:.6f} BTC @ {price:.2f} (Liquidation finale)")
                btc_balance = 0
                entry_price = None
                peak_price = None

        # Affichage portefeuille toutes les bougies
        total_value = usdt_balance + btc_balance * price
        print(f"{datetime.now()} → Portfolio Value: {total_value:.2f} USDT, BTC: {btc_balance:.6f}")

        # Attendre la prochaine vérification
        time.sleep(SLEEP_TIME)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)
