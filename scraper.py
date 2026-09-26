import requests
import json
import sys
from datetime import datetime, timezone
from bs4 import BeautifulSoup


def is_bcv_frozen_day(now_utc):
    """Sáb/dom/lun la tasa BCV no cambia durante el día: se scrapea una sola
    vez, en la corrida de las 04:00-04:59 UTC (00:00-00:59 Venezuela, cuando
    el BCV publica). En las demás corridas de esos días se omite el BCV y se
    conserva el valor existente. De martes a viernes se scrapea siempre."""
    return now_utc.weekday() in (5, 6, 0) and now_utc.hour != 4


def get_bcv():
    try:
        url = "https://www.bcv.org.ve/"
        response = requests.get(url, verify=False, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        dolar = soup.find(id="dolar").find("strong").text.strip().replace(',', '.')
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

        # Promedio de los primeros 5 anuncios para estabilidad
        prices = [float(adv['adv']['price']) for adv in data['data'][:5]]
        return sum(prices) / len(prices)
    except Exception as e:
        print(f"Error Binance: {e}")
        return None


def main():
    try:
        with open('data.json', 'r') as f:
            prev = json.load(f)
    except Exception:
        prev = {}

    # Partimos de las tasas anteriores: lo que falle hoy conserva su último valor.
    rates = {
        'bcv_usd': prev.get('bcv_usd'),
        'bcv_eur': prev.get('bcv_eur'),
        'binance_usdt': prev.get('binance_usdt'),
    }

    now_utc = datetime.now(timezone.utc)

    if is_bcv_frozen_day(now_utc):
        print("Sáb/dom/lun: la tasa BCV no cambia durante el día; se actualiza una sola vez (00:00 VE).")
    else:
        bcv_data = get_bcv()
        if bcv_data:
            rates['bcv_usd'] = bcv_data['usd']
            rates['bcv_eur'] = bcv_data['eur']

    binance_price = get_binance()
    if binance_price:
        rates['binance_usdt'] = binance_price

    if rates['bcv_usd'] is None or rates['binance_usdt'] is None:
        print("ERROR: no hay tasas nuevas ni valores previos que conservar.")
        sys.exit(1)

    rates['updated_at'] = datetime.now(timezone.utc).isoformat()

    with open('data.json', 'w') as f:
        json.dump(rates, f, indent=4)

    print("Datos actualizados correctamente en data.json")


if __name__ == "__main__":
    main()
