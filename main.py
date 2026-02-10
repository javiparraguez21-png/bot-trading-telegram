import schedule
import time
from datetime import datetime
from tradingview_ta import TA_Handler, Interval, Exchange
import requests
from deep_translator import GoogleTranslator
import feedparser

# ================= VARIABLES =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

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

# ================= MERCADO TRADINGVIEW =================
PAIRS = {
    "EURUSD": {"symbol": "EURUSD", "exchange": "FX_IDC"},
    "GBPUSD": {"symbol": "GBPUSD", "exchange": "FX_IDC"},
    "XAUUSD": {"symbol": "XAUUSD", "exchange": "OANDA"},
    "DXY": {"symbol": "DXY", "exchange": "ICEUS"},
    "VIX": {"symbol": "VIX", "exchange": "CBOE"}
}

def obtener_datos_tradingview():
    datos = {}
    for par, info in PAIRS.items():
        try:
            handler = TA_Handler(
                symbol=info["symbol"],
                screener="forex" if par in ["EURUSD","GBPUSD"] else "commodities" if par=="XAUUSD" else "indices",
                exchange=info["exchange"],
                interval=Interval.INTERVAL_1_MINUTE
            )
            analysis = handler.get_analysis()
            datos[par] = {
                "precio": analysis.indicators["close"],
                "tendencia": analysis.summary["RECOMMENDATION"],  # BUY, STRONG_BUY, NEUTRAL, SELL, STRONG_SELL
                "fuerza": analysis.indicators.get("RSI", None)  # RSI como fuerza relativa
            }
        except Exception as e:
            print(f"[{datetime.now()}] Error obteniendo {par}: {e}")
            datos[par] = {"precio": None, "tendencia": "❌ Datos insuficientes", "fuerza": None}
    return datos

# ================= NOTICIAS =================
RSS_FEEDS = [
    "https://www.economist.com/feeds/print-sections/77/geopolitics.xml",
    "https://elpais.com/rss/elpais/internacional.xml",
    "https://theconversation.com/us/topics/global/rss",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html"
]

def obtener_noticias():
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
                noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}")
        except:
            continue
    return noticias

# ================= MENSAJE =================
def construir_mensaje_alertas(seccion="General"):
    datos = obtener_datos_tradingview()
    noticias = obtener_noticias()
    
    mensaje = f"🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐\n📍 Sección: {seccion}\n\n"
    for par, info in datos.items():
        precio = info["precio"]
        tendencia = info["tendencia"]
        fuerza = info["fuerza"]
        if precio is None:
            precio_texto = "❌ Datos insuficientes"
        else:
            precio_texto = f"{precio:.4f}" if par not in ["XAUUSD"] else f"{precio:.2f}"
        fuerza_texto = f" (RSI: {fuerza})" if fuerza else ""
        mensaje += f"{par}: {precio_texto} – Tendencia: {tendencia}{fuerza_texto}\n"
    
    if noticias:
        mensaje += "\n*Últimas noticias relevantes:*\n" + "\n\n".join(noticias)
    
    return mensaje

def enviar_alerta_seccion(seccion):
    mensaje = construir_mensaje_alertas(seccion)
    enviar_mensaje_telegram(mensaje)
    print(f"[{datetime.now()}] Alerta enviada para {seccion}")

# ================= HORARIOS =================
SECCIONES = {
    "Asia": {"pre_market": "21:30", "interval_minutes": 20},
    "Londres": {"pre_market": "07:30", "interval_minutes": 20},
    "Nueva York": {"pre_market": "09:30", "interval_minutes": 20}
}

for seccion, info in SECCIONES.items():
    # Pre-market
    schedule.every().day.at(info["pre_market"]).do(enviar_alerta_seccion, seccion)
    # Durante mercado cada 20 minutos
    for h in range(24):
        for m in range(0, 60, info["interval_minutes"]):
            hora_formato = f"{h:02d}:{m:02d}"
            schedule.every().day.at(hora_formato).do(enviar_alerta_seccion, seccion)

# ================= LOOP =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")

while True:
    schedule.run_pending()
    time.sleep(1)
