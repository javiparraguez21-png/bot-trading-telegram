import os
import requests
import schedule
import time
from datetime import datetime
from deep_translator import GoogleTranslator
import feedparser  # Para RSS

# ================= VARIABLES =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Noticias RSS y NewsAPI
NEWS_API_KEY = "ea6acd4f9dca4de99fab812dc069a67b"
RSS_FEEDS = [
    "https://www.economist.com/feeds/print-sections/77/geopolitics.xml",
    "https://elpais.com/rss/elpais/internacional.xml",
    "https://theconversation.com/us/topics/global/rss",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html"
]

# Símbolos para TradingView
SIMBOLOS_TRADINGVIEW = {
    "EURUSD": "FX:EURUSD",
    "GBPUSD": "FX:GBPUSD",
    "XAUUSD": "FX:XAUUSD",
    "DXY": "ICEUS:DXY",
    "VIX": "CBOE:VIX"
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

# ========== DATOS EN TIEMPO REAL ==========
def obtener_datos_tradingview():
    datos = {}
    for par, simbolo in SIMBOLOS_TRADINGVIEW.items():
        try:
            url = f"https://api.tradingview.com/symbols/{simbolo}/quote"
            r = requests.get(url, timeout=5)
            d = r.json()
            datos[par] = {
                "c": float(d.get("last_price", 0)),
                "pc": float(d.get("prev_close", 0))
            }
        except Exception as e:
            print(f"[{datetime.now()}] Error obteniendo {par}: {e}")
            datos[par] = {"c": None, "pc": None}
    return datos

# ========== TENDENCIA ==========
def calcular_tendencia(valor, previo, umbral=0.1):
    try:
        if valor is None or previo in [None,0]:
            return "❌ Datos insuficientes"
        cambio = ((valor - previo)/previo)*100
        if cambio > umbral:
            return f"🔺 Alcista (+{cambio:.2f}%)"
        elif cambio < -umbral:
            return f"🔻 Bajista ({cambio:.2f}%)"
        else:
            return f"⏺ Neutral ({cambio:.2f}%)"
    except:
        return "❌ Error"

# ========== DETECCIÓN DIV/LIQ ==========
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
    eur_pc = datos.get("EURUSD", {}).get("pc")
    if eur_pc in [None,0] or eur is None:
        return None
    cambio = ((eur - eur_pc)/eur_pc)*100
    if abs(cambio) > 0.5:
        return f"⚠️ Posible manipulación de Londres ({cambio:.2f}%)"
    return None

# ========== NOTICIAS ==========
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
                noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}")
        except:
            pass
    return noticias

def obtener_noticias_relevantes():
    noticias = obtener_noticias_rss()
    # Se puede agregar NewsAPI si quieres
    return noticias[:5]  # Limitamos máximo 5 noticias para no romper Telegram

# ========== CONSTRUIR MENSAJE ==========
def construir_mensaje_alertas(seccion="Global"):
    datos = obtener_datos_tradingview()
    alertas = []

    # Tendencias
    tendencias = {}
    for par in ["EURUSD","GBPUSD","XAUUSD","DXY","VIX"]:
        valor = datos.get(par, {}).get("c")
        previo = datos.get(par, {}).get("pc")
        tendencias[par] = calcular_tendencia(valor, previo)

    divergencia = detectar_divergencia(datos)
    if divergencia: alertas.append(divergencia)

    manipulacion = detectar_manipulacion(datos)
    if manipulacion: alertas.append(manipulacion)

    # VIX
    vix = datos.get("VIX", {}).get("c")
    vix_texto = tendencias.get("VIX","❌ Error")

    noticias = obtener_noticias_relevantes()
    if noticias:
        alertas.append(f"*Últimas noticias ({seccion}):*\n" + "\n".join(noticias))

    # Construcción final
    mensaje = f"""
🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐
📍 Sección: {seccion}

EURUSD: {datos.get('EURUSD', {}).get('c',0):.4f} – {tendencias['EURUSD']}
GBPUSD: {datos.get('GBPUSD', {}).get('c',0):.4f} – {tendencias['GBPUSD']}
XAUUSD: {datos.get('XAUUSD', {}).get('c',0):.2f} – {tendencias['XAUUSD']}
DXY: {datos.get('DXY', {}).get('c',0):.4f} – {tendencias['DXY']}
VIX: {vix if vix else '❌'} – {vix_texto}

*Alertas:*
""" + ("\n".join(alertas) if alertas else "✅ Sin alertas relevantes")

    return mensaje

def enviar_alerta_seccion(seccion):
    mensaje = construir_mensaje_alertas(seccion)
    enviar_mensaje_telegram(mensaje)

# ========== HORARIOS PRE-MARKET & DURANTE SESIÓN ==========
SECCIONES = {
    "Tokio": {"pre_market":"00:00","inicio": "01:00","fin":"08:00"},
    "Londres": {"pre_market":"08:30","inicio":"09:00","fin":"16:00"},
    "Nueva York": {"pre_market":"13:30","inicio":"14:00","fin":"21:00"},
}

for seccion, horas in SECCIONES.items():
    # Pre-market
    schedule.every().day.at(horas["pre_market"]).do(enviar_alerta_seccion,seccion)
    # Durante sesión cada 20 minutos
    hora_inicio = int(horas["inicio"].split(":")[0])
    hora_fin = int(horas["fin"].split(":")[0])
    for h in range(hora_inicio,hora_fin+1):
        for m in [0,20,40]:
            schedule.every().day.at(f"{h:02d}:{m:02d}").do(enviar_alerta_seccion,seccion)

# ========== LOOP PRINCIPAL ==========
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")

while True:
    schedule.run_pending()
    time.sleep(1)
