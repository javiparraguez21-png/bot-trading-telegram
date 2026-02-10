import os
import requests
import schedule
import time
from datetime import datetime
from deep_translator import GoogleTranslator
import feedparser

# ================= VARIABLES =================
# Telegram
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# APIs
FINNHUB_API_KEY = "d632dchr01qnpqnvhurgd632dchr01qnpqnvhus0"
NEWS_API_KEY = "ea6acd4f9dca4de99fab812dc069a67b"

# ================= CONFIG =================
SECCIONES = {
    "Asia": {"pre_market": "00:30", "inicio": 1, "fin": 9},
    "Londres": {"pre_market": "10:30", "inicio": 11, "fin": 15},
    "Nueva York": {"pre_market": "14:30", "inicio": 14, "fin": 20}
}

RSS_FEEDS = [
    "https://www.economist.com/feeds/print-sections/77/geopolitics.xml",
    "https://elpais.com/rss/elpais/internacional.xml",
    "https://theconversation.com/us/topics/global/rss",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html"
]

MAX_LONG_MSG = 3900  # Telegram máximo 4096 caracteres, dejando margen

# ================= FUNCIONES =================
def enviar_mensaje_telegram(texto):
    try:
        # Dividir mensaje si es muy largo
        partes = [texto[i:i+MAX_LONG_MSG] for i in range(0, len(texto), MAX_LONG_MSG)]
        for parte in partes:
            r = requests.post(URL_TELEGRAM, data={
                "chat_id": CHAT_ID,
                "text": parte,
                "parse_mode": "Markdown"
            })
            if r.status_code != 200:
                print(f"[{datetime.now()}] Error Telegram: {r.text}")
    except Exception as e:
        print(f"[{datetime.now()}] Excepción al enviar mensaje: {e}")

# ------------------- DATOS MERCADO -------------------
def obtener_datos_macro():
    tickers = ["EURUSD", "GBPUSD", "XAUUSD", "DXY", "^VIX"]
    datos = {}
    for t in tickers:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={t}&token={FINNHUB_API_KEY}")
            data = r.json()
            datos[t] = {"c": data.get("c", None), "pc": data.get("pc", None)}
        except:
            datos[t] = {"c": None, "pc": None}
    return datos

# ------------------- TENDENCIAS -------------------
def calcular_tendencia(valor, previo):
    try:
        if valor is None or previo in [None, 0]:
            return "❌ Datos insuficientes", 0
        cambio = ((valor - previo)/previo)*100
        if cambio > 0.1:
            return "Alcista 🔺", cambio
        elif cambio < -0.1:
            return "Bajista 🔻", cambio
        else:
            return "Neutral ➖", cambio
    except:
        return "❌ Error", 0

# ------------------- ALERTAS -------------------
def detectar_divergencia(datos):
    eur, dxy = datos.get("EURUSD", {}).get("c"), datos.get("DXY", {}).get("c")
    eur_pc, dxy_pc = datos.get("EURUSD", {}).get("pc"), datos.get("DXY", {}).get("pc")
    if all(isinstance(x,(int,float)) for x in [eur,dxy,eur_pc,dxy_pc]):
        if (eur > eur_pc) and (dxy < dxy_pc):
            return "🔺 Divergencia alcista EURUSD vs DXY"
        elif (eur < eur_pc) and (dxy > dxy_pc):
            return "🔻 Divergencia bajista EURUSD vs DXY"
    return None

def detectar_manipulacion(datos):
    try:
        eur, eur_prev = datos.get("EURUSD", {}).get("c"), datos.get("EURUSD", {}).get("pc")
        if eur_prev in [None,0] or eur is None:
            return None
        cambio = ((eur - eur_prev)/eur_prev)*100
        if abs(cambio) > 0.5:
            return f"⚠️ Posible manipulación de Londres ({cambio:.2f}%)"
    except:
        return None

# ------------------- NOTICIAS -------------------
def obtener_noticias_rss():
    noticias = []
    for feed in RSS_FEEDS:
        try:
            d = feedparser.parse(feed)
            for entry in d.entries[:5]:
                titulo, descripcion, enlace = entry.get("title",""), entry.get("summary",""), entry.get("link","")
                try:
                    titulo_es = GoogleTranslator(source='en', target='es').translate(titulo)
                    descripcion_es = GoogleTranslator(source='en', target='es').translate(descripcion)
                except:
                    titulo_es, descripcion_es = titulo, descripcion
                noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}")
        except Exception as e:
            print(f"[{datetime.now()}] Error RSS {feed}: {e}")
    return noticias

def obtener_noticias():
    noticias = obtener_noticias_rss()
    try:
        r = requests.get(f"https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=5&apiKey={NEWS_API_KEY}").json()
        for n in r.get("articles", []):
            titulo, descripcion, enlace = n.get("title",""), n.get("description",""), n.get("url","")
            try:
                titulo_es = GoogleTranslator(source='en', target='es').translate(titulo)
                descripcion_es = GoogleTranslator(source='en', target='es').translate(descripcion)
            except:
                titulo_es, descripcion_es = titulo, descripcion
            noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}")
    except:
        pass
    return noticias

# ------------------- CONSTRUIR MENSAJE -------------------
def construir_mensaje_alertas(seccion="General"):
    datos = obtener_datos_macro()
    alertas = []
    lineas = []

    for par in ["EURUSD","GBPUSD","XAUUSD","DXY"]:
        valor, previo = datos.get(par, {}).get("c"), datos.get(par, {}).get("pc")
        tendencia, cambio = calcular_tendencia(valor, previo)
        if valor is None:
            valor_text = "❌"
        else:
            valor_text = f"{valor:.4f}" if par != "XAUUSD" else f"{valor:.2f}"
        lineas.append(f"{par}: {valor_text} ({cambio:+.2f}%) {tendencia}")

    vix = datos.get("^VIX", {}).get("c")
    if isinstance(vix,(int,float)):
        vix_texto = "🔴 Alta volatilidad" if vix > 25 else "🟢 Baja/Moderada"
        if vix > 25:
            alertas.append("⚡ VIX alto – cuidado con volatilidad")
        vix_valor = f"{vix:.2f}"
    else:
        vix_texto, vix_valor = "❌ Error", "❌"

    divergencia = detectar_divergencia(datos)
    if divergencia: alertas.append(divergencia)
    manipulacion = detectar_manipulacion(datos)
    if manipulacion: alertas.append(manipulacion)

    noticias = obtener_noticias()
    if noticias:
        alertas.append(f"*Últimas noticias ({seccion}):*\n" + "\n\n".join(noticias[:5]))

    mensaje = f"🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐\n📍 Sección: {seccion}\n\n"
    mensaje += "\n".join(lineas)
    mensaje += f"\nVIX: {vix_valor} ({vix_texto})\n\n"
    if alertas:
        mensaje += "*Alertas:*\n" + "\n".join(alertas)
    return mensaje

# ------------------- ENVIAR ALERTAS -------------------
def enviar_alerta_seccion(seccion):
    mensaje = construir_mensaje_alertas(seccion)
    enviar_mensaje_telegram(mensaje)

# ================= HORARIOS =================
for sec, conf in SECCIONES.items():
    # Pre-market
    schedule.every().day.at(conf["pre_market"]).do(enviar_alerta_seccion, sec)
    # Durante la sesión cada 20 min
    for h in range(conf["inicio"], conf["fin"]+1):
        for m in [0,20,40]:
            hora = f"{h:02d}:{m:02d}"
            schedule.every().day.at(hora).do(enviar_alerta_seccion, sec)

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")
enviar_alerta_seccion("General")

while True:
    schedule.run_pending()
    time.sleep(1)
