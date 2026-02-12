import requests, schedule, time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from tradingview_ta import TA_Handler, Interval
import feedparser
from deep_translator import GoogleTranslator

# ================= TELEGRAM =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
# ================= CONFIG =================
RIESGO_POR_TRADE = 0.005
RR_MINIMO = 2

# ================= ACTIVOS =================
ACTIVOS = {
    "EURUSD": {"symbol": "EURUSD", "screener": "forex", "exchange": "FX_IDC"},
    "GBPUSD": {"symbol": "GBPUSD", "screener": "forex", "exchange": "FX_IDC"},
    "XAUUSD": {"symbol": "XAUUSD", "screener": "forex", "exchange": "FX_IDC"},
    "DXY": {"symbol": "DXY", "screener": "forex", "exchange": "TVC"},
    "VIX": {"symbol": "VIX", "screener": "cfd", "exchange": "TVC"},
}

# ================= TIMEFRAMES =================
TIMEFRAMES = {
    "D1": Interval.INTERVAL_1_DAY,
    "H4": Interval.INTERVAL_4_HOURS,
    "H1": Interval.INTERVAL_1_HOUR,
    "M15": Interval.INTERVAL_15_MINUTES,
    "M5": Interval.INTERVAL_5_MINUTES,
    "M1": Interval.INTERVAL_1_MINUTE,
}

# ================= SESIONES (HORA CHILE) =================
SESIONES = {
    "Asia": (dtime(21, 0), dtime(5, 0)),
    "Londres": (dtime(4, 0), dtime(13, 0)),
    "New York": (dtime(9, 0), dtime(18, 0))
}

last_update_id = 0
rangos = {"Asia": {}, "Londres": {}}
alertas_enviadas = set()

# ================= TELEGRAM =================
def enviar(msg, botones=False):
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    if botones:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "🔄 Actualizar", "callback_data": "update"}]]
        }
    try:
        requests.post(f"{BASE_URL}/sendMessage", json=payload)
    except:
        pass

# ================= SESION ACTUAL (CHILE REAL) =================
def sesion_actual():
    ahora = datetime.now(ZoneInfo("America/Santiago")).time()
    for s, (i, f) in SESIONES.items():
        if i < f and i <= ahora <= f:
            return s
        if i > f and (ahora >= i or ahora <= f):
            return s
    return "Fuera"

# ================= ANALISIS MULTI TF =================
def analisis_multi_tf(activo):
    score = 0
    for intervalo in TIMEFRAMES.values():
        try:
            h = TA_Handler(**ACTIVOS[activo], interval=intervalo)
            r = h.get_analysis()
            rec = r.summary["RECOMMENDATION"]
            if rec in ["BUY", "STRONG_BUY"]:
                score += 1
            elif rec in ["SELL", "STRONG_SELL"]:
                score -= 1
        except:
            continue
    return score

# ================= PRECIO =================
def precio_actual(activo):
    try:
        h = TA_Handler(**ACTIVOS[activo], interval=Interval.INTERVAL_5_MINUTES)
        r = h.get_analysis()
        return r.indicators["close"]
    except:
        return None

# ================= ALERTA AMD =================
def alerta_amd(activo, texto, precio, nivel, direccion):
    score = analisis_multi_tf(activo)

    if direccion == "BUY" and score < 3:
        return
    if direccion == "SELL" and score > -3:
        return

    sl = abs(precio - nivel)
    tp = round(precio + sl * RR_MINIMO if direccion == "BUY"
               else precio - sl * RR_MINIMO, 2)

    enviar(
        f"🚨 *ALERTA AMD – {activo}*\n"
        f"{texto}\n\n"
        f"📍 Precio: {precio}\n"
        f"🛑 SL técnico: {nivel}\n"
        f"🎯 TP estimado: {tp}\n\n"
        f"⚖️ Riesgo: {RIESGO_POR_TRADE*100}%\n"
        f"📐 RR: 1:{RR_MINIMO}\n"
        "_Confirmación Multi-TF activa_"
    )

# ================= AMD =================
def detectar_amd():
    sesion = sesion_actual()

    for a in ["EURUSD", "GBPUSD", "XAUUSD"]:
        p = precio_actual(a)
        if not p:
            continue

        if sesion == "Asia":
            rangos["Asia"][a] = rangos["Asia"].get(a, {"h": p, "l": p})
            rangos["Asia"][a]["h"] = max(rangos["Asia"][a]["h"], p)
            rangos["Asia"][a]["l"] = min(rangos["Asia"][a]["l"], p)

        if sesion == "Londres" and a in rangos["Asia"]:
            h, l = rangos["Asia"][a]["h"], rangos["Asia"][a]["l"]

            if p > h and (a, "LON_MAX") not in alertas_enviadas:
                alerta_amd(a, "Sweep máximo de Asia", p, h, "SELL")
                alertas_enviadas.add((a, "LON_MAX"))

            if p < l and (a, "LON_MIN") not in alertas_enviadas:
                alerta_amd(a, "Sweep mínimo de Asia", p, l, "BUY")
                alertas_enviadas.add((a, "LON_MIN"))

# ================= DASHBOARD =================
def dashboard():
    ahora = datetime.now(ZoneInfo("America/Santiago")).strftime("%d/%m/%Y | %H:%M 🇨🇱")

    msg = (
        "📊 *MAESTRO ANALISTA IA – MARKET SENTIMENT*\n"
        f"🕒 {ahora}\n"
        f"📍 Sesión: {sesion_actual()}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    for a in ACTIVOS:
        score = analisis_multi_tf(a)

        if score >= 4:
            estado = "📈 ALCISTA"
        elif score <= -4:
            estado = "📉 BAJISTA"
        else:
            estado = "↔️ RANGO"

        msg += f"*{a}* ➜ {estado}\n"

    msg += "\n━━━━━━━━━━━━━━━━━━\n"
    msg += "📰 *Noticias clave:*\n"

    feeds = [
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "https://www.reuters.com/rssFeed/worldNews"
    ]

    noticias_lista = []
    for f in feeds:
        feed = feedparser.parse(f)
        for e in feed.entries[:2]:
            try:
                t = GoogleTranslator(source="en", target="es").translate(e.title)
            except:
                t = e.title
            noticias_lista.append(f"• {t}")

    msg += "\n".join(noticias_lista[:4])

    return msg

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
            if u["message"]["text"] in ["/estado", "/actualizar"]:
                enviar(dashboard(), botones=True)

        if "callback_query" in u:
            enviar(dashboard(), botones=True)

# ================= SCHEDULE =================
schedule.every(20).minutes.do(lambda: enviar(dashboard(), botones=True))
schedule.every(2).minutes.do(detectar_amd)

# ================= START =================
enviar("✅ *AMD SMART BOT PRO activo*\nChile 🇨🇱 sincronizado correctamente", botones=True)

while True:
    schedule.run_pending()
    revisar_updates()
    time.sleep(2)
