import os
import requests

# ================= OPCIÓN 1: USAR DIRECTAMENTE EL TOKEN Y CHAT_ID =================
TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"  # Tu token real
CHAT_ID = "5933788259"  # Tu chat ID real

# ================= OPCIÓN 2: USAR VARIABLES DE ENTORNO (más seguro) =================
# TOKEN = os.getenv("TELEGRAM_TOKEN")
# CHAT_ID = os.getenv("CHAT_ID")

# ================= ENVÍO DEL MENSAJE DE PRUEBA =================
try:
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": "✅ Prueba Telegram desde Python"}
    )
    print("Respuesta Telegram:", r.text)
except Exception as e:
    print("Error al enviar mensaje:", e)
