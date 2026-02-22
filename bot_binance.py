# 🤖 BOT BINANCE FUTURES - GEMINI 2.0 FLASH
# Trading 24/7 de Criptomonedas con IA
# V5.3 - Multi-Timeframe + Prompt Enriquecido + SQLite + Métricas de Riesgo
# ═══════════════════════════════════════════════════════════════════════════════

from binance.client import Client
from binance.enums import *
import time, os, http.server, socketserver, threading, requests, json, sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai
from zoneinfo import ZoneInfo
from persistence import (
    inicializar_db, registrar_trade_abierto, registrar_trade_cerrado,
    registrar_decision, registrar_balance_diario, calcular_metricas_riesgo,
    obtener_datos_kelly, generar_resumen_metricas
)
from indicators import (
    calcular_rsi, calcular_ema, calcular_macd, calcular_bollinger,
    calcular_atr, calcular_volumen_relativo, detectar_soportes_resistencias,
    obtener_tendencia_ema, analizar_indicadores_completo
)

load_dotenv()
sys.stdout.reconfigure(line_buffering=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN GLOBAL - TRADING ACTIVO CON TRAILING SL + FUNDING PROTECTION
# ═══════════════════════════════════════════════════════════════════════════════
USAR_TESTNET = os.getenv("BINANCE_TESTNET", "True").lower() in ("true", "1", "yes")
CONFIANZA_MINIMA = 0.70   # 70% - V3.7: Aumentado para mayor selectividad
ESCUDO_TRABAJO = 0.80     # 80% del balance disponible para trading
ESCUDO_SEGURO = 0.20      # 20% protegido
TIEMPO_POR_ACTIVO = 10    # Segundos entre análisis de cada activo
VELAS_CANTIDAD = 200      # Cantidad de velas a obtener
APALANCAMIENTO = 3        # Apalancamiento conservador x3
TOP_ACTIVOS = 15          # Activos a analizar por volumen
MAX_POSICIONES = 3        # Máximo 3 posiciones simultáneas (V3.4: reducido para menor riesgo)

# ═══════════════════════════════════════════════════════════════════════════════
# TRAILING STOP LOSS CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
TRAILING_SL_PERCENT = 0.015  # 1.5% - distancia del trailing
MONITOREO_INTERVALO = int(os.getenv("MONITOREO_INTERVALO", "30"))  # 30s default
LOG_FRECUENCIA_MONITOREO = 5 # Mostrar log de monitoreo cada 5 ciclos (5 min)

# Scheduler de tareas para controlar carga de CPU/API
INTERVALO_GUARDIAN = 30
INTERVALO_VERIFICAR_SL = 120
INTERVALO_TRAILING = 30
INTERVALO_TRADES_CERRADOS = 120
INTERVALO_RESUMEN_POSICIONES = 300

# ═══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS SEMANALES (V3.0) - Resumen cada viernes a las 18:00
# ═══════════════════════════════════════════════════════════════════════════════
# Balance inicial del proyecto (04/01/2026) - usado para calcular ROI total
BALANCE_INICIAL_PROYECTO = 4524.29  # V3.7: Nuevo inicio desde balance actual (09/02/2026)

# Diccionario para almacenar estadísticas semanales
# - balance_inicio_semana: balance al inicio de la semana actual
# - ganados/perdidos: contadores de trades positivos/negativos
# - monto_ganado/monto_perdido: suma de ganancias/pérdidas en USD
# - cierres_guardian: trades cerrados por el sistema guardián de emergencia
# - ultimo_resumen: fecha/hora del último resumen enviado para evitar duplicados
stats_semanales = {
    "balance_inicio_semana": 0,      # Balance al iniciar la semana
    "ganados": 0,                    # Contador de trades ganados
    "perdidos": 0,                   # Contador de trades perdidos
    "monto_ganado": 0,               # Total USD ganado esta semana
    "monto_perdido": 0,              # Total USD perdido esta semana
    "cierres_guardian": 0,           # Trades cerrados por guardian de emergencia
    "ultimo_resumen": None           # Timestamp del último resumen enviado
}

# ═══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE RIESGO AVANZADA V3.0
# ═══════════════════════════════════════════════════════════════════════════════

# --- DRAWDOWN MÁXIMO DIARIO ---
# Si las pérdidas del día superan este %, el bot pausa nuevos trades hasta mañana
# Esto protege el capital en días malos y evita "tilt"
# Ejemplo: Con -3%, si pierdes $189 de $6,307 en un día → pausa
DRAWDOWN_MAXIMO_DIARIO = 0.05       # -5% máximo pérdida diaria (V3.7: reducido para protección)
DRAWDOWN_ACTIVO = True              # Activar protección de drawdown

# --- ATR PARA STOP LOSS DINÁMICO ---
# El ATR mide la volatilidad real del mercado
# SL basado en ATR se adapta a la volatilidad actual del activo
# Multiplicadores recomendados:
#   - 1.0x ATR: Agresivo (stop tight, más stops pero menos pérdida por stop)
#   - 1.5x ATR: Balanceado (recomendado)
#   - 2.0x ATR: Conservador (stop amplio, menos stops pero más pérdida por stop)
ATR_SL_ACTIVO = False               # V5.0: DESACTIVADO - ATR SL causaba inconsistencia, volver a SL fijo
ATR_SL_MULTIPLICADOR = 2.0          # SL = Precio - (2.0 * ATR) - No usado si ATR_SL_ACTIVO=False
ATR_SL_MINIMO_PERCENT = 0.015       # No usado si ATR_SL_ACTIVO=False

# --- KELLY CRITERION PARA POSITION SIZING ---
# Fórmula de Kelly: f* = (p * b - q) / b
#   p = probabilidad de ganar (win-rate)
#   q = probabilidad de perder (1 - p)
#   b = ratio ganancia/pérdida promedio
# El resultado es el % óptimo del capital a arriesgar
# Usamos "medio Kelly" (50% del resultado) para ser más conservadores
KELLY_ACTIVO = False                # V5.0: DESACTIVADO - Kelly con historial negativo causa espiral descendente
KELLY_FRACCION = 0.5                # Usar 50% del Kelly (más conservador)
KELLY_MINIMO = 0.02                 # Mínimo 2% del capital
KELLY_MAXIMO = 0.10                 # Máximo 10% del capital

# Estadísticas diarias para drawdown y Kelly
# Se resetean cada día a las 00:00
stats_diarias = {
    "balance_inicio_dia": 0,        # Balance al inicio del día
    "trades_ganados": 0,            # Trades ganados hoy (para Kelly)
    "trades_perdidos": 0,           # Trades perdidos hoy (para Kelly)
    "monto_ganado": 0,              # Suma de ganancias hoy
    "monto_perdido": 0,             # Suma de pérdidas hoy
    "drawdown_pausado": False,      # True si bot pausado por drawdown
    "fecha_actual": None            # Para detectar cambio de día
}

# ═══════════════════════════════════════════════════════════════════════════════
# PROTECCIÓN CONTRA FUNDING FEES (V2.5)
# ═══════════════════════════════════════════════════════════════════════════════
FUNDING_PROTECTION = True       # Activar protección de funding
MAX_DIAS_POSICION = 5           # Cerrar posiciones después de 5 días
TP_DINAMICO_DIAS = 3            # Después de 3 días, ajustar TP
TP_DINAMICO_PERCENT = 0.02      # TP reducido a 2% después de X días

# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA GUARDIÁN V3.8 - PROTECCIÓN OPTIMIZADA
# ═══════════════════════════════════════════════════════════════════════════════
GUARDIAN_ACTIVO = True          # Activar sistema guardián
MAX_PERDIDA_PERMITIDA = -0.07   # V3.8: -7% cierre obligatorio (antes -10%)
LOG_DETALLADO = os.getenv("LOG_DETALLADO", "true").lower() in ("true", "1", "yes")

# ═══════════════════════════════════════════════════════════════════════════════
# TEMPORALIDADES DINÁMICAS
# ═══════════════════════════════════════════════════════════════════════════════
TEMPORALIDADES = ['1h', '4h']  # V5.0: Solo 1h y 4h (15m/30m demasiado ruido para x3)

# V5.0: TP/SL estilo enero - SL amplio da espacio, TP alcanzable
TP_SL_CONFIG = {
    "1h":  {"tp": 0.035, "sl": 0.025},    # +3.5%, -2.5% (R:R 1.4:1) - SL amplio como enero
    "4h":  {"tp": 0.06, "sl": 0.035},     # +6%, -3.5% (R:R 1.71:1)
}

# ═══════════════════════════════════════════════════════════════════════════════
# FEAR & GREED INDEX
# ═══════════════════════════════════════════════════════════════════════════════
FEAR_GREED_API = "https://api.alternative.me/fng/"

# ═══════════════════════════════════════════════════════════════════════════════
# PROTECCIONES V5.1 - REDUCCIÓN DE EVENTOS IMPREDECIBLES
# ═══════════════════════════════════════════════════════════════════════════════
NOTICIAS_PROTECCION_ACTIVA = True
CRYPTO_PANIC_URL = "https://cryptopanic.com/api/v1/posts/"
CRYPTO_PANIC_KEY = os.getenv("CRYPTOPANIC_API_KEY")
PAUSA_NOTICIAS_MINUTOS = 120
NOTICIAS_CHECK_INTERVALO = 300  # 5 min
NOTICIAS_KEYWORDS_ALTO_IMPACTO = (
    "sec", "hack", "exploit", "ban", "lawsuit", "fed", "fomc", "cpi",
    "liquidation", "liquidations", "bankruptcy", "crash", "etf denied",
    "exchange halted", "outage", "default", "war", "sanction"
)

HORARIO_PROTEGIDO_ACTIVO = True
try:
    TZ_MERCADO = ZoneInfo("America/New_York")
except Exception:
    TZ_MERCADO = None

# V5.3: Zona horaria local (Guatemala = UTC-6)
try:
    TZ_LOCAL = ZoneInfo("America/Guatemala")
except Exception:
    TZ_LOCAL = None

def hora_local():
    """Retorna datetime actual en hora Guatemala (UTC-6).
    En Koyeb el servidor está en UTC, sin esto todo está +6h descuadrado."""
    if TZ_LOCAL:
        return datetime.now(TZ_LOCAL)
    return datetime.now()  # Fallback a hora del servidor
VENTANA_USA_INICIO_MIN = 8 * 60 + 30   # 08:30 ET
VENTANA_USA_FIN_MIN = 9 * 60 + 30      # 09:30 ET
VENTANA_FED_DIA = 2                    # Miércoles
VENTANA_FED_INICIO_MIN = 13 * 60 + 45  # 13:45 ET
VENTANA_FED_FIN_MIN = 14 * 60 + 30     # 14:30 ET

pausa_noticias_hasta = None
ultimo_check_noticias = 0.0

# Controles de rendimiento/estabilidad
task_last_run = {}
log_throttle = {}
_positions_cache = {"ts": 0.0, "data": None}
_exchange_info_cache = {"ts": 0.0, "data": None}
_sl_retry_cooldown_until = {}  # {symbol: timestamp}
SL_REINTENTO_COOLDOWN = 300  # 5 minutos

# ═══════════════════════════════════════════════════════════════════════════════
# SERVIDOR DE SALUD (KOYEB)
# ═══════════════════════════════════════════════════════════════════════════════
def servidor_salud():
    PORT = int(os.getenv("PORT", 8000))
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"BINANCE BOT V5.0 - RESET INTELIGENTE + ANTI-TENDENCIA")
        def log_message(self, format, *args):
            pass
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            httpd.serve_forever()
    except: pass
threading.Thread(target=servidor_salud, daemon=True).start()

# ═══════════════════════════════════════════════════════════════════════════════
# COMUNICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def log(mensaje):
    print(f"[BINANCE] {mensaje}", flush=True)


def should_run_task(task_name, interval_seconds):
    """Ejecuta una tarea solo si ya pasó su intervalo."""
    now = time.time()
    last = task_last_run.get(task_name, 0.0)
    if now - last >= interval_seconds:
        task_last_run[task_name] = now
        return True
    return False


def log_throttled(key, mensaje, cooldown=180):
    """Evita spam de logs repetidos."""
    now = time.time()
    last = log_throttle.get(key, 0.0)
    if now - last >= cooldown:
        log_throttle[key] = now
        log(mensaje)


def obtener_posiciones(client, ttl=2, force=False):
    """Cachea posiciones por segundos para reducir llamadas API redundantes."""
    now = time.time()
    if not force and _positions_cache["data"] is not None and now - _positions_cache["ts"] < ttl:
        return _positions_cache["data"]
    posiciones = client.futures_position_information()
    _positions_cache["ts"] = now
    _positions_cache["data"] = posiciones
    return posiciones


def obtener_exchange_info(client, ttl=1800, force=False):
    """Cachea exchange_info (pesado y casi estático)."""
    now = time.time()
    if not force and _exchange_info_cache["data"] is not None and now - _exchange_info_cache["ts"] < ttl:
        return _exchange_info_cache["data"]
    info = client.futures_exchange_info()
    _exchange_info_cache["ts"] = now
    _exchange_info_cache["data"] = info
    return info

# ═══════════════════════════════════════════════════════════════════════════════
# FEAR & GREED INDEX
# ═══════════════════════════════════════════════════════════════════════════════
def obtener_fear_greed():
    """Obtiene el índice Fear & Greed actual (0-100)"""
    try:
        response = requests.get(FEAR_GREED_API, timeout=10)
        data = response.json()
        valor = int(data['data'][0]['value'])
        clasificacion = data['data'][0]['value_classification']
        return valor, clasificacion
    except:
        return 50, "Neutral"  # Default si falla


def _en_rango_minutos(actual_min, inicio_min, fin_min):
    return inicio_min <= actual_min <= fin_min


def es_horario_protegido():
    """Evita ventanas con volatilidad macro elevada (hora ET)."""
    if not HORARIO_PROTEGIDO_ACTIVO:
        return False, ""
    if not TZ_MERCADO:
        return False, ""
    try:
        ahora_et = datetime.now(TZ_MERCADO)
        actual_min = ahora_et.hour * 60 + ahora_et.minute

        if _en_rango_minutos(actual_min, VENTANA_USA_INICIO_MIN, VENTANA_USA_FIN_MIN):
            return True, "Ventana macro USA 08:30-09:30 ET"

        if ahora_et.weekday() == VENTANA_FED_DIA and _en_rango_minutos(actual_min, VENTANA_FED_INICIO_MIN, VENTANA_FED_FIN_MIN):
            return True, "Ventana FOMC/FED 13:45-14:30 ET (miércoles)"

        return False, ""
    except Exception as e:
        if LOG_DETALLADO:
            log(f"⚠️ Error validando horario protegido: {e}")
        return False, ""


def _es_noticia_reciente(published_at_iso, max_min=180):
    try:
        fecha_pub = datetime.fromisoformat(published_at_iso.replace("Z", "+00:00"))
        return (datetime.now(fecha_pub.tzinfo) - fecha_pub).total_seconds() <= max_min * 60
    except Exception:
        return True


def detectar_noticia_alto_impacto():
    """Consulta CryptoPanic y detecta noticias con palabras de alto impacto."""
    if not NOTICIAS_PROTECCION_ACTIVA or not CRYPTO_PANIC_KEY:
        return False, ""
    try:
        params = {
            "auth_token": CRYPTO_PANIC_KEY,
            "kind": "news",
            "public": "true",
            "currencies": "BTC,ETH,SOL,BNB,XRP"
        }
        response = requests.get(CRYPTO_PANIC_URL, params=params, timeout=10)
        data = response.json() if response.ok else {}
        for post in data.get("results", [])[:15]:
            titulo = (post.get("title") or "").lower()
            if not _es_noticia_reciente(post.get("published_at", "")):
                continue
            if any(keyword in titulo for keyword in NOTICIAS_KEYWORDS_ALTO_IMPACTO):
                return True, post.get("title", "Noticia de alto impacto detectada")
        return False, ""
    except Exception as e:
        if LOG_DETALLADO:
            log(f"⚠️ Error consultando noticias: {e}")
        return False, ""


def en_pausa_por_noticias():
    """Activa una pausa temporal si se detecta evento noticioso de alto impacto."""
    global pausa_noticias_hasta, ultimo_check_noticias

    if not NOTICIAS_PROTECCION_ACTIVA:
        return False, ""

    ahora = datetime.now()
    if pausa_noticias_hasta and ahora < pausa_noticias_hasta:
        mins_restantes = int((pausa_noticias_hasta - ahora).total_seconds() / 60)
        return True, f"Pausa por noticias activa ({mins_restantes} min restantes)"

    if time.time() - ultimo_check_noticias < NOTICIAS_CHECK_INTERVALO:
        return False, ""

    ultimo_check_noticias = time.time()
    detectado, titular = detectar_noticia_alto_impacto()
    if detectado:
        pausa_noticias_hasta = ahora + timedelta(minutes=PAUSA_NOTICIAS_MINUTOS)
        log(f"📰 Noticia de alto impacto detectada. Pausa de trading por {PAUSA_NOTICIAS_MINUTOS} min.")
        log(f"📰 Titular: {titular}")
        return True, "Pausa por noticia de alto impacto"
    return False, ""

# ═══════════════════════════════════════════════════════════════════════════════
# INDICADORES TÉCNICOS V3.0 - Para mejorar decisiones de IA
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_rsi(precios_cierre, periodo=14):
    """
    Calcula el RSI (Relative Strength Index) de una lista de precios.
    
    El RSI mide la velocidad y magnitud de los movimientos de precio recientes
    para evaluar condiciones de sobrecompra o sobreventa.
    
    Parámetros:
        precios_cierre: Lista de precios de cierre (más reciente al final)
        periodo: Número de períodos para el cálculo (default 14)
    
    Retorna:
        float: Valor RSI entre 0 y 100
        - RSI > 70: Sobrecompra (posible venta)
        - RSI < 30: Sobreventa (posible compra)
        - RSI 30-70: Zona neutral
    
    Fórmula:
        RSI = 100 - (100 / (1 + RS))
        RS = Promedio de ganancias / Promedio de pérdidas
    """
    if len(precios_cierre) < periodo + 1:
        return 50  # Valor neutral si no hay suficientes datos
    
    # Calcular cambios de precio
    cambios = []
    for i in range(1, len(precios_cierre)):
        cambios.append(precios_cierre[i] - precios_cierre[i-1])
    
    # Separar ganancias y pérdidas
    ganancias = [max(0, c) for c in cambios]
    perdidas = [abs(min(0, c)) for c in cambios]
    
    # Calcular promedios del período
    avg_ganancia = sum(ganancias[-periodo:]) / periodo
    avg_perdida = sum(perdidas[-periodo:]) / periodo
    
    # Evitar división por cero
    if avg_perdida == 0:
        return 100  # Máximo RSI si no hay pérdidas
    
    # Calcular RS y RSI
    rs = avg_ganancia / avg_perdida
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)


def calcular_ema(precios_cierre, periodo):
    """
    Calcula la EMA (Exponential Moving Average) de una lista de precios.
    
    La EMA da más peso a los precios recientes, reaccionando más rápido
    que la SMA (Simple Moving Average) a cambios de precio.
    
    Parámetros:
        precios_cierre: Lista de precios de cierre (más reciente al final)
        periodo: Número de períodos (20, 50, 200 son comunes)
    
    Retorna:
        float: Valor de la EMA
    
    Uso para tendencia:
        - Precio > EMA: Tendencia alcista
        - Precio < EMA: Tendencia bajista
        - EMA corta > EMA larga: Cruce alcista (señal de compra)
        - EMA corta < EMA larga: Cruce bajista (señal de venta)
    
    Fórmula:
        Multiplicador = 2 / (periodo + 1)
        EMA = (Precio_actual - EMA_anterior) * Multiplicador + EMA_anterior
    """
    if len(precios_cierre) < periodo:
        return precios_cierre[-1] if precios_cierre else 0
    
    # Multiplicador de suavizado
    multiplicador = 2 / (periodo + 1)
    
    # EMA inicial = SMA de los primeros 'periodo' valores
    ema = sum(precios_cierre[:periodo]) / periodo
    
    # Calcular EMA para cada precio subsiguiente
    for precio in precios_cierre[periodo:]:
        ema = (precio - ema) * multiplicador + ema
    
    return round(ema, 4)


def calcular_macd(precios_cierre, rapida=12, lenta=26, signal=9):
    """
    Calcula el MACD (Moving Average Convergence Divergence).
    V5.2: Optimizado a O(n) con EMAs incrementales (antes O(n²)).
    """
    if len(precios_cierre) < lenta + signal:
        return {"macd": 0, "signal": 0, "histograma": 0}
    
    # EMA incrementales O(n)
    mult_r = 2 / (rapida + 1)
    mult_l = 2 / (lenta + 1)
    mult_s = 2 / (signal + 1)
    
    # Inicializar EMAs con SMA de los primeros N valores
    ema_r = sum(precios_cierre[:rapida]) / rapida
    ema_l = sum(precios_cierre[:lenta]) / lenta
    
    # Calcular EMA rápida y lenta incrementalmente
    macd_values = []
    for i, precio in enumerate(precios_cierre):
        if i >= rapida:
            ema_r = (precio - ema_r) * mult_r + ema_r
        if i >= lenta:
            ema_l = (precio - ema_l) * mult_l + ema_l
            macd_values.append(ema_r - ema_l)
    
    if not macd_values:
        return {"macd": 0, "signal": 0, "histograma": 0}
    
    macd = macd_values[-1]
    
    # Signal line como EMA del MACD
    if len(macd_values) >= signal:
        ema_sig = sum(macd_values[:signal]) / signal
        for val in macd_values[signal:]:
            ema_sig = (val - ema_sig) * mult_s + ema_sig
        signal_line = ema_sig
    else:
        signal_line = macd
    
    histograma = macd - signal_line
    
    return {
        "macd": round(macd, 4),
        "signal": round(signal_line, 4),
        "histograma": round(histograma, 4)
    }


def calcular_bollinger(precios_cierre, periodo=20, desviaciones=2):
    """
    Calcula las Bandas de Bollinger.
    
    Las Bandas de Bollinger miden la volatilidad y proporcionan niveles
    relativos de precios altos y bajos.
    
    Parámetros:
        precios_cierre: Lista de precios de cierre
        periodo: Período para SMA (default 20)
        desviaciones: Número de desviaciones estándar (default 2)
    
    Retorna:
        dict con:
        - superior: Banda superior (SMA + 2*StdDev)
        - media: SMA del período
        - inferior: Banda inferior (SMA - 2*StdDev)
        - ancho: Ancho de banda (volatilidad)
        - posicion: % del precio dentro de las bandas (0-100)
    
    Uso:
        - Precio cerca de banda superior: Posible sobrecompra
        - Precio cerca de banda inferior: Posible sobreventa
        - Bandas estrechas: Baja volatilidad, posible ruptura próxima
        - Bandas anchas: Alta volatilidad
    """
    if len(precios_cierre) < periodo:
        precio_actual = precios_cierre[-1] if precios_cierre else 0
        return {
            "superior": precio_actual,
            "media": precio_actual,
            "inferior": precio_actual,
            "ancho": 0,
            "posicion": 50
        }
    
    # Últimos N precios
    ultimos = precios_cierre[-periodo:]
    
    # SMA (Media)
    sma = sum(ultimos) / periodo
    
    # Desviación estándar
    varianza = sum((p - sma) ** 2 for p in ultimos) / periodo
    std_dev = varianza ** 0.5
    
    # Bandas
    banda_superior = sma + (desviaciones * std_dev)
    banda_inferior = sma - (desviaciones * std_dev)
    
    # Ancho de banda (% de volatilidad)
    ancho = ((banda_superior - banda_inferior) / sma) * 100 if sma > 0 else 0
    
    # Posición del precio actual dentro de las bandas (0-100%)
    precio_actual = precios_cierre[-1]
    rango = banda_superior - banda_inferior
    if rango > 0:
        posicion = ((precio_actual - banda_inferior) / rango) * 100
        posicion = max(0, min(100, posicion))  # Clamp entre 0 y 100
    else:
        posicion = 50
    
    return {
        "superior": round(banda_superior, 4),
        "media": round(sma, 4),
        "inferior": round(banda_inferior, 4),
        "ancho": round(ancho, 2),
        "posicion": round(posicion, 1)
    }


def calcular_atr(precios_high, precios_low, precios_close, periodo=14):
    """
    Calcula el ATR (Average True Range).
    
    El ATR mide la volatilidad del mercado y es útil para:
    - Establecer Stop Loss dinámicos (1x-2x ATR)
    - Determinar tamaño de posición
    - Identificar cambios en volatilidad
    
    Parámetros:
        precios_high: Lista de precios máximos
        precios_low: Lista de precios mínimos
        precios_close: Lista de precios de cierre
        periodo: Período para el promedio (default 14)
    
    Retorna:
        float: Valor ATR (en unidades de precio)
    
    True Range = max(
        High - Low,
        abs(High - Close_anterior),
        abs(Low - Close_anterior)
    )
    ATR = Promedio móvil del True Range
    
    Uso para Stop Loss:
        - SL conservador: Precio - (2 * ATR)
        - SL agresivo: Precio - (1 * ATR)
    """
    if len(precios_close) < periodo + 1:
        # Fallback: usar rango simple
        if precios_high and precios_low:
            return precios_high[-1] - precios_low[-1]
        return 0
    
    true_ranges = []
    
    for i in range(1, len(precios_close)):
        high = precios_high[i]
        low = precios_low[i]
        close_prev = precios_close[i-1]
        
        # True Range es el máximo de estos tres valores
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        
        true_range = max(tr1, tr2, tr3)
        true_ranges.append(true_range)
    
    # ATR = Promedio de los últimos 'periodo' True Ranges
    if len(true_ranges) >= periodo:
        atr = sum(true_ranges[-periodo:]) / periodo
    else:
        atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0
    
    return round(atr, 4)


def calcular_volumen_relativo(volumenes, periodo=20):
    """
    Calcula el volumen relativo comparado con el promedio.
    
    El volumen relativo ayuda a confirmar movimientos de precio:
    - Alto volumen + movimiento fuerte = movimiento confirmado
    - Bajo volumen + movimiento fuerte = posible falsa ruptura
    
    Parámetros:
        volumenes: Lista de volúmenes (más reciente al final)
        periodo: Período para calcular promedio (default 20)
    
    Retorna:
        float: Ratio de volumen (1.0 = promedio, 2.0 = doble del promedio)
    
    Interpretación:
        - > 1.5: Volumen alto (movimiento significativo)
        - 0.8 - 1.5: Volumen normal
        - < 0.8: Volumen bajo (posible falta de interés)
    """
    if len(volumenes) < periodo:
        return 1.0  # Volumen promedio por defecto
    
    # Promedio de los últimos N períodos
    promedio = sum(volumenes[-periodo:]) / periodo
    
    # Volumen actual
    volumen_actual = volumenes[-1]
    
    # Ratio
    if promedio > 0:
        ratio = volumen_actual / promedio
    else:
        ratio = 1.0
    
    return round(ratio, 2)


def detectar_soportes_resistencias(precios_high, precios_low, precios_close, ventana=20):
    """
    Detecta niveles de soporte y resistencia básicos.
    
    Soportes y resistencias son niveles donde el precio históricamente
    ha encontrado dificultad para bajar (soporte) o subir (resistencia).
    
    Parámetros:
        precios_high: Lista de precios máximos
        precios_low: Lista de precios mínimos
        precios_close: Lista de precios de cierre
        ventana: Período para buscar máximos/mínimos (default 20)
    
    Retorna:
        dict con:
        - resistencia: Nivel de resistencia más cercano
        - soporte: Nivel de soporte más cercano
        - distancia_resistencia: % de distancia a resistencia
        - distancia_soporte: % de distancia a soporte
    
    Método simplificado:
        - Resistencia = Máximo de los últimos N períodos
        - Soporte = Mínimo de los últimos N períodos
    """
    if not precios_high or not precios_low or len(precios_close) < ventana:
        precio = precios_close[-1] if precios_close else 0
        return {
            "resistencia": precio,
            "soporte": precio,
            "distancia_resistencia": 0,
            "distancia_soporte": 0
        }
    
    # Resistencia = Máximo reciente
    resistencia = max(precios_high[-ventana:])
    
    # Soporte = Mínimo reciente
    soporte = min(precios_low[-ventana:])
    
    # Precio actual
    precio_actual = precios_close[-1]
    
    # Distancias en porcentaje
    if precio_actual > 0:
        dist_resistencia = ((resistencia - precio_actual) / precio_actual) * 100
        dist_soporte = ((precio_actual - soporte) / precio_actual) * 100
    else:
        dist_resistencia = 0
        dist_soporte = 0
    
    return {
        "resistencia": round(resistencia, 4),
        "soporte": round(soporte, 4),
        "distancia_resistencia": round(dist_resistencia, 2),
        "distancia_soporte": round(dist_soporte, 2)
    }


def obtener_tendencia_ema(precio_actual, ema20, ema50, ema200=None):
    """
    Determina la tendencia basada en las EMAs.
    
    Parámetros:
        precio_actual: Precio actual del activo
        ema20: EMA de 20 períodos
        ema50: EMA de 50 períodos
        ema200: EMA de 200 períodos (opcional)
    
    Retorna:
        str: 'ALCISTA_FUERTE', 'ALCISTA', 'BAJISTA', 'BAJISTA_FUERTE', o 'LATERAL'
    
    Lógica:
        - Precio > EMA20 > EMA50 > EMA200 = Alcista fuerte
        - Precio > EMA20 > EMA50 = Alcista
        - Precio < EMA20 < EMA50 = Bajista
        - Precio < EMA20 < EMA50 < EMA200 = Bajista fuerte
    """
    if ema200:
        if precio_actual > ema20 > ema50 > ema200:
            return "ALCISTA_FUERTE"
        elif precio_actual < ema20 < ema50 < ema200:
            return "BAJISTA_FUERTE"
    
    if precio_actual > ema20 > ema50:
        return "ALCISTA"
    elif precio_actual < ema20 < ema50:
        return "BAJISTA"
    else:
        return "LATERAL"


def analizar_indicadores_completo(klines):
    """
    Función principal que calcula TODOS los indicadores técnicos a partir de las velas.
    
    Parámetros:
        klines: Lista de velas de Binance (formato [timestamp, open, high, low, close, volume, ...])
    
    Retorna:
        dict con todos los indicadores calculados, listo para pasar a la IA
    """
    if not klines or len(klines) < 50:
        return None
    
    # Extraer datos de las velas
    precios_open = [float(k[1]) for k in klines]
    precios_high = [float(k[2]) for k in klines]
    precios_low = [float(k[3]) for k in klines]
    precios_close = [float(k[4]) for k in klines]
    volumenes = [float(k[5]) for k in klines]
    
    precio_actual = precios_close[-1]
    
    # Calcular indicadores
    rsi = calcular_rsi(precios_close, 14)
    ema20 = calcular_ema(precios_close, 20)
    ema50 = calcular_ema(precios_close, 50)
    ema200 = calcular_ema(precios_close, 200) if len(precios_close) >= 200 else None
    macd = calcular_macd(precios_close)
    bollinger = calcular_bollinger(precios_close)
    atr = calcular_atr(precios_high, precios_low, precios_close)
    volumen_rel = calcular_volumen_relativo(volumenes)
    sr = detectar_soportes_resistencias(precios_high, precios_low, precios_close)
    tendencia = obtener_tendencia_ema(precio_actual, ema20, ema50, ema200)
    
    return {
        "precio_actual": precio_actual,
        "rsi": rsi,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "tendencia_ema": tendencia,
        "macd": macd,
        "bollinger": bollinger,
        "atr": atr,
        "atr_percent": round((atr / precio_actual) * 100, 2) if precio_actual > 0 else 0,
        "volumen_relativo": volumen_rel,
        "soporte": sr["soporte"],
        "resistencia": sr["resistencia"],
        "dist_soporte": sr["distancia_soporte"],
        "dist_resistencia": sr["distancia_resistencia"]
    }

# ═══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE RIESGO AVANZADA V3.0 - FUNCIONES
# ═══════════════════════════════════════════════════════════════════════════════

def verificar_nuevo_dia(balance_actual):
    """
    Verifica si es un nuevo día y reinicia las estadísticas diarias.
    
    Esta función se llama al inicio de cada ciclo para:
    1. Detectar si cambió el día (usando la fecha actual)
    2. Si es nuevo día: reiniciar stats_diarias y balance_inicio_dia
    3. Si es el mismo día: mantener las estadísticas
    
    Parámetros:
        balance_actual: Balance actual de la cuenta
    
    Retorna:
        bool: True si es un nuevo día, False si es el mismo
    """
    from datetime import datetime
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    
    if stats_diarias["fecha_actual"] != hoy:
        # Es un nuevo día - reiniciar estadísticas
        stats_diarias["fecha_actual"] = hoy
        stats_diarias["balance_inicio_dia"] = balance_actual
        stats_diarias["trades_ganados"] = 0
        stats_diarias["trades_perdidos"] = 0
        stats_diarias["monto_ganado"] = 0
        stats_diarias["monto_perdido"] = 0
        stats_diarias["drawdown_pausado"] = False
        log(f"📅 Nuevo día detectado: {hoy}. Stats diarias reiniciadas. Balance inicio: ${balance_actual:.2f}")
        return True
    
    return False


def verificar_drawdown_diario(balance_actual):
    """
    Verifica si se ha superado el drawdown máximo diario.
    
    El drawdown diario es la pérdida porcentual desde el inicio del día.
    Si supera DRAWDOWN_MAXIMO_DIARIO (-3%), el bot pausa nuevos trades.
    
    Parámetros:
        balance_actual: Balance actual de la cuenta
    
    Retorna:
        bool: True si el bot debe seguir operando, False si debe pausar
    
    Fórmula:
        drawdown = (balance_actual - balance_inicio_dia) / balance_inicio_dia
        Si drawdown < -DRAWDOWN_MAXIMO_DIARIO → PAUSAR
    
    Ejemplo:
        - Balance inicio día: $6,307
        - Balance actual: $6,118
        - Drawdown: -3.0% → PAUSAR
    """
    if not DRAWDOWN_ACTIVO:
        return True  # Continuar si no está activo
    
    # Si ya está pausado, verificar si debemos seguir pausados
    if stats_diarias["drawdown_pausado"]:
        log("⏸️ Bot pausado por drawdown diario. Esperando nuevo día...")
        return False
    
    balance_inicio = stats_diarias["balance_inicio_dia"]
    
    # Si no hay balance de inicio, no podemos calcular
    if balance_inicio <= 0:
        return True
    
    # Calcular drawdown actual
    drawdown = (balance_actual - balance_inicio) / balance_inicio
    
    # Si el drawdown supera el máximo permitido
    if drawdown < -DRAWDOWN_MAXIMO_DIARIO:
        perdida_usd = balance_inicio - balance_actual
        stats_diarias["drawdown_pausado"] = True
        log(f"🛑 DRAWDOWN MÁXIMO ALCANZADO!")
        log(f"   Balance inicio día: ${balance_inicio:.2f}")
        log(f"   Balance actual: ${balance_actual:.2f}")
        log(f"   Pérdida: ${perdida_usd:.2f} ({drawdown*100:.2f}%)")
        log(f"   Límite: -{DRAWDOWN_MAXIMO_DIARIO*100}%")
        log(f"   ⏸️ Bot PAUSADO hasta mañana. Guardian sigue activo.")
        return False
    
    return True


def calcular_sl_atr(precio_actual, atr, side):
    """
    Calcula el Stop Loss dinámico basado en ATR (Average True Range).
    
    V3.7: Ahora usa un SL MÍNIMO de 1.5% para evitar SL demasiado cercanos
    en activos de baja volatilidad (como VOXELUSDT).
    
    El ATR representa la volatilidad real del mercado. Un SL basado en ATR
    se adapta automáticamente a las condiciones actuales:
    - Alta volatilidad → SL más amplio (evita stops innecesarios)
    - Baja volatilidad → SL más tight (protege mejor)
    
    Parámetros:
        precio_actual: Precio de entrada de la posición
        atr: Valor ATR calculado para el activo
        side: 'BUY' para LONG, 'SELL' para SHORT
    
    Retorna:
        float: Precio del Stop Loss
    
    Fórmula:
        LONG:  SL = max(Precio - ATR*mult, Precio * 0.985)
        SHORT: SL = min(Precio + ATR*mult, Precio * 1.015)
    """
    if not ATR_SL_ACTIVO or atr <= 0:
        # Fallback: usar SL fijo del 2.5%
        if side == 'BUY':
            return precio_actual * 0.975  # -2.5%
        else:
            return precio_actual * 1.025  # +2.5%
    
    # Calcular distancia del SL basada en ATR
    distancia_sl_atr = atr * ATR_SL_MULTIPLICADOR
    
    # V3.7: Calcular SL mínimo basado en porcentaje (para evitar SL muy cercanos)
    distancia_sl_minima = precio_actual * ATR_SL_MINIMO_PERCENT
    
    # Usar la distancia mayor entre ATR y el mínimo
    distancia_sl = max(distancia_sl_atr, distancia_sl_minima)
    
    if side == 'BUY':  # LONG
        sl_precio = precio_actual - distancia_sl
    else:  # SHORT
        sl_precio = precio_actual + distancia_sl
    
    return round(sl_precio, 4)



def calcular_kelly(saldo_disponible, confianza_ia):
    """
    Calcula el monto óptimo de inversión usando el Kelly Criterion.
    
    El Kelly Criterion es una fórmula matemática que determina el % óptimo
    del capital a arriesgar basándose en el historial de trades.
    
    Fórmula de Kelly:
        f* = (p * b - q) / b
        Donde:
        - p = probabilidad de ganar (win-rate)
        - q = probabilidad de perder (1 - p)
        - b = ratio ganancia/pérdida promedio
    
    Usamos "Medio Kelly" (KELLY_FRACCION = 0.5) para ser más conservadores,
    ya que el Kelly completo puede ser muy agresivo.
    
    Parámetros:
        saldo_disponible: Capital disponible para trading
        confianza_ia: Confianza de la IA (0.70 a 1.0)
    
    Retorna:
        float: Monto a invertir en USD
    
    Ejemplo:
        - Win-rate: 60% (0.6)
        - Ratio G/P: 1.5
        - Kelly = (0.6 * 1.5 - 0.4) / 1.5 = 0.33 (33%)
        - Medio Kelly = 16.5%
        - Limitado a KELLY_MAXIMO (10%) → 10%
    """
    if not KELLY_ACTIVO:
        # Fallback al método original basado en confianza
        rango_confianza = 1.0 - CONFIANZA_MINIMA
        exceso = max(0, confianza_ia - CONFIANZA_MINIMA)
        porcentaje = 2 + (exceso / rango_confianza) * 8
        return saldo_disponible * (porcentaje / 100)
    
    # V4.0 FIX: Usar stats_semanales (más datos) en lugar de stats_diarias
    total_trades = stats_semanales["ganados"] + stats_semanales["perdidos"]
    
    # Si no hay suficientes trades, usar método original
    if total_trades < 3:  # V4.0: Reducido de 5 a 3 trades mínimo
        rango_confianza = 1.0 - CONFIANZA_MINIMA
        exceso = max(0, confianza_ia - CONFIANZA_MINIMA)
        porcentaje = 2 + (exceso / rango_confianza) * 8
        return saldo_disponible * (porcentaje / 100)
    
    # Calcular win-rate (probabilidad de ganar)
    p = stats_semanales["ganados"] / total_trades
    q = 1 - p
    
    # Calcular ratio ganancia/pérdida promedio
    # V4.0: Usar stats semanales para ratio ganancia/pérdida
    if stats_semanales["perdidos"] > 0 and stats_semanales["monto_perdido"] > 0:
        avg_ganancia = stats_semanales["monto_ganado"] / max(1, stats_semanales["ganados"])
        avg_perdida = stats_semanales["monto_perdido"] / stats_semanales["perdidos"]
        b = avg_ganancia / avg_perdida if avg_perdida > 0 else 1.5
    else:
        b = 1.5  # Default ratio
    
    # Fórmula de Kelly
    # f* = (p * b - q) / b
    kelly = (p * b - q) / b
    
    # Aplicar fracción Kelly (más conservador)
    kelly_ajustado = kelly * KELLY_FRACCION
    
    # Limitar entre mínimo y máximo
    kelly_final = max(KELLY_MINIMO, min(KELLY_MAXIMO, kelly_ajustado))
    
    # Si Kelly es negativo, usar mínimo (no deberíamos operar, pero usamos mínimo)
    if kelly < 0:
        kelly_final = KELLY_MINIMO
        log(f"⚠️ Kelly negativo ({kelly*100:.1f}%). Usando mínimo {KELLY_MINIMO*100}%")
    
    monto = saldo_disponible * kelly_final
    
    if LOG_DETALLADO:
        log(f"📊 Kelly: WR={p*100:.0f}% | Ratio={b:.2f} | Kelly={kelly*100:.1f}% | Final={kelly_final*100:.1f}% | ${monto:.2f}")
    
    return round(monto, 2)


def actualizar_stats_trade(pnl):
    """
    Actualiza las estadísticas diarias después de cada trade cerrado.
    
    Esta función se llama cuando se cierra un trade para actualizar:
    - Contador de trades ganados/perdidos
    - Monto total ganado/perdido hoy
    
    Parámetros:
        pnl: Profit/Loss del trade (positivo = ganancia, negativo = pérdida)
    """
    if pnl >= 0:
        stats_diarias["trades_ganados"] += 1
        stats_diarias["monto_ganado"] += pnl
    else:
        stats_diarias["trades_perdidos"] += 1
        stats_diarias["monto_perdido"] += abs(pnl)


# ═══════════════════════════════════════════════════════════════════════════════
# CÁLCULO DE MONTO (Escudo 80/20) - Entre 2% y 10%
# ═══════════════════════════════════════════════════════════════════════════════
def calcular_monto(saldo, confianza):
    """V5.2: Calcula monto con interés compuesto — reinvierte ganancias, protege en pérdidas.
    
    Fórmula base: Porcentaje 2-10% del balance disponible según confianza.
    Interés compuesto:
    - Si balance creció vs BALANCE_INICIAL_PROYECTO → escalar porcentaje hasta 1.5x
    - Si balance bajó → reducir porcentaje hasta 0.5x (protección)
    - Cap de seguridad: nunca más del 12% del balance disponible
    """
    saldo_disponible = saldo * ESCUDO_TRABAJO
    # Mapear confianza 70%-100% a porcentaje base 2%-10%
    rango_confianza = 1.0 - CONFIANZA_MINIMA  # 0.30
    exceso = max(0, confianza - CONFIANZA_MINIMA)  # 0 a 0.30
    porcentaje_base = 2 + (exceso / rango_confianza) * 8  # 2% a 10%
    porcentaje_base = min(10, max(2, porcentaje_base))
    
    # V5.2: Factor de interés compuesto
    ganancia_acumulada = saldo - BALANCE_INICIAL_PROYECTO
    if ganancia_acumulada > 0 and saldo > BALANCE_INICIAL_PROYECTO:
        # Balance creció → escalar posiciones proporcionalmente (interés compuesto)
        # Ejemplo: balance creció 20% → factor = 1.20 (cap 1.50)
        factor_compuesto = min(1.5, 1 + (ganancia_acumulada / BALANCE_INICIAL_PROYECTO))
        porcentaje = porcentaje_base * factor_compuesto
        porcentaje = min(12, porcentaje)  # Cap de seguridad en 12%
    else:
        # Balance bajó → reducir posiciones (protección anti-pérdida)
        # Ejemplo: balance bajó 30% → factor = 0.70 (mín 0.50)
        factor_desgaste = max(0.5, saldo / BALANCE_INICIAL_PROYECTO) if BALANCE_INICIAL_PROYECTO > 0 else 1.0
        porcentaje = porcentaje_base * factor_desgaste
    
    monto = saldo_disponible * (porcentaje / 100)
    
    if LOG_DETALLADO:
        factor = porcentaje / porcentaje_base if porcentaje_base > 0 else 1
        log(f"   💰 Interés compuesto: factor {factor:.2f}x | base {porcentaje_base:.1f}% → ajustado {porcentaje:.1f}% | ${monto:.2f}")
    
    return max(1, round(monto, 2))

# ═══════════════════════════════════════════════════════════════════════════════
# CONEXIÓN A BINANCE
# ═══════════════════════════════════════════════════════════════════════════════
def conectar_binance():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET")
    
    if USAR_TESTNET:
        client = Client(api_key, api_secret, testnet=True)
        log("📡 Conectado a Binance TESTNET (modo prueba)")
    else:
        client = Client(api_key, api_secret)
        log("📡 Conectado a Binance PRODUCCIÓN")
    
    return client

# ═══════════════════════════════════════════════════════════════════════════════
# OBTENER TODOS LOS SÍMBOLOS DE FUTUROS
# ═══════════════════════════════════════════════════════════════════════════════
def obtener_simbolos_futuros(client):
    """Obtiene todos los pares de futuros USDT activos ordenados por volumen"""
    try:
        # Obtener información del exchange
        info = obtener_exchange_info(client)
        
        # Filtrar solo pares USDT activos
        simbolos = [s['symbol'] for s in info['symbols'] 
                   if s['status'] == 'TRADING' 
                   and s['quoteAsset'] == 'USDT'
                   and not s['symbol'].endswith('_PERP')]
        
        # Obtener volumen 24h para ordenar
        tickers = client.futures_ticker()
        vol_dict = {t['symbol']: float(t['quoteVolume']) for t in tickers}
        
        # Ordenar por volumen descendente
        simbolos_ordenados = sorted(simbolos, key=lambda x: vol_dict.get(x, 0), reverse=True)
        
        log(f"📊 Encontrados: {len(simbolos_ordenados)} pares de futuros activos")
        return simbolos_ordenados[:TOP_ACTIVOS]  # Top N por volumen
        
    except Exception as e:
        log(f"⚠️ Error obteniendo símbolos: {e}")
        return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT"]  # Fallback

# ═══════════════════════════════════════════════════════════════════════════════
# CONTAR POSICIONES ABIERTAS
# ═══════════════════════════════════════════════════════════════════════════════
def contar_posiciones_abiertas(client):
    """Cuenta las posiciones abiertas actuales"""
    try:
        positions = obtener_posiciones(client)
        abiertas = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        return len(abiertas)
    except:
        return 0

def obtener_simbolos_con_posicion(client):
    """Obtiene la lista de símbolos que ya tienen posición abierta"""
    try:
        positions = obtener_posiciones(client)
        return [p['symbol'] for p in positions if float(p.get('positionAmt', 0)) != 0]
    except:
        return []

# ═══════════════════════════════════════════════════════════════════════════════
# OBTENER VELAS (KLINES)
# ═══════════════════════════════════════════════════════════════════════════════
def obtener_velas(client, symbol, interval='1h', limit=200):
    """Obtiene las últimas N velas del símbolo"""
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        # Cada kline: [timestamp, open, high, low, close, volume, ...]
        velas = [{
            'timestamp': k[0],
            'open': float(k[1]),
            'high': float(k[2]),
            'low': float(k[3]),
            'close': float(k[4]),
            'volume': float(k[5])
        } for k in klines]
        return velas
    except Exception as e:
        log(f"⚠️ Error obteniendo velas de {symbol}: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# OBTENER BALANCE DE FUTUROS
# ═══════════════════════════════════════════════════════════════════════════════
def obtener_balance(client):
    """Obtiene el balance total (wallet balance) en USDT para ROI preciso"""
    try:
        balances = client.futures_account_balance()
        for b in balances:
            if b['asset'] == 'USDT':
                # V3.6: Usar 'balance' (wallet balance) en vez de 'availableBalance'
                # Esto da un ROI más estable que no fluctúa con posiciones abiertas
                return float(b['balance'])
        return 0
    except Exception as e:
        log(f"⚠️ Error obteniendo balance: {e}")
        return 0

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAR APALANCAMIENTO
# ═══════════════════════════════════════════════════════════════════════════════
def configurar_apalancamiento(client, symbol, leverage=3):
    """Configura el apalancamiento para el símbolo"""
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        return True
    except Exception as e:
        if "No need to change leverage" not in str(e):
            log(f"⚠️ Error configurando apalancamiento: {e}")
        return True

# ═══════════════════════════════════════════════════════════════════════════════
# CALCULAR CANTIDAD DE CONTRATOS
# ═══════════════════════════════════════════════════════════════════════════════
def calcular_cantidad(client, symbol, monto_usdt, precio_actual):
    """Calcula la cantidad de contratos según el monto USDT y precisión del símbolo"""
    try:
        info = obtener_exchange_info(client)
        symbol_info = next((s for s in info['symbols'] if s['symbol'] == symbol), None)
        
        if not symbol_info:
            return None
            
        quantity_precision = int(symbol_info['quantityPrecision'])
        cantidad = monto_usdt / precio_actual
        cantidad = round(cantidad, quantity_precision)
        
        min_qty = float(next((f['minQty'] for f in symbol_info['filters'] 
                             if f['filterType'] == 'LOT_SIZE'), 0.001))
        
        if cantidad < min_qty:
            return None
            
        return cantidad
        
    except Exception as e:
        log(f"⚠️ Error calculando cantidad: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# TRAILING STOP LOSS - FUNCIONES
# ═══════════════════════════════════════════════════════════════════════════════
posiciones_tracking = {}  # {symbol: {'side': 'LONG/SHORT', 'best_price': X, 'entry': Y}}

def cancelar_ordenes_sl(client, symbol):
    """V4.0: Solo cancela órdenes STOP_MARKET, PRESERVA Take Profit"""
    try:
        ordenes = client.futures_get_open_orders(symbol=symbol)
        for orden in ordenes:
            # V4.0 FIX: Solo cancelar STOP_MARKET, NUNCA TAKE_PROFIT_MARKET
            if orden['type'] in ['STOP_MARKET', 'STOP', 'STOP_LOSS_MARKET']:
                client.futures_cancel_order(symbol=symbol, orderId=orden['orderId'])
                log(f"   🗑️ Orden SL cancelada: {orden['orderId']} ({orden['type']})")
        # También cancelar Algo Orders de tipo stop
        try:
            algo_ordenes = client.futures_get_open_algo_orders()
            if algo_ordenes:
                for o in algo_ordenes:
                    if o.get('symbol') == symbol and o.get('type') in ['STOP_MARKET', 'STOP']:
                        try:
                            client.futures_cancel_algo_order(algoId=o.get('algoId'))
                        except:
                            pass
        except:
            pass
    except Exception as e:
        if LOG_DETALLADO:
            log(f"⚠️ Error cancelando órdenes SL de {symbol}: {e}")


def existe_orden_sl_abierta(client, symbol):
    """Verifica si hay al menos una orden de stop o TP activa para el símbolo.
    V5.2: También cuenta TAKE_PROFIT_MARKET como protección válida
    ya que consume cupo de stop orders y protege la posición."""
    TIPOS_PROTECCION = ('STOP', 'STOP_MARKET', 'STOP_LOSS', 'STOP_LOSS_MARKET',
                        'TAKE_PROFIT', 'TAKE_PROFIT_MARKET')
    try:
        ordenes = client.futures_get_open_orders(symbol=symbol)
        for orden in ordenes:
            tipo = (orden.get('type', '') or '').upper()
            if any(t in tipo for t in TIPOS_PROTECCION):
                return True
    except Exception:
        pass

    try:
        algo_ordenes = client.futures_get_open_algo_orders()
        if algo_ordenes:
            for orden in algo_ordenes:
                if orden.get('symbol') != symbol:
                    continue
                tipo = (orden.get('type', '') or '').upper()
                if any(t in tipo for t in TIPOS_PROTECCION):
                    return True
    except Exception:
        pass

    return False

def crear_orden_sl(client, symbol, side, precio, cantidad):
    """V5.0: Crea SL con orden STOP_MARKET tradicional (método principal)
    Returns: tuple (success: bool, already_protected: bool)
        - (True, False): SL creado exitosamente
        - (False, True): Error -4045, ya hay protección SL existente
        - (False, False): Error real, SL NO fue creado
    """
    try:
        # Obtener precisión del precio
        info = obtener_exchange_info(client)
        symbol_info = next((s for s in info['symbols'] if s['symbol'] == symbol), None)
        if symbol_info:
            price_precision = int(symbol_info['pricePrecision'])
            precio = round(precio, price_precision)
        
        # V5.0: Método 1 - STOP_MARKET tradicional (funcionaba en enero V2.0)
        try:
            client.futures_create_order(
                symbol=symbol,
                side=side,
                type='STOP_MARKET',
                stopPrice=str(precio),
                closePosition='true'
            )
            return True, False
        except Exception as trad_error:
            trad_str = str(trad_error)
            if '-4045' in trad_str:
                # V5.2: Log siempre (antes bloqueado por LOG_DETALLADO)
                log_throttled(f"sl_4045_trad_{symbol}", f"   ⚠️ {symbol}: Binance reporta -4045 al crear SL tradicional", 120)
                return False, True  # already_protected
            
            # Fallback: Algo Order API
            log(f"   ⚠️ SL tradicional falló, intentando Algo Order...")
            try:
                client.futures_create_algo_order(
                    symbol=symbol,
                    side=side,
                    type='STOP_MARKET',
                    triggerPrice=str(precio),
                    quantity=str(cantidad)
                )
                return True, False
            except Exception as algo_error:
                if '-4045' in str(algo_error):
                    # V5.2: Log siempre (antes bloqueado por LOG_DETALLADO)
                    log_throttled(f"sl_4045_algo_{symbol}", f"   ⚠️ {symbol}: Binance reporta -4045 también en Algo Order", 120)
                    return False, True
                log(f"   ⚠️ Algo Order también falló: {algo_error}")
                return False, False
                
    except Exception as e:
        error_str = str(e)
        if '-4045' in error_str:
            return False, True
        log(f"⚠️ Error creando SL: {e}")
        return False, False

def actualizar_trailing_sl(client):
    """Monitorea posiciones y actualiza SL con trailing 1.5%"""
    global posiciones_tracking
    
    try:
        positions = obtener_posiciones(client)
        
        for pos in positions:
            symbol = pos['symbol']
            cantidad = float(pos.get('positionAmt', 0))
            
            if cantidad == 0:
                # Posición cerrada, limpiar tracking
                if symbol in posiciones_tracking:
                    del posiciones_tracking[symbol]
                continue
            
            precio_actual = float(pos['markPrice'])
            entry_price = float(pos['entryPrice'])
            side = 'LONG' if cantidad > 0 else 'SHORT'
            
            # Inicializar tracking si es nueva posición
            if symbol not in posiciones_tracking:
                posiciones_tracking[symbol] = {
                    'side': side,
                    'best_price': precio_actual,
                    'entry': entry_price,
                    'last_sl': None
                }
                log(f"📍 Nueva posición detectada: {symbol} {side}")
            
            tracking = posiciones_tracking[symbol]
            
            # V4.0: Trailing SL mejorado - se activa con ganancia > 0.5%
            ganancia_actual = ((precio_actual - entry_price) / entry_price) if side == 'LONG' else ((entry_price - precio_actual) / entry_price)
            
            if side == 'LONG':
                if precio_actual > tracking['best_price']:
                    tracking['best_price'] = precio_actual
                
                # V4.0 FIX: Activar trailing cuando ganancia > 0.5% (antes requería SL > entry)
                if ganancia_actual > 0.005:  # > 0.5% de ganancia
                    nuevo_sl = tracking['best_price'] * (1 - TRAILING_SL_PERCENT)
                    
                    if tracking['last_sl'] is None or nuevo_sl > tracking['last_sl']:
                        cancelar_ordenes_sl(client, symbol)
                        success, _ = crear_orden_sl(client, symbol, 'SELL', nuevo_sl, abs(cantidad))
                        if success:
                            tracking['last_sl'] = nuevo_sl
                            ganancia_pct = ((nuevo_sl - entry_price) / entry_price) * 100
                            log(f"📈 Trailing SL ajustado ({symbol}): ${nuevo_sl:.4f} ({ganancia_pct:+.2f}% vs entry)")
            
            else:  # SHORT
                if precio_actual < tracking['best_price']:
                    tracking['best_price'] = precio_actual
                
                # V4.0 FIX: Activar trailing cuando ganancia > 0.5%
                if ganancia_actual > 0.005:  # > 0.5% de ganancia
                    nuevo_sl = tracking['best_price'] * (1 + TRAILING_SL_PERCENT)
                    
                    if tracking['last_sl'] is None or nuevo_sl < tracking['last_sl']:
                        cancelar_ordenes_sl(client, symbol)
                        success, _ = crear_orden_sl(client, symbol, 'BUY', nuevo_sl, abs(cantidad))
                        if success:
                            tracking['last_sl'] = nuevo_sl
                            ganancia_pct = ((entry_price - nuevo_sl) / entry_price) * 100
                            log(f"📉 Trailing SL ajustado ({symbol}): ${nuevo_sl:.4f} ({ganancia_pct:+.2f}% vs entry)")
                        
    except Exception as e:
        log(f"⚠️ Error en trailing SL: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA GUARDIÁN V2.7 - MONITOREO COMPLETO DE POSICIONES
# ═══════════════════════════════════════════════════════════════════════════════
def guardian_posiciones(client):
    """
    Guardián de emergencia - Monitorea TODAS las posiciones independientemente.
    Cierra automáticamente si la pérdida supera MAX_PERDIDA_PERMITIDA (-10%).
    Esta función funciona INDEPENDIENTE de las órdenes SL en Binance.
    """
    if not GUARDIAN_ACTIVO:
        return
    
    try:
        positions = obtener_posiciones(client)
        
        for pos in positions:
            symbol = pos['symbol']
            cantidad = float(pos.get('positionAmt', 0))
            
            if cantidad == 0:
                continue
            
            # Calcular PNL porcentual
            entry_price = float(pos['entryPrice'])
            mark_price = float(pos['markPrice'])
            unrealized_pnl = float(pos.get('unRealizedProfit', 0))
            
            # Calcular porcentaje de ganancia/pérdida
            if entry_price > 0:
                if cantidad > 0:  # LONG
                    pnl_porcentaje = (mark_price - entry_price) / entry_price
                else:  # SHORT
                    pnl_porcentaje = (entry_price - mark_price) / entry_price
            else:
                pnl_porcentaje = 0
            
            # ═══════════════════════════════════════════════════════════════════
            # CIERRE DE EMERGENCIA POR PÉRDIDA MÁXIMA (-10%)
            # ═══════════════════════════════════════════════════════════════════
            if pnl_porcentaje <= MAX_PERDIDA_PERMITIDA:
                side = 'SELL' if cantidad > 0 else 'BUY'
                
                log(f"⛔ GUARDIÁN: {symbol} en {pnl_porcentaje*100:.2f}% (límite: {MAX_PERDIDA_PERMITIDA*100}%)")
                log(f"⛔ CERRANDO POSICIÓN DE EMERGENCIA: {symbol}")
                
                try:
                    # Cancelar todas las órdenes pendientes primero
                    client.futures_cancel_all_open_orders(symbol=symbol)
                    
                    # Cerrar la posición a mercado
                    client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type='MARKET',
                        quantity=abs(cantidad)
                    )
                    
                    log(f"✅ Posición {symbol} cerrada por Guardián. PNL: ${unrealized_pnl:.2f}")
                    
                    # V3.0: Acumular estadística en stats_semanales para el resumen semanal
                    stats_semanales["cierres_guardian"] += 1
                    
                    # V3.0: Ya NO se envía Telegram individual
                    # El cierre se incluirá en el resumen semanal del viernes
                    # (Antes enviaba notificación aquí, ahora solo log)
                    
                except Exception as e:
                    log(f"❌ Error cerrando posición de emergencia {symbol}: {e}")
                    # V3.0: Ya no se envía Telegram de error individual
            
            # V4.0 FIX: Logear TODAS las posiciones activas (antes solo > 5%)
            elif LOG_DETALLADO:
                estado = "🟢" if pnl_porcentaje > 0 else "🔴"
                side_str = 'LONG' if cantidad > 0 else 'SHORT'
                log_throttled(
                    f"guardian_status_{symbol}",
                    f"{estado} Guardián {symbol} {side_str}: {pnl_porcentaje*100:.2f}% (PNL: ${unrealized_pnl:.2f})",
                    60
                )
                
    except Exception as e:
        log(f"⚠️ Error en Guardián: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# V3.9: LOG RESUMEN DE POSICIONES ACTIVAS
# ═══════════════════════════════════════════════════════════════════════════════
def log_resumen_posiciones(client):
    """V3.9: Muestra un resumen claro de todas las posiciones activas con PNL y estado SL"""
    try:
        positions = obtener_posiciones(client)
        activas = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        
        if not activas:
            return
        
        log(f"📋 ═══ RESUMEN POSICIONES ({len(activas)}/{MAX_POSICIONES}) ═══")
        
        pnl_total = 0
        for pos in activas:
            symbol = pos['symbol']
            cantidad = float(pos['positionAmt'])
            entry = float(pos['entryPrice'])
            mark = float(pos['markPrice'])
            pnl = float(pos.get('unRealizedProfit', 0))
            pnl_total += pnl
            
            side = 'LONG' if cantidad > 0 else 'SHORT'
            
            # Calcular ROI %
            if entry > 0:
                if cantidad > 0:
                    roi = ((mark - entry) / entry) * 100
                else:
                    roi = ((entry - mark) / entry) * 100
            else:
                roi = 0
            
            estado = "🟢" if pnl >= 0 else "🔴"
            
            # Verificar SL rápido (sin API calls extra, usar _sl_verificados)
            sl_status = "✅" if ('_sl_verificados' in globals() and symbol in _sl_verificados) else "❓"
            
            log(f"   {estado} {symbol} {side}: ROI {roi:+.2f}% (${pnl:+.2f}) | SL: {sl_status}")
        
        log(f"   💰 PNL Total No Realizado: ${pnl_total:+.2f}")
        log(f"📋 ═══════════════════════════════════════════")
        
    except Exception as e:
        log(f"⚠️ Error en resumen posiciones: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# VERIFICAR QUE EXISTAN ÓRDENES SL EN BINANCE
# ═══════════════════════════════════════════════════════════════════════════════
def verificar_ordenes_sl_existen(client):
    """
    V3.9: Verifica que cada posición tenga una orden SL activa y COHERENTE.
    Mejoras sobre V3.4:
    - Cache con TTL de 5 minutos (antes era permanente)
    - Validación de coherencia: SL debe estar del lado correcto
    - No marca como verificado si la creación falla
    """
    global _sl_verificados  # dict: {symbol: timestamp}
    
    SL_VERIFICACION_TTL = 300  # Re-verificar cada 5 minutos
    
    # Inicializar dict si no existe
    if '_sl_verificados' not in globals():
        _sl_verificados = {}
    
    try:
        positions = obtener_posiciones(client)
        
        for pos in positions:
            symbol = pos['symbol']
            cantidad = float(pos.get('positionAmt', 0))
            
            if cantidad == 0:
                # Si la posición se cerró, quitar del tracking
                _sl_verificados.pop(symbol, None)
                _sl_retry_cooldown_until.pop(symbol, None)
                continue
            
            # V3.9: Re-verificar si han pasado más de 5 minutos (TTL)
            if symbol in _sl_verificados:
                if time.time() - _sl_verificados[symbol] < SL_VERIFICACION_TTL:
                    continue

            # Si el símbolo está en cooldown por reintentos fallidos, no volver a golpear API
            if time.time() < _sl_retry_cooldown_until.get(symbol, 0):
                continue
            
            entry_price = float(pos['entryPrice'])
            mark_price = float(pos['markPrice'])
            side = 'LONG' if cantidad > 0 else 'SHORT'
            
            # V3.9: Verificar SL en AMBOS endpoints con búsqueda más amplia
            try:
                tiene_sl = False
                sl_precio_encontrado = None
                
                # 1. Buscar en Algo Orders
                try:
                    algo_ordenes = client.futures_get_open_algo_orders()
                    if algo_ordenes:
                        for o in algo_ordenes:
                            if o.get('symbol') == symbol and (
                                o.get('type') in ['STOP_MARKET', 'STOP', 'STOP_LOSS', 'STOP_LOSS_MARKET'] or
                                'stop' in o.get('type', '').lower()
                            ):
                                tiene_sl = True
                                sl_precio_encontrado = float(o.get('triggerPrice', 0) or o.get('stopPrice', 0) or 0)
                                break
                except Exception:
                    pass
                
                # 2. Buscar en órdenes tradicionales
                if not tiene_sl:
                    try:
                        ordenes_tradicionales = client.futures_get_open_orders(symbol=symbol)
                        if ordenes_tradicionales:
                            for o in ordenes_tradicionales:
                                if (o.get('type') in ['STOP_MARKET', 'STOP', 'STOP_LOSS', 'STOP_LOSS_MARKET'] or
                                    'stop' in o.get('type', '').lower()):
                                    tiene_sl = True
                                    sl_precio_encontrado = float(o.get('stopPrice', 0) or o.get('triggerPrice', 0) or 0)
                                    break
                    except Exception:
                        pass
                
                if tiene_sl and sl_precio_encontrado and sl_precio_encontrado > 0:
                    # V3.9: VALIDAR COHERENCIA del SL
                    sl_coherente = True
                    if side == 'LONG' and sl_precio_encontrado > entry_price * 1.01:
                        # SL de un LONG está ARRIBA del entry → INCOHERENTE
                        log(f"⛔ {symbol} LONG: SL en ${sl_precio_encontrado:.2f} está ARRIBA del entry ${entry_price:.2f} → INCOHERENTE")
                        sl_coherente = False
                    elif side == 'SHORT' and sl_precio_encontrado < entry_price * 0.99:
                        # SL de un SHORT está DEBAJO del entry → INCOHERENTE
                        log(f"⛔ {symbol} SHORT: SL en ${sl_precio_encontrado:.2f} está DEBAJO del entry ${entry_price:.2f} → INCOHERENTE")
                        sl_coherente = False
                    
                    if sl_coherente:
                        _sl_verificados[symbol] = time.time()
                    else:
                        # Cancelar SL incoherente y crear uno nuevo
                        log(f"🔄 Cancelando SL incoherente de {symbol} y recreando...")
                        cancelar_ordenes_sl(client, symbol)
                        tiene_sl = False  # Forzar creación de nuevo SL
                
                if not tiene_sl:
                    # V4.0 FIX: SL emergencia a -3% (antes -7%) — Guardian sigue como red de seguridad a -7%
                    SL_EMERGENCIA_PERCENT = 0.03  # -3% es más razonable que -7%
                    # V5.1: anclar primero al entry para preservar riesgo previsto,
                    # y ajustar a un nivel válido vs mark para evitar rechazo inmediato.
                    if side == 'LONG':
                        sl_objetivo_entry = entry_price * (1 - SL_EMERGENCIA_PERCENT)
                        sl_precio = min(sl_objetivo_entry, mark_price * 0.995)
                        sl_side = 'SELL'
                    else:
                        sl_objetivo_entry = entry_price * (1 + SL_EMERGENCIA_PERCENT)
                        sl_precio = max(sl_objetivo_entry, mark_price * 1.005)
                        sl_side = 'BUY'
                    
                    log_throttled(
                        f"sl_missing_{symbol}",
                        f"⚠️ {symbol} SIN orden SL válida. SL emergencia objetivo(entry): ${sl_objetivo_entry:.4f} | aplicado: ${sl_precio:.4f}",
                        120
                    )
                    
                    success, already_protected = crear_orden_sl(client, symbol, sl_side, sl_precio, abs(cantidad))
                    
                    if success:
                        log(f"✅ SL de emergencia creado para {symbol}")
                        _sl_verificados[symbol] = time.time()
                        _sl_retry_cooldown_until.pop(symbol, None)
                    elif already_protected:
                        # V5.2 FIX: -4045 = Binance confirma que max stop orders fue alcanzado
                        # Aceptar como protegido directamente (rompe el bucle infinito anterior)
                        _sl_verificados[symbol] = time.time()
                        _sl_retry_cooldown_until.pop(symbol, None)
                        log_throttled(
                            f"sl_4045_accepted_{symbol}",
                            f"✅ {symbol}: -4045 aceptado como protegido (max stop orders alcanzado)",
                            300
                        )
                    else:
                        _sl_retry_cooldown_until[symbol] = time.time() + SL_REINTENTO_COOLDOWN
                        log_throttled(
                            f"sl_not_created_{symbol}",
                            f"⛔ SL NO CREADO para {symbol}. Cooldown {int(SL_REINTENTO_COOLDOWN/60)} min.",
                            120
                        )
                    
            except Exception as e:
                log(f"⚠️ Error verificando SL de {symbol}: {e}")
                    
    except Exception as e:
        log(f"⚠️ Error en verificar_ordenes_sl_existen: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# PROTECCIÓN FUNDING FEES - CIERRE POR TIEMPO MÁXIMO
# ═══════════════════════════════════════════════════════════════════════════════
def verificar_tiempo_posiciones(client):
    """Cierra posiciones que excedan MAX_DIAS_POSICION días"""
    try:
        positions = obtener_posiciones(client)
        
        for pos in positions:
            symbol = pos['symbol']
            cantidad = float(pos.get('positionAmt', 0))
            
            if cantidad == 0:
                continue
            
            # Obtener trades recientes para encontrar fecha de entrada
            try:
                trades = client.futures_account_trades(symbol=symbol, limit=50)
                if not trades:
                    continue
                
                # Encontrar el trade de apertura más antiguo para esta posición
                trade_apertura = None
                for trade in trades:
                    if trade.get('realizedPnl', '0') == '0' or float(trade.get('realizedPnl', 0)) == 0:
                        # Trade de apertura (sin PnL realizado)
                        trade_apertura = trade
                        break
                
                if not trade_apertura:
                    continue
                
                # Calcular días desde apertura
                timestamp_apertura = int(trade_apertura['time'])
                fecha_apertura = datetime.fromtimestamp(timestamp_apertura / 1000)
                dias_abierto = (datetime.now() - fecha_apertura).days
                
                if dias_abierto >= MAX_DIAS_POSICION:
                    side = 'SELL' if cantidad > 0 else 'BUY'
                    entry_price = float(pos['entryPrice'])
                    mark_price = float(pos['markPrice'])
                    pnl = float(pos.get('unRealizedProfit', 0))
                    
                    log(f"⏰ Cerrando {symbol} por tiempo: {dias_abierto} días (máx: {MAX_DIAS_POSICION})")
                    
                    # Cerrar posición
                    client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type='MARKET',
                        quantity=abs(cantidad)
                    )
                    
                    # V3.0: Ya no se envía Telegram individual (se incluye en resumen semanal)
                    # enviar_telegram(f"""... cierre por tiempo ...""")
                    log(f"✅ Posición {symbol} cerrada por tiempo ({dias_abierto} días). PNL: ${pnl:.2f}")
                    
            except Exception as e:
                log(f"⚠️ Error verificando tiempo de {symbol}: {e}")
                
    except Exception as e:
        log(f"⚠️ Error en verificar_tiempo_posiciones: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# PROTECCIÓN FUNDING FEES - CIERRE SI FUNDING > PNL
# ═══════════════════════════════════════════════════════════════════════════════
def verificar_funding_vs_pnl(client):
    """Cierra posiciones donde los funding fees superan las ganancias"""
    try:
        positions = obtener_posiciones(client)
        
        for pos in positions:
            symbol = pos['symbol']
            cantidad = float(pos.get('positionAmt', 0))
            
            if cantidad == 0:
                continue
            
            unrealized_pnl = float(pos.get('unRealizedProfit', 0))
            
            # Obtener funding fees acumulados
            try:
                # Obtener income de los últimos 7 días
                income = client.futures_income_history(
                    symbol=symbol,
                    incomeType='FUNDING_FEE',
                    limit=100
                )
                
                total_funding = sum(float(i.get('income', 0)) for i in income)
                
                # Si el funding (negativo) supera el PNL positivo → cerrar
                if unrealized_pnl > 0 and abs(total_funding) > unrealized_pnl:
                    side = 'SELL' if cantidad > 0 else 'BUY'
                    entry_price = float(pos['entryPrice'])
                    mark_price = float(pos['markPrice'])
                    
                    log(f"💸 Cerrando {symbol}: Funding ${total_funding:.2f} > PNL ${unrealized_pnl:.2f}")
                    
                    # Cerrar posición
                    client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type='MARKET',
                        quantity=abs(cantidad)
                    )
                    
                    # V3.0: Ya no se envía Telegram individual
                    # enviar_telegram(f"""... cierre funding > PNL ...""")
                    log(f"✅ Posición {symbol} cerrada (funding > PNL). PNL: ${unrealized_pnl:.2f}")
                    
            except Exception as e:
                # API puede no soportar income_history en testnet
                pass
                
    except Exception as e:
        log(f"⚠️ Error en verificar_funding_vs_pnl: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# PROTECCIÓN FUNDING FEES - TAKE PROFIT DINÁMICO
# ═══════════════════════════════════════════════════════════════════════════════
def ajustar_tp_dinamico(client):
    """Reduce el TP después de X días para asegurar ganancias"""
    try:
        positions = obtener_posiciones(client)
        
        for pos in positions:
            symbol = pos['symbol']
            cantidad = float(pos.get('positionAmt', 0))
            
            if cantidad == 0:
                continue
            
            unrealized_pnl = float(pos.get('unRealizedProfit', 0))
            entry_price = float(pos['entryPrice'])
            mark_price = float(pos['markPrice'])
            
            # Solo si está en ganancia
            if unrealized_pnl <= 0:
                continue
            
            # Verificar días abierto
            try:
                trades = client.futures_account_trades(symbol=symbol, limit=50)
                if not trades:
                    continue
                
                trade_apertura = None
                for trade in trades:
                    if float(trade.get('realizedPnl', 0)) == 0:
                        trade_apertura = trade
                        break
                
                if not trade_apertura:
                    continue
                
                timestamp_apertura = int(trade_apertura['time'])
                fecha_apertura = datetime.fromtimestamp(timestamp_apertura / 1000)
                dias_abierto = (datetime.now() - fecha_apertura).days
                
                if dias_abierto >= TP_DINAMICO_DIAS:
                    side = 'LONG' if cantidad > 0 else 'SHORT'
                    
                    # Calcular nuevo TP reducido
                    if side == 'LONG':
                        nuevo_tp = entry_price * (1 + TP_DINAMICO_PERCENT)
                        # Solo ajustar si el precio ya superó el nuevo TP potencial
                        if mark_price < nuevo_tp:
                            continue
                    else:
                        nuevo_tp = entry_price * (1 - TP_DINAMICO_PERCENT)
                        if mark_price > nuevo_tp:
                            continue
                    
                    # Cancelar órdenes TP existentes
                    try:
                        ordenes = client.futures_get_open_orders(symbol=symbol)
                        for orden in ordenes:
                            if orden['type'] == 'TAKE_PROFIT_MARKET':
                                client.futures_cancel_order(symbol=symbol, orderId=orden['orderId'])
                    except:
                        pass
                    
                    # Crear nuevo TP más cercano
                    try:
                        info = obtener_exchange_info(client)
                        symbol_info = next((s for s in info['symbols'] if s['symbol'] == symbol), None)
                        if symbol_info:
                            price_precision = int(symbol_info['pricePrecision'])
                            nuevo_tp = round(nuevo_tp, price_precision)
                        
                        tp_side = 'SELL' if cantidad > 0 else 'BUY'
                        client.futures_create_order(
                            symbol=symbol,
                            side=tp_side,
                            type='TAKE_PROFIT_MARKET',
                            stopPrice=nuevo_tp,
                            closePosition=True
                        )
                        
                        log(f"📈 TP Dinámico ajustado ({symbol}): ${nuevo_tp:.4f} (días: {dias_abierto})")
                        # V3.0: Ya no se envía Telegram individual
                        # enviar_telegram(f"""... TP dinámico ajustado ...""")
                        
                    except Exception as e:
                        log(f"⚠️ Error creando TP dinámico: {e}")
                        
            except Exception as e:
                pass
                
    except Exception as e:
        log(f"⚠️ Error en ajustar_tp_dinamico: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# EJECUTAR ORDEN DE FUTUROS
# ═══════════════════════════════════════════════════════════════════════════════
def ejecutar_orden(client, symbol, side, cantidad, tp=None, sl=None):
    """Ejecuta una orden de mercado en futuros con TP y SL inicial"""
    try:
        # Orden de mercado
        orden = client.futures_create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=cantidad
        )
        
        order_id = orden['orderId']
        log(f"   ✅ Orden ejecutada: {order_id}")
        
        # Configurar TP y SL iniciales
        if tp and sl:
            # Obtener precisión del precio
            info = obtener_exchange_info(client)
            symbol_info = next((s for s in info['symbols'] if s['symbol'] == symbol), None)
            if symbol_info:
                price_precision = int(symbol_info['pricePrecision'])
                tp = round(tp, price_precision)
                sl = round(sl, price_precision)
            
            # Take Profit
            try:
                tp_side = 'SELL' if side == 'BUY' else 'BUY'
                client.futures_create_order(
                    symbol=symbol,
                    side=tp_side,
                    type='TAKE_PROFIT_MARKET',
                    stopPrice=tp,
                    closePosition=True
                )
                log(f"   📈 TP configurado: ${tp}")
            except Exception as e:
                log(f"   ⚠️ Error creando TP: {e}")
            
            # V5.0: Stop Loss inicial con STOP_MARKET tradicional (método de enero)
            try:
                sl_side = 'SELL' if side == 'BUY' else 'BUY'
                client.futures_create_order(
                    symbol=symbol,
                    side=sl_side,
                    type='STOP_MARKET',
                    stopPrice=str(sl),
                    closePosition='true'
                )
                log(f"   📉 SL inicial: ${sl} (Trailing activo)")
            except Exception as e:
                log(f"   ⛔ ERROR CRÍTICO: SL inicial no creado para {symbol}: {e}")
                # V3.9: Reintentar SL con mark_price actual como fallback
                try:
                    mark_info = client.futures_position_information(symbol=symbol)
                    if mark_info:
                        mk_price = float(mark_info[0]['markPrice'])
                        if side == 'BUY':  # LONG
                            sl_retry = mk_price * (1 - 0.03)  # V4.0: -3%
                        else:  # SHORT
                            sl_retry = mk_price * (1 + 0.03)  # V4.0: +3%
                        # V5.2: Aplicar precisión correcta para tokens baratos
                        try:
                            info_ex = obtener_exchange_info(client)
                            sym_info = next((s for s in info_ex['symbols'] if s['symbol'] == symbol), None)
                            if sym_info:
                                sl_retry = round(sl_retry, int(sym_info['pricePrecision']))
                        except Exception:
                            sl_retry = round(sl_retry, 6)  # Fallback a 6 decimales
                        sl_side = 'SELL' if side == 'BUY' else 'BUY'
                        success, _ = crear_orden_sl(client, symbol, sl_side, sl_retry, cantidad)
                        if success:
                            log(f"   ✅ SL de emergencia creado en retry: ${sl_retry:.6f}")
                        else:
                            log(f"   ⛔ SL NO CREADO para {symbol}. Guardian será protección.")
                except Exception as e2:
                    log(f"   ⛔ SL NO CREADO para {symbol} (retry falló: {e2}). Guardian será protección.")
        
        return True, order_id
        
    except Exception as e:
        log(f"   ❌ Error ejecutando orden: {e}")
        return False, str(e)

# ═══════════════════════════════════════════════════════════════════════════════
# VERIFICAR POSICIONES CERRADAS (P&L)
# ═══════════════════════════════════════════════════════════════════════════════
posiciones_notificadas = set()


def inicializar_cache_trades(client, limit=50):
    """Carga trades ya existentes al iniciar para no re-loguear historial antiguo."""
    global posiciones_notificadas
    try:
        trades = client.futures_account_trades(limit=limit)
        for trade in trades:
            pnl = float(trade.get('realizedPnl', 0))
            if pnl == 0:
                continue
            unique_key = f"{trade.get('orderId', '')}_{trade.get('symbol', '')}_{pnl}"
            posiciones_notificadas.add(unique_key)
        log(f"📦 Cache de trades inicializada: {len(posiciones_notificadas)} eventos previos")
    except Exception as e:
        log(f"⚠️ Error inicializando cache de trades: {e}")

def verificar_posiciones_cerradas(client):
    """
    Verifica trades recientes y acumula estadísticas semanales (V3.0).
    
    Esta función:
    1. Obtiene los últimos 20 trades de la cuenta
    2. Filtra los que tienen PNL realizado (posiciones cerradas)
    3. Acumula ganancias/pérdidas en stats_semanales
    4. No envía notificaciones individuales (solo log)
    
    Las estadísticas se incluirán en el resumen semanal del viernes.
    """
    global posiciones_notificadas, stats_semanales
    try:
        # Obtener los últimos 20 trades de futuros
        trades = client.futures_account_trades(limit=20)
        
        for trade in trades:
            order_id = trade.get('orderId', '')
            symbol = trade.get('symbol', '')
            pnl = float(trade.get('realizedPnl', 0))
            
            # Ignorar trades sin PNL realizado (posiciones aún abiertas)
            if pnl == 0:
                continue
            
            # Crear clave única para evitar contar el mismo trade dos veces
            unique_key = f"{order_id}_{symbol}_{pnl}"
            if unique_key in posiciones_notificadas:
                continue
            
            # Marcar como procesado
            posiciones_notificadas.add(unique_key)
            
            # Limpiar set si crece demasiado (evitar memory leak)
            if len(posiciones_notificadas) > 200:
                posiciones_notificadas.clear()  # V5.2: Reset completo (set no tiene orden)
            
            # ═══════════════════════════════════════════════════════════════
            # ACUMULAR ESTADÍSTICAS SEMANALES (V3.0)
            # ═══════════════════════════════════════════════════════════════
            if pnl > 0:
                # Trade ganador: incrementar contador y sumar ganancia
                stats_semanales["ganados"] += 1
                stats_semanales["monto_ganado"] += pnl
                log(f"💰 Posición ganada ({symbol}): +${pnl:.2f}")
            else:
                # Trade perdedor: incrementar contador y sumar pérdida
                stats_semanales["perdidos"] += 1
                stats_semanales["monto_perdido"] += abs(pnl)
                log(f"💸 Posición perdida ({symbol}): -${abs(pnl):.2f}")
            
            # V3.0: Actualizar también estadísticas diarias (para Kelly Criterion)
            actualizar_stats_trade(pnl)
            
            # V5.3: Registrar trade cerrado en SQLite
            try:
                registrar_trade_cerrado(symbol, pnl)
            except Exception as db_err:
                if LOG_DETALLADO:
                    log(f"⚠️ Error registrando cierre en DB: {db_err}")
            
            # V3.0: NO SE ENVÍA TELEGRAM INDIVIDUAL
            # Todas las estadísticas se incluyen en el resumen semanal del viernes
            
    except Exception as e:
        if LOG_DETALLADO:
            log(f"⚠️ Error verificando posiciones cerradas: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# ENVIAR RESUMEN SEMANAL (V3.0) - Solo viernes a las 18:00
# ═══════════════════════════════════════════════════════════════════════════════
def es_viernes_18h():
    """
    Verifica si es viernes a las 18:00 (hora Guatemala).
    """
    ahora = hora_local()
    es_viernes = ahora.weekday() == 4
    es_hora_18 = ahora.hour == 18
    return es_viernes and es_hora_18


# V5.3: Resumen diario a las 22:00 hora Guatemala
_resumen_diario_enviado = False

def es_hora_resumen_diario():
    """Verifica si es hora de enviar el resumen diario (22:00 Guatemala)."""
    return hora_local().hour == 22

def enviar_resumen_diario(client):
    """V5.3: Envía resumen diario con balance, PNL y métricas de riesgo."""
    try:
        fecha = hora_local().strftime("%d/%m/%Y")
        balance = obtener_balance(client)
        
        # Registrar balance fin de día
        registrar_balance_diario(hora_local().strftime("%Y-%m-%d"), balance_fin=balance)
        
        # Obtener métricas
        metricas_texto = generar_resumen_metricas()
        
        pnl_dia = stats_diarias.get('pnl_dia', 0)
        emoji_dia = "📈" if pnl_dia >= 0 else "📉"
        
        mensaje = f"""📊 *RESUMEN DIARIO V5.3*
📅 {fecha}

━━━━━━━━━━━━━━━━━━━━━━━
💵 *Balance:* `${balance:.2f}`
{emoji_dia} *PNL Hoy:* `${pnl_dia:+.2f}`

{metricas_texto}

━━━━━━━━━━━━━━━━━━━━━━━
🤖 Bot Binance V5.3 Activo ✅"""
        
        enviar_telegram(mensaje)
        log(f"📊 Resumen diario enviado: {fecha}")
        
        # Registrar balance inicio del nuevo día
        registrar_balance_diario(
            (hora_local() + timedelta(days=1)).strftime("%Y-%m-%d"),
            balance_inicio=balance
        )
    except Exception as e:
        log(f"⚠️ Error enviando resumen diario: {e}")

def enviar_resumen_semanal(client):
    """
    Genera y envía un resumen semanal por Telegram.
    
    Este resumen incluye:
    - Balance inicial del proyecto (04/01/2026): $5,293.49
    - Balance actual de la cuenta
    - Diferencia en USD desde el inicio del proyecto
    - ROI total del proyecto (%)
    - Estadísticas de la semana (trades ganados/perdidos)
    - ROI de la semana actual
    
    El resumen se envía cada viernes a las 18:00 y las estadísticas
    semanales se reinician para la nueva semana.
    """
    global stats_semanales
    try:
        # Obtener fecha actual formateada
        fecha_actual = hora_local().strftime("%d/%m/%Y")
        
        # Obtener balance actual de Binance
        balance_actual = obtener_balance(client)
        
        # ═══════════════════════════════════════════════════════════════════
        # CÁLCULO DE ROI TOTAL DEL PROYECTO
        # ═══════════════════════════════════════════════════════════════════
        # Ganancia total = Balance actual - Balance inicial del proyecto
        ganancia_total = balance_actual - BALANCE_INICIAL_PROYECTO
        
        # ROI Total = (Ganancia / Balance Inicial) * 100
        # Ejemplo: ($6,307 - $5,293) / $5,293 * 100 = 19.15%
        roi_total = (ganancia_total / BALANCE_INICIAL_PROYECTO) * 100
        
        # ═══════════════════════════════════════════════════════════════════
        # CÁLCULO DE ESTADÍSTICAS SEMANALES
        # ═══════════════════════════════════════════════════════════════════
        # Resultado neto de la semana = Ganancias - Pérdidas
        resultado_semana = stats_semanales["monto_ganado"] - stats_semanales["monto_perdido"]
        
        # Emoji según resultado positivo o negativo
        emoji_semana = "💹" if resultado_semana >= 0 else "📉"
        emoji_total = "💹" if ganancia_total >= 0 else "📉"
        
        # Calcular ROI semanal si hay balance inicial de semana
        if stats_semanales["balance_inicio_semana"] > 0:
            roi_semanal = (resultado_semana / stats_semanales["balance_inicio_semana"]) * 100
        else:
            roi_semanal = 0
        
        # ═══════════════════════════════════════════════════════════════════
        # V5.2: INTERÉS COMPUESTO — Proyecciones a corto y largo plazo
        # ═══════════════════════════════════════════════════════════════════
        FECHA_INICIO_PROYECTO = datetime(2026, 2, 9)  # V3.7 reset
        dias_operando = max(1, (hora_local().replace(tzinfo=None) - FECHA_INICIO_PROYECTO).days)
        
        if balance_actual > 0 and BALANCE_INICIAL_PROYECTO > 0:
            # Tasa diaria compuesta: (balance_final / balance_inicial) ^ (1/días) - 1
            factor_diario = (balance_actual / BALANCE_INICIAL_PROYECTO) ** (1 / dias_operando)
            tasa_diaria_pct = (factor_diario - 1) * 100
            
            # Proyecciones con interés compuesto
            proy_30d = balance_actual * (factor_diario ** 30)
            proy_90d = balance_actual * (factor_diario ** 90)
            proy_365d = balance_actual * (factor_diario ** 365)
            
            # ROI anualizado compuesto
            roi_anual = ((factor_diario ** 365) - 1) * 100
        else:
            tasa_diaria_pct = 0
            proy_30d = proy_90d = proy_365d = balance_actual
            roi_anual = 0
        
        # ═══════════════════════════════════════════════════════════════════
        # CONSTRUIR MENSAJE DE TELEGRAM
        # ═══════════════════════════════════════════════════════════════════
        mensaje = f"""📊 *RESUMEN SEMANAL BINANCE V5.2*
📅 Fecha: {fecha_actual}

━━━━━━━━━━━━━━━━━━━━━━━
📈 *RENDIMIENTO TOTAL DEL PROYECTO*
━━━━━━━━━━━━━━━━━━━━━━━
💰 *Balance Inicial:* `${BALANCE_INICIAL_PROYECTO:.2f}`
💵 *Balance Actual:* `${balance_actual:.2f}`
{emoji_total} *Ganancia Total:* `${ganancia_total:.2f}`
📊 *ROI Total:* `{roi_total:.2f}%`
📆 *Días operando:* `{dias_operando}`
💹 *Tasa diaria compuesta:* `{tasa_diaria_pct:+.3f}%`

━━━━━━━━━━━━━━━━━━━━━━━
🔮 *PROYECCIÓN INTERÉS COMPUESTO*
━━━━━━━━━━━━━━━━━━━━━━━
📅 *30 días:* `${proy_30d:,.2f}`
📅 *90 días:* `${proy_90d:,.2f}`
📅 *1 año:* `${proy_365d:,.2f}`
📊 *ROI anualizado:* `{roi_anual:+.1f}%`

━━━━━━━━━━━━━━━━━━━━━━━
📋 *ESTA SEMANA*
━━━━━━━━━━━━━━━━━━━━━━━
✅ *Trades Ganados:* `{stats_semanales['ganados']}`
❌ *Trades Perdidos:* `{stats_semanales['perdidos']}`
💰 *Ganancias:* `+${stats_semanales['monto_ganado']:.2f}`
💸 *Pérdidas:* `-${stats_semanales['monto_perdido']:.2f}`
🛡️ *Cierres Guardian:* `{stats_semanales['cierres_guardian']}`
{emoji_semana} *Resultado Semana:* `${resultado_semana:.2f}`
📈 *ROI Semanal:* `{roi_semanal:.2f}%`

━━━━━━━━━━━━━━━━━━━━━━━
🤖 Bot Binance V5.3 Activo ✅"""
        
        # V5.3: Añadir métricas de riesgo al resumen
        try:
            metricas_texto = generar_resumen_metricas()
            mensaje += f"\n\n{metricas_texto}"
        except Exception:
            pass
        
        # Enviar mensaje por Telegram
        enviar_telegram(mensaje)
        log(f"📊 Resumen semanal enviado: {fecha_actual}")
        
        # ═══════════════════════════════════════════════════════════════════
        # RESETEAR ESTADÍSTICAS PARA LA NUEVA SEMANA
        # ═══════════════════════════════════════════════════════════════════
        stats_semanales["balance_inicio_semana"] = balance_actual  # Guardar balance actual como inicio
        stats_semanales["ganados"] = 0
        stats_semanales["perdidos"] = 0
        stats_semanales["monto_ganado"] = 0
        stats_semanales["monto_perdido"] = 0
        stats_semanales["cierres_guardian"] = 0
        stats_semanales["ultimo_resumen"] = hora_local()
        
    except Exception as e:
        log(f"⚠️ Error enviando resumen semanal: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO PRINCIPAL DE TRADING (Gemini 2.0 + Fear & Greed) - NEW SDK
# ═══════════════════════════════════════════════════════════════════════════════
def ejecutar_trading(client, gemini_client):
    log("\n" + "="*60)
    log("🧠 GEMINI 2.0 + FEAR & GREED: Iniciando ciclo de análisis...")
    log("="*60)
    
    try:
        saldo = obtener_balance(client)
        if saldo < 1:
            log("⚠️ Balance insuficiente para operar")
            return
            
        log(f"💰 Balance disponible: ${saldo:.2f} USDT")
        
        # Verificar espacios disponibles
        pos_abiertas = contar_posiciones_abiertas(client)
        espacios_disponibles = MAX_POSICIONES - pos_abiertas
        log(f"📊 Posiciones: {pos_abiertas}/{MAX_POSICIONES} | Espacios: {espacios_disponibles}")
        
        if espacios_disponibles <= 0:
            log("� Posiciones llenas. Monitoreando trailing SL...")
            return
        
        # Obtener Fear & Greed Index
        fg_valor, fg_clasificacion = obtener_fear_greed()
        log(f"🎭 Fear & Greed Index: {fg_valor}/100 ({fg_clasificacion})")
        
        # Obtener símbolos ya con posición (para evitar duplicados)
        simbolos_con_posicion = obtener_simbolos_con_posicion(client)
        
        # Obtener y analizar activos
        simbolos = obtener_simbolos_futuros(client)
        log(f"� Analizando top {len(simbolos)} pares por volumen...")
        
        # Lista para guardar oportunidades
        oportunidades = []
        
        for symbol in simbolos:
            # Saltar si ya tenemos posición en este símbolo
            if symbol in simbolos_con_posicion:
                log(f"⏭️ Saltando {symbol} (ya tiene posición)")
                continue
                
            try:
                # ═══════════════════════════════════════════════════════════════════
                # V5.3: MULTI-TIMEFRAME — Descargar velas 1h Y 4h
                # ═══════════════════════════════════════════════════════════════════
                velas_1h = obtener_velas(client, symbol, '1h', VELAS_CANTIDAD)
                if not velas_1h or len(velas_1h) < 50:
                    continue
                
                velas_4h = obtener_velas(client, symbol, '4h', 100)
                
                log(f"🧠 Analizando: {symbol} (1h: {len(velas_1h)} velas | 4h: {len(velas_4h) if velas_4h else 0} velas)")
                
                # ═══════════════════════════════════════════════════════════════════
                # V5.3: CALCULAR 14 INDICADORES para AMBAS temporalidades
                # ═══════════════════════════════════════════════════════════════════
                klines_1h = [[v['timestamp'], v['open'], v['high'], v['low'], v['close'], v['volume']] for v in velas_1h]
                ind_1h = analizar_indicadores_completo(klines_1h)
                
                ind_4h = None
                if velas_4h and len(velas_4h) >= 50:
                    klines_4h = [[v['timestamp'], v['open'], v['high'], v['low'], v['close'], v['volume']] for v in velas_4h]
                    ind_4h = analizar_indicadores_completo(klines_4h)
                
                if not ind_1h:
                    log(f"   ⚠️ No se pudieron calcular indicadores para {symbol}")
                    continue
                
                # Usar 1h como referencia principal
                indicadores = ind_1h
                precio_actual = ind_1h['precio_actual']
                precios_1h = [v['close'] for v in velas_1h[-100:]]
                precio_max_1h = max(precios_1h)
                precio_min_1h = min(precios_1h)
                volatilidad = ((precio_max_1h - precio_min_1h) / precio_actual) * 100
                posicion_rango = ((precio_actual - precio_min_1h) / (precio_max_1h - precio_min_1h) * 100) if precio_max_1h != precio_min_1h else 50
                
                # ═══════════════════════════════════════════════════════════════════
                # V5.3: PRE-FILTRO EN CÓDIGO — Ahorrar llamadas a Gemini
                # Si no hay señal clara → skip sin gastar API
                # ═══════════════════════════════════════════════════════════════════
                rsi = ind_1h['rsi']
                tendencia = (ind_1h.get('tendencia_ema', '') or '').upper()
                
                # Skip si RSI neutral + tendencia lateral + rango medio
                if (40 < rsi < 60 and 'LATERAL' in tendencia and 35 < posicion_rango < 65):
                    if LOG_DETALLADO:
                        log(f"   ⏭️ {symbol}: Pre-filtro skip (RSI {rsi:.0f}, {tendencia}, rango {posicion_rango:.0f}%)")
                    continue
                
                # ═══════════════════════════════════════════════════════════════════
                # V5.3: PREPARAR LAS 200 VELAS CRUDAS para cotejo completo
                # Gemini puede cotejar patrones en las velas vs los indicadores
                # ═══════════════════════════════════════════════════════════════════
                velas_csv_lines = []
                for v in velas_1h:
                    velas_csv_lines.append(
                        f"{v['open']:.6f},{v['high']:.6f},{v['low']:.6f},{v['close']:.6f},{v['volume']:.0f}"
                    )
                velas_csv = "\n".join(velas_csv_lines)
                
                # ═══════════════════════════════════════════════════════════════════
                # V5.3: PROMPT ENRIQUECIDO — 14 indicadores × 2 temporalidades
                #        + 200 velas crudas para detección de patrones
                # ═══════════════════════════════════════════════════════════════════
                
                # Bloque 4h (si disponible)
                bloque_4h = ""
                if ind_4h:
                    precios_4h = [v['close'] for v in velas_4h[-50:]]
                    vol_4h = ((max(precios_4h) - min(precios_4h)) / precio_actual) * 100 if precios_4h else 0
                    rango_4h = ((precio_actual - min(precios_4h)) / (max(precios_4h) - min(precios_4h)) * 100) if precios_4h and max(precios_4h) != min(precios_4h) else 50
                    bloque_4h = f"""
══════════════════════════════════
TEMPORALIDAD 4H (100 velas = ~17 días)
══════════════════════════════════
- RSI(14): {ind_4h['rsi']:.1f}
- Tendencia EMA: {ind_4h['tendencia_ema']} (EMA20: ${ind_4h['ema20']}, EMA50: ${ind_4h['ema50']})
- MACD: {ind_4h['macd']['macd']:.6f} | Signal: {ind_4h['macd']['signal']:.6f} | Histograma: {ind_4h['macd']['histograma']:.6f}
- Bollinger: Sup ${ind_4h['bollinger']['superior']} | Inf ${ind_4h['bollinger']['inferior']} | Pos: {ind_4h['bollinger']['posicion']}%
- ATR(14): ${ind_4h['atr']:.6f} ({ind_4h['atr_percent']:.2f}%)
- Volumen relativo: {ind_4h['volumen_relativo']}x
- Soporte: ${ind_4h['soporte']} ({ind_4h['dist_soporte']:.2f}%) | Resistencia: ${ind_4h['resistencia']} ({ind_4h['dist_resistencia']:.2f}%)
- Volatilidad: {vol_4h:.2f}% | Pos en rango: {rango_4h:.1f}%"""
                
                prompt = f"""Eres un trader profesional de criptomonedas con análisis técnico y fundamental.
Analiza TODOS los indicadores y las velas crudas antes de decidir.

MERCADO GLOBAL:
🎭 Fear & Greed Index: {fg_valor}/100 ({fg_clasificacion})
- 0-25: Extreme Fear (oportunidad de compra, NUNCA SHORT)
- 26-45: Fear (considerar LONGs en soportes)
- 46-55: Neutral
- 56-75: Greed (precaución con LONGs)
- 76-100: Extreme Greed (preferir SHORTs o WAIT)

══════════════════════════════════
ANÁLISIS COMPLETO DE {symbol}
══════════════════════════════════

TEMPORALIDAD 1H (200 velas = ~8 días)
══════════════════════════════════
- Precio actual: ${precio_actual}
- RSI(14): {ind_1h['rsi']:.1f}
- Tendencia EMA: {ind_1h['tendencia_ema']} (EMA20: ${ind_1h['ema20']}, EMA50: ${ind_1h['ema50']})
- MACD: {ind_1h['macd']['macd']:.6f} | Signal: {ind_1h['macd']['signal']:.6f} | Histograma: {ind_1h['macd']['histograma']:.6f}
- Bollinger: Sup ${ind_1h['bollinger']['superior']} | Med ${ind_1h['bollinger']['media']} | Inf ${ind_1h['bollinger']['inferior']} | Pos: {ind_1h['bollinger']['posicion']}%
- ATR(14): ${ind_1h['atr']:.6f} ({ind_1h['atr_percent']:.2f}%)
- Volumen relativo: {ind_1h['volumen_relativo']}x
- Soporte: ${ind_1h['soporte']} ({ind_1h['dist_soporte']:.2f}%) | Resistencia: ${ind_1h['resistencia']} ({ind_1h['dist_resistencia']:.2f}%)
- Volatilidad: {volatilidad:.2f}% | Pos en rango: {posicion_rango:.1f}%
{bloque_4h}

══════════════════════════════════
LAS 200 VELAS 1H COMPLETAS (open,high,low,close,volume)
Analiza patrones: dojis, envolventes, doble techo/suelo, divergencias RSI.
Coteja estos datos con los indicadores calculados arriba.
══════════════════════════════════
{velas_csv}

REGLAS ESTRICTAS:
1. Confianza mínima: 70%
2. NUNCA operar CONTRA la tendencia EMA dominante
3. Si tendencia ALCISTA → solo LONG o WAIT (PROHIBIDO SHORT)
4. Si tendencia BAJISTA → solo SHORT o WAIT (PROHIBIDO LONG)
5. Si Fear < 25 → SOLO LONGs o WAIT (NUNCA SHORT)
6. Si Greed > 75 → PREFERIR SHORTs o WAIT
7. Si precio en 20% inferior del rango → considerar LONG
8. Si precio en 80% superior del rango → considerar SHORT
9. Si MACD histograma cambia de signo → confirma entrada
10. Si ambas temporalidades (1h y 4h) coinciden en dirección → mayor confianza
11. Si divergencia entre RSI y precio → señal fuerte
12. Elige temporalidad: 1h si volatilidad >2%, 4h si volatilidad <2%

Responde SOLO con este JSON, sin explicación adicional:
{{"ACCION": "LONG/SHORT/WAIT", "CONFIANZA": 0.75, "TEMPORALIDAD": "1h", "RAZON": "explicacion breve"}}"""
                
                # V3.7: Retry logic con exponential backoff para errores 429
                MAX_RETRIES = 3
                respuesta = None
                for attempt in range(MAX_RETRIES):
                    try:
                        response = gemini_client.models.generate_content(
                            model='gemini-2.0-flash',
                            contents=prompt
                        )
                        respuesta = response.text
                        break
                    except Exception as api_error:
                        error_str = str(api_error)
                        if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                            if attempt < MAX_RETRIES - 1:
                                wait_time = 15 * (attempt + 1)
                                log(f"   ⏳ API limit alcanzado, esperando {wait_time}s...")
                                time.sleep(wait_time)
                                continue
                        raise api_error
                
                if not respuesta:
                    log(f"   ⚠️ No se pudo obtener respuesta de Gemini para {symbol}")
                    continue
                
                # V3.8: Validación robusta de JSON
                try:
                    respuesta_limpia = respuesta.replace("```json","").replace("```","").strip()
                    data = json.loads(respuesta_limpia)
                    
                    if "ACCION" not in data or "CONFIANZA" not in data:
                        log(f"   ⚠️ Respuesta IA incompleta, saltando {symbol}")
                        continue
                        
                except json.JSONDecodeError as e:
                    log(f"   ⚠️ JSON inválido de IA para {symbol}, saltando")
                    continue
                
                accion = data.get('ACCION', 'WAIT')
                confianza = float(data.get('CONFIANZA', 0))
                temporalidad = data.get('TEMPORALIDAD', '1h')
                razon = data.get('RAZON', 'Sin razón')
                
                if confianza > 1:
                    confianza = confianza / 100
                
                if temporalidad not in TEMPORALIDADES:
                    temporalidad = '1h'
                
                # ═══════════════════════════════════════════════════════════════════
                # V5.3: VALIDACIÓN POST-IA — El código FUERZA las reglas
                # ═══════════════════════════════════════════════════════════════════
                
                # REGLA 1: NO SHORT en Extreme Fear
                if fg_valor < 25 and accion == "SHORT":
                    log(f"   ⛔ REGLA: SHORT rechazado en Extreme Fear (F&G={fg_valor})")
                    accion = "WAIT"
                    razon = f"SHORT rechazado: F&G {fg_valor} < 25 (Extreme Fear)"
                    confianza = 0
                
                # REGLA 2: NO operar CONTRA la tendencia EMA
                tendencia_ema = (ind_1h.get('tendencia_ema', '') or '').upper()
                if 'ALCISTA' in tendencia_ema and accion == "SHORT":
                    log(f"   ⛔ REGLA: SHORT rechazado en tendencia ALCISTA ({tendencia_ema})")
                    accion = "WAIT"
                    confianza = 0
                elif 'BAJISTA' in tendencia_ema and accion == "LONG":
                    log(f"   ⛔ REGLA: LONG rechazado en tendencia BAJISTA ({tendencia_ema})")
                    accion = "WAIT"
                    confianza = 0
                
                # V5.3 REGLA 3: Si 4h contradice 1h, reducir confianza
                if ind_4h and confianza > 0:
                    tend_4h = (ind_4h.get('tendencia_ema', '') or '').upper()
                    if accion == "LONG" and 'BAJISTA' in tend_4h:
                        confianza *= 0.7  # Penalizar 30%
                        log(f"   ⚠️ 4h contradice 1h (BAJISTA vs LONG): confianza reducida a {int(confianza*100)}%")
                    elif accion == "SHORT" and 'ALCISTA' in tend_4h:
                        confianza *= 0.7
                        log(f"   ⚠️ 4h contradice 1h (ALCISTA vs SHORT): confianza reducida a {int(confianza*100)}%")
                
                conf_pct = int(confianza * 100)
                log(f"   📊 IA: {accion} | Confianza: {conf_pct}% | Temp: {temporalidad}")
                log(f"   💭 {razon[:80]}")
                
                # Guardar oportunidad si es válida
                if accion in ["LONG", "SHORT"] and confianza >= CONFIANZA_MINIMA:
                    oportunidades.append({
                        'symbol': symbol,
                        'accion': accion,
                        'confianza': confianza,
                        'temporalidad': temporalidad,
                        'razon': razon,
                        'precio_actual': precio_actual,
                        'volatilidad': volatilidad,
                        'indicadores': indicadores
                    })
                    log(f"   ✨ Oportunidad guardada!")
                    # V5.3: Registrar decisión ejecutable en SQLite
                    try:
                        registrar_decision(symbol, accion, confianza, temporalidad, razon[:200], fg_valor, True)
                    except Exception:
                        pass
                elif accion == "WAIT":
                    log(f"   ⏸️ IA decide esperar")
                else:
                    log(f"   ⏸️ Confianza {conf_pct}% < {int(CONFIANZA_MINIMA*100)}%")
                    
            except Exception as e:
                log(f"   ⚠️ Error en {symbol}: {e}")
                
            time.sleep(TIEMPO_POR_ACTIVO)
        
        # Ordenar oportunidades por confianza (mayor primero)
        oportunidades.sort(key=lambda x: x['confianza'], reverse=True)
        
        log(f"\n🎯 Oportunidades encontradas: {len(oportunidades)}")
        
        # Ejecutar las mejores oportunidades (hasta llenar espacios)
        ejecutadas = 0
        for op in oportunidades:
            if ejecutadas >= espacios_disponibles:
                log(f"✅ Espacios llenos. {len(oportunidades) - ejecutadas} oportunidades pendientes.")
                break
            
            # V3.4: Verificar drawdown ANTES de cada orden
            # Esto evita ejecutar múltiples órdenes si el balance ya bajó
            balance_pre_orden = obtener_balance(client)
            if not verificar_drawdown_diario(balance_pre_orden):
                log(f"🛑 Drawdown detectado. Deteniendo ejecución de órdenes.")
                break
            
            symbol = op['symbol']
            accion = op['accion']
            confianza = op['confianza']
            temporalidad = op['temporalidad']
            precio_actual = op['precio_actual']
            razon = op['razon']
            indicadores = op.get('indicadores', None)  # V3.0: Obtenemos indicadores
            
            conf_pct = int(confianza * 100)
            
            # ═════════════════════════════════════════════════════════════════
            # V3.0: KELLY CRITERION PARA POSITION SIZING
            # Calcula el monto óptimo basándose en win-rate histórico
            # ═════════════════════════════════════════════════════════════════
            saldo_disponible = saldo * ESCUDO_TRABAJO
            if KELLY_ACTIVO:
                monto = calcular_kelly(saldo_disponible, confianza)
            else:
                monto = calcular_monto(saldo, confianza)
            
            # Obtener TP/SL según temporalidad
            config = TP_SL_CONFIG.get(temporalidad, TP_SL_CONFIG["1h"])
            
            if accion == "LONG":
                tp = precio_actual * (1 + config["tp"])
                # ═════════════════════════════════════════════════════════════
                # V3.0: ATR PARA STOP LOSS DINÁMICO
                # El SL se adapta a la volatilidad actual del mercado
                # ═════════════════════════════════════════════════════════════
                if ATR_SL_ACTIVO and indicadores and indicadores.get('atr', 0) > 0:
                    sl = calcular_sl_atr(precio_actual, indicadores['atr'], 'BUY')
                    log(f"   📊 SL dinámico ATR: ${sl:.4f} (ATR: ${indicadores['atr']:.4f})")
                else:
                    sl = precio_actual * (1 - config["sl"])
            else:  # SHORT
                tp = precio_actual * (1 - config["tp"])
                if ATR_SL_ACTIVO and indicadores and indicadores.get('atr', 0) > 0:
                    sl = calcular_sl_atr(precio_actual, indicadores['atr'], 'SELL')
                    log(f"   📊 SL dinámico ATR: ${sl:.4f} (ATR: ${indicadores['atr']:.4f})")
                else:
                    sl = precio_actual * (1 + config["sl"])
            
            # Configurar apalancamiento
            configurar_apalancamiento(client, symbol, APALANCAMIENTO)
            
            # Calcular cantidad
            cantidad = calcular_cantidad(client, symbol, monto * APALANCAMIENTO, precio_actual)
            
            if cantidad:
                side = 'BUY' if accion == 'LONG' else 'SELL'
                
                log(f"\n🚀 EJECUTANDO ORDEN #{ejecutadas + 1}")
                log(f"   📍 Par: {symbol} | Acción: {accion}")
                log(f"   💰 Monto: ${monto} | Cantidad: {cantidad}")
                log(f"   📈 TP: ${tp:.4f} | 📉 SL: ${sl:.4f}")
                log(f"   ⏱️ Temporalidad: {temporalidad}")
                log(f"   🎯 Confianza: {conf_pct}%")
                
                check, order_id = ejecutar_orden(client, symbol, side, cantidad, tp, sl)
                
                if check:
                    ejecutadas += 1
                    # La estadística se acumula en stats_semanales y se envía el viernes
                    log(f"   ✅ Orden ejecutada exitosamente: {symbol} {accion}")
                    # V5.3: Registrar trade en SQLite
                    try:
                        registrar_trade_abierto(
                            symbol=symbol, side=side, action=accion,
                            entry_price=precio_actual, quantity=cantidad,
                            confidence=confianza, temporalidad=temporalidad,
                            razon=razon[:200]
                        )
                    except Exception as db_err:
                        log(f"   ⚠️ Error registrando trade en DB: {db_err}")
            else:
                log(f"   ⚠️ Cantidad mínima no alcanzada para {symbol}")
        
        log(f"\n✅ Ciclo completado. {ejecutadas} órdenes ejecutadas.")
        
    except Exception as e:
        log(f"⚠️ Error en ciclo de trading: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTE DE INICIO
# ═══════════════════════════════════════════════════════════════════════════════
def generar_reporte_inicio(saldo, status_gemini, fg_valor, fg_clasificacion):
    """Genera un reporte detallado del estado inicial del bot"""
    reporte = f"""🤖 *BINANCE BOT V5.0 ONLINE*
🚀 BINANCE FUTUROS: `{status_gemini}`

💰 *BALANCE DETECTADO:*
💵 USDT Disponible: `${saldo:.2f}`
🛡️ Escudo 80/20 %
👨🏻‍💻 Trabajo 80%
🛟 Seguro 20%

⚙️ *CONFIGURACIÓN:*
🔧 Modo: `{'TESTNET' if USAR_TESTNET else 'PRODUCCIÓN'}`
📊 Apalancamiento: `x{APALANCAMIENTO}`
🎯 Confianza mínima: `{int(CONFIANZA_MINIMA*100)}%`
📈 Top activos: `{TOP_ACTIVOS}`
📉 Max posiciones: `{MAX_POSICIONES}`

🆕 *FUNCIONES V5.0:*
📊 **RESUMEN DIARIO:** Activado ✅
📍 Trailing SL: `1.5% activo` ✅
⏱️ Temporalidades: `{', '.join(TEMPORALIDADES)}`
🎭 Fear & Greed: `{fg_valor} ({fg_clasificacion})`

💸 *PROTECCIÓN FUNDING FEES:* 🟢 ACTIVA
⏰ Cierre por tiempo: `5 días máx`
📈 TP dinámico: `Después de 3 días`
💵 Funding vs PNL: `Auto-cierre si fees > ganancias`

🧠 *CEREBRO IA:*
🤖 Gemini 2.0 Flash (New SDK): `{status_gemini}`

⏰ HORARIO: 24/7 (Sin pausas)
🔄 Monitoreo: `cada {MONITOREO_INTERVALO}s`"""
    return reporte

# ═══════════════════════════════════════════════════════════════════════════════
# ARRANQUE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
log("🚀 Iniciando Bot Binance Futuros V5.0...")
log("📊 Daily Summary + Guardian System + New GenAI SDK")

# Conexión a Binance
try:
    client = conectar_binance()
    saldo = obtener_balance(client)
    log(f"✅ Conexión exitosa. Balance: ${saldo:.2f} USDT")
except Exception as e:
    log(f"❌ ERROR FATAL: No se pudo conectar a Binance: {e}")
    sys.exit()

# Configurar Gemini 2.0 - NUEVO SDK google-genai
status_gemini = "🔴 ERROR"
gemini_client = None
try:
    gemini_client = genai.Client(api_key=os.getenv("API_KEY_GEMINI"))
    status_gemini = "🟢 CONECTADO"
    log("🧠 Cargando Motor: Gemini 2.0 Flash (New SDK)... ✅")
except Exception as e:
    log(f"⚠️ Error cargando Gemini 2.0: {e}")
    sys.exit()

# Obtener Fear & Greed inicial
fg_valor, fg_clasificacion = obtener_fear_greed()
log(f"🎭 Fear & Greed Index: {fg_valor}/100 ({fg_clasificacion})")

# Reporte de inicio - V3.0: Solo log, no Telegram (el resumen viene el viernes)
reporte = generar_reporte_inicio(saldo, status_gemini, fg_valor, fg_clasificacion)
log(reporte)
# V3.0: Ya no se envía Telegram al iniciar
# enviar_telegram(reporte)  # Comentado - solo resumen semanal
log("📩 Telegram: Resumen semanal cada viernes a las 18:00")

# ═══════════════════════════════════════════════════════════════════════════════
# INICIALIZAR ESTADÍSTICAS SEMANALES (V3.0)
# ═══════════════════════════════════════════════════════════════════════════════
# Guardar balance actual como inicio de semana para calcular ROI semanal
stats_semanales["balance_inicio_semana"] = saldo
# Marcar que no se ha enviado resumen aún (None = nunca enviado)
stats_semanales["ultimo_resumen"] = None

# Evitar re-procesar trades históricos al reiniciar contenedor
inicializar_cache_trades(client)

# V5.3: Inicializar base de datos SQLite
inicializar_db()
log("📦 Base de datos SQLite inicializada")

# V5.3: Registrar balance de inicio del día
registrar_balance_diario(hora_local().strftime("%Y-%m-%d"), balance_inicio=saldo)

# Inicializar tracking de posiciones existentes
pos_iniciales = contar_posiciones_abiertas(client)
if pos_iniciales > 0:
    log(f"🛡️ {pos_iniciales} posiciones existentes detectadas. Activando Guardian + Trailing SL...")
    guardian_posiciones(client)  # Primero verificar emergencias
    verificar_ordenes_sl_existen(client)  # Verificar que tengan SL
    actualizar_trailing_sl(client)
else:
    log("✅ Sin posiciones abiertas. Listo para operar.")

log("✅ Bot V5.0 iniciado. Guardian + SL Coherence + Resumen Semanal activos...")

# ═══════════════════════════════════════════════════════════════════════════════
# BUCLE PRINCIPAL - 24/7 CON MONITOREO CONTINUO + GUARDIAN + RESUMEN SEMANAL
# ═══════════════════════════════════════════════════════════════════════════════
# Contador de ciclos para decidir cuándo hacer análisis completo
ciclo_analisis = 0
# Cada 4 ciclos de monitoreo (4 * 30s = 2 min) hacer análisis completo de mercado
CICLOS_PARA_ANALISIS = 4
# Variable para controlar que solo se envíe 1 resumen por viernes
resumen_enviado_esta_hora = False

while True:
    try:
        ciclo_analisis += 1
        
        # ═════════════════════════════════════════════════════════════════════
        # V3.0: GESTIÓN DE RIESGO AVANZADA - Verificación diaria
        # Reinicia stats al inicio de cada día y verifica drawdown máximo
        # ═════════════════════════════════════════════════════════════════════
        balance_actual = obtener_balance(client)
        
        # Verificar si es un nuevo día (reinicia stats_diarias)
        verificar_nuevo_dia(balance_actual)
        
        # Verificar drawdown máximo diario (-3%)
        # Si se supera, el bot pausa nuevos trades pero Guardian sigue activo
        puede_operar = verificar_drawdown_diario(balance_actual)
        
        # ═════════════════════════════════════════════════════════════════════
        # SCHEDULER OPERATIVO - control de carga CPU/API
        # ═════════════════════════════════════════════════════════════════════
        if GUARDIAN_ACTIVO and should_run_task("guardian", INTERVALO_GUARDIAN):
            guardian_posiciones(client)

        if GUARDIAN_ACTIVO and should_run_task("verificar_sl", INTERVALO_VERIFICAR_SL):
            verificar_ordenes_sl_existen(client)

        if should_run_task("trailing", INTERVALO_TRAILING):
            actualizar_trailing_sl(client)

        if should_run_task("trades_cerrados", INTERVALO_TRADES_CERRADOS):
            verificar_posiciones_cerradas(client)
        
        # ═════════════════════════════════════════════════════════════════════
        # RESUMEN SEMANAL - Solo viernes a las 18:00 (V3.0)
        # Envía un único mensaje por Telegram con el resumen de la semana
        # ═════════════════════════════════════════════════════════════════════
        if es_viernes_18h():
            if not resumen_enviado_esta_hora:
                enviar_resumen_semanal(client)
                resumen_enviado_esta_hora = True
        else:
            resumen_enviado_esta_hora = False
        
        # V5.3: RESUMEN DIARIO - Todos los días a las 22:00
        if es_hora_resumen_diario():
            if not _resumen_diario_enviado:
                enviar_resumen_diario(client)
                _resumen_diario_enviado = True
        else:
            _resumen_diario_enviado = False
        
        # Protección contra Funding Fees (cada ciclo de análisis para evitar spam API)
        if FUNDING_PROTECTION and ciclo_analisis >= CICLOS_PARA_ANALISIS:
            verificar_tiempo_posiciones(client)
            verificar_funding_vs_pnl(client)
            ajustar_tp_dinamico(client)
        
        # ═════════════════════════════════════════════════════════════════════
        # V3.0: TRADING - Solo si NO estamos pausados por drawdown
        # ═════════════════════════════════════════════════════════════════════
        # Cada N ciclos, hacer análisis completo de mercado
        if ciclo_analisis >= CICLOS_PARA_ANALISIS:
            if puede_operar:
                en_horario_bloqueado, motivo_horario = es_horario_protegido()
                en_pausa_noticias_activa, motivo_noticias = en_pausa_por_noticias()

                if en_horario_bloqueado:
                    log(f"⏸️ Trading pausado por horario protegido: {motivo_horario}")
                elif en_pausa_noticias_activa:
                    log(f"⏸️ Trading pausado por noticias: {motivo_noticias}")
                else:
                    # V3.9: Solo entrar a ejecutar_trading si hay espacios disponibles
                    pos_activas = contar_posiciones_abiertas(client)
                    if pos_activas < MAX_POSICIONES:
                        ejecutar_trading(client, gemini_client)
                    else:
                        log(f"📊 {pos_activas}/{MAX_POSICIONES} posiciones activas. Sin análisis IA.")
            else:
                log("⏸️ Trading pausado por protección de drawdown diario")
            ciclo_analisis = 0
        else:
            # Log de monitoreo controlado por intervalo para evitar ruido
            if should_run_task("log_monitoreo", INTERVALO_RESUMEN_POSICIONES) or ciclo_analisis == 1:
                pos_abiertas = contar_posiciones_abiertas(client)
                log(f"👁️ Monitoreo V5.0... Posiciones: {pos_abiertas}/{MAX_POSICIONES}")
                if pos_abiertas > 0:
                    log_resumen_posiciones(client)
        
        time.sleep(MONITOREO_INTERVALO)
        
    except Exception as e:
        log(f"⚠️ Error en bucle principal: {e}")
        time.sleep(60)
