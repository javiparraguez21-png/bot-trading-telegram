import requests
import schedule
import time
from datetime import datetime, time as dtime
from tradingview_ta import TA_Handler, Interval
import feedparser
from deep_translator import GoogleTranslator

# ================= TELEGRAM =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ================= ACTIVOS (TRADINGVIEW FIX) =================
ACTIVOS = {
    "EURUSD": {"symbol": "EURUSD", "screener": "forex", "exchange": "FX_IDC"},
    "GBPUSD": {"symbol": "GBPUSD", "screener": "forex", "exchange": "FX_IDC"},
    "XAUUSD": {"symbol": "XAUUSD", "screener": "forex", "exchange": "FX_IDC"},
    "DXY": {"symbol": "DXY", "screener": "indices", "exchange": "TVC"},
    "VIX": {"symbol": "VIX", "screener": "indices", "exchange": "CBOE"}
}

# ================= SESIONES (CHILE 🇨🇱) =================
SESIONES = {
    "Asia": (dtime(21, 0), dtime(5, 0)),
    "Londres": (dtime(4, 0), dtime(13, 0)),
    "Nueva York": (dtime(9, 0), dtime(18, 0))
}

# ================= ESTADO =================
ultimo_sesgo = None
last_update_id = None

# ================= TELEGRAM =================
def enviar(msg, botones=False):
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    }

    if botones:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "🔄 Actualizar ahora", "callback_data": "update"}
            ]]
        }

    requests.post(f"{BASE_URL}/sendMessage", json=payload)

# ================= SESIÓN ACTUAL =================
def sesion_actual():
    ahora = datetime.now().time()
    for nombre, (inicio, fin) in SESIONES.items():
        if inicio < fin:
            if inicio <= ahora <= fin:
                return nombre
        else:
            if ahora >= inicio or ahora <= fin:
                return nombre
    return "Fuera de sesión"

# ================= DATOS =================
def obtener_datos():
    datos = {}
    for a, c in ACTIVOS.items():
        try:
            h = TA_Handler(
                symbol=c["symbol"],
                screener=c["screener"],
                exchange=c["exchange"],
                interval=Interval.INTERVAL_15_MINUTES
            )
            r = h.get_analysis()
            datos[a] = {
                "precio": r.indicators["close"],
                "tendencia": r.summary["RECOMMENDATION"],
                "rsi": round(r.indicators["RSI"], 1)
            }
        except:
            datos[a] = None
    return datos

# ================= SESGO =================
def calcular_sesgo(datos):
    sesgo = []

    if datos["DXY"] and datos["DXY"]["tendencia"] in ["BUY", "STRONG_BUY"]:
        sesgo.append("USD_FUERTE")

    if datos["VIX"] and datos["VIX"]["tendencia"] in ["BUY", "STRONG_BUY"]:
        sesgo.append("RISK_OFF")

    if datos["XAUUSD"] and datos["XAUUSD"]["tendencia"] in ["BUY", "STRONG_BUY"]:
        sesgo.append("ORO_DEMANDA")

    return sesgo if sesgo else ["NEUTRAL"]

# ================= MARKET SCORE =================
def market_score(sesgo):
    score = 50
    if "USD_FUERTE" in sesgo:
        score -= 10
    if "RISK_OFF" in sesgo:
        score -= 20
    if "ORO_DEMANDA" in sesgo:
        score -= 5
    if sesgo == ["NEUTRAL"]:
        score -= 5
    return max(0, min(100, score))

# ================= NOTICIAS (FILTRADAS) =================
def noticias_alto_impacto():
    keywords = ["fed", "inflation", "cpi", "rates", "dollar", "war", "oil"]
    feed = feedparser.parse("https://www.cnbc.com/id/100727362/device/rss/rss.html")
    out = []

    for e in feed.entries:
        titulo = e.title.lower()
        if any(k in titulo for k in keywords):
            try:
                t = GoogleTranslator(source="en", target="es").translate(e.title)
            except:
                t = e.title
            out.append(f"🔴 {t}")
        if len(out) == 2:
            break

    return out or ["🟢 Sin noticias macro críticas"]

# ================= DECISIÓN =================
def decision_operativa(score, sesion):
    if sesion == "Fuera de sesión":
        return "❌ *No operar – fuera de sesión*"
    if score < 35:
        return "❌ *Contexto desfavorable – proteger capital*"
    if score < 60:
        return "⚠️ *Solo setups A+ con confirmación*"
    return "✅ *Contexto favorable para operar*"

# ================= DASHBOARD =================
def dashboard(pre=False):
    global ultimo_sesgo

    datos = obtener_datos()
    sesgo = calcular_sesgo(datos)
    score = market_score(sesgo)
    news = noticias_alto_impacto()
    sesion = sesion_actual()

    msg = "📊 *DASHBOARD MACRO TRADING PRO*\n\n"

    for a, d in datos.items():
        if d:
            msg += f"*{a}*: {d['precio']} | {d['tendencia']} | RSI {d['rsi']}\n"

    msg += f"\n📍 *Sesión actual:* {sesion}"
    msg += f"\n🧠 *Sesgo:* {', '.join(sesgo)}"
    msg += f"\n📊 *Market Score:* {score}/100"
    msg += f"\n\n🎯 *Decisión:* {decision_operativa(score, sesion)}"

    if sesgo != ultimo_sesgo:
        msg += "\n\n🚨 *CAMBIO DE SESGO DETECTADO*"
        ultimo_sesgo = sesgo

    msg += "\n\n📰 *Noticias macro:*\n" + "\n".join(news)

    return msg

# ================= MANUAL UPDATE =================
def revisar_updates():
    global last_update_id
    r = requests.get(f"{BASE_URL}/getUpdates", params={"timeout": 1}).json()
    for u in r.get("result", []):
        last_update_id = u["update_id"]
        if "callback_query" in u:
            if u["callback_query"]["data"] == "update":
                enviar(dashboard(), botones=True)

# ================= SCHEDULE =================
schedule.every().hour.at(":00").do(lambda: enviar(dashboard(), botones=True))
schedule.every().day.at("03:45").do(lambda: enviar(dashboard(pre=True), botones=True))
schedule.every().day.at("08:45").do(lambda: enviar(dashboard(pre=True), botones=True))
schedule.every().day.at("20:45").do(lambda: enviar(dashboard(pre=True), botones=True))

# ================= START =================
enviar("✅ *Bot Macro Trading PRO activo*\nChile 🇨🇱 sincronizado", botones=True)
print("BOT MACRO PRO INICIADO")

while True:
    schedule.run_pending()
    revisar_updates()
    time.sleep(2)
