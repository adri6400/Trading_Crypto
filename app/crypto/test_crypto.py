import time
from datetime import datetime
from binance.client import Client
import numpy as np
import csv
import math
# Remplacez par vos propres clés API
API_KEY = 'wBk3JT4e3D66Ozla3SrVsj2yPtdKEIxO0ov367d4mvx0ltlgLWF3CInS43J1cXUZ'
API_SECRET = 'JfvBOFAMvHWxp1162U2qU6in4neKzPDNRhsx6iNyc6Jdpds3Zx0OwYU6d026Pjcs'

client = Client(API_KEY, API_SECRET)

# Liste des cryptos à surveiller, sans Bitcoin
SYMBOLS = ['ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 'XRPUSDT', 'DOGEUSDT','XRPUSDT','TRXUSDT', 'AVAXUSDT']
INTERVAL = Client.KLINE_INTERVAL_1MINUTE
LOOKBACK_PERIOD = '3 days ago UTC'
CHECK_INTERVAL = 30
PRICE_DROP_THRESHOLD = 0.02
PRICE_INCREASE_TARGET = 0.015
STOP_LOSS_THRESHOLD = 0.10
MIN_USDT_BALANCE = 10
INVEST_RATIO = 0.40 # Utilisez 10% du solde USDT disponible
CSV_FILE = 'positions.csv'
LOG_FILE = 'transactions.log'

def log_transaction(message):
    with open(LOG_FILE, 'a') as log_file:
        log_file.write(f"{datetime.now()} - {message}\n")
    print(message)

def get_historical_data(symbol, interval, lookback_period):
    klines = client.get_historical_klines(symbol, interval, lookback_period)
    closes = [float(kline[4]) for kline in klines]
    return np.array(closes)

def get_usdt_balance():
    account = client.get_account()
    balance_usdt = next((float(asset['free']) for asset in account['balances'] if asset['asset'] == 'USDT'), 0.0)
    return balance_usdt

def get_min_order_size(symbol):
    exchange_info = client.get_exchange_info()
    min_qty = None
    min_notional = None
    step_size = None
    for s in exchange_info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    min_qty = float(f['minQty'])
                    step_size = float(f['stepSize'])
                elif f['filterType'] == 'NOTIONAL':
                    min_notional = float(f.get('minNotional', 0))
            return min_qty, min_notional, step_size
    return None, None, None

def load_positions():
    positions = {}
    try:
        with open(CSV_FILE, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                symbol = row['symbol']
                positions[symbol] = {
                    'in_position': row['in_position'] == 'True',
                    'buy_price': float(row['buy_price']) if row['buy_price'] else 0.0
                }
    except FileNotFoundError:
        positions = {symbol: {'in_position': False, 'buy_price': 0.0} for symbol in SYMBOLS}
    return positions

def save_positions(positions):
    with open(CSV_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['symbol', 'in_position', 'buy_price'])
        for symbol, position in positions.items():
            writer.writerow([symbol, position['in_position'], position['buy_price']])

def main():
    positions = load_positions()

    while True:
        usdt_balance = get_usdt_balance() * INVEST_RATIO  # Utiliser seulement une partie du solde        
        for symbol in SYMBOLS:
            closes = get_historical_data(symbol, INTERVAL, LOOKBACK_PERIOD)
            current_price = closes[-1]
            min_price_72h = np.min(closes)
            position = positions.get(symbol, {'in_position': False, 'buy_price': 0.0})
            
            # Obtenir les quantités minimales et le step_size
            min_qty, min_notional, step_size = get_min_order_size(symbol)
            if min_notional is None or min_qty is None or step_size is None:
                log_transaction(f"Erreur : Impossible d'obtenir les minimums pour {symbol}")
                continue
            
            # Calculer la quantité possible et l'arrondir au step_size
            quantity = usdt_balance / current_price
            quantity = math.floor(quantity / step_size) * step_size  # Arrondir selon le step_size
            
            if quantity < min_qty or usdt_balance < min_notional:
                continue

            if not position['in_position']:
                if usdt_balance >= MIN_USDT_BALANCE and current_price <= min_price_72h * (1 + PRICE_DROP_THRESHOLD):
                    log_transaction(f"Achat de {symbol} à {current_price} avec {usdt_balance} USDT disponible")
                    client.order_market_buy(symbol=symbol, quantity=quantity)
                    position['buy_price'] = current_price
                    position['in_position'] = True
                    usdt_balance -= position['buy_price']
                    save_positions(positions)
                else:
                    print(f"Fonds insuffisants pour acheter {symbol} ou prix non optimal")
            else:
                if current_price >= position['buy_price'] * (1 + PRICE_INCREASE_TARGET):
                    log_transaction(f"Vente de {symbol} à {current_price} pour prendre un profit")
                    client.order_market_sell(symbol=symbol, quantity=quantity)
                    position['in_position'] = False
                    usdt_balance += current_price
                    save_positions(positions)
                elif current_price <= position['buy_price'] * (1 - STOP_LOSS_THRESHOLD):
                    log_transaction(f"Vente de {symbol} à {current_price} pour limiter les pertes")
                    client.order_market_sell(symbol=symbol, quantity=quantity)
                    position['in_position'] = False
                    usdt_balance += current_price
                    save_positions(positions)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()