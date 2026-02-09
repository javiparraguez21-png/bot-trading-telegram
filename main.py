import os
import requests
import schedule
import time
from datetime import datetime
import pytz

# ======= VARIABLES DE ENTORNO =======
TELEGRAM_TOKEN = os.getenv(8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc)
CHAT_ID = os.getenv(5933788259)

URL_TELEGRAM = f"https://api.telegram.org/bot{AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc}/sendMessage"

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
# Usa la zona horaria de Londres y NY
london_tz = pytz.timezone('Europe/London')
newyork_tz = pytz.timezone('America/New_York')

# Antes de Londres: 30 min antes de apertura (07:00 AM hora Chile ≈ 11:00 GMT en invierno)
schedule.every().day.at("10:30").do(enviar_reporte)  # Ajusta según horario real

# Durante Londres: cada 30 min (07:00-16:00 Chile / 11:00-20:00 GMT)
for hour in range(11, 20):
    schedule.every().day.at(f"{hour}:00").do(enviar_reporte)
    schedule.every().day.at(f"{hour}:30").do(enviar_reporte)

# Durante New York: cada 30 min (09:30-16:00 NY)
for hour in range(14, 21):  # Ajusta según diferencia horaria
    schedule.every().day.at(f"{hour}:00").do(enviar_reporte)
    schedule.every().day.at(f"{hour}:30").do(enviar_reporte)

# ======= LOOP PRINCIPAL =======
print("BOT MACRO ACTIVO 24/7")
enviar_reporte()  # envío inicial de prueba

while True:
    schedule.run_pending()
    time.sleep(1)

