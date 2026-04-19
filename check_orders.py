import os
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET')
testnet = os.getenv('BINANCE_TESTNET', 'True').lower() in ('true', '1', 'yes')

base_url = "https://testnet.binancefuture.com" if testnet else "https://fapi.binance.com"

def get_open_orders():
    endpoint = "/fapi/v1/openOrders"
    params = f"timestamp={int(time.time() * 1000)}"
    signature = hmac.new(api_secret.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()
    
    headers = {"X-MBX-APIKEY": api_key}
    url = f"{base_url}{endpoint}?{params}&signature={signature}"
    
    response = requests.get(url, headers=headers)
    print("Open Orders Status:", response.status_code)
    for o in response.json():
        print(o)

def get_algo_orders():
    endpoint = "/fapi/v1/allForceOrders" # just to see if there's anything else, wait algo is /fapi/v1/openOrders and /fapi/v1/allOpenOrders. Ah, /fapi/v1/openOrders returns ALL open orders. 
    pass

get_open_orders()
