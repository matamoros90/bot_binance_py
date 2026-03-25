# 🤖 BOT BINANCE FUTURES - GEMINI 2.5 FLASH
# Trading 24/7 de Criptomonedas con IA
# V5.3 - Multi-Timeframe + Prompt Enriquecido + SQLite + Métricas de Riesgo
# ═══════════════════════════════════════════════════════════════════════════════

from binance.client import Client
from binance.enums import *
import time, os, http.server, socketserver, threading, requests, json, sys, re
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
BOT_VERSION = "V5.12"
CONFIANZA_MINIMA = 0.65   # V5.12: 65% mínimo (antes 50% dejaba pasar trades basura)
ESCUDO_TRABAJO = 1.00     # 100% del balance disponible como base de calculo de monto
ESCUDO_SEGURO = 0.20      # 20% conceptual de reserva (no usado directamente en el sizing)
TIEMPO_POR_ACTIVO = 10    # Segundos entre análisis de cada activo
VELAS_CANTIDAD = 200      # Cantidad de velas a obtener
APALANCAMIENTO = 3        # Apalancamiento conservador x3
TOP_ACTIVOS = 30          # Activos a analizar por volumen (Aumentado para buscar más oportunidades)
MAX_POSICIONES = 10       # Máximo 10 posiciones simultáneas (Aumentado para High Frequency Day Trading)

# ═══════════════════════════════════════════════════════════════════════════════
# TRAILING STOP LOSS CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
TRAILING_SL_PERCENT = 0.025  # V5.12: 2.5% trailing (antes 1.5% — muy tight con 3x leverage)
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
KELLY_ACTIVO = True                 # V5.8: REACTIVADO - Usamos Kelly para gestionar riesgo en lugar del IA Constraint
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
TP_DINAMICO_DIAS = 1            # Después de 1 día (24h), ajustar TP
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
TEMPORALIDADES = ['15m']  # V5.8: Temporalidad más baja para Scalping/Day Trading Activo

# V5.8: Ajuste de Scalping para temporalidad de 15m
TP_SL_CONFIG = {
    "15m":  {"tp": 0.020, "sl": 0.008},    # V5.12: +2.0%, -0.8% (R:R 2.5:1) — más espacio para crecer
}

# V5.8: Modo rango (Ajustado a 15m)
TP_SL_RANGO_CONFIG = {
    "15m":  {"tp": 0.015, "sl": 0.006},     # V5.12: +1.5%, -0.6% (antes 1.0%)
}
FACTOR_MONTO_RANGO = 0.70         # Reducir exposición en mercado lateral

# V5.4: Filtro financiero mínimo por operación (EV neto)
FEE_ROUNDTRIP_EST = 0.0012        # 0.12% estimado ida+vuelta
SLIPPAGE_EST = 0.0006             # 0.06% slippage conservador
EV_MINIMO = 0.0                   # Desactivado: solo se usa EV como informacion, no como filtro duro

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
_tp_dinamico_cooldown = {}  # {symbol: timestamp} — evita reintentos de TP cada 30s
TP_DINAMICO_COOLDOWN = 3600  # 1 hora entre intentos de ajuste TP por símbolo

# ═══════════════════════════════════════════════════════════════════════════════
# SERVIDOR DE SALUD + API REST (KOYEB)
# ═══════════════════════════════════════════════════════════════════════════════
from expo_push import guardar_push_token

# Variables para almacenar último resumen (para servir via API)
_ultimo_resumen_diario = {}
_ultimo_resumen_semanal = {}
_servidor_inicio = time.time()

def servidor_salud():
    PORT = int(os.getenv("PORT", 8000))
    class Handler(http.server.SimpleHTTPRequestHandler):

        def _send_json(self, data, status=200):
            """Envía respuesta JSON con CORS headers."""
            body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            """CORS preflight."""
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
            self.end_headers()

        def do_POST(self):
            if self.path == "/api/register-push-token":
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length))
                    token = body.get("token", "")
                    if token:
                        guardar_push_token(token)
                        self._send_json({"ok": True, "message": "Token registrado"})
                    else:
                        self._send_json({"ok": False, "message": "Token vacío"}, 400)
                except Exception as e:
                    self._send_json({"ok": False, "message": str(e)}, 500)
            else:
                self._send_json({"error": "Not found"}, 404)

        def do_GET(self):
            path = self.path.split("?")[0]  # Ignorar query params

            if path == "/api/status":
                try:
                    fg_val, fg_label = obtener_fear_greed()
                    pos = contar_posiciones_abiertas(client) if client else 0
                    bal = obtener_balance(client) if client else 0
                    puede = verificar_drawdown_diario(bal) if client else False
                    self._send_json({
                        "version": BOT_VERSION,
                        "balance": round(bal, 2),
                        "posiciones_abiertas": pos,
                        "max_posiciones": MAX_POSICIONES,
                        "fear_greed": fg_val,
                        "fear_greed_label": fg_label,
                        "uptime_seconds": int(time.time() - _servidor_inicio),
                        "puede_operar": puede,
                        "timestamp": hora_local().isoformat(),
                    })
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)

            elif path == "/api/resumen-diario":
                self._send_json(_ultimo_resumen_diario or {
                    "fecha": hora_local().strftime("%d/%m/%Y"),
                    "balance": 0, "pnl_dia": 0,
                    "metricas": "", "timestamp": hora_local().isoformat(),
                })

            elif path == "/api/resumen-semanal":
                self._send_json(_ultimo_resumen_semanal or {
                    "balance_inicial": stats_semanales.get("balance_inicio_semana", 0),
                    "balance_actual": 0, "roi_semanal": 0,
                    "trades_ganados": stats_semanales.get("ganados", 0),
                    "trades_perdidos": stats_semanales.get("perdidos", 0),
                    "win_rate": 0, "profit_factor": 0,
                    "timestamp": hora_local().isoformat(),
                })

            elif path == "/api/trades":
                try:
                    from persistence import _get_conn
                    conn = _get_conn()
                    c = conn.cursor()
                    c.execute("""
                        SELECT id, symbol, side, action, pnl, confidence,
                               temporalidad, razon, closed_at
                        FROM trades
                        WHERE status = 'CLOSED' AND pnl != 0
                        ORDER BY closed_at DESC
                        LIMIT 20
                    """)
                    rows = c.fetchall()
                    conn.close()
                    trades = [dict(row) for row in rows]
                    self._send_json(trades)
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)

            elif path == "/api/metricas":
                try:
                    metricas = calcular_metricas_riesgo(dias=30)
                    self._send_json(metricas)
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)

            else:
                # Health check original
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(f"BINANCE BOT {BOT_VERSION} - SCORE + EV + FALLBACK".encode())

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
# FEAR & GREED INDEX Y MACROECONOMÍA TRADICIONAL
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

import yfinance as yf

def obtener_macros_financieras_para_gemini():
    """V5.10: Extrae comportamiento macroeconómico del mercado tradicional vía Yahoo Finance"""
    try:
        # Extraemos el comportamiento del S&P500
        sp500 = yf.Ticker("^GSPC").history(period="2d")
        if len(sp500) >= 2:
            close_ayer = sp500['Close'].iloc[0]
            close_hoy = sp500['Close'].iloc[1]
            variacion_sp500 = ((close_hoy - close_ayer) / close_ayer) * 100
        else:
            variacion_sp500 = 0.0

        if variacion_sp500 > 0.5:
            return f"SP500: +{variacion_sp500:.2f}% (ALCISTA - Mercado tradicional fuerte)"
        elif variacion_sp500 < -0.5:
            return f"SP500: {variacion_sp500:.2f}% (BAJISTA - Mercado tradicional débil)"
        else:
            return f"SP500: {variacion_sp500:.2f}% (NEUTRAL - Consolidación)"
    except Exception as e:
        log(f"⚠️ Error obteniendo datos de Yahoo Finance: {e}")
        return "Macro: NEUTRAL (API Error)"


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
    hoy = hora_local().strftime("%Y-%m-%d")
    
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
        # V5.10 FIX: Throttle al mensaje para evitar spam cada 30s
        log_throttled(
            "drawdown_pausado_msg",
            "⏸️ Bot pausado por drawdown diario. Esperando nuevo día...",
            cooldown=300  # Máximo 1 vez cada 5 minutos
        )
        return False
    
    balance_inicio = stats_diarias["balance_inicio_dia"]
    
    # Si no hay balance de inicio, no podemos calcular
    if balance_inicio <= 0:
        return True
    
    # Calcular drawdown actual
    drawdown = (balance_actual - balance_inicio) / balance_inicio
    stats_diarias["pnl_dia"] = balance_actual - balance_inicio
    
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
        confianza_ia: Confianza de la IA (0.66 a 1.0)
    
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
    
    # Prevenir ZeroDivisionError si b es 0
    if b <= 0:
        b = 1.5
        
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
# CÁLCULO DE MONTO SIMPLE - 5% FIJO DEL BALANCE
# ═══════════════════════════════════════════════════════════════════════════════
def calcular_monto(saldo, confianza):
    """Calcula un monto fijo del 5% del saldo operativo.
    
    - Usa el 100% del balance para el ESCUDO_TRABAJO (1.0).
    - El interés compuesto ocurre de forma natural: a mayor saldo, mayor monto en USD.
    - La confianza de la IA se usa solo para decidir si entrar o no (CONFIANZA_MINIMA),
      no para escalar agresivamente el tamaño de la posición.
    """
    saldo_disponible = saldo * ESCUDO_TRABAJO
    porcentaje = 5.0  # 5% fijo por operación sobre el saldo disponible
    monto = saldo_disponible * (porcentaje / 100.0)

    if LOG_DETALLADO:
        log(f"   💰 Monto fijo: {porcentaje:.1f}% del saldo operativo | ${monto:.2f}")

    return max(1, round(monto, 2))


def calcular_ev_neto(confianza, tp_pct, sl_pct, modo_mercado="TREND"):
    """Calcula valor esperado neto por operación descontando fees/slippage."""
    confianza = max(0.0, min(0.99, confianza))
    penalizacion_modo = 0.05 if modo_mercado == "RANGE" else 0.0
    # Evita sobreestimar probabilidad de acierto solo por confianza IA
    p_win = max(0.40, min(0.90, confianza - penalizacion_modo))

    ev_bruto = (p_win * tp_pct) - ((1 - p_win) * sl_pct)
    costos_estimados = FEE_ROUNDTRIP_EST + SLIPPAGE_EST
    ev_neto = ev_bruto - costos_estimados

    return ev_neto, p_win


def generar_senal_fallback(ind_actual, posicion_rango, fg_valor):
    """Genera señal técnica de respaldo cuando la IA responde WAIT."""
    if not ind_actual:
        return None, 0.0, None, "Sin datos de indicadores"

    t1 = (ind_actual.get('tendencia_ema', '') or '').upper()
    rsi = float(ind_actual.get('rsi', 50))
    macd_hist = float((ind_actual.get('macd') or {}).get('histograma', 0))
    atr_pct = float(ind_actual.get('atr_percent', 0))
    vol_rel = float(ind_actual.get('volumen_relativo', 1))

    # Evita solo los casos totalmente muertos (casi sin movimiento ni volumen)
    if atr_pct < 0.05 and vol_rel < 0.5:
        return None, 0.0, None, "Volatilidad y volumen casi nulos"

    # Continuación bajista
    if 'BAJISTA' in t1:
        if 38 <= rsi <= 62 and posicion_rango >= 55 and macd_hist < 0:
            conf = 0.72 + (0.02 if vol_rel >= 1.10 else 0)
            if fg_valor < 25:
                conf -= 0.03
            conf = max(0.70, min(0.85, conf))
            return "SHORT", conf, "temp_actual", "Fallback técnico: continuación bajista (EMA+MACD+rango)"

    # Continuación alcista
    if 'ALCISTA' in t1:
        if 38 <= rsi <= 62 and posicion_rango <= 45 and macd_hist > 0:
            conf = 0.72 + (0.02 if vol_rel >= 1.10 else 0)
            if fg_valor > 75:
                conf -= 0.03
            conf = max(0.70, min(0.85, conf))
            return "LONG", conf, "temp_actual", "Fallback técnico: continuación alcista (EMA+MACD+rango)"

    # Reversión extrema (muy selectiva)
    if fg_valor <= 12 and rsi <= 20 and posicion_rango <= 15 and macd_hist > -0.005:
        return "LONG", 0.70, "temp_actual", "Fallback técnico: sobreventa extrema + fear extremo"

    if fg_valor >= 88 and rsi >= 80 and posicion_rango >= 85 and macd_hist < 0.005:
        return "SHORT", 0.70, "temp_actual", "Fallback técnico: sobrecompra extrema + greed extremo"

    # V5.12: Eliminados fallbacks de baja confianza (65%) que forzaban trades basura.
    # Solo se mantienen los setups de alta convicción arriba (continuación tendencia 72%+
    # y reversión extrema 70%).

    return None, 0.0, None, "Sin setup fallback de alta convicción"

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


def obtener_balance_total(client):
    """V5.11: Obtiene equity total (wallet balance + unrealized PNL).
    Usado para drawdown para evitar falsos positivos cuando hay ganancias abiertas."""
    try:
        account = client.futures_account()
        return float(account.get('totalWalletBalance', 0)) + float(account.get('totalUnrealizedProfit', 0))
    except Exception as e:
        log(f"⚠️ Error obteniendo balance total: {e}")
        # Fallback a wallet balance
        return obtener_balance(client)

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
            if '-4045' in trad_str or '-4130' in trad_str:
                # Silenciado error -4045/-4130 como solicitado en el Motor de Scalping
                # para evitar spam cuando se persigue el precio muy de cerca.
                return False, True  # already_protected
            
            # Fallback: Algo Order API
            log(f"   ⚠️ SL tradicional falló, intentando Algo Order...")
            try:
                # V5.3 Fix: usar closePosition en vez de quantity (evita error max quantity)
                client.futures_create_algo_order(
                    symbol=symbol,
                    side=side,
                    type='STOP_MARKET',
                    triggerPrice=str(precio),
                    closePosition='true'
                )
                return True, False
            except Exception as algo_error:
                algo_str = str(algo_error)
                if '-4045' in algo_str or '-4130' in algo_str:
                    # Silenciado error -4045/-4130 en la API secundaria también
                    return False, True
                log(f"   ⚠️ Algo Order también falló: {algo_error}")
                return False, False
                
    except Exception as e:
        error_str = str(e)
        if '-4045' in error_str or '-4130' in error_str:
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
            
            # V5.12: Trailing SL con break-even + activación a +1.0%
            ganancia_actual = ((precio_actual - entry_price) / entry_price) if side == 'LONG' else ((entry_price - precio_actual) / entry_price)
            
            if side == 'LONG':
                if precio_actual > tracking['best_price']:
                    tracking['best_price'] = precio_actual
                
                # V5.12: Break-even SL — cuando ganancia >= 1.5%, mover SL a entry + 0.1%
                if ganancia_actual >= 0.015 and (tracking['last_sl'] is None or tracking['last_sl'] < entry_price):
                    be_sl = entry_price * 1.001  # Entry + 0.1% (cubre comisiones)
                    cancelar_ordenes_sl(client, symbol)
                    success, _ = crear_orden_sl(client, symbol, 'SELL', be_sl, abs(cantidad))
                    if success:
                        tracking['last_sl'] = be_sl
                        log(f"🛡️ Break-even SL ({symbol}): ${be_sl:.4f} (+0.1% vs entry)")
                
                # V5.12: Trailing activo cuando ganancia > 1.0% (antes 0.5%)
                if ganancia_actual > 0.010:
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
                
                # V5.12: Break-even SL — cuando ganancia >= 1.5%, mover SL a entry - 0.1%
                if ganancia_actual >= 0.015 and (tracking['last_sl'] is None or tracking['last_sl'] > entry_price):
                    be_sl = entry_price * 0.999  # Entry - 0.1% (cubre comisiones)
                    cancelar_ordenes_sl(client, symbol)
                    success, _ = crear_orden_sl(client, symbol, 'BUY', be_sl, abs(cantidad))
                    if success:
                        tracking['last_sl'] = be_sl
                        log(f"🛡️ Break-even SL ({symbol}): ${be_sl:.4f} (-0.1% vs entry)")
                
                # V5.12: Trailing activo cuando ganancia > 1.0% (antes 0.5%)
                if ganancia_actual > 0.010:
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
                    pnl_porcentaje = ((mark_price - entry_price) / entry_price) * APALANCAMIENTO
                else:  # SHORT
                    pnl_porcentaje = ((entry_price - mark_price) / entry_price) * APALANCAMIENTO
            else:
                pnl_porcentaje = 0
            
            # ═══════════════════════════════════════════════════════════════════
            # MOTOR DE SCALPING - COBRO SEGURO POR ROI% (V5.11)
            # ═══════════════════════════════════════════════════════════════════
            # V5.11: Target basado en 5% ROI sobre margen inicial (antes $60 fijo inalcanzable)
            SCALPING_ROI_TARGET = 0.05  # 5% ROI sobre margen
            margen_inicial = abs(cantidad) * entry_price / APALANCAMIENTO
            scalping_target_usd = margen_inicial * SCALPING_ROI_TARGET
            if unrealized_pnl >= scalping_target_usd:
                side = 'SELL' if cantidad > 0 else 'BUY'
                
                log(f"⚡ SCALPING: {symbol} alcanzó ganancia rápida (${unrealized_pnl:.2f})")
                log(f"⚡ CERRANDO POSICIÓN PARA ASEGURAR GANANCIA: {symbol}")
                
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
                    
                    log(f"✅ Posición {symbol} cerrada por Scalping. PNL: ${unrealized_pnl:.2f}")
                    continue  # Saltar el resto de comprobaciones para este símbolo
                except Exception as e:
                    log(f"❌ Error cerrando posición por Scalping {symbol}: {e}")

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
            
            # V5.3 Fix: Pérdidas > 3% SIEMPRE visibles (antes ocultas por LOG_DETALLADO)
            elif pnl_porcentaje < -0.03:
                estado = "🔴"
                side_str = 'LONG' if cantidad > 0 else 'SHORT'
                log(f"{estado} Guardián {symbol} {side_str}: {pnl_porcentaje*100:.2f}% (PNL: ${unrealized_pnl:.2f})")
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
                except Exception as e:
                    log(f"⚠️ Exception in futures_get_open_algo_orders para {symbol}: {e}")
                
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
                    except Exception as e:
                        log(f"⚠️ Exception in futures_get_open_orders para {symbol}: {e}")
                
                if tiene_sl and sl_precio_encontrado and sl_precio_encontrado > 0:
                    # V3.9: VALIDAR COHERENCIA del SL
                    sl_coherente = True
                    if side == 'LONG' and sl_precio_encontrado > mark_price * 1.01:
                        # SL de un LONG está ARRIBA del mark_price → INCOHERENTE (Binance lo rechazaría de todos modos)
                        log(f"⛔ {symbol} LONG: SL en ${sl_precio_encontrado:.2f} está ARRIBA del mark ${mark_price:.2f} → INCOHERENTE")
                        sl_coherente = False
                    elif side == 'SHORT' and sl_precio_encontrado < mark_price * 0.99:
                        # SL de un SHORT está DEBAJO del mark_price → INCOHERENTE
                        log(f"⛔ {symbol} SHORT: SL en ${sl_precio_encontrado:.2f} está DEBAJO del mark ${mark_price:.2f} → INCOHERENTE")
                        sl_coherente = False
                    
                    if sl_coherente:
                        _sl_verificados[symbol] = time.time()
                    else:
                        # Cancelar SL incoherente y crear uno nuevo
                        log(f"🔄 Cancelando SL incoherente de {symbol} y recreando...")
                        cancelar_ordenes_sl(client, symbol)
                        tiene_sl = False  # Forzar creación de nuevo SL
                
                if not tiene_sl:
                    # V5.12: SL emergencia a -1.5% (antes -3% = -9% con 3x leverage)
                    SL_EMERGENCIA_PERCENT = 0.015  # -1.5% alineado con config SL normal
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
                    
                    # Intentar crear SL de forma silenciosa primero
                    success, already_protected = crear_orden_sl(client, symbol, sl_side, sl_precio, abs(cantidad))
                    
                    if success:
                        log(f"⚠️ {symbol} SIN orden SL válida. SL emergencia objetivo(entry): ${sl_objetivo_entry:.4f} | aplicado: ${sl_precio:.4f}")
                        log(f"✅ SL de emergencia creado exitosamente para {symbol}")
                        _sl_verificados[symbol] = time.time()
                        _sl_retry_cooldown_until.pop(symbol, None)
                    elif already_protected:
                        # V5.2 FIX: -4045 = max stop orders, -4130 = closePosition order exist
                        # Aceptar como protegido directamente y dar un TTL mayor para no golpear la API
                        _sl_verificados[symbol] = time.time() + 3600  # Darle 1 hora de TTL extra si está protegido por UI
                        _sl_retry_cooldown_until.pop(symbol, None)
                        # Reducir el logging innecesario para evitar confusión
                        pass
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
                # V5.10 FIX Bug #4: Filtrar solo últimas 48h para evitar comparar
                # funding histórico acumulado contra PNL actual (falsos positivos)
                start_time_ms = int((time.time() - 48 * 3600) * 1000)
                income = client.futures_income_history(
                    symbol=symbol,
                    incomeType='FUNDING_FEE',
                    startTime=start_time_ms,
                    limit=20
                )
                
                total_funding = sum(float(i.get('income', 0)) for i in income)
                
                # Si el funding (negativo) supera el PNL positivo → cerrar
                if unrealized_pnl > 0 and abs(total_funding) > unrealized_pnl:
                    side = 'SELL' if cantidad > 0 else 'BUY'
                    entry_price = float(pos['entryPrice'])
                    mark_price = float(pos['markPrice'])
                    
                    log(f"💸 Cerrando {symbol}: Funding ${total_funding:.2f} > PNL ${unrealized_pnl:.2f}")
                    
                    # V5.10 FIX Bug #4: Usar reduceOnly=True para garantizar cierre total sin inversión
                    client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type='MARKET',
                        quantity=abs(cantidad),
                        reduceOnly=True
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
    """V5.11: Reduce el TP después de X días para asegurar ganancias.
    Corregido: lógica de guard conditions, cooldown por símbolo, filtro amplio de TP."""
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
            
            # V5.11: Cooldown por símbolo para evitar reintentar cada 30s
            now = time.time()
            cooldown_hasta = _tp_dinamico_cooldown.get(symbol, 0)
            if now < cooldown_hasta:
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
                    
                    # V5.11 FIX: Calcular TP cercano al precio actual para asegurar ganancia
                    # El TP dinámico busca poner un TP ligeramente arriba/abajo del precio actual
                    # para que se ejecute pronto y asegure la ganancia acumulada.
                    if side == 'LONG':
                        # TP ligeramente por encima del precio actual
                        nuevo_tp = max(entry_price * (1 + TP_DINAMICO_PERCENT), mark_price * 1.003)
                    else:  # SHORT
                        # TP ligeramente por debajo del precio actual
                        nuevo_tp = min(entry_price * (1 - TP_DINAMICO_PERCENT), mark_price * 0.997)
                    
                    # Cancelar TODOS los TP existentes (TAKE_PROFIT_MARKET y TAKE_PROFIT)
                    tp_cancelado_ok = False
                    try:
                        ordenes = client.futures_get_open_orders(symbol=symbol)
                        tps_encontrados = [o for o in ordenes if o['type'] in ('TAKE_PROFIT_MARKET', 'TAKE_PROFIT')]
                        if not tps_encontrados:
                            tp_cancelado_ok = True
                        else:
                            for orden in tps_encontrados:
                                client.futures_cancel_order(symbol=symbol, orderId=orden['orderId'])
                            time.sleep(0.5)
                            tp_cancelado_ok = True
                    except Exception as cancel_err:
                        log(f"⚠️ No se pudo cancelar TP de {symbol}: {cancel_err}")
                        tp_cancelado_ok = False
                    
                    if not tp_cancelado_ok:
                        _tp_dinamico_cooldown[symbol] = now + TP_DINAMICO_COOLDOWN
                        continue
                    
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
                            closePosition=True,
                            timeInForce='GTE_GTC'
                        )
                        
                        log(f"📈 TP Dinámico ajustado ({symbol}): ${nuevo_tp:.4f} (días: {dias_abierto})")
                        _tp_dinamico_cooldown[symbol] = now + TP_DINAMICO_COOLDOWN
                        
                    except Exception as e:
                        # V5.11: Throttle error y aplicar cooldown para evitar spam
                        log_throttled(
                            f"tp_dinamico_error_{symbol}",
                            f"⚠️ Error creando TP dinámico ({symbol}): {e}",
                            cooldown=TP_DINAMICO_COOLDOWN
                        )
                        _tp_dinamico_cooldown[symbol] = now + TP_DINAMICO_COOLDOWN
                        
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

            sl_creado = False
            # Stop Loss inicial con STOP_MARKET tradicional
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
                sl_creado = True
            except Exception as e:
                log(f"   ⛔ ERROR CRÍTICO: SL inicial no creado para {symbol}: {e}")
                # Reintentar SL con mark_price actual como fallback
                try:
                    mark_info = client.futures_position_information(symbol=symbol)
                    if mark_info:
                        mk_price = float(mark_info[0]['markPrice'])
                        if side == 'BUY':  # LONG
                            sl_retry = mk_price * (1 - 0.03)
                        else:  # SHORT
                            sl_retry = mk_price * (1 + 0.03)

                        try:
                            info_ex = obtener_exchange_info(client)
                            sym_info = next((s for s in info_ex['symbols'] if s['symbol'] == symbol), None)
                            if sym_info:
                                sl_retry = round(sl_retry, int(sym_info['pricePrecision']))
                        except Exception:
                            sl_retry = round(sl_retry, 6)

                        sl_side = 'SELL' if side == 'BUY' else 'BUY'
                        success, _ = crear_orden_sl(client, symbol, sl_side, sl_retry, cantidad)
                        if success:
                            sl_creado = True
                            log(f"   ✅ SL de emergencia creado en retry: ${sl_retry:.6f}")
                        else:
                            log(f"   ⛔ SL NO CREADO para {symbol}. Guardian será protección.")
                except Exception as e2:
                    log(f"   ⛔ SL NO CREADO para {symbol} (retry falló: {e2}). Guardian será protección.")

            # V5.4: SL obligatorio - si no hay SL, cerrar posición inmediatamente
            if not sl_creado:
                log(f"   ⛔ SL obligatorio incumplido en {symbol}. Cerrando posición por seguridad...")
                try:
                    side_cierre = 'SELL' if side == 'BUY' else 'BUY'
                    pos_info = client.futures_position_information(symbol=symbol)
                    qty_cierre = abs(cantidad)
                    if pos_info:
                        qty_pos = abs(float(pos_info[0].get('positionAmt', 0)))
                        if qty_pos > 0:
                            qty_cierre = qty_pos

                    if qty_cierre > 0:
                        client.futures_create_order(
                            symbol=symbol,
                            side=side_cierre,
                            type='MARKET',
                            quantity=qty_cierre,
                            reduceOnly='true'
                        )
                    log(f"   ✅ Posición cerrada por seguridad (sin SL válido)")
                except Exception as close_err:
                    log(f"   ❌ ERROR CRÍTICO: no se pudo cerrar {symbol} tras fallo de SL: {close_err}")
                return False, "SL_NO_VALIDO"

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
            
            # Limpiar set si crece demasiado (evitar memory leak sin borrar recentes)
            if len(posiciones_notificadas) > 5000:
                # Convertir a lista y quedarse con la mitad más reciente sería ideal, 
                # pero para evitar PnL duplicado en loop actual no usamos clear().
                posiciones_notificadas = set(list(posiciones_notificadas)[-2500:])
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

def generar_reporte_inicio(saldo, status_gemini, fg_valor, fg_clasificacion):
    """Genera un reporte detallado del estado inicial del bot"""
    reporte = f"""🤖 *BINANCE BOT {BOT_VERSION} ONLINE*
🚀 BINANCE FUTUROS: `{status_gemini}`

💰 *BALANCE DETECTADO:*
💵 USDT Disponible: `${saldo:.2f}`
🛡️ Escudo 80/20 %
👨🏻‍💻 Trabajo 80%
🛟 Seguro 20%

🤖 Gemini 2.5 Flash (New SDK): `{status_gemini}`"""
    return reporte

def enviar_resumen_diario(client):
    """V5.3: Envía resumen diario con balance, PNL y métricas de riesgo."""
    global _ultimo_resumen_diario
    try:
        fecha = hora_local().strftime("%d/%m/%Y")
        balance = obtener_balance(client)
        
        # Registrar balance fin de día
        registrar_balance_diario(hora_local().strftime("%Y-%m-%d"), balance_fin=balance)
        
        # Obtener métricas
        metricas_texto = generar_resumen_metricas()
        
        pnl_dia = stats_diarias.get('pnl_dia', 0)
        emoji_dia = "📈" if pnl_dia >= 0 else "📉"
        
        mensaje = f"""📊 *RESUMEN DIARIO {BOT_VERSION}*
📅 {fecha}

━━━━━━━━━━━━━━━━━━━━━━━
💵 *Balance:* `${balance:.2f}`
{emoji_dia} *PNL Hoy:* `${pnl_dia:+.2f}`

{metricas_texto}

━━━━━━━━━━━━━━━━━━━━━━━
🤖 Bot Binance {BOT_VERSION} Activo ✅"""
        
        enviar_telegram(mensaje)
        log(f"📊 Resumen diario enviado: {fecha}")
        
        # V5.10: Cachear para API + Push Notification
        _ultimo_resumen_diario = {
            "fecha": fecha, "balance": round(balance, 2),
            "pnl_dia": round(pnl_dia, 2), "metricas": metricas_texto,
            "timestamp": hora_local().isoformat(),
        }
        try:
            from expo_push import enviar_push_notification
            pnl_sign = "+" if pnl_dia >= 0 else ""
            enviar_push_notification(
                f"📊 Resumen Diario - {fecha}",
                f"Balance: ${balance:.2f} | PNL: {pnl_sign}${pnl_dia:.2f}",
                {"type": "resumen_diario"}
            )
        except Exception:
            pass
        
        # Registrar balance inicio del nuevo día
        registrar_balance_diario(
            (hora_local() + timedelta(days=1)).strftime("%Y-%m-%d"),
            balance_inicio=balance
        )
    except Exception as e:
        log(f"⚠️ Error enviando resumen diario: {e}")

def enviar_resumen_semanal(client):
    """
    Genera y envía un resumen semanal por Telegram (WOW Summary V5.7).
    Se envía cada viernes a las 18:00 (Guatemala).
    """
    global stats_semanales, _ultimo_resumen_semanal
    try:
        # Obtener balance actual
        balance_actual = obtener_balance(client)
        
        # Obtener métricas de la base de datos (últimos 7 días)
        metricas_semanales = calcular_metricas_riesgo(dias=7)
        
        # Balance Inicial (usando el del proyecto o el inicio de semana)
        balance_inicial = stats_semanales.get("balance_inicio_semana", BALANCE_INICIAL_PROYECTO)
        if balance_inicial <= 0:
            balance_inicial = balance_actual
            
        roi_semanal = ((balance_actual - balance_inicial) / balance_inicial) * 100 if balance_inicial > 0 else 0
        
        trades_ganados = metricas_semanales.get('total_trades', 0) * (metricas_semanales.get('win_rate', 0) / 100.0)
        trades_ganados = int(round(trades_ganados))
        trades_perdidos = metricas_semanales.get('total_trades', 0) - trades_ganados
        
        win_rate = metricas_semanales.get('win_rate', 0.0)
        profit_factor = metricas_semanales.get('profit_factor', 0.0)
        
        # Formatear ROI con el signo adecuado
        roi_str = f"+{roi_semanal:.2f}%" if roi_semanal >= 0 else f"{roi_semanal:.2f}%"

        mensaje = f"""📊 RESUMEN SEMANAL V5.7 📊
🗓️ Viernes 18:00 (Guatemala)

💰 Balance Inicial: ${balance_inicial:,.2f}
💸 Balance Actual: ${balance_actual:,.2f}
📈 ROI Semanal: {roi_str}

✅ Operaciones Ganadas: {trades_ganados}
❌ Operaciones Perdidas: {trades_perdidos}
🎯 Win Rate: {win_rate:.1f}%
⚖️ Profit Factor: {profit_factor:.2f}

🤖 Estado del Bot: ÓPTIMO"""
        
        enviar_telegram(mensaje)
        log(f"📊 Resumen semanal (WOW Summary) enviado correctamente.")
        
        # V5.10: Cachear para API + Push Notification
        _ultimo_resumen_semanal = {
            "balance_inicial": round(balance_inicial, 2),
            "balance_actual": round(balance_actual, 2),
            "roi_semanal": round(roi_semanal, 2),
            "trades_ganados": trades_ganados,
            "trades_perdidos": trades_perdidos,
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "timestamp": hora_local().isoformat(),
        }
        try:
            from expo_push import enviar_push_notification
            enviar_push_notification(
                "📊 Resumen Semanal 🗓️",
                f"ROI: {roi_str} | Win Rate: {win_rate:.1f}% | Balance: ${balance_actual:,.2f}",
                {"type": "resumen_semanal"}
            )
        except Exception:
            pass
        
        # ═══════════════════════════════════════════════════════════════════
        # RESETEAR ESTADÍSTICAS PARA LA NUEVA SEMANA
        # ═══════════════════════════════════════════════════════════════════
        stats_semanales["balance_inicio_semana"] = balance_actual
        stats_semanales["ganados"] = 0
        stats_semanales["perdidos"] = 0
        stats_semanales["monto_ganado"] = 0
        stats_semanales["monto_perdido"] = 0
        stats_semanales["cierres_guardian"] = 0
        stats_semanales["ultimo_resumen"] = hora_local()
        
    except Exception as e:
        log(f"⚠️ Error enviando resumen semanal: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO PRINCIPAL DE TRADING (Gemini 2.5 + Fear & Greed) - NEW SDK
# ═══════════════════════════════════════════════════════════════════════════════
def ejecutar_trading(client, gemini_client):
    log("\n" + "="*60)
    log("🧠 GEMINI 2.5 + FEAR & GREED: Iniciando ciclo de análisis...")
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
            log(" Posiciones llenas. Monitoreando trailing SL...")
            return
        
        # Obtener Fear & Greed Index y Macroeconomía
        fg_valor, fg_clasificacion = obtener_fear_greed()
        macro_tradicional = obtener_macros_financieras_para_gemini()
        log(f"🎭 Fear & Greed Index: {fg_valor}/100 ({fg_clasificacion}) | 🌎 Macro Tradicional: {macro_tradicional}")
        
        # Obtener símbolos ya con posición (para evitar duplicados)
        simbolos_con_posicion = obtener_simbolos_con_posicion(client)
        
        # Obtener y analizar activos
        simbolos = obtener_simbolos_futuros(client)
        log(f" Analizando top {len(simbolos)} pares por volumen...")
        
        # Lista para guardar oportunidades
        oportunidades = []
        
        for symbol in simbolos:
            # Saltar si ya tenemos posición en este símbolo
            if symbol in simbolos_con_posicion:
                log(f"⏭️ Saltando {symbol} (ya tiene posición)")
                continue
                
            try:
                # ═══════════════════════════════════════════════════════════════════
                # V5.9: SCALPING / DAY TRADING DINÁMICO
                # ═══════════════════════════════════════════════════════════════════
                temp_actual = TEMPORALIDADES[0]
                velas_actual = obtener_velas(client, symbol, temp_actual, VELAS_CANTIDAD)
                if not velas_actual or len(velas_actual) < 200:
                    continue
                
                log(f"🧠 Analizando: {symbol} ({temp_actual}: {len(velas_actual)} velas)")
                
                # ═══════════════════════════════════════════════════════════════════
                # V5.9: CALCULAR INDICADORES
                # ═══════════════════════════════════════════════════════════════════
                klines_actual = [[v['timestamp'], v['open'], v['high'], v['low'], v['close'], v['volume']] for v in velas_actual]
                ind_actual = analizar_indicadores_completo(klines_actual)
                
                if not ind_actual:
                    log(f"   ⚠️ No se pudieron calcular indicadores para {symbol}")
                    continue
                
                # Referencia principal
                indicadores = ind_actual
                precio_actual = ind_actual['precio_actual']
                precios_actual = [v['close'] for v in velas_actual[-100:]]
                precio_max_actual = max(precios_actual)
                precio_min_actual = min(precios_actual)
                volatilidad = ((precio_max_actual - precio_min_actual) / precio_actual) * 100
                posicion_rango = ((precio_actual - precio_min_actual) / (precio_max_actual - precio_min_actual) * 100) if precio_max_actual != precio_min_actual else 50
                
                # ═══════════════════════════════════════════════════════════════════
                # V5.3: PRE-FILTRO EN CÓDIGO — Ahorrar llamadas a Gemini
                # Si no hay señal clara → skip sin gastar API
                # ═══════════════════════════════════════════════════════════════════
                rsi = ind_actual['rsi']
                tendencia = (ind_actual.get('tendencia_ema', '') or '').upper()
                
                # Skip si RSI estrictamente neutral + tendencia lateral + rango medio apretado
                if (45 < rsi < 55 and 'LATERAL' in tendencia and 45 < posicion_rango < 55):
                    if LOG_DETALLADO:
                        log(f"   ⏭️ {symbol}: Pre-filtro skip (RSI {rsi:.0f}, {tendencia}, rango {posicion_rango:.0f}%)")
                    continue
                
                # ═══════════════════════════════════════════════════════════════════
                # V5.3: PREPARAR LAS 200 VELAS CRUDAS para cotejo completo
                # Gemini puede cotejar patrones en las velas vs los indicadores.
                # Para el modelo usamos solo las últimas ~120 velas para no saturar el prompt.
                velas_prompt = velas_actual[-120:] if len(velas_actual) > 120 else velas_actual
                velas_csv_lines = []
                for v in velas_prompt:
                    velas_csv_lines.append(
                        f"{v['open']:.6f},{v['high']:.6f},{v['low']:.6f},{v['close']:.6f},{v['volume']:.0f}"
                    )
                velas_csv = "\n".join(velas_csv_lines)
                
                # ═══════════════════════════════════════════════════════════════════
                # V5.9: PROMPT ENRIQUECIDO SCALPING INSTITUCIONAL
                # ═══════════════════════════════════════════════════════════════════
                
                prompt = f"""Eres un Day Trader institucional. Tu objetivo exclusivo es identificar movimientos intradiarios limpios de entre 1.5% y 2.5% en la temporalidad de {temp_actual}. Ignora el ruido macroeconómico de largo plazo. Evalúa el Valor Esperado (EV) asumiendo los Take Profits agresivos de nuestras reglas.

MERCADO GLOBAL Y SENTIMIENTO:
🎭 Fear & Greed Index: {fg_valor}/100 ({fg_clasificacion})
- 0-25: Extreme Fear (sesgo LONG; los SHORTs necesitan confirmación bajista clara)
- 26-45: Fear (favorecer LONGs en soporte)
- 46-55: Neutral
- 56-75: Greed (favorecer SHORTs tácticos)
- 76-100: Extreme Greed (sesgo SHORT; LONG solo con confirmación alcista fuerte)

🌎 Macroeconomía (Mercado Tradicional): {macro_tradicional}
- Utiliza esta lectura extra para entender el flujo de capital global e institucional.
- Si la macroeconomía refleja aversión al riesgo (Sp500 cayendo fuerte), los short en crypto tienen viento a favor.

══════════════════════════════════
ANÁLISIS COMPLETO DE {symbol}
══════════════════════════════════

TEMPORALIDAD {temp_actual} (200 velas)
══════════════════════════════════
- Precio actual: ${precio_actual}
- RSI(14): {ind_actual['rsi']:.1f}
- Tendencia EMA: {ind_actual['tendencia_ema']} (EMA20: ${ind_actual['ema20']}, EMA50: ${ind_actual['ema50']}, EMA200: ${ind_actual.get('ema200', 'N/A')})
- MACD: {ind_actual['macd']['macd']:.6f} | Signal: {ind_actual['macd']['signal']:.6f} | Histograma: {ind_actual['macd']['histograma']:.6f}
- Bollinger: Sup ${ind_actual['bollinger']['superior']} | Med ${ind_actual['bollinger']['media']} | Inf ${ind_actual['bollinger']['inferior']} | Pos: {ind_actual['bollinger']['posicion']}%
- ATR(14): ${ind_actual['atr']:.6f} ({ind_actual['atr_percent']:.2f}%)
- Volumen relativo: {ind_actual['volumen_relativo']}x
- Soporte: ${ind_actual['soporte']} ({ind_actual['dist_soporte']:.2f}%) | Resistencia: ${ind_actual['resistencia']} ({ind_actual['dist_resistencia']:.2f}%)
- Volatilidad: {volatilidad:.2f}% | Pos en rango: {posicion_rango:.1f}%

══════════════════════════════════
LAS 120 VELAS {temp_actual} MÁS RECENTES (open,high,low,close,volume)
Analiza patrones: dojis, envolventes, doble techo/suelo, divergencias RSI.
Úsalas para confirmar o invalidar la lectura de los indicadores anteriores.
══════════════════════════════════
{velas_csv}

REGLAS OPERATIVAS SCALPING EXTREMO (15m):
1. Tu misión es operar Frecuentemente. Identifica cualquier setup intradiario que ofrezca un rápido 1.5%.
2. Escala de CONFIANZA obligatoria:
   - Si respondes "WAIT", la CONFIANZA debe ser 0%.
   - Si respondes "LONG" o "SHORT", la CONFIANZA debe ser realista según el setup técnico (ej. 60% a 95%).
3. NO seas conservador. Un Scalper toma riesgos a favor del momentum más cercano.
4. Tendencia ALCISTA: prioriza LONG; permite SHORT si hay sobrecompra rápida (RSI > 70).
5. Tendencia BAJISTA: prioriza SHORT; permite LONG si hay rebote rápido en soporte o RSI < 30.
6. Macroeconomía y Fear & Greed: Úsalos como apoyo direccional, pero no dejes que el "Fear" macro te asuste de tomar un LONG si el gráfico de 15m tiene buen momentum.
7. Si precio en 20% inferior del rango y RSI < 40: Favorece LONG fuerte.
8. Si precio en 80% superior del rango y RSI > 60: Favorece SHORT fuerte.
9. Tienes que tomar decisiones: si hay oportunidad mínima, entra LONG o SHORT. Solo usa WAIT en consolidaciones muertas (volumen nulo o patrón inexistente).

Responde SOLO con este JSON, sin explicación adicional:
{{"ACCION": "LONG/SHORT/WAIT", "CONFIANZA": 0.75, "TEMPORALIDAD": "{temp_actual}", "RAZON": "explicacion breve"}}"""
                
                # V3.7: Retry logic con exponential backoff para errores 429
                MAX_RETRIES = 3
                respuesta = None
                for attempt in range(MAX_RETRIES):
                    try:
                        response = gemini_client.models.generate_content(
                            model='gemini-2.5-flash',
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
                
                accion = str(data.get('ACCION', 'WAIT')).upper()
                confianza = float(data.get('CONFIANZA', 0))
                temporalidad = data.get('TEMPORALIDAD', temp_actual)
                razon = data.get('RAZON', 'Sin razón')

                if confianza > 1:
                    confianza = confianza / 100
                confianza = max(0.0, min(0.99, confianza))

                if temporalidad not in TEMPORALIDADES:
                    temporalidad = temp_actual

                # V5.5: Fallback técnico cuando IA se fuerza erróneamente en esperar o falla
                if accion not in ["LONG", "SHORT"]:
                    accion_fb, conf_fb, temp_fb, razon_fb = generar_senal_fallback(
                        ind_actual, posicion_rango, fg_valor
                    )
                    if accion_fb:
                        accion = accion_fb
                        confianza = max(confianza, conf_fb)
                        if temp_fb:
                            temporalidad = temp_fb
                        razon = f"{razon_fb}. IA original: WAIT."
                        log(f"   🔁 Fallback activado: {accion} ({int(confianza*100)}%)")

                # ═══════════════════════════════════════════════════════════════════
                # V5.5: VALIDACIÓN POST-IA con score (evita bloqueo total)
                # ═══════════════════════════════════════════════════════════════════
                tendencia_ema = (ind_actual.get('tendencia_ema', '') or '').upper()
                rsi_actual = ind_actual.get('rsi', 50)
                atr_pct_actual = ind_actual.get('atr_percent', 0)
                boll_ancho_actual = (ind_actual.get('bollinger') or {}).get('ancho', 0)
                modo_mercado = "RANGE" if ('LATERAL' in tendencia_ema and atr_pct_actual < 1.2 and boll_ancho_actual < 8) else "TREND"

                score_ajuste = 0.0
                reglas_aplicadas = []

                # Fear extremo: penaliza SHORT ligero, pero prioriza el scalping rápido
                if fg_valor < 25 and accion == "SHORT":
                    if modo_mercado == "TREND" and 'BAJISTA' in tendencia_ema and rsi_actual > 35:
                        score_ajuste -= 0.05
                        reglas_aplicadas.append("Fear<25 penaliza SHORT (-5%)")
                    else:
                        score_ajuste -= 0.10
                        reglas_aplicadas.append("Fear<25 penaliza SHORT sin confirmación (-10%)")

                # Alineación/contradicción con tendencia principal de scalping
                if accion == "LONG" and 'BAJISTA' in tendencia_ema:
                    if modo_mercado == "RANGE" and rsi_actual <= 25 and posicion_rango <= 20:
                        score_ajuste -= 0.02
                        reglas_aplicadas.append("LONG contra tendencia en rango")
                    else:
                        score_ajuste -= 0.15
                        reglas_aplicadas.append("LONG contra tendencia EMA (-15%)")
                elif accion == "SHORT" and 'ALCISTA' in tendencia_ema:
                    if modo_mercado == "RANGE" and rsi_actual >= 75 and posicion_rango >= 80:
                        score_ajuste -= 0.02
                        reglas_aplicadas.append("SHORT contra tendencia en rango")
                    else:
                        score_ajuste -= 0.15
                        reglas_aplicadas.append("SHORT contra tendencia EMA (-15%)")
                elif accion in ["LONG", "SHORT"]:
                    score_ajuste += 0.10
                    reglas_aplicadas.append("Dirección alineada con tendencia Scalping (+10%)")

                # ═══════════════════════════════════════════════════════════════════
                # V5.9: GPS EMA 200 - RELAJADO PARA SCALPING
                # ═══════════════════════════════════════════════════════════════════
                ema_200_actual = ind_actual.get('ema200')
                if ema_200_actual and accion in ["LONG", "SHORT"]:
                    if accion == "LONG" and precio_actual < ema_200_actual:
                        log(f"   ⚠️ GPS: LONG contra EMA200 (Precio ${precio_actual} < EMA200 ${ema_200_actual}) - Penalización ligera.")
                        score_ajuste -= 0.05
                    elif accion == "SHORT" and precio_actual > ema_200_actual:
                        log(f"   ⚠️ GPS: SHORT contra EMA200 (Precio ${precio_actual} > EMA200 ${ema_200_actual}) - Penalización ligera.")
                        score_ajuste -= 0.05

                if accion in ["LONG", "SHORT"]:
                    confianza = max(0.0, min(0.99, confianza + score_ajuste))
                    if LOG_DETALLADO:
                        log(f"   🧭 Modo: {modo_mercado} | Ajuste: {score_ajuste:+.2f}")
                        if reglas_aplicadas:
                            log(f"   🧪 Reglas: {'; '.join(reglas_aplicadas)[:120]}")
                else:
                    modo_mercado = "TREND"

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
                        'modo_mercado': modo_mercado,
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
            
            # V5.12: Verificar drawdown ANTES de cada orden usando equity total
            # Evita pausar innecesariamente cuando hay unrealized PNL positivo
            balance_pre_orden = obtener_balance_total(client)
            if not verificar_drawdown_diario(balance_pre_orden):
                log(f"🛑 Drawdown detectado. Deteniendo ejecución de órdenes.")
                break
            
            symbol = op['symbol']
            accion = op['accion']
            confianza = op['confianza']
            temporalidad = op['temporalidad']
            precio_actual = op['precio_actual']
            modo_mercado = op.get('modo_mercado', 'TREND')
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

            if modo_mercado == "RANGE":
                monto *= FACTOR_MONTO_RANGO

            # V5.4: TP/SL según régimen de mercado
            config_source = TP_SL_RANGO_CONFIG if modo_mercado == "RANGE" else TP_SL_CONFIG
            # Usar la config de la temporalidad si existe; si no, tomar la primera disponible
            if temporalidad in config_source:
                config = config_source[temporalidad]
            else:
                # fallback seguro independientemente de que exista clave "1h" o no
                primera_key = next(iter(config_source.keys()))
                config = config_source[primera_key]

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

            # V5.4: Filtro EV neto (objetivo: no entrar a trades con expectativa negativa)
            tp_pct = abs(tp - precio_actual) / precio_actual if precio_actual > 0 else 0
            sl_pct = abs(sl - precio_actual) / precio_actual if precio_actual > 0 else 0
            ev_neto, p_win_est = calcular_ev_neto(confianza, tp_pct, sl_pct, modo_mercado)
            if ev_neto < EV_MINIMO:
                log(
                    f"   ⏭️ {symbol} omitido por EV neto bajo: {ev_neto*100:+.3f}% "
                    f"(p_win est. {p_win_est*100:.1f}%, modo {modo_mercado})"
                )
                continue

            monto = max(1, round(monto, 2))
            if LOG_DETALLADO:
                log(f"   📐 EV neto: {ev_neto*100:+.3f}% | p_win est.: {p_win_est*100:.1f}% | modo: {modo_mercado}")

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
    reporte = f"""🤖 *BINANCE BOT {BOT_VERSION} ONLINE*
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

🆕 *FUNCIONES V5.5:*
📊 **RESUMEN DIARIO:** Activado ✅
📍 Trailing SL: `1.5% activo` ✅
⏱️ Temporalidades: `{', '.join(TEMPORALIDADES)}`
🎭 Fear & Greed: `{fg_valor} ({fg_clasificacion})`

💸 *PROTECCIÓN FUNDING FEES:* 🟢 ACTIVA
⏰ Cierre por tiempo: `5 días máx`
📈 TP dinámico: `Después de 1 día`
💵 Funding vs PNL: `Auto-cierre si fees > ganancias`

🧠 *CEREBRO IA:*
🤖 Gemini 2.5 Flash (New SDK): `{status_gemini}`

⏰ HORARIO: 24/7 (Sin pausas)
🔄 Monitoreo: `cada {MONITOREO_INTERVALO}s`"""
    return reporte

# ═══════════════════════════════════════════════════════════════════════════════
# ARRANQUE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
log(f"🚀 Iniciando Bot Binance Futuros {BOT_VERSION}...")
log("📊 Daily Summary + Guardian System + New GenAI SDK")

# Conexión a Binance
try:
    client = conectar_binance()
    saldo = obtener_balance(client)
    log(f"✅ Conexión exitosa. Balance: ${saldo:.2f} USDT")
except Exception as e:
    log(f"❌ ERROR FATAL: No se pudo conectar a Binance: {e}")
    sys.exit()

# Configurar Gemini 2.5 - NUEVO SDK google-genai
status_gemini = "🔴 ERROR"
gemini_client = None
try:
    gemini_client = genai.Client(api_key=os.getenv("API_KEY_GEMINI"))
    status_gemini = "🟢 CONECTADO"
    log("🧠 Cargando Motor: Gemini 2.5 Flash (New SDK)... ✅")
except Exception as e:
    log(f"⚠️ Error cargando Gemini 2.5: {e}")
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

log(f"✅ Bot {BOT_VERSION} iniciado. Guardian + SL Coherence + Resumen Semanal activos...")

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
        
        # V5.11: Usar equity total (wallet + unrealized PNL) para drawdown
        # Esto evita falsos positivos cuando hay ganancias abiertas
        balance_equity = obtener_balance_total(client)
        
        # Verificar si es un nuevo día (reinicia stats_diarias)
        verificar_nuevo_dia(balance_equity)
        
        # Verificar drawdown máximo diario usando equity total
        # Si se supera, el bot pausa nuevos trades pero Guardian sigue activo
        puede_operar = verificar_drawdown_diario(balance_equity)
        
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
                log(f"👁️ Monitoreo {BOT_VERSION}... Posiciones: {pos_abiertas}/{MAX_POSICIONES}")
                if pos_abiertas > 0:
                    log_resumen_posiciones(client)
        
        time.sleep(MONITOREO_INTERVALO)
        
    except Exception as e:
        log(f"⚠️ Error en bucle principal: {e}")
        time.sleep(60)
