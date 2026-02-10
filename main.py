import requests
import schedule
import time
from datetime import datetime, time as dtime
from tradingview_ta import TA_Handler, Interval
import feedparser
from deep_translator import GoogleTranslator

# ================= TELEGRAM (TUS CREDENCIALES) =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ================= ACTIVOS (TRADINGVIEW FIX DEFINITIVO) =================
ACTIVOS = {
    "EURUSD": {"symbol": "EURUSD", "screener": "forex", "exchange": "FX_IDC"},
    "GBPUSD": {"symbol": "GBPUSD", "screener": "forex", "exchange": "FX_IDC"},
    "XAUUSD": {"symbol": "XAUUSD", "screener": "forex", "exchange": "FX_IDC"},
    "DXY": {"symbol": "DXY", "screener": "indices", "exchange": "TVC"},
    "VIX": {"symbol": "VIX", "screener": "indices", "exchange": "CBOE"}
}

# ================= SESIONES (HORARIO CHILE 🇨🇱) =================
SESIONES = {
    "Asia": (dtime(21, 0), dtime(5, 0)),
    "Londres": (dtime(4, 0), dtime(13, 0)),
    "Nueva York": (dtime(9, 0), dtime(18, 0))
}

# ================= ESTADO GLOBAL =================
ultimo_sesgo = None
last_update_id = None

# ================= TELEGRAM =================
def enviar_mensaje(texto, botones=False):
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown"
    }

    if botones:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "🔄 Actualizar ahora", "callback_data": "update"}
            ]]
        }

    requests.post(f"{BASE_URL}/sendMessage", json=payload)

# ================= DATOS DE MERCADO =================
def obtener_datos():
    datos = {}
    for activo, cfg in ACTIVOS.items():
        try:
            handler = TA_Handler(
                symbol=cfg["symbol"],
                screener=cfg["screener"],
                exchange=cfg["exchange"],
                interval=Interval.INTERVAL_15_MINUTES
            )
            a = handler.get_analysis()
            datos[activo] = {
                "precio": a.indicators["close"],
                "tendencia": a.summary["RECOMMENDATION"],
                "rsi": round(a.indicators["RSI"], 1)
            }
        except Exception:
            datos[activo] = None
    return datos

# ================= SESGO MACRO =================
def calcular_sesgo(datos):
    sesgo = []

    if datos["DXY"] and datos["DXY"]["tendencia"] in ["BUY", "STRONG_BUY"]:
        sesgo.append("USD_FUERTE")

    if datos["VIX"] and datos["VIX"]["tendencia"] in ["BUY", "STRONG_BUY"]:
        sesgo.append("RISK_OFF")

    if datos["XAUUSD"] and datos["XAUUSD"]["tendencia"] in ["BUY", "STRONG_BUY"]:
        sesgo.append("ORO_DEMANDA")

    return sesgo if sesgo else ["NEUTRAL"]

# ================= NOTICIAS =================
def obtener_noticias():
    feed = feedparser.parse("https://www.cnbc.com/id/100727362/device/rss/rss.html")
    noticias = []

    for e in feed.entries[:2]:
        try:
            titulo = GoogleTranslator(source="en", target="es").translate(e.title)
        except:
            titulo = e.title
        noticias.append(f"📰 {titulo}")

    return noticias

# ================= DASHBOARD =================
def construir_dashboard(pre_market=False):
    global ultimo_sesgo

    datos = obtener_datos()
    sesgo_actual = calcular_sesgo(datos)
    noticias = obtener_noticias()

    mensaje = "📊 *DASHBOARD MACRO TRADING PRO*\n\n"

    for activo, d in datos.items():
        if d:
            mensaje += f"*{activo}*: {d['precio']} | {d['tendencia']} | RSI {d['rsi']}\n"

    mensaje += "\n🧠 *Sesgo actual:*\n" + ", ".join(sesgo_actual)

    if sesgo_actual != ultimo_sesgo:
        mensaje += "\n\n🚨 *CAMBIO DE SESGO DETECTADO*"
        ultimo_sesgo = sesgo_actual

    if pre_market:
        mensaje += "\n\n⏳ *PRE-MARKET CHECK*\n"
        mensaje += "• Identificar activo dominante\n"
        mensaje += "• Evitar entradas pre-noticia\n"
        mensaje += "• Confirmar sesgo en M15 / H1\n"

    mensaje += "\n\n📰 *Noticias clave:*\n" + "\n".join(noticias)

    return mensaje

# ================= PRE-MARKET =================
def enviar_pre_market():
    enviar_mensaje(construir_dashboard(pre_market=True), botones=True)

# ================= ACTUALIZACIÓN MANUAL (BOTÓN) =================
def revisar_actualizaciones():
    global last_update_id

    params = {"timeout": 1}
    if last_update_id:
        params["offset"] = last_update_id + 1

    r = requests.get(f"{BASE_URL}/getUpdates", params=params).json()

    if "result" in r:
        for update in r["result"]:
            last_update_id = update["update_id"]

            if "callback_query" in update:
                data = update["callback_query"]["data"]
                if data == "update":
                    enviar_mensaje(construir_dashboard(), botones=True)

# ================= SCHEDULE =================
schedule.every().hour.at(":00").do(lambda: enviar_mensaje(construir_dashboard(), botones=True))

# Pre-market sesiones (Chile)
schedule.every().day.at("03:45").do(enviar_pre_market)  # Londres
schedule.every().day.at("08:45").do(enviar_pre_market)  # NY
schedule.every().day.at("20:45").do(enviar_pre_market)  # Asia

# ================= START =================
print("🤖 BOT MACRO TRADING PRO INICIADO")
enviar_mensaje("✅ *Bot Macro Trading PRO activo*\nSesiones Chile 🇨🇱 sincronizadas", botones=True)

while True:
    schedule.run_pending()
    revisar_actualizaciones()
    time.sleep(2)
