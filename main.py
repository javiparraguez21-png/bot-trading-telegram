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

# ================= FUNCIONES =================
def enviar_mensaje_telegram(texto):
    try:
        if len(texto) > 3900:
            texto = texto[:3900] + "\n...📌 Mensaje truncado por límite de Telegram"
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
    tickers = ["EURUSD","GBPUSD","XAUUSD","DXY","^VIX"]
    datos = {}
    for t in tickers:
        url = f"https://finnhub.io/api/v1/quote?symbol={t}&token={FINNHUB_API_KEY}"
        try:
            r = requests.get(url)
            datos[t] = r.json()
            if "c" not in datos[t] or "pc" not in datos[t]:
                datos[t] = {"c": None, "pc": None, "h": None, "l": None, "o": None}
        except:
            datos[t] = {"c": None, "pc": None, "h": None, "l": None, "o": None}
    return datos

# ================= DETECCIÓN =================
def detectar_divergencia(datos):
    eur = datos.get("EURUSD", {}).get("c")
    dxy = datos.get("DXY", {}).get("c")
    eur_pc = datos.get("EURUSD", {}).get("pc")
    dxy_pc = datos.get("DXY", {}).get("pc")
    if all(isinstance(x,(int,float)) for x in [eur,dxy,eur_pc,dxy_pc]):
        if (eur > eur_pc) and (dxy < dxy_pc):
            return "🔺 *Divergencia alcista EURUSD vs DXY*"
        elif (eur < eur_pc) and (dxy > dxy_pc):
            return "🔻 *Divergencia bajista EURUSD vs DXY*"
    return None

def detectar_manipulacion(datos):
    eur_data = datos.get("EURUSD", {})
    eur = eur_data.get("c")
    eur_prev = eur_data.get("pc")
    if eur is None or eur_prev in (None, 0):
        return None
    cambio = ((eur - eur_prev)/eur_prev)*100
    if abs(cambio) > 0.5:
        return f"⚠️ *Posible manipulación de Londres ({cambio:.2f}%) *"
    return None

def calcular_tendencia(valor, previo, umbral=0.1):
    try:
        if valor is None or previo in (None,0):
            return "⚪ Datos insuficientes"
        cambio = ((valor - previo)/previo)*100
        if cambio > umbral:
            return "📈 🟢 Alcista"
        elif cambio < -umbral:
            return "📉 🔴 Bajista"
        else:
            return "➡️ 🟡 Neutral"
    except:
        return "⚪ Error"

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
                noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
        except Exception as e:
            print(f"[{datetime.now()}] Error leyendo RSS {feed}: {e}")
    return noticias

def obtener_noticias_relevantes():
    noticias = []
    noticias.extend(obtener_noticias_rss())
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
            noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
    except:
        pass
    return noticias

# ================= FORMATEO =================
def formatear_activo(nombre, datos, tendencia):
    if not datos or datos.get("c") is None:
        return f"{nombre} – ⚪ Datos insuficientes – Tendencia: {tendencia}"
    precio = datos.get("c", 0)
    maximo = datos.get("h", 0)
    minimo = datos.get("l", 0)
    apertura = datos.get("o", 0)
    return f"{nombre} – 💰 Precio: {precio} | 📈 Máx: {maximo} | 📉 Mín: {minimo} | 🏁 Apertura: {apertura} | Tendencia: {tendencia}"

# ================= CONSTRUIR MENSAJE =================
def construir_mensaje_alertas(seccion="Global"):
    datos = obtener_datos_macro()
    alertas = []

    # Tendencias
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
        vix_texto = "⚪ Error al obtener VIX"

    noticias = obtener_noticias_relevantes()
    if noticias:
        alertas.append(f"*Últimas noticias relevantes ({seccion}):*\n" + "\n".join(noticias))

    if not alertas: return None

    mensaje = f"""
🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐
📍 Sección: {seccion}

{formatear_activo('EURUSD', datos.get('EURUSD'), tendencias['EURUSD'])}
{formatear_activo('GBPUSD', datos.get('GBPUSD'), tendencias['GBPUSD'])}
{formatear_activo('XAUUSD', datos.get('XAUUSD'), tendencias['XAUUSD'])}
{formatear_activo('DXY', datos.get('DXY'), tendencias['DXY'])}
VIX – {vix} ({vix_texto})

*Alertas:*
""" + "\n".join(alertas)

    return mensaje

def enviar_alerta_seccion(seccion):
    mensaje = construir_mensaje_alertas(seccion)
    if mensaje:
        enviar_mensaje_telegram(mensaje)
    else:
        print(f"[{datetime.now()}] Sin alertas relevantes para {seccion}")

# ================= HORARIOS =================
SECCIONES = {
    "Asia": {"pre_market": "01:30", "sesion": range(2,10)},
    "Londres": {"pre_market": "08:30", "sesion": range(9,17)},
    "Nueva York": {"pre_market": "13:30", "sesion": range(14,22)}
}

agenda = schedule

for seccion, horas in SECCIONES.items():
    agenda.every().day.at(horas["pre_market"]).do(enviar_alerta_seccion, seccion)
    for h in horas["sesion"]:
        agenda.every().hour.at(":00").do(enviar_alerta_seccion, seccion)
        agenda.every().hour.at(":20").do(enviar_alerta_seccion, seccion)
        agenda.every().hour.at(":40").do(enviar_alerta_seccion, seccion)

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")
enviar_alerta_seccion("Global")

while True:
    agenda.run_pending()
    time.sleep(1)
