import requests
import schedule
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from tradingview_ta import TA_Handler, Interval
import feedparser
from bs4 import BeautifulSoup

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
    "VIX": {"symbol": "VIX", "screener": "cfd", "exchange": "TVC"}
}

# ================= TIMEFRAMES =================
TIMEFRAMES = {
    "D1": Interval.INTERVAL_1_DAY,
    "H4": Interval.INTERVAL_4_HOURS,
    "H1": Interval.INTERVAL_1_HOUR,
    "M15": Interval.INTERVAL_15_MINUTES,
    "M5": Interval.INTERVAL_5_MINUTES,
    "M1": Interval.INTERVAL_1_MINUTE
}

# ================= SESIONES CHILE =================
SESIONES = {
    "Asia": (dtime(21, 0), dtime(5, 0)),
    "Londres": (dtime(4, 0), dtime(13, 0)),
    "New York": (dtime(9, 0), dtime(18, 0))
}

# Estado global
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
    requests.post(f"{BASE_URL}/sendMessage", json=payload)

# ================= SESIÓN =================
def sesion_actual():
    ahora = datetime.now(ZoneInfo("America/Santiago")).time()
    for s, (inicio, fin) in SESIONES.items():
        if inicio < fin and inicio <= ahora <= fin:
            return s
        if inicio > fin and (ahora >= inicio or ahora <= fin):
            return s
    return "Fuera"

# ================= TENDENCIA MULTI TF =================
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

# ================= PRECIO ACTUAL =================
def obtener_precio(activo):
    try:
        h = TA_Handler(**ACTIVOS[activo], interval=Interval.INTERVAL_1_MINUTE)
        r = h.get_analysis()
        return r.indicators["close"]
    except:
        return None

# ================= OPINION PRECIO =================
def opinion_precio(activo, precio, rango_asia, rango_londres):
    opinion = ""
    if rango_asia and precio:
        high_asia, low_asia = rango_asia
        if precio > high_asia:
            opinion += "🔼 Por encima de High Asia → posible pullback o continuación\n"
        if precio < low_asia:
            opinion += "🔽 Por debajo de Low Asia → presión bajista\n"
        if low_asia <= precio <= high_asia:
            opinion += "↔ Dentro de rango Asia → sin dirección clara\n"
    if rango_londres and precio:
        high_lon, low_lon = rango_londres
        if precio > high_lon:
            opinion += "🔼 Por encima de High Londres → posible rompe y continúa\n"
        if precio < low_lon:
            opinion += "🔽 Por debajo de Low Londres → posible fuerza bajista\n"
    return opinion or "📌 Precio en zona neutral"

# ================= MANIPULACIÓN DE RANGOS =================
def detectar_amd():
    sesion = sesion_actual()
    for a in ACTIVOS:
        p = obtener_precio(a)
        if not p:
            continue

        # Rango Asia
        if sesion == "Asia":
            rangos["Asia"][a] = rangos["Asia"].get(a, {"h": p, "l": p})
            rangos["Asia"][a]["h"] = max(rangos["Asia"][a]["h"], p)
            rangos["Asia"][a]["l"] = min(rangos["Asia"][a]["l"], p)

        # Londres rompe Asia
        if sesion == "Londres" and a in rangos["Asia"]:
            high_asia = rangos["Asia"][a]["h"]
            low_asia = rangos["Asia"][a]["l"]
            if p > high_asia and (a, "LON_HIGH") not in alertas_enviadas:
                enviar(f"🚨 *Manipulación Londres alta de Asia*\n{a} rompió High Asia ({high_asia})\nPrecio: {p}")
                alertas_enviadas.add((a, "LON_HIGH"))
            if p < low_asia and (a, "LON_LOW") not in alertas_enviadas:
                enviar(f"🚨 *Manipulación Londres baja de Asia*\n{a} rompió Low Asia ({low_asia})\nPrecio: {p}")
                alertas_enviadas.add((a, "LON_LOW"))

        # New York rompe Londres
        if sesion == "New York" and a in rangos["Londres"]:
            high_lon = rangos["Londres"][a]["h"]
            low_lon = rangos["Londres"][a]["l"]
            if p > high_lon and (a, "NY_HIGH") not in alertas_enviadas:
                enviar(f"🚨 *Manipulación NY alta de Londres*\n{a} rompió High Londres ({high_lon})\nPrecio: {p}")
                alertas_enviadas.add((a, "NY_HIGH"))
            if p < low_lon and (a, "NY_LOW") not in alertas_enviadas:
                enviar(f"🚨 *Manipulación NY baja de Londres*\n{a} rompió Low Londres ({low_lon})\nPrecio: {p}")
                alertas_enviadas.add((a, "NY_LOW"))

# ================= NOTICIAS FOREX FACTORY =================
def noticias_forex_factory():
    url = "https://www.forexfactory.com/calendar.php?week=this"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    events = []
    rows = soup.find_all("tr", {"class": "calendar_row"})
    for row in rows:
        impact = row.find("td", {"class": "impact"})
        if impact and ("high" in impact.text.lower() or "medium" in impact.text.lower()):
            time_cell = row.find("td", {"class": "time"})
            pair_cell = row.find("td", {"class": "pair"})
            event_cell = row.find("td", {"class": "event"})
            impact_txt = impact.text.strip()
            event_time = time_cell.text.strip()
            pair = pair_cell.text.strip()
            desc = event_cell.text.strip()
            events.append(f"{event_time} | {pair} | {desc} ({impact_txt})")
    return "🗓️ *Calendario Forex Factory:*\n" + "\n".join(events[:8])

# ================= DASHBOARD FINAL =================
def dashboard():
    ahora = datetime.now(ZoneInfo("America/Santiago")).strftime("%d/%m/%Y | %H:%M 🇨🇱")
    msg = (
        "📊 *MAESTRO ANALISTA IA – MARKET SENTIMENT*\n"
        f"🕒 {ahora}\n"
        f"📍 Sesión: {sesion_actual()}\n"
        "━━━━━━━━━━━━━━━━━━\n"
    )

    for a in ACTIVOS:
        precio = obtener_precio(a)
        rango_asia = None
        rango_lon = None
        if a in rangos["Asia"]:
            rango_asia = (rangos["Asia"][a]["h"], rangos["Asia"][a]["l"])
        if a in rangos["Londres"]:
            rango_lon = (rangos["Londres"][a]["h"], rangos["Londres"][a]["l"])

        opin = opinion_precio(a, precio, rango_asia, rango_lon)
        score = analisis_multi_tf(a)

        if score >= 4:
            estado = "📈 ALCISTA"
        elif score <= -4:
            estado = "📉 BAJISTA"
        else:
            estado = "↔️ RANGO"

        msg += f"\n*{a}* ➜ {estado} | {precio}\n{opin}\n"

    msg += "\n━━━━━━━━━━━━━━━━━━\n"
    msg += noticias_forex_factory()
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
enviar("✅ *AMD SMART BOT PRO con noticias FF*\nChile 🇨🇱 sincronizado", botones=True)

while True:
    schedule.run_pending()
    revisar_updates()
    time.sleep(2)
