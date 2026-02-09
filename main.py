import os
import requests
import schedule
import time
from datetime import datetime
from deep_translator import GoogleTranslator
import feedparser  # Para leer RSS

# ================= VARIABLES =================
# Telegram
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# APIs
FINNHUB_API_KEY = "d632dchr01qnpqnvhurgd632dchr01qnpqnvhus0"
NEWS_API_KEY = "ea6acd4f9dca4de99fab812dc069a67b"

# ================= DEBUG =================
print("===== VERIFICANDO VARIABLES DE ENTORNO =====")
print(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN}")
print(f"CHAT_ID: {CHAT_ID}")
print(f"FINNHUB_API_KEY: {FINNHUB_API_KEY}")
print(f"NEWS_API_KEY: {NEWS_API_KEY}")
print("===========================================")

# ================= FUNCIONES =================
def enviar_mensaje_telegram(texto):
    MAX_CHARS = 4000
    try:
        for i in range(0, len(texto), MAX_CHARS):
            r = requests.post(URL_TELEGRAM, data={
                "chat_id": CHAT_ID,
                "text": texto[i:i+MAX_CHARS],
                "parse_mode": "Markdown"
            })
            if r.status_code != 200:
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
                datos[t] = {"c": None, "pc": None}
        except:
            datos[t] = {"c": None, "pc": None}
    return datos

# ================= DETECCIÓN =================
def detectar_divergencia(datos):
    eur = datos.get("EURUSD", {}).get("c")
    dxy = datos.get("DXY", {}).get("c")
    eur_pc = datos.get("EURUSD", {}).get("pc")
    dxy_pc = datos.get("DXY", {}).get("pc")
    if all(isinstance(x,(int,float)) and x != 0 for x in [eur,dxy,eur_pc,dxy_pc]):
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
        if not all(isinstance(x,(int,float)) for x in [eur, eur_prev]):
            return None
        if eur_prev == 0:
            return None
        cambio = ((eur - eur_prev)/eur_prev)*100
        if abs(cambio) > 0.5:
            return f"⚠️ Posible manipulación de Londres ({cambio:.2f}%)"
        return None
    except:
        return None

def calcular_tendencia(valor, previo, umbral=0.1):
    """Determina si el par es Alcista, Neutral o Bajista, previniendo división por cero"""
    if valor is None or previo in [None,0]:
        return "❌ Datos insuficientes"
    cambio = ((valor - previo)/previo)*100
    if cambio > umbral:
        return "📈 Alcista"
    elif cambio < -umbral:
        return "📉 Bajista"
    else:
        return "➡️ Neutral"

# ================= NOTICIAS =================
RSS_FEEDS = [
    "https://www.economist.com/feeds/print-sections/77/geopolitics.xml",
    "https://elpais.com/rss/elpais/internacional.xml",
    "https://theconversation.com/us/topics/global/rss",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html"
]

def obtener_noticias_rss(max_por_feed=3):
    noticias = []
    for feed in RSS_FEEDS:
        try:
            d = feedparser.parse(feed)
            for entry in d.entries[:max_por_feed]:
                titulo = entry.get("title","")
                descripcion = entry.get("summary","")
                enlace = entry.get("link","")
                try:
                    titulo_es = GoogleTranslator(source='en', target='es').translate(titulo)
                    descripcion_es = GoogleTranslator(source='en', target='es').translate(descripcion)
                except:
                    titulo_es = titulo
                    descripcion_es = descripcion
                noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
        except Exception as e:
            print(f"[{datetime.now()}] Error leyendo RSS {feed}: {e}")
    return noticias

def obtener_noticias_relevantes(max_newsapi=3):
    noticias = obtener_noticias_rss()
    url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize={max_newsapi}&apiKey={NEWS_API_KEY}"
    try:
        r = requests.get(url).json()
        for n in r.get("articles", [])[:max_newsapi]:
            titulo = n.get("title","")
            descripcion = n.get("description","")
            enlace = n.get("url","")
            try:
                titulo_es = GoogleTranslator(source='en', target='es').translate(titulo)
                descripcion_es = GoogleTranslator(source='en', target='es').translate(descripcion)
            except:
                titulo_es = titulo
                descripcion_es = descripcion
            noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
    except:
        pass
    return noticias

# ================= CONSTRUIR MENSAJE =================
def construir_mensaje_alertas(seccion="General"):
    datos = obtener_datos_macro()
    alertas = []

    # Tendencias por par
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

    if not alertas: return None

    mensaje = f"""
🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐
📍 Sección: {seccion}

EURUSD: {datos.get('EURUSD')} – Tendencia: {tendencias['EURUSD']}
GBPUSD: {datos.get('GBPUSD')} – Tendencia: {tendencias['GBPUSD']}
XAUUSD: {datos.get('XAUUSD')} – Tendencia: {tendencias['XAUUSD']}
DXY: {datos.get('DXY')} – Tendencia: {tendencias['DXY']}
VIX: {vix} ({vix_texto})

*Alertas:*
""" + "\n".join(alertas)

    return mensaje

def enviar_alerta_seccion(seccion):
    mensaje = construir_mensaje_alertas(seccion)
    if mensaje:
        enviar_mensaje_telegram(mensaje)
    else:
        print(f"[{datetime.now()}] Sin alertas relevantes en {seccion}")

# ================= HORARIOS =================
SECCIONES = {
    "Asia": {"pre": "01:30", "sesion": range(2,10)},     # Horas aproximadas en UTC
    "Londres": {"pre": "10:30", "sesion": range(11,16)},
    "Nueva York": {"pre": "14:30", "sesion": range(15,21)}
}

for sec, val in SECCIONES.items():
    # Pre-market
    schedule.every().day.at(val["pre"]).do(enviar_alerta_seccion, sec)
    # Durante la sesión cada 20 minutos
    for h in val["sesion"]:
        for m in [0,20,40]:
            schedule.every().day.at(f"{h:02d}:{m:02d}").do(enviar_alerta_seccion, sec)

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")

# Mensaje de prueba al iniciar
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")

# Envío inicial de alertas
for sec in SECCIONES:
    enviar_alerta_seccion(sec)

while True:
    schedule.run_pending()
    time.sleep(1)
