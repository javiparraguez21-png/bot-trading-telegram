import requests, schedule, time
from datetime import datetime, time as dtime
from tradingview_ta import TA_Handler, Interval
import feedparser
from deep_translator import GoogleTranslator

# ================= TELEGRAM =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ================= CONFIG =================
RIESGO_POR_TRADE = 0.005   # 0.5%
RR_MINIMO = 2

# ================= ACTIVOS =================
ACTIVOS = {
    "EURUSD": {"symbol": "EURUSD", "screener": "forex", "exchange": "FX_IDC"},
    "GBPUSD": {"symbol": "GBPUSD", "screener": "forex", "exchange": "FX_IDC"},
    "XAUUSD": {"symbol": "XAUUSD", "screener": "forex", "exchange": "FX_IDC"},
}

# ================= SESIONES CHILE =================
SESIONES = {
    "Asia": (dtime(21, 0), dtime(5, 0)),
    "Londres": (dtime(4, 0), dtime(13, 0)),
    "New York": (dtime(9, 0), dtime(18, 0))
}

# ================= ESTADO GLOBAL =================
last_update_id = 0
rangos = {
    "Asia": {},
    "Londres": {}
}
alertas_enviadas = set()

# ================= TELEGRAM =================
def enviar(msg, botones=False):
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    if botones:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "🔄 Actualizar", "callback_data": "update"}]]
        }
    requests.post(f"{BASE_URL}/sendMessage", json=payload)

# ================= SESION =================
def sesion_actual():
    ahora = datetime.now().time()
    for s, (i, f) in SESIONES.items():
        if i < f and i <= ahora <= f: return s
        if i > f and (ahora >= i or ahora <= f): return s
    return "Fuera"

# ================= DATOS =================
def precio_actual(activo):
    h = TA_Handler(**ACTIVOS[activo], interval=Interval.INTERVAL_5_MINUTES)
    r = h.get_analysis()
    return r.indicators["close"]

# ================= AMD =================
def detectar_amd():
    sesion = sesion_actual()

    for a in ACTIVOS:
        p = precio_actual(a)

        if sesion == "Asia":
            rangos["Asia"][a] = rangos["Asia"].get(a, {"h": p, "l": p})
            rangos["Asia"][a]["h"] = max(rangos["Asia"][a]["h"], p)
            rangos["Asia"][a]["l"] = min(rangos["Asia"][a]["l"], p)

        if sesion == "Londres" and a in rangos["Asia"]:
            h, l = rangos["Asia"][a]["h"], rangos["Asia"][a]["l"]

            if p > h and (a, "LON_MAX") not in alertas_enviadas:
                alerta_amd(a, "Manipulación sobre máximo de Asia", p, h, "SELL")
                alertas_enviadas.add((a, "LON_MAX"))

            if p < l and (a, "LON_MIN") not in alertas_enviadas:
                alerta_amd(a, "Manipulación bajo mínimo de Asia", p, l, "BUY")
                alertas_enviadas.add((a, "LON_MIN"))

        if sesion == "New York" and a in rangos["Londres"]:
            h, l = rangos["Londres"][a]["h"], rangos["Londres"][a]["l"]

            if p > h and (a, "NY_MAX") not in alertas_enviadas:
                alerta_amd(a, "Manipulación sobre máximo de Londres", p, h, "SELL")
                alertas_enviadas.add((a, "NY_MAX"))

            if p < l and (a, "NY_MIN") not in alertas_enviadas:
                alerta_amd(a, "Manipulación bajo mínimo de Londres", p, l, "BUY")
                alertas_enviadas.add((a, "NY_MIN"))

# ================= ALERTA =================
def alerta_amd(activo, texto, precio, nivel, direccion):
    sl = abs(precio - nivel)
    tp = round(precio + sl * RR_MINIMO if direccion == "BUY" else precio - sl * RR_MINIMO, 2)

    enviar(
        f"🚨 *ALERTA AMD – {activo}*\n"
        f"{texto}\n\n"
        f"📍 Precio: {precio}\n"
        f"🛑 SL técnico: {nivel}\n"
        f"🎯 TP estimado: {tp}\n\n"
        f"⚖️ Riesgo: {RIESGO_POR_TRADE*100}%\n"
        f"📐 RR: 1:{RR_MINIMO}\n"
        "_Modelo AMD: Liquidez → Reversión institucional_"
    )

# ================= NOTICIAS =================
def noticias():
    feeds = [
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "https://www.reuters.com/rssFeed/worldNews",
        "https://www.aljazeera.com/xml/rss/all.xml"
    ]
    out = []
    for f in feeds:
        feed = feedparser.parse(f)
        for e in feed.entries[:2]:
            try:
                t = GoogleTranslator(source="en", target="es").translate(e.title)
            except:
                t = e.title
            out.append(f"📰 {t}")
    return out[:4]

# ================= DASHBOARD =================
def dashboard():
    return (
        "📊 *AMD SMART BOT – ESTADO GENERAL*\n"
        f"🕒 {datetime.utcnow().strftime('%d/%m %H:%M UTC')}\n"
        f"📍 Sesión actual: {sesion_actual()}\n\n"
        "🧠 *Modelo AMD activo*\n"
        "🔔 Alertas solo en manipulación real\n\n"
        "📰 *Noticias clave:*\n" +
        "\n".join(noticias())
    )

# ================= UPDATES =================
def revisar_updates():
    global last_update_id
    r = requests.get(
        f"{BASE_URL}/getUpdates",
        params={"timeout": 1, "offset": last_update_id + 1}
    ).json()

    for u in r.get("result", []):
        last_update_id = u["update_id"]

        if "message" in u and u["message"].get("text"):
            cmd = u["message"]["text"]
            if cmd == "/estado":
                enviar(dashboard())
            if cmd == "/actualizar":
                enviar(dashboard(), botones=True)

        if "callback_query" in u:
            enviar(dashboard(), botones=True)

# ================= SCHEDULE =================
schedule.every(20).minutes.do(lambda: enviar(dashboard(), botones=True))
schedule.every(2).minutes.do(detectar_amd)

# ================= START =================
enviar("✅ *AMD SMART BOT activo*\nChile 🇨🇱 sincronizado", botones=True)

while True:
    schedule.run_pending()
    revisar_updates()
    time.sleep(2)
