import os
import requests
from datetime import datetime

# ================= VARIABLES DE ENTORNO =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# ================= MINI LOG DE VERIFICACIÓN =================
print("===== VERIFICANDO VARIABLES DE ENTORNO =====")
print(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN}")
print(f"CHAT_ID: {CHAT_ID}")
print(f"FINNHUB_API_KEY: {FINNHUB_API_KEY}")
print(f"NEWS_API_KEY: {NEWS_API_KEY}")
print("===========================================")

# ================= URL TELEGRAM =================
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# ================= FUNCIONES =================
def enviar_mensaje_telegram(texto):
    """Envía mensaje a Telegram con Markdown, emojis y colores"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Faltan TELEGRAM_TOKEN o CHAT_ID")
        return
    try:
        r = requests.post(URL_TELEGRAM, data={
            "chat_id": CHAT_ID,
            "text": texto,
            "parse_mode": "Markdown"
        })
        if r.status_code == 200:
            print(f"[{datetime.now()}] Mensaje enviado correctamente")
        else:
            print(f"[{datetime.now()}] Error Telegram: {r.text}")
    except Exception as e:
        print(f"[{datetime.now()}] Excepción al enviar mensaje: {e}")

# ================= MENSAJE DE PRUEBA =================
def enviar_mensaje_prueba():
    mensaje_prueba = """
📊 *MENSAJE DE PRUEBA – BOT ULTRA PRO*

✅ Este mensaje confirma que Telegram está conectado correctamente desde Railway.
"""
    enviar_mensaje_telegram(mensaje_prueba)

# ================= EJECUCIÓN =================
print("🤖 BOT MACRO ULTRA PRO – TEST DE TELEGRAM")
enviar_mensaje_prueba()
