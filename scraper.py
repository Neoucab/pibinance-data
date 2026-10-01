"""Scraper de tasas de Ndolar — FUENTE ÚNICA DE VERDAD.

Este archivo es el único scraper del proyecto y vive en el repo público
`Neoucab/pibinance-data`, que es donde corre el cron horario que escribe
`data.json`. Antes existía una copia en el repo privado que se bifurcó del
producción y quedó sin los campos de variación: no se vuelve a duplicar.

Salida:
  data.json             — tasas que consume la app (planas + variación)
  binance_history.json  — historial corto para la referencia de 24 h

Seguridad:
  - TLS verificado (verify=True). El certificado del BCV es un DV público
    válido (Sectigo), no hay razón para desactivarlo: con verify=False una
    respuesta manipitada se convertiría en tasas falsas para todos.
  - Rango sanity en cada tasa: un valor absurdo se descarta y se conserva el
    último valor bueno, en lugar de publicarse.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import certifi
import requests
from bs4 import BeautifulSoup

INTERMEDIATE_PEM = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "certs", "sectigo-dv-r36.pem"
)


def ca_bundle():
    """Ruta de un bundle CA = certifi + el intermedio que el BCV no envía.

    El BCV sirve una cadena incompleta (hoja `*.bcv.org.ve` sin el
    intermedio Sectigo). curl y schannel lo resuelven igual, pero OpenSSL
    —que es lo que usa Python y los runners de GitHub Actions— no. Por eso
    antes se usaba verify=False, que abre la puerta a que alguien inyecte
    tasas falsas. Fijar el intermedio mantiene la verificación activa: si
    el intermedio fuese falso, la cadena no llegaría a una raíz de confianza
    y la verificación fallaría.
    """
    bundle = certifi.where()
    try:
        with open(INTERMEDIATE_PEM, "r", encoding="utf-8") as f:
            extra = f.read()
    except OSError:
        print("Aviso: falta certs/sectigo-dv-r36.pem; el BCV fallará la verificación.")
        return bundle
    fd, path = tempfile.mkstemp(suffix=".pem")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(open(bundle, encoding="utf-8").read())
        out.write("\n")
        out.write(extra)
    return path

# Hora oficial del proyecto: Caracas, Venezuela (UTC-4 fijo, sin horario de
# verano). Nunca se usa la hora local de la máquina, que puede estar desviada.
try:
    CARACAS = ZoneInfo("America/Caracas")
except Exception:
    CARACAS = timezone(timedelta(hours=-4), name="America/Caracas")

BCV_URL = "https://www.bcv.org.ve/"
BINANCE_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

# Rangos amplios a propósito: solo descartan valores que no pueden ser una tasa
# real (negativos, ceros, dígitos de más o una respuesta inyectada).
MIN_RATE = 1.0
MAX_RATE = 1_000_000.0

CA_BUNDLE = ca_bundle()


def in_range(value):
    """Devuelve el valor si es una tasa plausible; None si no lo es."""
    if value is None:
        return None
    if MIN_RATE <= value <= MAX_RATE:
        return value
    print(f"Descartado valor fuera de rango: {value}")
    return None


def is_bcv_frozen_day(now_caracas):
    """Sáb/dom/lun la tasa BCV no cambia durante el día: se scrapea una sola
    vez, en la corrida de las 00:00-00:59 de Caracas (cuando el BCV publica).
    En las demás corridas de esos días se omite el BCV y se conserva el valor
    existente. De martes a viernes se scrapea siempre."""
    return now_caracas.weekday() in (5, 6, 0) and now_caracas.hour != 0


def get_bcv():
    try:
        response = requests.get(
            BCV_URL,
            timeout=15,
            verify=CA_BUNDLE,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NdolarBot/1.0)"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        dolar = soup.find(id="dolar").find("strong").text.strip().replace(",", ".")
        euro = soup.find(id="euro").find("strong").text.strip().replace(",", ".")

        return {
            "usd": in_range(float(dolar)),
            "eur": in_range(float(euro)),
        }
    except Exception as e:
        print(f"Error BCV: {e}")
        return None


def get_binance():
    try:
        payload = {
            "asset": "USDT",
            "fiat": "VES",
            "merchantCheck": True,
            "page": 1,
            "payTypes": [],
            "publisherType": None,
            "rows": 10,
            "tradeType": "BUY",
        }
        response = requests.post(BINANCE_URL, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()

        # Promedio de los primeros 5 anuncios para estabilidad
        prices = [float(adv["adv"]["price"]) for adv in data["data"][:5]]
        return in_range(sum(prices) / len(prices))
    except Exception as e:
        print(f"Error Binance: {e}")
        return None


def load_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def main():
    prev = load_json("data.json", {})

    # Partimos de las tasas anteriores: lo que falle hoy conserva su último valor.
    rates = {
        "bcv_usd": in_range(prev.get("bcv_usd")),
        "bcv_eur": in_range(prev.get("bcv_eur")),
        "binance_usdt": in_range(prev.get("binance_usdt")),
    }

    now_caracas = datetime.now(CARACAS)

    if is_bcv_frozen_day(now_caracas):
        print("Sáb/dom/lun: la tasa BCV no cambia durante el día; se actualiza una sola vez (00:00 VE).")
    else:
        bcv_data = get_bcv()
        if bcv_data:
            for key in ("usd", "eur"):
                if bcv_data[key] is not None:
                    rates["bcv_" + key] = bcv_data[key]

    binance_price = get_binance()
    if binance_price is not None:
        rates["binance_usdt"] = binance_price

    if rates["bcv_usd"] is None or rates["binance_usdt"] is None:
        print("ERROR: no hay tasas nuevas ni valores previos que conservar.")
        sys.exit(1)

    rates["updated_at"] = datetime.now(CARACAS).isoformat()

    # ------------------------------------------------------------------
    # Campos opcionales de variación. Aditivos: las apps ya instaladas
    # leen solo las claves planas y no se rompen.
    # ------------------------------------------------------------------

    # BCV: último valor DISTINTO publicado antes del actual (no la lectura
    # anterior, que en días congelados repite el mismo valor).
    prev_bcv = in_range(prev.get("bcv_usd"))
    if (
        rates["bcv_usd"] is not None
        and prev_bcv is not None
        and rates["bcv_usd"] != prev_bcv
    ):
        rates["bcv_usd_previous_value"] = prev_bcv
        prev_at = prev.get("updated_at")
        rates["bcv_usd_previous_at"] = str(prev_at)[:10] if prev_at else None
    elif in_range(prev.get("bcv_usd_previous_value")) is not None:
        # El valor actual no cambió (p. ej. sáb/dom/lun): se conserva la
        # referencia previa que ya estaba publicada.
        rates["bcv_usd_previous_value"] = prev["bcv_usd_previous_value"]
        rates["bcv_usd_previous_at"] = prev.get("bcv_usd_previous_at")

    # Binance: valor más cercano a 24 h atrás, de un historial corto (últimos
    # 30 puntos) guardado en binance_history.json.
    history = load_json("binance_history.json", [])
    if not isinstance(history, list):
        history = []
    history = [
        h
        for h in history
        if isinstance(h, dict) and h.get("at") and in_range(h.get("value")) is not None
    ]
    if rates["binance_usdt"] is not None:
        history.append({"at": rates["updated_at"], "value": rates["binance_usdt"]})
    history = history[-30:]
    with open("binance_history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    try:
        now_dt = datetime.fromisoformat(rates["updated_at"])
        target = now_dt - timedelta(hours=24)
        best = None
        for h in history:
            try:
                t = datetime.fromisoformat(str(h["at"]))
            except Exception:
                continue
            if t.tzinfo is None:
                t = t.replace(tzinfo=CARACAS)
            d = abs((t - target).total_seconds())
            if best is None or d < best[0]:
                best = (d, h)
        # Solo publicar la referencia si hay un punto razonablemente cercano a
        # 24 h (tolerancia 3 h); si no, omitir el campo.
        if best and best[0] <= 3 * 3600:
            rates["binance_usdt_ref_24h_value"] = best[1]["value"]
            rates["binance_usdt_ref_24h_at"] = best[1]["at"]
    except Exception as e:
        print(f"Aviso: no se pudo calcular la referencia 24 h: {e}")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(rates, f, indent=4)

    print("Datos actualizados correctamente en data.json")


if __name__ == "__main__":
    main()
