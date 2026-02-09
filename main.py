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

# ================= CONFIGURACION SECCIONES =================
SECCIONES = {
    "Asia": {"pre_market": "07:00", "sesion": list(range(7, 16))},       # 07:00 - 15:59
    "Londres": {"pre_market": "10:30", "sesion": list(range(11, 16))},   # 11:00 - 15:59
    "Nueva York": {"pre_market": "14:30", "sesion": list(range(14, 21))} # 14:00 - 20:59
}

# ================= FUNCIONES =================
def enviar_mensaje_telegram(texto):
    try:
        # Escapar caracteres especiales para Markdown
        texto = texto.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")
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

def obtener_datos_macro():
    tickers = ["EURUSD", "GBPUSD", "XAUUSD", "DXY", "^VIX"]
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
    try:
        if valor is None or previo is None or previo == 0:
            return "❌ Datos insuficientes"
        cambio = ((valor - previo)/previo)*100
        if cambio > umbral:
            return "🔺 Alcista"
        elif cambio < -umbral:
            return "🔻 Bajista"
        else:
            return "⏺ Neutral"
    except:
        return "❌ Error"

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
    if eur is None or eur_prev is None or eur_prev == 0:
        return None
    cambio = ((eur - eur_prev)/eur_prev)*100
    if abs(cambio) > 0.5:
        return f"⚠️ Posible manipulación Londres ({cambio:.2f}%)"
    return None

# ================= NOTICIAS =================
RSS_FEEDS = [
    "https://www.economist.com/feeds/print-sections/77/geopolitics.xml",
    "https://elpais.com/rss/elpais/internacional.xml",
    "https://theconversation.com/us/topics/global/rss",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html"
]

def obtener_noticias_rss():
    noticias = []
    for feed in RSS_FEEDS:
        try:
            d = feedparser.parse(feed)
            for entry in d.entries[:5]:
                titulo = entry.get("title","")
                descripcion = entry.get("summary","")
                enlace = entry.get("link","")
                try:
                    titulo_es = GoogleTranslator(source='en', target='es').translate(titulo)
                    descripcion_es = GoogleTranslator(source='en', target='es').translate(descripcion)
                except:
                    titulo_es = titulo
                    descripcion_es = descripcion
                noticias.append(f"📰 {titulo_es}\n{descripcion_es}\n🔗 {enlace}")
        except Exception as e:
            print(f"[{datetime.now()}] Error leyendo RSS {feed}: {e}")
    return noticias

def obtener_noticias_relevantes():
    noticias = []
    noticias.extend(obtener_noticias_rss())
    try:
        r = requests.get(f"https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=5&apiKey={NEWS_API_KEY}").json()
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
            noticias.append(f"📰 {titulo_es}\n{descripcion_es}\n🔗 {enlace}")
    except:
        pass
    return noticias[:10]  # Limitar para no exceder Telegram

# ================= CONSTRUIR MENSAJE =================
def construir_mensaje_alertas(seccion):
    datos = obtener_datos_macro()
    alertas = []

    tendencias = {}
    for par in ["EURUSD","GBPUSD","XAUUSD","DXY"]:
        valor = datos.get(par, {}).get("c")
        previo = datos.get(par, {}).get("pc")
        tendencias[par] = calcular_tendencia(valor, previo)

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

    mensaje = f"🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐\n📍 Sección: {seccion}\n\n" \
              f"EURUSD: {tendencias['EURUSD']}\n" \
              f"GBPUSD: {tendencias['GBPUSD']}\n" \
              f"XAUUSD: {tendencias['XAUUSD']}\n" \
              f"DXY: {tendencias['DXY']}\n" \
              f"VIX: {vix_texto}\n\n"

    if alertas:
        mensaje += "*Alertas:*\n" + "\n".join(alertas)
    else:
        mensaje += "✅ Sin alertas importantes en este momento."

    return mensaje

def enviar_alerta_seccion(seccion):
    mensaje = construir_mensaje_alertas(seccion)
    enviar_mensaje_telegram(mensaje)

# ================= HORARIOS =================
for seccion, info in SECCIONES.items():
    # Pre-market
    schedule.every().day.at(info["pre_market"]).do(enviar_alerta_seccion, seccion)
    # Durante sesión cada 20 minutos
    for h in info["sesion"]:
        schedule.every().day.at(f"{h:02d}:00").do(enviar_alerta_seccion, seccion)
        schedule.every().day.at(f"{h:02d}:20").do(enviar_alerta_seccion, seccion)
        schedule.every().day.at(f"{h:02d}:40").do(enviar_alerta_seccion, seccion)

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")

while True:
    schedule.run_pending()
    time.sleep(1)
