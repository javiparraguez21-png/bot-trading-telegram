import os
import requests
import schedule
import time
from datetime import datetime
from deep_translator import GoogleTranslator
import feedparser

# ================= VARIABLES =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

FINNHUB_API_KEY = "d632dchr01qnpqnvhurgd632dchr01qnpqnvhus0"
NEWS_API_KEY = "ea6acd4f9dca4de99fab812dc069a67b"

# Keywords para filtrar noticias
KEYWORDS = ["FED","BCE","Trump","geopolítica","inflación","banco central","tensiones"]

# RSS Fuentes
RSS_FEEDS = [
    "https://elpais.com/rss/elpais/internacional.xml",
    "https://theconversation.com/global/rss",
    "https://rss.feedspot.com/economist_rss_feeds/",  # The Economist
    # Google News RSS filtrando por site
    "https://news.google.com/rss/search?q=site:cnbc.com+OR+site:bloomberglinea.com&hl=es&gl=ES&ceid=ES:es"
]

# ================= FUNCIONES =================
def enviar_mensaje_telegram(texto):
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

# ================= DATOS DEL MERCADO =================
def obtener_datos_macro():
    tickers = ["EURUSD", "GBPUSD", "XAUUSD", "DXY", "^VIX"]
    datos = {}
    for t in tickers:
        url = f"https://finnhub.io/api/v1/quote?symbol={t}&token={FINNHUB_API_KEY}"
        try:
            r = requests.get(url)
            datos[t] = r.json()
            if "c" not in datos[t] or "pc" not in datos[t]:
                datos[t] = {"c": None, "pc": None, "o": None}
        except:
            datos[t] = {"c": None, "pc": None, "o": None}
    return datos

def calcular_tendencia(actual, previo):
    if actual is None or previo is None:
        return "❌ Datos insuficientes"
    if actual > previo:
        return "🔺 Alcista"
    elif actual < previo:
        return "🔻 Bajista"
    else:
        return "➖ Neutral"

def detectar_divergencia(datos):
    eur = datos.get("EURUSD", {}).get("c")
    dxy = datos.get("DXY", {}).get("c")
    eur_pc = datos.get("EURUSD", {}).get("pc")
    dxy_pc = datos.get("DXY", {}).get("pc")
    if all(isinstance(x,(int,float)) for x in [eur,dxy,eur_pc,dxy_pc]):
        if (eur > eur_pc) and (dxy < dxy_pc):
            return "🔺 Divergencia alcista EURUSD vs DXY"
        elif (eur < eur_pc) and (dxy > dxy_pc):
            return "🔻 Divergencia bajista EURUSD vs DXY"
    return None

def detectar_manipulacion(datos):
    try:
        eur_data = datos.get("EURUSD", {})
        eur = eur_data.get("c")
        eur_prev = eur_data.get("pc")
        if eur is None or eur_prev is None or eur_prev == 0:
            return None
        cambio = ((eur - eur_prev)/eur_prev)*100
        if abs(cambio) > 0.5:
            return f"⚠️ Posible manipulación de Londres ({cambio:.2f}%)"
        return None
    except:
        return None

# ================= NOTICIAS =================
def obtener_noticias_rss():
    noticias = []
    for feed in RSS_FEEDS:
        try:
            d = feedparser.parse(feed)
            for entry in d.entries[:5]:
                titulo = entry.title if "title" in entry else ""
                descripcion = entry.summary if "summary" in entry else ""
                enlace = entry.link if "link" in entry else ""
                try:
                    titulo_es = GoogleTranslator(source='auto', target='es').translate(titulo)
                    descripcion_es = GoogleTranslator(source='auto', target='es').translate(descripcion)
                except:
                    titulo_es = titulo
                    descripcion_es = descripcion
                if any(k.lower() in (titulo_es+descripcion_es).lower() for k in KEYWORDS):
                    noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
        except Exception as e:
            print(f"[{datetime.now()}] Error RSS {feed}: {e}")
    return noticias

def obtener_noticias_api():
    noticias = []
    url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=5&apiKey={NEWS_API_KEY}"
    try:
        r = requests.get(url).json()
        for n in r.get("articles", []):
            titulo = n.get("title","")
            descripcion = n.get("description","")
            enlace = n.get("url","")
            try:
                titulo_es = GoogleTranslator(source='en', target='es').translate(titulo)
                descripcion_es = GoogleTranslator(source='en', target='es').translate(descripcion)
            except:
                titulo_es = titulo
                descripcion_es = descripcion
            if any(k.lower() in (titulo_es+descripcion_es).lower() for k in KEYWORDS):
                noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
    except:
        pass
    return noticias

def obtener_noticias_relevantes():
    return obtener_noticias_rss() + obtener_noticias_api()

# ================= CONSTRUIR MENSAJE =================
def construir_mensaje_alertas():
    datos = obtener_datos_macro()
    alertas = []

    # Tendencia y alertas de pares
    pares = ["EURUSD","GBPUSD","XAUUSD","DXY"]
    info_pares = []
    for p in pares:
        d = datos.get(p, {})
        c = d.get("c")
        pc = d.get("pc")
        o = d.get("o")
        tendencia = calcular_tendencia(c, pc)
        tendencia_diaria = calcular_tendencia(c, o)
        info_pares.append(f"{p}: {c} ({tendencia}, Tendencia diaria: {tendencia_diaria})")
    
    divergencia = detectar_divergencia(datos)
    if divergencia: alertas.append(divergencia)
    
    manipulacion = detectar_manipulacion(datos)
    if manipulacion: alertas.append(manipulacion)
    
    vix = datos.get("^VIX", {}).get("c")
    if isinstance(vix,(int,float)):
        vix_texto = "🔴 Alta volatilidad" if vix > 25 else "🟢 Baja/Moderada volatilidad"
        if vix > 25: alertas.append("⚡ VIX alto – cuidado con volatilidad")
    else:
        vix_texto = "❌ Error al obtener VIX"
    
    noticias = obtener_noticias_relevantes()
    if noticias:
        alertas.append(f"*Últimas noticias relevantes:*\n" + "\n".join(noticias))
    
    if not alertas: return None
    
    mensaje = f"""
📊 *MAESTRO ANALISTA IA – ALERTAS MACRO*

""" + "\n".join(info_pares) + f"\nVIX: {vix} ({vix_texto})\n\n*Alertas:*\n" + "\n".join(alertas)
    
    return mensaje

def enviar_si_hay_alerta():
    mensaje = construir_mensaje_alertas()
    if mensaje:
        enviar_mensaje_telegram(mensaje)
    else:
        print(f"[{datetime.now()}] Sin alertas relevantes, no se envió mensaje")

# ================= HORARIOS =================
schedule.every().day.at("10:30").do(enviar_si_hay_alerta)
for hour in range(11,16):
    schedule.every().day.at(f"{hour}:00").do(enviar_si_hay_alerta)
    schedule.every().day.at(f"{hour}:30").do(enviar_si_hay_alerta)
for hour in range(14,21):
    schedule.every().day.at(f"{hour}:00").do(enviar_si_hay_alerta)
    schedule.every().day.at(f"{hour}:30").do(enviar_si_hay_alerta)

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")
enviar_si_hay_alerta()

while True:
    schedule.run_pending()
    time.sleep(1)
