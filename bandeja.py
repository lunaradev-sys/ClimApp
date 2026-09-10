import os
import time
import threading
import webbrowser

import subprocess

import requests
import pystray
from PIL import Image, ImageDraw, ImageFont

LAT, LON = -37.03, -73.16
BASE      = os.path.dirname(os.path.abspath(__file__))
WIDGET    = os.path.join(BASE, "widget", "index.html")
INTERVALO = 15 * 60          # segundos entre actualizaciones
PROYECTO = os.path.join(BASE, "escritorio")
ELECTRON = os.path.join(PROYECTO, "node_modules", "electron", "dist", "electron.exe")

CODIGOS = {
    0:"Despejado", 1:"Casi despejado", 2:"Parcial nublado", 3:"Nublado",
    45:"Neblina", 48:"Neblina helada",
    51:"Llovizna", 53:"Llovizna", 55:"Llovizna intensa",
    61:"Lluvia débil", 63:"Lluvia", 65:"Lluvia fuerte",
    66:"Lluvia helada", 67:"Lluvia helada",
    71:"Nieve", 73:"Nieve", 75:"Nieve intensa",
    80:"Chubascos", 81:"Chubascos", 82:"Chubascos fuertes",
    95:"Tormenta", 96:"Tormenta", 99:"Tormenta",
}


def dibujar(texto):
    """Genera el ícono: el número de la temperatura sobre fondo transparente."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    try:
        fuente = ImageFont.truetype("segoeuib.ttf", 46 if len(texto) <= 2 else 36)
    except OSError:
        fuente = ImageFont.load_default()

    caja = d.textbbox((0, 0), texto, font=fuente)
    x = (64 - (caja[2] - caja[0])) / 2 - caja[0]
    y = (64 - (caja[3] - caja[1])) / 2 - caja[1]

    # Blanco para barra oscura. Si usás tema claro, cambiá a (0, 0, 0, 255).
    d.text((x, y), texto, font=fuente, fill=(255, 255, 255, 255))
    return img


def pedir():
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": LAT,
        "longitude": LON,
        "current": "temperature_2m,weather_code",
        "daily": "precipitation_sum,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 1,
    }, timeout=20)
    r.raise_for_status()
    return r.json()


def refrescar(tray):
    while True:
        try:
            j   = pedir()
            t   = round(j["current"]["temperature_2m"])
            cod = j["current"]["weather_code"]
            mm  = j["daily"]["precipitation_sum"][0] or 0
            pr  = j["daily"]["precipitation_probability_max"][0]

            tray.icon  = dibujar(str(t))
            tray.title = (f"Coronel · {t}° · {CODIGOS.get(cod, '—')}\n"
                          f"Hoy: {mm:.1f} mm · {pr}% de probabilidad")
        except Exception as e:
            tray.title = f"Clima Coronel — sin conexión ({e})"

        time.sleep(INTERVALO)


def abrir(icon, item):
    try:
        subprocess.Popen(
            [ELECTRON, PROYECTO],
            cwd=PROYECTO,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        # Si Electron no está, al menos abrimos el widget en el navegador
        webbrowser.open("file:///" + WIDGET.replace("\\", "/"))


def salir(icon, item):
    icon.stop()


if __name__ == "__main__":
    tray = pystray.Icon(
        "clima",
        dibujar("--"),
        "Clima Coronel",
        menu=pystray.Menu(
            pystray.MenuItem("Abrir widget", abrir, default=True),
            pystray.MenuItem("Salir", salir),
        ),
    )

    threading.Thread(target=refrescar, args=(tray,), daemon=True).start()
    tray.run()