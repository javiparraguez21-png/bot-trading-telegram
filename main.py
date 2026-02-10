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

RSS_FEEDS = [
    "https://www.economist.com/feeds/print-sections/77/geopolitics.xml",
    "https://elpais.com/rss/elpais/internacional.xml",
    "https://theconversation.com/us/topics/global/rss",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html"
]

SECCIONES = {
    "Tokio": {"horarios": ["02:30"]},
    "Londres": {"horarios": ["10:30"]},
    "Nueva York": {"horarios": ["14:30"]}
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

# ======= DATOS DEL MERCADO =======
def obtener_datos_macro():
    activos = {
        "EURUSD": "OANDA:EUR_USD",
        "GBPUSD": "OANDA:GBP_USD",
        "XAUUSD": "OANDA:XAU_USD",
        "DXY": "ICEUS:DXY",
        "^VIX": "CBOE:VIX"
    }
    datos = {}
    for simbolo, f in activos.items():
        url = f"https://finnhub.io/api/v1/quote?symbol={f}&token={FINNHUB_API_KEY}"
        try:
            r = requests.get(url, timeout=10)
            info = r.json()
            c = info.get("c") or 0.0
            pc = info.get("pc") or 0.0
            datos[simbolo] = {"c": c, "pc": pc}
        except Exception as e:
            print(f"[{datetime.now()}] Error obteniendo {simbolo}: {e}")
            datos[simbolo] = {"c": 0.0, "pc": 0.0}
    return datos

def calcular_tendencia(valor, previo):
    if valor is None or previo in (None, 0):
        return "❌ Datos insuficientes", 0.0, "Neutral"
    cambio = ((valor - previo)/previo)*100
    # Determinar fuerza
    if cambio > 0.5:
        return "📈 Alcista fuerte", cambio, "Alcista"
    elif cambio > 0.1:
        return "📈 Alcista", cambio, "Alcista"
    elif cambio < -0.5:
        return "📉 Bajista fuerte", cambio, "Bajista"
    elif cambio < -0.1:
        return "📉 Bajista", cambio, "Bajista"
    else:
        return "➡️ Neutral", cambio, "Neutral"

def proyeccion_premarket(valor, previo, vix):
    """Proyección pre-market según tendencia y volatilidad"""
    if valor is None or previo in (None,0):
        return "❌ Datos insuficientes"
    cambio = ((valor-previo)/previo)*100
    fuerza = "Normal"
    if vix and vix > 25:
        fuerza = "Alta volatilidad"
    if cambio > 0.3:
        return f"📈 Alcista ({fuerza})"
    elif cambio < -0.3:
        return f"📉 Bajista ({fuerza})"
    else:
        return f"➡️ Neutral ({fuerza})"

# ======= NOTICIAS =======
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
                noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
        except Exception as e:
            print(f"[{datetime.now()}] Error leyendo RSS {feed}: {e}")
    return noticias

def obtener_noticias_relevantes():
    noticias = obtener_noticias_rss()
    url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=5&apiKey={NEWS_API_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
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
            noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
    except:
        pass
    return noticias

# ======= CONSTRUIR MENSAJE =======
def construir_mensaje_alertas(seccion="General"):
    datos = obtener_datos_macro()
    lineas = []

    for par in ["EURUSD","GBPUSD","XAUUSD","DXY"]:
        c = datos[par]["c"]
        pc = datos[par]["pc"]
        tendencia, cambio, simple = calcular_tendencia(c, pc)
        premarket = proyeccion_premarket(c, pc, datos["^VIX"]["c"])
        lineas.append(f"{par}: {c:.4f} ({cambio:+.2f}%) {tendencia} | Pre-market: {premarket}")

    vix = datos["^VIX"]["c"]
    tendencia_vix, cambio_vix, _ = calcular_tendencia(vix, datos["^VIX"]["pc"])
    vix_texto = "🔴 Alta volatilidad" if vix > 25 else "🟢 Baja/Moderada volatilidad"
    lineas.append(f"VIX: {vix:.2f} ({tendencia_vix}) {vix_texto}")

    noticias = obtener_noticias_relevantes()
    alertas = [f"*Últimas noticias relevantes ({seccion}):*\n" + "\n".join(noticias[:5])] if noticias else []

    mensaje = f"""
🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐
📍 Sección: {seccion}

""" + "\n".join(lineas) + "\n\n*Alertas:*\n" + ("\n".join(alertas) if alertas else "Sin alertas importantes")

    if len(mensaje) > 3500:
        mensaje = mensaje[:3500] + "\n\n...Mensaje truncado..."
    return mensaje

def enviar_alerta_seccion(seccion="General"):
    print(f"[{datetime.now()}] Enviando alerta {seccion}...")
    mensaje = construir_mensaje_alertas(seccion)
    enviar_mensaje_telegram(mensaje)

# ======= PROGRAMAR HORARIOS =======
def programar_alertas():
    for seccion, data in SECCIONES.items():
        for hora in data["horarios"]:
            schedule.every().day.at(hora).do(enviar_alerta_seccion, seccion)
        # Cada 20 minutos durante la sesión
        schedule.every(20).minutes.do(enviar_alerta_seccion, seccion)

# ======= INICIO =======
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")
programar_alertas()

# ======= LOOP =======
while True:
    schedule.run_pending()
    time.sleep(1)
