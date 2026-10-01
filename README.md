# pibinance-data

Feed público de tasas (VES) que consume la app **Ndolar**, más las releases del
APK y la web de descarga.

- **App**: https://neoucab.github.io/pibinance-data/
- **Privacidad**: https://neoucab.github.io/pibinance-data/privacidad.html
- **APK directo**: https://github.com/Neoucab/pibinance-data/releases/latest/download/Ndolar.apk

## Qué hay aquí

| Ruta | Qué es |
|---|---|
| `scraper.py` | Scraper **canónico** (BCV + Binance P2P). Corre en el cron de este repo. |
| `certs/sectigo-dv-r36.pem` | Intermedio de la cadena TLS del BCV (ver abajo). |
| `data.json` | Tasas que consume la app. Lo escribe el cron. |
| `binance_history.json` | Últimos 30 valores de Binance, para la referencia de 24 h. |
| `docs/index.html` | Landing de descarga (GitHub Pages, HTTPS forzado). |
| `docs/privacidad.html` | Política de privacidad. |
| `.github/workflows/scrape.yml` | Cron horario (`15 * * * *`) que ejecuta el scraper y versiona los datos. |

## `data.json`

```jsonc
{
  "bcv_usd": 866.5612,
  "bcv_eur": 973.92813268,
  "binance_usdt": 960.302,
  "updated_at": "2026-10-01T16:58:22-04:00",

  // Opcionales (aditivos: una app vieja los ignora)
  "bcv_usd_previous_value": 860.1753,
  "bcv_usd_previous_at": "2026-10-01",
  "binance_usdt_ref_24h_value": 950.11,
  "binance_usdt_ref_24h_at": "2026-09-30T16:55:00-04:00"
}
```

- `updated_at` se reescribe **en cada corrida**, aunque las tasas no cambien. Es lo
  que usa la app para saber si el feed está sano.
- El BCV no publica sábado, domingo ni lunes: su tasa queda congelada a propósito y
  solo se scrapea alrededor de las 00:15 de Caracas.
- `binance_usdt` es el promedio de los 5 primeros anuncios de compra de USDT/VES.

## Por qué está el intermedio `certs/sectigo-dv-r36.pem`

El BCV sirve una cadena TLS **incompleta**: envía el certificado hoja
(`*.bcv.org.ve`) pero no el intermedio Sectigo. curl y schannel lo resuelven
igual, pero OpenSSL —que usan Python y los runners de GitHub Actions— no, y por
eso el scraper usaba `verify=False`. Eso dejaba la puerta abierta a que alguien
inyectara tasas falsas a todos los usuarios.

Fijar el intermedio (que se obtuvo de la URL AIA del propio certificado del BCV)
permite mantener la verificación activa. **Es seguro fijarlo**: si el intermedio
fuera falso, la cadena no llegaría a una raíz de confianza y la verificación
fallaría.

## Ejecutar el scraper en local

```bash
pip install -r requirements.txt   # versiones fijadas a propósito
python scraper.py
```

Escribe `data.json` y `binance_history.json` en el directorio actual.

## Publicar el APK

Las releases se crean desde el repo privado (ver su README, sección 5.2); aquí solo
se sube el artefacto firmado:

```bash
gh release create v1.2.3 -R Neoucab/pibinance-data \
  ./Ndolar.apk#Ndolar.apk --title "Ndolar v1.2.3" --notes "..." --latest
```

El archivo **debe** llamarse `Ndolar.apk`: la app y la landing lo descargan con
esa URL.
