import requests
import schedule
import time
from datetime import datetime
from deep_translator import GoogleTranslator
from tradingview_ta import TA_Handler, Interval, Exchange
import feedparser

# ================= VARIABLES =================
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

RSS_FEEDS = [
    "https://www.economist.com/feeds/print-sections/77/geopolitics.xml",
    "https://elpais.com/rss/elpais/internacional.xml",
    "https://theconversation.com/us/topics/global/rss",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html"
]

ACTIVOS = {
    "EURUSD": {"exchange":"FX", "symbol":"EURUSD"},
    "GBPUSD": {"exchange":"FX", "symbol":"GBPUSD"},
    "XAUUSD": {"exchange":"COMEX", "symbol":"XAUUSD"},
    "DXY": {"exchange":"ICEUS", "symbol":"DXY"},
    "VIX": {"exchange":"CBOE", "symbol":"VIX"}
}

SECCIONES = {
    "Asia": {"inicio":"21:00","fin":"05:00"},
    "Londres": {"inicio":"06:00","fin":"15:00"},
    "Nueva York": {"inicio":"10:00","fin":"19:00"}
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

def obtener_datos_activos():
    datos = {}
    for nombre, info in ACTIVOS.items():
        try:
            handler = TA_Handler(
                symbol=info["symbol"],
                screener="forex" if info["exchange"]=="FX" else "crypto",
                exchange=info["exchange"],
                interval=Interval.INTERVAL_1_MINUTE
            )
            res = handler.get_analysis()
            precio = res.indicators.get("close")
            fuerza = res.moving_averages.get("COMPUTE")
            tendencia = res.summary["RECOMMENDATION"]
            datos[nombre] = {
                "precio": precio,
                "fuerza": fuerza,
                "tendencia": tendencia
            }
        except Exception as e:
            print(f"[{datetime.now()}] Error obteniendo {nombre}: {e}")
            datos[nombre] = {
                "precio": None,
                "fuerza": None,
                "tendencia": "❌ Datos insuficientes"
            }
    return datos

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

def construir_mensaje_alerta(seccion):
    datos = obtener_datos_activos()
    noticias = obtener_noticias_rss()
    
    mensaje = f"🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐\n📍 Sección: {seccion}\n\n"
    
    for activo, info in datos.items():
        precio = info["precio"] if info["precio"] is not None else 0.0
        tendencia = info["tendencia"]
        mensaje += f"{activo}: {precio} ({tendencia})\n"
    
    if noticias:
        mensaje += "\n*Últimas noticias relevantes:*\n" + "\n".join(noticias[:5])
    
    return mensaje

def enviar_alerta_seccion(seccion):
    print(f"[{datetime.now()}] Enviando alerta sección {seccion}...")
    mensaje = construir_mensaje_alerta(seccion)
    enviar_mensaje_telegram(mensaje)

# ================= HORARIOS =================
def programar_alertas():
    for seccion, horas in SECCIONES.items():
        inicio_hora, _ = horas["inicio"].split(":")
        for h in range(24):
            # Cada 20 minutos dentro del horario
            for minuto in [0,20,40]:
                hora_str = f"{h:02d}:{minuto:02d}"
                schedule.every().day.at(hora_str).do(enviar_alerta_seccion, seccion=seccion)

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")

programar_alertas()

while True:
    schedule.run_pending()
    time.sleep(1)
