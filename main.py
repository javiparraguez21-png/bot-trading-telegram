import os
import requests
import schedule
import time
from datetime import datetime
import pytz

# ======= VARIABLES DE ENTORNO =======
# IMPORTANTE: Debes configurar estas variables en Railway (Settings -> Variables)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# URL de Telegram
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# ======= FUNCIONES =======
def enviar_reporte():
    mensaje = """
📊 MAESTRO ANALISTA IA – MARKET SENTIMENT

🕒 PRE MARKET LONDRES

Sentimiento global: Neutral
💵 USD: Sin fuerza clara
⚡ Volatilidad esperada: Media

EURUSD: Rango
GBPUSD: Rango
XAUUSD: Alcista leve
DXY: Consolidación

Plan:
- Esperar confirmación en apertura de Londres
- Evitar entradas impulsivas
"""
    try:
        requests.post(URL_TELEGRAM, data={
            "chat_id": CHAT_ID,
            "text": mensaje
        })
        print(f"[{datetime.now()}] Mensaje enviado correctamente")
    except Exception as e:
        print(f"[{datetime.now()}] Error enviando mensaje: {e}")

# ======= HORARIOS =======
# Zona horaria de Londres y NY
london_tz = pytz.timezone('Europe/London')
newyork_tz = pytz.timezone('America/New_York')

# Antes de Londres: 30 min antes de apertura (ajusta según tu horario real)
schedule.every().day.at("10:30").do(enviar_reporte)  # ejemplo hora GMT

# Durante Londres: cada 30 min (ajusta según tu zona horaria)
for hour in range(11, 20):  # 11:00 a 19:30 GMT
    schedule.every().day.at(f"{hour}:00").do(enviar_reporte)
    schedule.every().day.at(f"{hour}:30").do(enviar_reporte)

# Durante New York: cada 30 min (ajusta según tu zona horaria)
for hour in range(14, 21):  # 14:00 a 20:30 GMT
    schedule.every().day.at(f"{hour}:00").do(enviar_reporte)
    schedule.every().day.at(f"{hour}:30").do(enviar_reporte)

# ======= LOOP PRINCIPAL =======
print("BOT MACRO ACTIVO 24/7")
enviar_reporte()  # envío inicial de prueba

while True:
    schedule.run_pending()
    time.sleep(1)
