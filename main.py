import os
import requests
import schedule
import time
from datetime import datetime
from deep_translator import GoogleTranslator

# ================= VARIABLES =================
# Telegram
TELEGRAM_TOKEN = "8142044386:AAFInOnDRJgUiWkRuDPeGnWhPJcvsF29IOc"
CHAT_ID = "5933788259"
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# APIs
FINNHUB_API_KEY = "d632dchr01qnpqnvhurgd632dchr01qnpqnvhus0"
NEWS_API_KEY = "ea6acd4f9dca4de99fab812dc069a67b"

# ================= CONFIG =================
SECCIONES = {
    "Asia": {"inicio": "19:00", "fin": "04:00"},      # horario Chile
    "Londres": {"inicio": "03:50", "fin": "13:00"},
    "Nueva York": {"inicio": "09:20", "fin": "16:00"}
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

# ================= DATOS DEL MERCADO =================
def obtener_datos_macro():
    tickers = ["EURUSD", "GBPUSD", "XAUUSD", "DXY", "^VIX"]
    datos = {}
    for t in tickers:
        url = f"https://finnhub.io/api/v1/quote?symbol={t}&token={FINNHUB_API_KEY}"
        try:
            r = requests.get(url, timeout=5)
            datos[t] = r.json()
            # Aseguramos que siempre existan c y pc
            if "c" not in datos[t] or "pc" not in datos[t]:
                datos[t] = {"c": None, "pc": None}
        except Exception as e:
            print(f"[{datetime.now()}] Error obteniendo {t}: {e}")
            datos[t] = {"c": None, "pc": None}
    return datos

# ================= TENDENCIAS =================
def calcular_tendencia(valor, previo, umbral=0.1):
    try:
        if valor is None or previo is None or previo == 0:
            return "❌ Datos insuficientes", 0.0
        cambio = ((valor - previo)/previo)*100
        if cambio > umbral:
            return "📈 Alcista", cambio
        elif cambio < -umbral:
            return "📉 Bajista", cambio
        else:
            return "➡️ Neutral", cambio
    except:
        return "❌ Error", 0.0

# ================= DETECCIÓN =================
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
        return f"⚠️ Posible manipulación de Londres ({cambio:.2f}%)"
    return None

# ================= NOTICIAS =================
def obtener_noticias_relevantes():
    noticias = []
    url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=5&apiKey={NEWS_API_KEY}"
    try:
        r = requests.get(url, timeout=5).json()
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

# ================= MENSAJE =================
def construir_mensaje_alertas(seccion):
    datos = obtener_datos_macro()
    alertas = []

    # Tendencias
    tendencias = {}
    for par in ["EURUSD","GBPUSD","XAUUSD","DXY"]:
        valor = datos.get(par, {}).get("c")
        previo = datos.get(par, {}).get("pc")
        tendencias[par], cambio = calcular_tendencia(valor, previo)
        if valor is not None:
            alertas.append(f"{par}: {valor:.4f} ({cambio:+.2f}%) – {tendencias[par]}")
        else:
            alertas.append(f"{par}: ❌ Datos insuficientes – {tendencias[par]}")

    # VIX
    vix = datos.get("^VIX", {}).get("c")
    if isinstance(vix,(int,float)):
        vix_texto = "🔴 Alta volatilidad" if vix > 25 else "🟢 Baja/Moderada"
        alertas.append(f"VIX: {vix} ({vix_texto})")
    else:
        alertas.append("VIX: ❌ Datos insuficientes")

    # Alertas de divergencia y manipulación
    div = detectar_divergencia(datos)
    if div: alertas.append(div)
    manip = detectar_manipulacion(datos)
    if manip: alertas.append(manip)

    # Noticias
    noticias = obtener_noticias_relevantes()
    if noticias:
        alertas.append(f"*Últimas noticias ({seccion}):*\n" + "\n".join(noticias))

    mensaje = f"🌐 *MAESTRO ANALISTA IA – ALERTAS MACRO* 🌐\n📍 Sección: {seccion}\n\n" + "\n".join(alertas)
    return mensaje

# ================= ENVÍO =================
def enviar_alerta_seccion(seccion):
    print(f"[{datetime.now()}] Enviando alerta de {seccion}...")
    mensaje = construir_mensaje_alertas(seccion)
    try:
        enviar_mensaje_telegram(mensaje)
    except Exception as e:
        print(f"[{datetime.now()}] Error al enviar alerta: {e}")

# ================= HORARIOS =================
# Cada 20 minutos dentro de la sesión
def programar_alertas():
    for seccion, horario in SECCIONES.items():
        h_inicio, m_inicio = map(int, horario["inicio"].split(":"))
        h_fin, m_fin = map(int, horario["fin"].split(":"))

        # Pre-market
        schedule.every().day.at(horario["inicio"]).do(enviar_alerta_seccion, seccion)

        # Cada 20 min durante la sesión
        current_hour = h_inicio
        while current_hour != (h_fin % 24):
            for minute in [0,20,40]:
                hora = f"{current_hour:02d}:{minute:02d}"
                try:
                    schedule.every().day.at(hora).do(enviar_alerta_seccion, seccion)
                except:
                    pass
            current_hour = (current_hour + 1) % 24

# ================= LOOP PRINCIPAL =================
print("🤖 BOT MACRO ULTRA PRO CON ALERTAS 24/7")

# Mensaje de inicio
enviar_mensaje_telegram("✅ El bot se ha iniciado correctamente y Telegram funciona.")

# Programar alertas
programar_alertas()

while True:
    schedule.run_pending()
    time.sleep(1)
