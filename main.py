import requests
import schedule
import time
from datetime import datetime
from deep_translator import GoogleTranslator

# =============================
# CONFIGURACIÓN
# =============================

import os

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_API = os.getenv("FINNHUB_API")
NEWS_API = os.getenv("NEWS_API")
        
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

translator = GoogleTranslator(source="en", target="es")

PALABRAS_CLAVE = [
    "fed","fomc","interest rate","inflation","cpi","ppi",
    "non farm payroll","jobs","unemployment","central bank",
    "ecb","boe","geopolitical","war","conflict","iran",
    "russia","ukraine","china","japan","sanctions",
    "trump","cnbc","gold","dollar"
]

# =============================
# FUNCIONES DATOS MERCADO
# =============================

def obtener_precio(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    r = requests.get(url).json()
    return r.get("c", None)

def clasificar_vix(vix):
    if vix is None:
        return "Sin dato"
    if vix < 15:
        return "🟢 Volatilidad Baja"
    elif vix < 25:
        return "🟡 Volatilidad Media"
    else:
        return "🔴 Volatilidad Alta"

def detectar_divergencia():
    dxy = obtener_precio("DXY")
    eurusd = obtener_precio("OANDA:EUR_USD")
    if dxy and eurusd:
        if dxy > 0 and eurusd > 0:
            if dxy > 100 and eurusd < 1.05:
                return True, f"DXY alto ({dxy}) vs EURUSD débil ({eurusd})"
    return False, "Sin divergencia clara"

# =============================
# NOTICIAS FILTRADAS
# =============================

def obtener_noticias_filtradas():
    url = (
        f"https://newsapi.org/v2/everything?"
        f"language=en&sortBy=publishedAt&pageSize=15&apiKey={NEWS_API_KEY}"
    )
    r = requests.get(url).json()
    noticias = ""

    if "articles" in r:
        for art in r["articles"]:
            title = art["title"].lower()
            if any(p in title for p in PALABRAS_CLAVE):
                titulo_es = translator.translate(art["title"])
                noticias += f"📰 {titulo_es}\n"

    if noticias == "":
        noticias = "Sin noticias macro relevantes"

    return noticias

# =============================
# MOTOR DE MERCADO
# =============================

def tipo_mercado(vix, hay_divergencia, noticias):
    if vix is None:
        return "Desconocido", 50, "Sin datos suficientes"

    if vix > 25:
        return "🔴 Mercado Altamente Volátil", 80, "Reducir riesgo y esperar confirmación"
    elif hay_divergencia:
        return "📈 Tendencia Probable", 70, "Buscar continuación a favor del USD"
    elif "fed" in noticias.lower() or "inflation" in noticias.lower():
        return "🟡 Mercado Sensible a Noticias", 65, "Operar después de noticias"
    else:
        return "🔄 Mercado en Rango", 60, "Scalping técnico"

def posible_manipulacion_londres(hora, vix, noticias):
    if vix is None:
        return False
    if "08:00" <= hora <= "09:00" and vix < 20 and "Sin noticias" in noticias:
        return True
    return False

# =============================
# MENSAJES
# =============================

def mensaje_pre_londres():
    noticias = obtener_noticias_filtradas()
    diver, texto_div = detectar_divergencia()
    vix = obtener_precio("VIX")
    estado_vix = clasificar_vix(vix)
    tipo, prob, reco = tipo_mercado(vix, diver, noticias)

    return f"""
🌍 MAPA MACRO DEL DÍA

VIX: {vix} → {estado_vix}

Tipo de mercado:
{tipo} ({prob}%)

Divergencia:
{texto_div}

Noticias:
{noticias}

Plan:
{reco}
"""

def mensaje_londres():
    noticias = obtener_noticias_filtradas()
    diver, texto_div = detectar_divergencia()
    vix = obtener_precio("VIX")
    estado_vix = clasificar_vix(vix)
    tipo, prob, reco = tipo_mercado(vix, diver, noticias)
    hora = datetime.now().strftime("%H:%M")

    manip = ""
    if posible_manipulacion_londres(hora, vix, noticias):
        manip = "Posible manipulación de Londres detectada"

    return f"""
LONDON SESSION UPDATE {hora}

VIX: {vix} → {estado_vix}

{tipo} ({prob}%)

{manip}

Divergencia:
{texto_div}

Noticias:
{noticias}

Recomendación:
{reco}
"""

def mensaje_ny():
    noticias = obtener_noticias_filtradas()
    diver, texto_div = detectar_divergencia()
    vix = obtener_precio("VIX")
    estado_vix = clasificar_vix(vix)
    tipo, prob, reco = tipo_mercado(vix, diver, noticias)
    hora = datetime.now().strftime("%H:%M")

    return f"""
NEW YORK SESSION {hora}

VIX: {vix} → {estado_vix}

{tipo} ({prob}%)

Divergencia:
{texto_div}

Noticias:
{noticias}

Recomendación:
{reco}
"""

# =============================
# TELEGRAM
# =============================

def enviar(msg):
    requests.post(URL_TELEGRAM, data={
        "chat_id": CHAT_ID,
        "text": msg
    })

# =============================
# HORARIOS (Chile)
# =============================

schedule.every().day.at("07:50").do(lambda: enviar(mensaje_pre_londres()))

def londres_loop():
    hora = datetime.now().strftime("%H:%M")
    if "08:00" <= hora <= "11:00":
        enviar(mensaje_londres())

schedule.every(30).minutes.do(londres_loop)

def ny_loop():
    hora = datetime.now().strftime("%H:%M")
    if "09:30" <= hora <= "16:00":
        enviar(mensaje_ny())

schedule.every(30).minutes.do(ny_loop)

# =============================
# LOOP PRINCIPAL
# =============================

print("BOT MACRO INSTITUCIONAL ACTIVO")

while True:
    schedule.run_pending()
    time.sleep(10)
