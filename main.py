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

# ================= HISTORIAL PARA MINI-CHARTS =================
HISTORIAL = {par: [] for par in ["EURUSD","GBPUSD","XAUUSD","DXY"]}  # guardaremos los últimos 10 precios

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
    if isinstance(eur, (int,float)) and isinstance(eur_prev,(int,float)) and eur_prev != 0:
        cambio = ((eur - eur_prev)/eur_prev)*100
        if abs(cambio) > 0.5:
            return f"⚠️ *Posible manipulación Londres ({cambio:.2f}%)"
    return None

def calcular_tendencia(valor, previo, umbral=0.1):
    if valor is None or previo is None:
        return "❌ Datos insuficientes"
    cambio = ((valor - previo)/previo)*100
    if cambio > umbral:
        return f"🔺 Alcista ({cambio:.2f}%)"
    elif cambio < -umbral:
        return f"🔻 Bajista ({cambio:.2f}%)"
    else:
        return f"➖ Neutral ({cambio:.2f}%)"

# ================= MINI-GRÁFICAS =================
def actualizar_historial(datos):
    for par in HISTORIAL.keys():
        valor = datos.get(par, {}).get("c")
        if valor is not None:
            HISTORIAL[par].append(valor)
            if len(HISTORIAL[par]) > 10:
                HISTORIAL[par].pop(0)

def generar_chart(par):
    precios = HISTORIAL.get(par, [])
    if not precios:
        return "❌ Sin datos"
    min_p = min(precios)
    max_p = max(precios)
    rango = max_p - min_p if max_p != min_p else 1
    chart = ""
    for p in precios:
        altura = int((p - min_p)/rango * 5)
        chart += "⬛" * altura + "⬜" * (5 - altura) + " "
    return chart.strip()

# ================= NOTICIAS =================
def obtener_noticias_rss():
    noticias = []
    for feed in RSS_FEEDS:
        try:
            d = feedparser.parse(feed)
            for entry in d.entries[:3]:
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
        except:
            continue
    return noticias

def obtener_noticias_api():
    noticias = []
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
            noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
    except:
        pass
    return noticias

def obtener_noticias_relevantes():
    noticias = []
    noticias.extend(obtener_noticias_rss())
    noticias.extend(obtener_noticias_api())
    noticias.sort(key=lambda x: len(x), reverse=True)
    return noticias[:5]

# ================= CONSTRUIR MENSAJE =================
def construir_mensaje_alertas(seccion):
    datos = obtener_datos_macro()
    actualizar_historial(datos)
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
        alertas.append(f"*Últimas noticias relevantes:*\n" + "\n".join(noticias))

    mensaje = f"🌏 *SESIÓN {seccion.upper()} – ALERTAS MACRO*\n\n"
    for par in ["EURUSD","GBPUSD","XAUUSD","DXY"]:
        chart = generar_chart(par)
        mensaje += f"{par}: {datos.get(par)} – {tendencias[par]}\n{chart}\n\n"
    mensaje += f"📈 VIX: {vix} ({vix_texto})\n\n"
    mensaje += "*Alertas:*\n" + ("\n".join(alertas) if alertas else "✅ Sin alertas importantes")
    return mensaje

def enviar_alerta_seccion(seccion):
    mensaje = construir_mensaje_alertas(seccion)
    enviar_mensaje_telegram(mensaje)

# ================= RESUMEN SEMANAL =================
def enviar_resumen_semanal():
    datos = obtener_datos_macro()
    mensaje = "📅 *RESUMEN SEMANAL – MERCADOS*\n\n"
    for par in ["EURUSD","GBPUSD","XAUUSD","DXY"]:
        valor = datos.get(par, {}).get("c")
        previo = datos.get(par, {}).get("pc")
        tendencia = calcular_tendencia(valor, previo)
        chart = generar_chart(par)
        mensaje += f"{par}: {valor} – {tendencia}\n{chart}\n\n"
    mensaje += "📰 *Ranking Noticias Semana:*\n"
    noticias = obtener_noticias_relevantes()
    for i,n in enumerate(noticias,1):
        mensaje += f"{i}. {n}\n"
    enviar_mensaje_telegram(mensaje)

# ================= HORARIOS =================
SECCIONES = {
    "Asia": {"pre_market":"00:30", "horas": range(1,10)},
    "Londres": {"pre_market":"10:30", "horas": range(11,16)},
    "Nueva York": {"pre_market":"14:30", "horas": range(15,21)}
}

for sec, cfg in SECCIONES.items():
    schedule.every().day.at(cfg["pre_market"]).do(enviar_alerta_seccion, sec)
    for h in cfg["horas"]:
        schedule.every().day.at(f"{h}:00").do(enviar_alerta_seccion, sec)
        schedule.every().day.at(f"{h}:20").do(enviar_alerta_seccion, sec)
        schedule.every().day.at(f"{h}:40").do(enviar_alerta_seccion, sec)

# Resumen semanal viernes 18:00
schedule.every().friday.at("18:00").do(enviar_resumen_semanal)

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")
enviar_alerta_seccion("Pre-market general")

while True:
    schedule.run_pending()
    time.sleep(1)
