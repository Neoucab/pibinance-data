"""Pruebas de la poda del historial de Binance.

Cubren el acoplamiento que rompió la referencia de 24 h: la poda anterior
guardaba «los últimos 30 puntos», así que su cobertura dependía de cada cuánto
corre el cron. Con una corrida por hora eran 30 h; con tres por hora, 10 h, y
`binance_usdt_ref_24h_value` desaparecía.
"""

from datetime import datetime, timedelta

import pytest

from scraper import CARACAS, HISTORY_MAX_POINTS, REF24H_TOLERANCE, prune_history

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=CARACAS)


def _history(step, days=8, now=NOW):
    """Puntos en orden de escritura: del más viejo al más nuevo."""
    points = []
    t = now - timedelta(days=days)
    while t <= now:
        points.append({"at": t.isoformat(), "value": 1000.0})
        t += step
    return points


def _closest_to_24h(points, now=NOW):
    """Distancia en segundos del punto más cercano a las 24 h atrás."""
    target = now - timedelta(hours=24)
    return min(
        abs((datetime.fromisoformat(p["at"]) - target).total_seconds())
        for p in points
    )


@pytest.mark.parametrize("minutes", [20, 60, 300, 588, 1440])
def test_la_referencia_24h_no_depende_de_la_frecuencia_del_cron(minutes):
    kept = prune_history(_history(timedelta(minutes=minutes)), NOW)
    assert _closest_to_24h(kept) <= REF24H_TOLERANCE.total_seconds()


def test_la_regla_anterior_de_30_puntos_fallaba_con_corridas_frecuentes():
    old = _history(timedelta(minutes=20))[-30:]
    span = datetime.fromisoformat(old[-1]["at"]) - datetime.fromisoformat(old[0]["at"])
    assert span < timedelta(hours=24)
    assert _closest_to_24h(old) > REF24H_TOLERANCE.total_seconds()


def test_descarta_los_puntos_fuera_de_la_ventana():
    kept = prune_history(
        [
            {"at": (NOW - timedelta(days=7)).isoformat(), "value": 1.0},
            {"at": (NOW - timedelta(hours=1)).isoformat(), "value": 1.0},
        ],
        NOW,
    )
    assert len(kept) == 1


def test_limita_la_cantidad_de_puntos():
    many = [
        {"at": (NOW - timedelta(minutes=i)).isoformat(), "value": 1000.0}
        for i in range(HISTORY_MAX_POINTS + 50)
    ]
    assert len(prune_history(many, NOW)) == HISTORY_MAX_POINTS


@pytest.mark.parametrize(
    "bad",
    [
        [{"at": "basura", "value": 1.0}],
        [{"at": None, "value": 1.0}],
        [{"value": 1.0}],
        [],
        ["x", 3, None],
    ],
)
def test_un_historial_corrupto_no_rompe_la_corrida(bad):
    assert prune_history(list(bad), NOW) == []


def test_acepta_timestamps_sin_zona_horaria():
    naive = (NOW.replace(tzinfo=None) - timedelta(hours=1)).isoformat()
    assert len(prune_history([{"at": naive, "value": 1.0}], NOW)) == 1
