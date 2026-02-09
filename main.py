import os
import requests
import schedule
import time
from datetime import datetime
from deep_translator import GoogleTranslator

# ================= VARIABLES DE ENTORNO =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# ======= MINI LOG DE VERIFICACIÓN =======
print("===== VERIFICANDO VARIABLES DE ENTORNO =====")
print(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN}")
print(f"CHAT_ID: {CHAT_ID}")
print("===========================================")

# ================= FUNCIONES =================
def enviar_mensaje_telegram(texto):
    """Envía mensaje a Telegram con Markdown, emojis y colores"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Faltan TELEGRAM_TOKEN o CHAT_ID")
        return
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

# ================= ALERTA SIMULADA =================
def enviar_mensaje_prueba():
    mensaje_prueba = """
📊 *MENSAJE DE PRUEBA – BOT ULTRA PRO*

EURUSD: 1.1234
GBPUSD: 1.2345
XAUUSD: 1900
DXY: 102.5
VIX: 18 🟢 Baja/Moderada volatilidad

*Alertas simuladas:*
🔺 Divergencia alcista EURUSD vs DXY
⚠️ Posible manipulación de Londres
📰 Últimas noticias relevantes:
• 📰 *Prueba de noticia 1* Descripción breve de prueba 🔗 https://example.com
• 📰 *Prueba de noticia 2* Descripción breve de prueba 🔗 https://example.com
"""
    enviar_mensaje_telegram(mensaje_prueba)

# ================= FUNCIONES DE ALERTAS REALES =================
def obtener_datos_macro():
    tickers = ["EURUSD", "GBPUSD", "XAUUSD", "DXY", "^VIX"]
    datos = {}
    for t in tickers:
        url = f"https://finnhub.io/api/v1/quote?symbol={t}&token={FINNHUB_API_KEY}"
        try:
            r = requests.get(url)
            datos[t] = r.json()
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
            return "🔺 Divergencia alcista EURUSD vs DXY"
        elif (eur < eur_pc) and (dxy > dxy_pc):
            return "🔻 Divergencia bajista EURUSD vs DXY"
    return None

def detectar_manipulacion(datos):
    eur = datos.get("EURUSD", {}).get("c")
    eur_prev = datos.get("EURUSD", {}).get("pc")
    if all(isinstance(x,(int,float)) for x in [eur, eur_prev]):
        cambio = ((eur - eur_prev)/eur_prev)*100
        if abs(cambio) > 0.5:
            return f"⚠️ Posible manipulación de Londres ({cambio:.2f}%)"
    return None

def obtener_noticias_relevantes():
    noticias = []
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
            keywords = ["FED","BCE","Trump","geopolítica","inflación","banco central","tensiones"]
            if any(k.lower() in (titulo_es+descripcion_es).lower() for k in keywords):
                noticias.append(f"📰 *{titulo_es}*\n{descripcion_es}\n🔗 {enlace}\n")
    except:
        pass
    return noticias

def construir_mensaje_alertas():
    datos = obtener_datos_macro()
    alertas = []
    divergencia = detectar_divergencia(datos)
    if divergencia: alertas.append(divergencia)
    manipulacion = detectar_manipulacion(datos)
    if manipulacion: alertas.append(manipulacion)
    
    vix = datos.get("^VIX", {}).get("c")
    vix_texto = ""
    if isinstance(vix, (int,float)):
        vix_texto = "🔴 Alta volatilidad" if vix > 25 else "🟢 Baja/Moderada volatilidad"
        if vix > 25: alertas.append("⚡ VIX alto – cuidado con volatilidad")
    else:
        vix_texto = "❌ Error al obtener VIX"

    noticias = obtener_noticias_relevantes()
    if noticias:
        alertas.append(f"*Últimas noticias relevantes:*\n" + "\n".join(noticias))
    
    if not alertas: return None
    
    mensaje = f"""
📊 *MAESTRO ANALISTA IA – ALERTAS MACRO*

EURUSD: {datos.get('EURUSD')}
GBPUSD: {datos.get('GBPUSD')}
XAUUSD: {datos.get('XAUUSD')}
DXY: {datos.get('DXY')}
VIX: {vix} ({vix_texto})

*Alertas:*
""" + "\n".join(alertas)
    return mensaje

def enviar_si_hay_alerta():
    mensaje = construir_mensaje_alertas()
    if mensaje:
        enviar_mensaje_telegram(mensaje)
    else:
        print(f"[{datetime.now()}] Sin alertas relevantes, no se envió mensaje")

# ================= HORARIOS =================
schedule.every().day.at("10:30").do(enviar_si_hay_alerta)
for hour in range(11,20):
    schedule.every().day.at(f"{hour}:00").do(enviar_si_hay_alerta)
    schedule.every().day.at(f"{hour}:30").do(enviar_si_hay_alerta)
for hour in range(14,21):
    schedule.every().day.at(f"{hour}:00").do(enviar_si_hay_alerta)
    schedule.every().day.at(f"{hour}:30").do(enviar_si_hay_alerta)

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")

# ⚡ MENSAJE DE PRUEBA INMEDIATO
enviar_mensaje_prueba()

# Envío inicial de alertas reales
enviar_si_hay_alerta()

while True:
    schedule.run_pending()
    time.sleep(1)

