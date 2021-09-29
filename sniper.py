# use for environment variables
import os, time

# used for dates
from datetime import date, datetime, timedelta

# use if needed to pass args to external modules
import sys

# used to grab the XML url list from a CSV file
import csv

# Math 
import math

# used to create threads & dynamic loading of modules
import threading
import importlib

# used for directory handling
import glob

# Needed for colorful console output Install with: python3 -m pip install colorama (Mac/Linux) or pip install colorama (PC)
from colorama import init
init()

# needed for the binance API / websockets / Exception handling
from binance.client import Client
from binance.exceptions import BinanceAPIException
from requests.exceptions import ReadTimeout, ConnectionError


# used to repeatedly execute the code
from itertools import count

# used to store trades and sell assets
import json

# Load helper modules
from helpers.parameters import (
    parse_args, load_config
)

# Load creds modules
from helpers.handle_creds import (
    load_correct_creds, test_api_key
)

# for colourful logging to the console
class txcolors:
    BUY = '\033[92m'
    WARNING = '\033[93m'
    SELL_LOSS = '\033[91m'
    SELL_PROFIT = '\033[32m'
    DIM = '\033[2m\033[35m'
    DEFAULT = '\033[39m'


# tracks profit/loss each session
global session_profit
session_profit = 0


TEST_MODE = True

PERCENTAGE = 1.004

SYMBOL = 'ETHUSD'

# path to the saved positions file
positions_file_path = 'positions.csv'

# path to the saved trades file
trades_file_path = 'trades.csv'

# positions column
positions_columns = ['date', 'id', 'pair', 'type', 'side', 'price', 'amount', 'filled', 'status', 'position']
# trades column
trades_columns = ['symbol', 'id', 'orderId', 'orderListId', 'price', 'qty', 'quoteQty', 'commission', 'commissionAsset', 'time', 'isBuyer', 'isMaker', 'isBestMatch']


def write_log(file_path, data, columns):
    try:
        with open(file_path, 'a+') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writerow(data)
            csvfile.close()
            print(f'{txcolors.BUY}Position with id {data["id"]} placed and saved to file')
    except IOError:
        print("I/O error")


# print with timestamps
old_out = sys.stdout
class St_ampe_dOut:
    """Stamped stdout."""
    nl = True
    def write(self, x):
        """Write function overloaded."""
        if x == '\n':
            old_out.write(x)
            self.nl = True
        elif self.nl:
            old_out.write(f'{txcolors.DIM}[{str(datetime.now().replace(microsecond=0))}]{txcolors.DEFAULT} {x}')
            self.nl = False
        else:
            old_out.write(x)

    def flush(self):
        pass

sys.stdout = St_ampe_dOut()

def current_price(): 
    avg_price = client.get_symbol_ticker(symbol=SYMBOL)
    return float(avg_price.get('price'))

def convert_volume(quantity):
    '''Converts the volume given in QUANTITY from USDT to ETH volume'''

    price = current_price()
    lot_size = 0
    volume = 0

    # Find the correct step size for each coin
    # max accuracy for BTC for example is 6 decimal points
    # while XRP is only 1
    try:
        info = client.get_symbol_info(SYMBOL)
        step_size = info['filters'][2]['stepSize']
        lot_size = step_size.index('1') - 1

        if lot_size < 0:
            lot_size = 0

    except:
        pass

    # # calculate the volume in coin from QUANTITY in USDT (default)
    volume = float(quantity / float(price))
    volume = float('{:.{}f}'.format(volume, lot_size))
    return volume


def get_balances(client): 
    details = client.get_account()
    balances = details.get('balances')

    usd = 0 
    eth = 0

    for balance in balances: 
        asset = balance.get('asset')
        if asset == 'USD': 
            usd = float(balance.get('free'))
        if asset == 'ETH': 
            eth = float(balance.get('free'))
    return usd, eth


POSITIONS = []

def place_test_order(client, side, quantity, price, coin_value = None):
    
    try:
        client.create_test_order(
            symbol = SYMBOL,
            side = side,
            type = 'LIMIT',
            quantity = quantity if coin_value == None else coin_value, 
            price = price, 
            timeInForce = 'GTC'
        ) 
    except Exception as e:
        print('Error ',e)  



def update_positions():
    '''add every coin bought to our portfolio for tracking/selling later'''
    print('Updating positions...')
    orders = client.get_open_orders(symbol=SYMBOL)

    # binance sometimes returns an empty list, the code will wait here until binance returns the order
    while orders == []:
        print('Binance is being slow in returning the order, calling the API again...')
        orders = client.get_open_orders(symbol=SYMBOL)
        time.sleep(1)

    for index, order in enumerate(orders):
        new_limit = {
            'date': datetime.now().strftime("%d/%m %H:%M:%S"),
            'id': order['orderId'],
            'pair': order['symbol'],
            'type': order['type'],
            'side': order['side'],
            'price': order['price'],
            'amount': order['origQty'],
            'filled': order['executedQty'],
            'status': order['status'],
            'position': POSITIONS[index]['position']
        }
        # Save positions
        write_log(positions_file_path, new_limit, positions_columns)


def get_positions(): 
    try:
        with open(positions_file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=",")
            positions = list(reader)
            for position in positions:
                csvfile.close()
                return position
    except IOError:
        print("I/O error")

def delete_positions(): 
    # opening the file with w+ mode truncates the file
    print("Deleting positions...")
    try:
        with open(positions_file_path, 'r+') as csvfile:
            csvfile.readline() # read one line
            csvfile.truncate(csvfile.tell()) # terminate the file here
            csvfile.close()
    except IOError:
        print("I/O error")


if __name__ == '__main__':
    print('Press Ctrl-Q to stop the script')

    args = parse_args()

    DEFAULT_CREDS_FILE = 'creds.yml'

    creds_file = args.creds if args.creds else DEFAULT_CREDS_FILE
    parsed_creds = load_config(creds_file)

    # Load creds for correct environment
    access_key, secret_key = load_correct_creds(parsed_creds)
    
    # Authenticate with the client, Ensure API key is good before continuing
    client = Client(access_key, secret_key, tld='us')

    # If the users has a bad / incorrect API key.
    # this will stop the script from starting, and display a helpful error.
    api_ready, msg = test_api_key(client, BinanceAPIException)

    if api_ready is not True:
       exit(f'{txcolors.SELL_LOSS}{msg}{txcolors.DEFAULT}')

    if not TEST_MODE:
        if not args.notimeout: # if notimeout skip this (fast for dev tests)
            print('WARNING: You are using the Mainnet and live funds. Waiting 30 seconds as a security measure')
            time.sleep(30)
    
    # seed initial prices
    READ_TIMEOUT_COUNT = 0
    CONNECTION_ERROR_COUNT = 0

    # place_positions(client)
    print('Starting monitoring positions...')
    while True:
        try:

            print("")
            # monitor_positions(client)
        except ReadTimeout as rt:
            READ_TIMEOUT_COUNT += 1
            print(f'{txcolors.WARNING}We got a timeout error from from binance. Going to re-loop. Current Count: {READ_TIMEOUT_COUNT}\n{rt}{txcolors.DEFAULT}')
        except ConnectionError as ce:
            CONNECTION_ERROR_COUNT +=1 
            print(f'{txcolors.WARNING}We got a timeout error from from binance. Going to re-loop. Current Count: {CONNECTION_ERROR_COUNT}\n{ce}{txcolors.DEFAULT}')
        time.sleep(3)



    




