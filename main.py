import requests
import schedule
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from tradingview_ta import TA_Handler, Interval
import feedparser
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# ================= TELEGRAM =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

CHILE_TZ = ZoneInfo("America/Santiago")
eventos_notificados = set()
rangos = {"Asia": {}, "Londres": {}}
alertas_enviadas = set()

# ================= CONFIG =================
RIESGO_POR_TRADE = 0.005
RR_MINIMO = 2

# ================= ACTIVOS =================
ACTIVOS = {
    "EURUSD": {"symbol": "EURUSD", "screener": "forex", "exchange": "FX_IDC"},
    "GBPUSD": {"symbol": "GBPUSD", "screener": "forex", "exchange": "FX_IDC"},
    "XAUUSD": {"symbol": "XAUUSD", "screener": "forex", "exchange": "OANDA"},
    "DXY": {"symbol": "DXY", "screener": "cfd", "exchange": "TVC"},
    "VIX": {"symbol": "VIX", "screener": "cfd", "exchange": "CBOE"}
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

# ================= TELEGRAM SEND =================
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

# ================= SESIÓN CHILE =================
def sesion_actual():
    ahora = datetime.now(CHILE_TZ).time()
    if dtime(21,0) <= ahora or ahora <= dtime(5,0):
        return "Asia"
    if dtime(4,0) <= ahora <= dtime(13,0):
        return "Londres"
    if dtime(9,0) <= ahora <= dtime(18,0):
        return "New York"
    return "Fuera"

# ================= MULTI TF =================
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
def precio_actual(activo):
    try:
        h = TA_Handler(**ACTIVOS[activo], interval=Interval.INTERVAL_5_MINUTES)
        r = h.get_analysis()
        return r.indicators.get("close")
    except:
        return None

# ================= ALERTAS AMD =================
def alerta_amd(activo, texto, precio, nivel, direccion):
    score = analisis_multi_tf(activo)
    if direccion == "BUY" and score < 3: return
    if direccion == "SELL" and score > -3: return
    sl = abs(precio - nivel)
    tp = round(precio + sl*RR_MINIMO if direccion=="BUY" else precio - sl*RR_MINIMO,2)
    enviar(
        f"🚨 *ALERTA AMD – {activo}*\n{texto}\n\n"
        f"📍 Precio: {precio}\n🛑 SL: {nivel}\n🎯 TP: {tp}\n"
        f"⚖️ Riesgo: {RIESGO_POR_TRADE*100}% | RR 1:{RR_MINIMO}"
    )

def detectar_amd():
    sesion = sesion_actual()
    for a in ["EURUSD","GBPUSD","XAUUSD"]:
        p = precio_actual(a)
        if not p: continue
        if sesion=="Asia":
            rangos["Asia"][a] = rangos["Asia"].get(a,{"h":p,"l":p})
            rangos["Asia"][a]["h"] = max(rangos["Asia"][a]["h"],p)
            rangos["Asia"][a]["l"] = min(rangos["Asia"][a]["l"],p)
        if sesion=="Londres" and a in rangos["Asia"]:
            h,l = rangos["Asia"][a]["h"], rangos["Asia"][a]["l"]
            if p>h and (a,"LON_H") not in alertas_enviadas:
                alerta_amd(a,"Londres rompió High Asia",p,h,"SELL")
                alertas_enviadas.add((a,"LON_H"))
            if p<l and (a,"LON_L") not in alertas_enviadas:
                alerta_amd(a,"Londres rompió Low Asia",p,l,"BUY")
                alertas_enviadas.add((a,"LON_L"))

# ================= FOREX FACTORY =================
def obtener_eventos_ff():
    url = "https://www.forexfactory.com/calendar.php?day=today"
    headers = {"User-Agent":"Mozilla/5.0"}
    r = requests.get(url,headers=headers,timeout=10)
    soup = BeautifulSoup(r.text,"html.parser")
    eventos=[]
    filas = soup.find_all("tr",class_="calendar__row")
    for row in filas:
        imp = row.find("td",class_="calendar__impact")
        if not imp or not imp.img: continue
        impacto = imp.img["title"]
        if impacto not in ["Medium Impact Expected","High Impact Expected"]:
            continue
        hora = row.find("td",class_="calendar__time").get_text(strip=True)
        moneda = row.find("td",class_="calendar__currency").get_text(strip=True)
        evento = row.find("td",class_="calendar__event").get_text(strip=True)
        eventos.append({"hora":hora,"moneda":moneda,"evento":evento,"impacto":impacto})
    return eventos

# ================= NOTIFICACIÓN 10 MIN =================
def revisar_eventos_ff():
    ahora = datetime.now(CHILE_TZ)
    eventos = obtener_eventos_ff()
    for ev in eventos:
        try:
            hora_ev = datetime.strptime(ev["hora"],"%H:%M").replace(
                year=ahora.year,month=ahora.month,day=ahora.day,tzinfo=CHILE_TZ
            )
            diff = (hora_ev - ahora).total_seconds()/60
            id_ev = ev["hora"]+ev["evento"]
            if 8<=diff<=10 and id_ev not in eventos_notificados:
                enviar(
                    f"🚨 *NOTICIA EN 10 MINUTOS*\n"
                    f"🕒 {ev['hora']} 🇨🇱\n💱 {ev['moneda']}\n"
                    f"📰 {ev['evento']}\n🔥 {ev['impacto']}"
                )
                eventos_notificados.add(id_ev)
        except:
            continue

# ================= MACRO & GEOPOLÍTICAS =================
def noticias_macro_geopol():
    feeds=[
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "https://www.reuters.com/rssFeed/worldNews",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://www.bloomberg.com/feed/podcast/feed.xml"
    ]
    keywords=[
        "fed","bce","boj","inflation","interest rate", "rates",
        "dollar", "oil","war","sanctions","russia","ukraine","iran",
        "geopolitics","conflict","central bank"
    ]
    noticias=[]
    for f in feeds:
        feed=feedparser.parse(f)
        for e in feed.entries[:3]:
            tit=e.title.lower()
            if any(k in tit for k in keywords):
                try:
                    t=GoogleTranslator(source="en",target="es").translate(e.title)
                except:
                    t=e.title
                context=(e.summary if hasattr(e,"summary") else "")[:120]
                noticias.append(f"• {t}\n  _{context}_")
    return noticias if noticias else ["• Sin noticias macro/geo relevantes"]

# ================= DASHBOARD =================
def dashboard():
    ahora = datetime.now(CHILE_TZ).strftime("%d/%m/%Y | %H:%M 🇨🇱")
    msg=f"📊 *MAESTRO ANALISTA IA – MARKET SENTIMENT*\n🕒 {ahora}\n📍 Sesión: {sesion_actual()}\n━━━━━━━━━━━━━━━━━━\n"
    for a in ACTIVOS:
        p=precio_actual(a)
        score=analisis_multi_tf(a)
        estado="↔️ RANGO"
        if score>=4: estado="📈 ALCISTA"
        if score<=-4: estado="📉 BAJISTA"
        msg+=f"*{a}* ➜ {estado} | {p}\n"
    msg+="\n━━━━━━━━━━━━━━━━━━\n🗓️ *Forex Factory (Medium/High)*\n"
    for ev in obtener_eventos_ff()[:6]:
        msg+=f"{ev['hora']} | {ev['moneda']} | {ev['evento']} 🔥\n"
    msg+="\n━━━━━━━━━━━━━━━━━━\n📰 *Noticias Macro & Geopolíticas*\n"
    msg+="\n".join(noticias_macro_geopol())
    return msg

# ================= UPDATES =================
def revisar_updates():
    global last_update_id
    r=requests.get(f"{BASE_URL}/getUpdates",params={"timeout":1,"offset":last_update_id+1}).json()
    for u in r.get("result",[]):
        last_update_id=u["update_id"]
        if "message" in u and u["message"].get("text"):
            if u["message"]["text"] in ["/estado","/actualizar"]:
                enviar(dashboard(),botones=True)
        if "callback_query" in u:
            enviar(dashboard(),botones=True)

# ================= SCHEDULE =================
schedule.every(20).minutes.do(lambda: enviar(dashboard(),botones=True))
schedule.every(1).minutes.do(revisar_eventos_ff)
schedule.every(2).minutes.do(detectar_amd)

# ================= START =================
enviar("✅ *AMD SMART BOT + Noticias COMPLETO 🇨🇱*",botones=True)
while True:
    schedule.run_pending()
    revisar_updates()
    time.sleep(2)
