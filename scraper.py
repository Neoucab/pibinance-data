import requests
import json
from datetime import datetime, timezone
from bs4 import BeautifulSoup

def get_bcv():
    try:
        url = "https://www.bcv.org.ve/"
        response = requests.get(url, verify=False, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extraer Dólar
        dolar = soup.find(id="dolar").find("strong").text.strip().replace(',', '.')
        # Extraer Euro
        euro = soup.find(id="euro").find("strong").text.strip().replace(',', '.')
        
        return {
            "usd": float(dolar),
            "eur": float(euro)
        }
    except Exception as e:
        print(f"Error BCV: {e}")
        return None

def get_binance():
    try:
        url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
        payload = {
            "asset": "USDT",
            "fiat": "VES",
            "merchantCheck": True,
            "page": 1,
            "payTypes": [],
            "publisherType": None,
            "rows": 10,
            "tradeType": "BUY"
        }
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        # Tomamos el promedio de los primeros 5 anuncios para estabilidad
        prices = [float(adv['adv']['price']) for adv in data['data'][:5]]
        avg_price = sum(prices) / len(prices)
        
        return avg_price
    except Exception as e:
        print(f"Error Binance: {e}")
        return None

def main():
    rates = {}
    
    bcv_data = get_bcv()
    if bcv_data:
        rates['bcv_usd'] = bcv_data['usd']
        rates['bcv_eur'] = bcv_data['eur']
    
    binance_price = get_binance()
    if binance_price:
        rates['binance_usdt'] = binance_price
        
    rates['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    with open('data.json', 'w') as f:
        json.dump(rates, f, indent=4)
    
    print("Datos actualizados correctamente en data.json")

if __name__ == "__main__":
    main()
