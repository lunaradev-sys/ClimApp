import sqlite3
import requests
from datetime import date

import json
import os

from statistics import median
from collections import defaultdict


LAT = -37.03
LON = -73.16
BASE   = os.path.dirname(os.path.abspath(__file__))
BD     = os.path.join(BASE, "clima.db")
SALIDA = os.path.join(BASE, "widget", "historico.js")
DIAS = 14                       
MODELOS = ["ecmwf_ifs025", "gfs025", "ecmwf_aifs025"]


def crear_bd():
    con = sqlite3.connect(BD)
    con.execute("""
        CREATE TABLE IF NOT EXISTS pronostico (
            modelo         TEXT,
            fecha_captura  TEXT,
            fecha_objetivo TEXT,
            anticipacion   INTEGER,
            precip_mm      REAL,
            prob_lluvia    REAL,
            temp_max       REAL,
            temp_min       REAL,
            viento_max     REAL,
            PRIMARY KEY (modelo, fecha_captura, fecha_objetivo)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS observado (
            fecha      TEXT PRIMARY KEY,
            precip_mm  REAL,
            temp_max   REAL,
            temp_min   REAL,
            viento_max REAL
        )
    """)
    con.commit()
    con.close()


def pedir_pronostico(modelo):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "daily": "temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,wind_speed_10m_max",
        "wind_speed_unit": "kn",
        "timezone": "auto",
        "forecast_days": DIAS,
        "models": modelo,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def serie(bloque, clave, modelo):
    if clave in bloque:
        return bloque[clave]
    return bloque.get(f"{clave}_{modelo}")


def guardar(modelo, datos):
    d = datos["daily"]
    fechas = d["time"]
    tmax   = serie(d, "temperature_2m_max", modelo)
    tmin   = serie(d, "temperature_2m_min", modelo)
    precip = serie(d, "precipitation_sum", modelo)
    viento = serie(d, "wind_speed_10m_max", modelo)

    hoy = date.today()
    filas = []
    for i, f in enumerate(fechas):
        anticipacion = (date.fromisoformat(f) - hoy).days
        filas.append((
            modelo, hoy.isoformat(), f, anticipacion,
            precip[i], None, tmax[i], tmin[i], viento[i]
        ))

    con = sqlite3.connect(BD)
    con.executemany("""
        INSERT OR REPLACE INTO pronostico
            (modelo, fecha_captura, fecha_objetivo, anticipacion,
             precip_mm, prob_lluvia, temp_max, temp_min, viento_max)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, filas)
    con.commit()
    con.close()
    return len(filas)


def resumen():
    modelo = MODELOS[0]
    con = sqlite3.connect(BD)
    filas = con.execute("""
        SELECT fecha_objetivo, precip_mm, temp_min, temp_max
        FROM pronostico
        WHERE fecha_captura = ?
          AND modelo = ?
          AND anticipacion BETWEEN 0 AND 6
        ORDER BY fecha_objetivo
    """, (date.today().isoformat(), modelo)).fetchall()
    con.close()

    print(f"\n{modelo}")
    print("fecha        lluvia   min   max")
    for f, p, tmin, tmax in filas:
        if p is None or tmin is None or tmax is None:
            continue
        print(f"{f}   {p:5.1f}mm  {tmin:4.1f}° {tmax:4.1f}°")

def pedir_ensemble(modelo="gfs025"):
    """30+ corridas del mismo modelo con condiciones apenas distintas."""
    url = "https://ensemble-api.open-meteo.com/v1/ensemble"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "precipitation",
        "timezone": "auto",
        "forecast_days": DIAS,
        "models": modelo,
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def procesar_ensemble(datos, umbral=1.0):
    """Convierte 30 corridas horarias en un número por día."""
    h = datos["hourly"]
    horas = h["time"]
    miembros = [k for k in h if k.startswith("precipitation")]

    por_dia = defaultdict(lambda: defaultdict(float))
    for m in miembros:
        valores = h[m]
        for i, t in enumerate(horas):
            if valores[i] is not None:
                por_dia[t[:10]][m] += valores[i]

    resultado = {}
    for dia, sumas in por_dia.items():
        totales = list(sumas.values())
        mojados = sum(1 for v in totales if v >= umbral)
        resultado[dia] = {
            "mediana": round(median(totales), 1),
            "prob": round(100 * mojados / len(totales)),
            "maximo": round(max(totales), 1),
            "miembros": len(totales),
        }
    return resultado


def guardar_ensemble(modelo, resultado):
    hoy = date.today()
    filas = []
    for dia, r in sorted(resultado.items()):
        anticipacion = (date.fromisoformat(dia) - hoy).days
        filas.append((
            f"{modelo}_ens", hoy.isoformat(), dia, anticipacion,
            r["mediana"], r["prob"], None, None, None
        ))

    con = sqlite3.connect(BD)
    con.executemany("""
        INSERT OR REPLACE INTO pronostico
            (modelo, fecha_captura, fecha_objetivo, anticipacion,
             precip_mm, prob_lluvia, temp_max, temp_min, viento_max)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, filas)
    con.commit()
    con.close()
    return len(filas)
def pedir_observado(dias_atras=7):
    """Sin 'models': acá queremos la mejor estimación de la realidad,
    no la opinión de un modelo en particular."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "daily": "temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,wind_speed_10m_max",
        "wind_speed_unit": "kn",
        "timezone": "auto",
        "past_days": dias_atras,
        "forecast_days": 1,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def guardar_observado(datos):
    d = datos["daily"]
    hoy = date.today().isoformat()

    filas = []
    for i, f in enumerate(d["time"]):
        if f >= hoy:          # el día de hoy todavía no termina
            continue
        filas.append((
            f,
            d["precipitation_sum"][i],
            d["temperature_2m_max"][i],
            d["temperature_2m_min"][i],
            d["wind_speed_10m_max"][i],
        ))

    print(f"  recibidos {len(d['time'])} días: {d['time'][0]} a {d['time'][-1]}")
    print(f"  hoy es {hoy}, guardo {len(filas)}")

    if not filas:
        return 0

    con = sqlite3.connect(BD)
    con.executemany("""
        INSERT OR REPLACE INTO observado
            (fecha, precip_mm, temp_max, temp_min, viento_max)
        VALUES (?, ?, ?, ?, ?)
    """, filas)
    con.commit()
    con.close()
    return len(filas)

def verificacion():
    con = sqlite3.connect(BD)
    filas = con.execute("""
        SELECT p.modelo,
               p.anticipacion,
               COUNT(*)                                  AS dias,
               ROUND(AVG(ABS(p.temp_max   - o.temp_max)), 2) AS err_temp,
               ROUND(AVG(ABS(p.precip_mm  - o.precip_mm)), 2) AS err_lluvia
        FROM pronostico p
        JOIN observado o ON p.fecha_objetivo = o.fecha
        WHERE p.temp_max IS NOT NULL
        GROUP BY p.modelo, p.anticipacion
        ORDER BY p.modelo, p.anticipacion
    """).fetchall()
    con.close()

    if not filas:
        print("\nTodavía no hay días verificables. Esto se llena solo.")
        return

    print("\nmodelo                ant  días   err°C   err_mm")
    for modelo, ant, n, et, el in filas:
        print(f"{modelo:20s} {ant:4d} {n:5d} {et:7} {el:8}")

    con = sqlite3.connect(BD)
    con.executemany("""
        INSERT OR REPLACE INTO observado
            (fecha, precip_mm, temp_max, temp_min, viento_max)
        VALUES (?, ?, ?, ?, ?)
    """, filas)
    con.commit()
    con.close()
    return len(filas)

def exportar_historico():
    con = sqlite3.connect(BD)

    filas = con.execute("""
        SELECT p.modelo,
               p.anticipacion,
               COUNT(*),
               ROUND(AVG(ABS(p.temp_max  - o.temp_max)),  2),
               ROUND(AVG(ABS(p.precip_mm - o.precip_mm)), 2),
               ROUND(AVG(CASE WHEN (p.precip_mm >= 1) = (o.precip_mm >= 1)
                              THEN 1.0 ELSE 0.0 END), 3)
        FROM pronostico p
        JOIN observado o ON p.fecha_objetivo = o.fecha
        WHERE p.precip_mm IS NOT NULL
        GROUP BY p.modelo, p.anticipacion
        ORDER BY p.modelo, p.anticipacion
    """).fetchall()

    verificados = con.execute("""
        SELECT COUNT(DISTINCT o.fecha)
        FROM observado o
        JOIN pronostico p ON p.fecha_objetivo = o.fecha
    """).fetchone()[0]

    con.close()

    datos = {
        "actualizado": date.today().isoformat(),
        "dias_verificados": verificados,
        "filas": [
            {"modelo": m, "anticipacion": a, "casos": n,
             "err_temp": et, "err_lluvia": el, "acierto": ac}
            for m, a, n, et, el, ac in filas
        ],
    }

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write("const HISTORICO = " +
                json.dumps(datos, ensure_ascii=False, indent=2) + ";\n")

    return len(datos["filas"])

def exportar_historico():
    con = sqlite3.connect(BD)

    filas = con.execute("""
        SELECT p.modelo,
               p.anticipacion,
               COUNT(*),
               ROUND(AVG(ABS(p.temp_max  - o.temp_max)),  2),
               ROUND(AVG(ABS(p.precip_mm - o.precip_mm)), 2),
               ROUND(AVG(CASE WHEN (p.precip_mm >= 1) = (o.precip_mm >= 1)
                              THEN 1.0 ELSE 0.0 END), 3)
        FROM pronostico p
        JOIN observado o ON p.fecha_objetivo = o.fecha
        WHERE p.precip_mm IS NOT NULL
        GROUP BY p.modelo, p.anticipacion
        ORDER BY p.modelo, p.anticipacion
    """).fetchall()

    verificados = con.execute("""
        SELECT COUNT(DISTINCT o.fecha)
        FROM observado o
        JOIN pronostico p ON p.fecha_objetivo = o.fecha
    """).fetchone()[0]

    con.close()

    datos = {
        "actualizado": date.today().isoformat(),
        "dias_verificados": verificados,
        "filas": [
            {"modelo": m, "anticipacion": a, "casos": n,
             "err_temp": et, "err_lluvia": el, "acierto": ac}
            for m, a, n, et, el, ac in filas
        ],
    }

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write("const HISTORICO = " +
                json.dumps(datos, ensure_ascii=False, indent=2) + ";\n")

    return len(datos["filas"])

if __name__ == "__main__":
    crear_bd()

    for modelo in MODELOS:
        datos = pedir_pronostico(modelo)
        print(f"{modelo}: {guardar(modelo, datos)} días guardados")

    ens = procesar_ensemble(pedir_ensemble("gfs025"))
    guardar_ensemble("gfs025", ens)

    print(f"observado: {guardar_observado(pedir_observado())} días")

    resumen()
    verificacion()

    print(f"histórico: {exportar_historico()} combinaciones exportadas")