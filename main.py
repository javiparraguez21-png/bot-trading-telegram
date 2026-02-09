import os
import requests
import schedule
import time
from datetime import datetime
from deep_translator import GoogleTranslator
import feedparser
import re

# ================= VARIABLES =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

FINNHUB_API_KEY = "d632dchr01qnpqnvhurgd632dchr01qnpqnvhus0"
NEWS_API_KEY = "ea6acd4f9dca4de99fab812dc069a67b"

RSS_FEEDS = [
    "https://www.economist.com/feeds/print-sections/77/geopolitics.xml",
    "https://elpais.com/rss/elpais/internacional.xml",
    "https://theconversation.com/us/topics/global/rss",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html"
]

SECCIONES = {
    "Asia": {"pre_market": "00:30", "sesion": range(1,10)},        # Horario ejemplo
    "Londres": {"pre_market": "10:30", "sesion": range(11,16)},
    "Nueva York": {"pre_market": "14:30", "sesion": range(14,21)}
}

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

def escapar_markdown(texto):
    if not texto:
        return ""
    caracteres = r'[_*[\]()~`>#+\-=|{}.!]'
    return re.sub(f"({caracteres})", r"\\\1", texto)

# ================= DATOS DEL MERCADO =================
def obtener_datos_macro():
    tickers = ["EURUSD","GBPUSD","XAUUSD","DXY","^VIX"]
    datos = {}
    for t in tickers:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={t}&token={FINNHUB_API_KEY}")
            datos[t] = r.json()
            if "c" not in datos[t] or "pc" not in datos[t]:
                datos[t] = {"c": None, "pc": None}
        except:
            datos[t] = {"c": None, "pc": None}
    return datos

def calcular_tendencia(valor, previo, umbral=0.1):
    if valor is None or previo in [None,0]:
        return "❌ Datos insuficientes"
    cambio = ((valor - previo)/previo)*100
    if cambio > umbral:
        return "🔺 Alcista"
    elif cambio < -umbral:
        return "🔻 Bajista"
    else:
        return "⚪ Neutral"

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
    eur = datos.get("EURUSD", {}).get("c")
    eur_prev = datos.get("EURUSD", {}).get("pc")
    if eur in [None] or eur_prev in [None,0]:
        return None
    cambio = ((eur - eur_prev)/eur_prev)*100
    if abs(cambio) > 0.5:
        return f"⚠️ Posible manipulación de Londres ({cambio:.2f}%)"
    return None

# ================= NOTICIAS =================
def obtener_noticias_rss():
    noticias = []
    for feed in RSS_FEEDS:
        try:
            d = feedparser.parse(feed)
            for entry in d.entries[:5]:
                titulo = escapar_markdown(GoogleTranslator(source='en', target='es').translate(entry.get("title","")))
                descripcion = escapar_markdown(GoogleTranslator(source='en', target='es').translate(entry.get("summary","")))
                enlace = entry.get("link","")
                noticias.append(f"📰 *{titulo}*\n{descripcion}\n🔗 {enlace}\n")
        except:
            continue
    return noticias

def obtener_noticias_relevantes():
    noticias = obtener_noticias_rss()
    try:
        r = requests.get(f"https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=5&apiKey={NEWS_API_KEY}").json()
        for n in r.get("articles", []):
            titulo = escapar_markdown(GoogleTranslator(source='en', target='es').translate(n.get("title","")))
            descripcion = escapar_markdown(GoogleTranslator(source='en', target='es').translate(n.get("description","")))
            enlace = n.get("url","")
            noticias.append(f"📰 *{titulo}*\n{descripcion}\n🔗 {enlace}\n")
    except:
        pass
    return noticias

# ================= CONSTRUIR MENSAJE =================
def construir_mensaje_alertas(seccion):
    datos = obtener_datos_macro()
    alertas = []

    # Tendencias
    tendencias = {}
    for par in ["EURUSD","GBPUSD","XAUUSD","DXY"]:
        valor = datos.get(par, {}).get("c")
        previo = datos.get(par, {}).get("pc")
        tendencias[par] = calcular_tendencia(valor, previo)

    # Alertas
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
        alertas.append(f"*Últimas noticias relevantes ({seccion}):*\n" + "\n".join(noticias))

    if not alertas: return None

    mensaje = f"""
🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐
📍 Sección: {seccion}

EURUSD: {datos.get('EURUSD', {}).get('c')} – Tendencia: {tendencias['EURUSD']}
GBPUSD: {datos.get('GBPUSD', {}).get('c')} – Tendencia: {tendencias['GBPUSD']}
XAUUSD: {datos.get('XAUUSD', {}).get('c')} – Tendencia: {tendencias['XAUUSD']}
DXY: {datos.get('DXY', {}).get('c')} – Tendencia: {tendencias['DXY']}
VIX: {vix} ({vix_texto})

*Alertas:*
""" + "\n".join(alertas)

    return mensaje

def enviar_alerta_seccion(seccion):
    mensaje = construir_mensaje_alertas(seccion)
    if mensaje:
        if len(mensaje) > 4000:
            # dividir mensajes largos
            partes = [mensaje[i:i+3900] for i in range(0,len(mensaje),3900)]
            for p in partes:
                enviar_mensaje_telegram(p)
        else:
            enviar_mensaje_telegram(mensaje)
    else:
        print(f"[{datetime.now()}] Sin alertas en {seccion}")

# ================= HORARIOS =================
for seccion, info in SECCIONES.items():
    # Pre-market
    schedule.every().day.at(info["pre_market"]).do(enviar_alerta_seccion, seccion)
    # Durante sesión cada 20 min
    for h in info["sesion"]:
        schedule.every().day.at(f"{h}:00").do(enviar_alerta_seccion, seccion)
        schedule.every().day.at(f"{h}:20").do(enviar_alerta_seccion, seccion)
        schedule.every().day.at(f"{h}:40").do(enviar_alerta_seccion, seccion)

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")

enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")
for seccion in SECCIONES.keys():
    enviar_alerta_seccion(seccion)

while True:
    schedule.run_pending()
    time.sleep(1)
