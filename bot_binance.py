# 🤖 BOT BINANCE FUTURES - GEMINI 2.0 FLASH
# Trading 24/7 de Criptomonedas con IA
# V3.4 - Fix Drawdown + SL Detection + Max 3 Posiciones
# ═══════════════════════════════════════════════════════════════════════════════

from binance.client import Client
from binance.enums import *
import time, os, http.server, socketserver, threading, requests, json, sys
from datetime import datetime
from dotenv import load_dotenv
from google import genai

load_dotenv()
sys.stdout.reconfigure(line_buffering=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN GLOBAL - TRADING ACTIVO CON TRAILING SL + FUNDING PROTECTION
# ═══════════════════════════════════════════════════════════════════════════════
USAR_TESTNET = os.getenv("BINANCE_TESTNET", "True").lower() in ("true", "1", "yes")
CONFIANZA_MINIMA = 0.65   # 65% - Permitir más operaciones (antes 70%)
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
MONITOREO_INTERVALO = 60     # 60s (antes 30s) para reducir carga de CPU
LOG_FRECUENCIA_MONITOREO = 5 # Mostrar log de monitoreo cada 5 ciclos (5 min)

# ═══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS SEMANALES (V3.0) - Resumen cada viernes a las 18:00
# ═══════════════════════════════════════════════════════════════════════════════
# Balance inicial del proyecto (04/01/2026) - usado para calcular ROI total
BALANCE_INICIAL_PROYECTO = 5293.49

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
DRAWDOWN_MAXIMO_DIARIO = 0.03       # -3% máximo pérdida diaria
DRAWDOWN_ACTIVO = True              # Activar protección de drawdown

# --- ATR PARA STOP LOSS DINÁMICO ---
# El ATR mide la volatilidad real del mercado
# SL basado en ATR se adapta a la volatilidad actual del activo
# Multiplicadores recomendados:
#   - 1.0x ATR: Agresivo (stop tight, más stops pero menos pérdida por stop)
#   - 1.5x ATR: Balanceado (recomendado)
#   - 2.0x ATR: Conservador (stop amplio, menos stops pero más pérdida por stop)
ATR_SL_ACTIVO = True                # Usar ATR para calcular SL dinámico
ATR_SL_MULTIPLICADOR = 1.5          # SL = Precio - (1.5 * ATR)

# --- KELLY CRITERION PARA POSITION SIZING ---
# Fórmula de Kelly: f* = (p * b - q) / b
#   p = probabilidad de ganar (win-rate)
#   q = probabilidad de perder (1 - p)
#   b = ratio ganancia/pérdida promedio
# El resultado es el % óptimo del capital a arriesgar
# Usamos "medio Kelly" (50% del resultado) para ser más conservadores
KELLY_ACTIVO = True                 # Usar Kelly Criterion para monto
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
# SISTEMA GUARDIÁN V2.7 - PROTECCIÓN ABSOLUTA
# ═══════════════════════════════════════════════════════════════════════════════
GUARDIAN_ACTIVO = True          # Activar sistema guardián
MAX_PERDIDA_PERMITIDA = -0.10   # -10% cierre obligatorio de emergencia
LOG_DETALLADO = True            # Logs completos, sin errores silenciosos

# ═══════════════════════════════════════════════════════════════════════════════
# TEMPORALIDADES DINÁMICAS
# ═══════════════════════════════════════════════════════════════════════════════
TEMPORALIDADES = ['15m', '30m', '1h', '4h']

# TP/SL inicial por temporalidad (antes del trailing)
TP_SL_CONFIG = {
    "15m": {"tp": 0.02, "sl": 0.01},     # +2%, -1%
    "30m": {"tp": 0.03, "sl": 0.015},    # +3%, -1.5%
    "1h":  {"tp": 0.05, "sl": 0.025},    # +5%, -2.5%
    "4h":  {"tp": 0.08, "sl": 0.04},     # +8%, -4%
}

# ═══════════════════════════════════════════════════════════════════════════════
# FEAR & GREED INDEX
# ═══════════════════════════════════════════════════════════════════════════════
FEAR_GREED_API = "https://api.alternative.me/fng/"

# ═══════════════════════════════════════════════════════════════════════════════
# SERVIDOR DE SALUD (KOYEB)
# ═══════════════════════════════════════════════════════════════════════════════
def servidor_salud():
    PORT = int(os.getenv("PORT", 8000))
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"BINANCE BOT V3.4 - FIX DRAWDOWN + SL + MAX 3 POS")
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
    
    El MACD muestra la relación entre dos EMAs y ayuda a identificar
    cambios en la fuerza, dirección, momentum y duración de una tendencia.
    
    Parámetros:
        precios_cierre: Lista de precios de cierre
        rapida: Período EMA rápida (default 12)
        lenta: Período EMA lenta (default 26)
        signal: Período para línea de señal (default 9)
    
    Retorna:
        dict con:
        - macd: Línea MACD (EMA rápida - EMA lenta)
        - signal: Línea de señal (EMA del MACD)
        - histograma: MACD - Signal (positivo = bullish, negativo = bearish)
    
    Señales:
        - MACD cruza arriba de Signal: Señal de compra
        - MACD cruza abajo de Signal: Señal de venta
        - Histograma creciente: Momentum alcista aumentando
        - Histograma decreciente: Momentum bajista aumentando
    """
    if len(precios_cierre) < lenta + signal:
        return {"macd": 0, "signal": 0, "histograma": 0}
    
    # Calcular EMAs
    ema_rapida = calcular_ema(precios_cierre, rapida)
    ema_lenta = calcular_ema(precios_cierre, lenta)
    
    # Línea MACD
    macd = ema_rapida - ema_lenta
    
    # Para calcular Signal, necesitamos histórico de MACD
    # Simplificación: usamos los últimos precios para aproximar
    macd_historico = []
    for i in range(signal + 10, len(precios_cierre)):
        ema_r = calcular_ema(precios_cierre[:i], rapida)
        ema_l = calcular_ema(precios_cierre[:i], lenta)
        macd_historico.append(ema_r - ema_l)
    
    if len(macd_historico) >= signal:
        signal_line = calcular_ema(macd_historico, signal)
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
        LONG:  SL = Precio - (ATR * multiplicador)
        SHORT: SL = Precio + (ATR * multiplicador)
    
    Ejemplo con ATR = $50, multiplicador 1.5:
        - LONG @ $1000: SL = $1000 - $75 = $925
        - SHORT @ $1000: SL = $1000 + $75 = $1075
    """
    if not ATR_SL_ACTIVO or atr <= 0:
        # Fallback: usar SL fijo del 2.5%
        if side == 'BUY':
            return precio_actual * 0.975  # -2.5%
        else:
            return precio_actual * 1.025  # +2.5%
    
    # Calcular distancia del SL basada en ATR
    distancia_sl = atr * ATR_SL_MULTIPLICADOR
    
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
    
    # Obtener estadísticas de trades
    total_trades = stats_diarias["trades_ganados"] + stats_diarias["trades_perdidos"]
    
    # Si no hay suficientes trades, usar método original
    if total_trades < 5:
        rango_confianza = 1.0 - CONFIANZA_MINIMA
        exceso = max(0, confianza_ia - CONFIANZA_MINIMA)
        porcentaje = 2 + (exceso / rango_confianza) * 8
        return saldo_disponible * (porcentaje / 100)
    
    # Calcular win-rate (probabilidad de ganar)
    p = stats_diarias["trades_ganados"] / total_trades
    q = 1 - p
    
    # Calcular ratio ganancia/pérdida promedio
    if stats_diarias["trades_perdidos"] > 0 and stats_diarias["monto_perdido"] > 0:
        avg_ganancia = stats_diarias["monto_ganado"] / max(1, stats_diarias["trades_ganados"])
        avg_perdida = stats_diarias["monto_perdido"] / stats_diarias["trades_perdidos"]
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
    """Calcula el monto a invertir basado en confianza (2% a 10% del balance disponible)"""
    saldo_disponible = saldo * ESCUDO_TRABAJO
    # Mapear confianza 70%-100% a porcentaje 2%-10%
    rango_confianza = 1.0 - CONFIANZA_MINIMA  # 0.30
    exceso = max(0, confianza - CONFIANZA_MINIMA)  # 0 a 0.30
    porcentaje = 2 + (exceso / rango_confianza) * 8  # 2% a 10%
    porcentaje = min(10, max(2, porcentaje))
    monto = saldo_disponible * (porcentaje / 100)
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
        info = client.futures_exchange_info()
        
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
        positions = client.futures_position_information()
        abiertas = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        return len(abiertas)
    except:
        return 0

def obtener_simbolos_con_posicion(client):
    """Obtiene la lista de símbolos que ya tienen posición abierta"""
    try:
        positions = client.futures_position_information()
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
    """Obtiene el balance disponible en USDT"""
    try:
        balances = client.futures_account_balance()
        for b in balances:
            if b['asset'] == 'USDT':
                return float(b['availableBalance'])
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
        info = client.futures_exchange_info()
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
    """Cancela órdenes SL anteriores del símbolo"""
    try:
        ordenes = client.futures_get_open_orders(symbol=symbol)
        for orden in ordenes:
            if orden['type'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
                client.futures_cancel_order(symbol=symbol, orderId=orden['orderId'])
    except Exception as e:
        if LOG_DETALLADO:
            log(f"⚠️ Error cancelando órdenes SL de {symbol}: {e}")

def crear_orden_sl(client, symbol, side, precio, cantidad):
    """Crea una nueva orden Stop Loss usando Algo Order API (Binance Dic 2025+)"""
    try:
        # Obtener precisión del precio
        info = client.futures_exchange_info()
        symbol_info = next((s for s in info['symbols'] if s['symbol'] == symbol), None)
        if symbol_info:
            price_precision = int(symbol_info['pricePrecision'])
            precio = round(precio, price_precision)
        
        # Usar Algo Order API con triggerPrice (parámetro correcto desde Dic 2025)
        client.futures_create_algo_order(
            symbol=symbol,
            side=side,
            type='STOP_MARKET',
            triggerPrice=str(precio),
            quantity=str(cantidad)
        )
        return True
    except Exception as e:
        error_str = str(e)
        # V3.1.3: Silenciar error -4045 (max stop order limit)
        # Este error indica que YA HAY suficientes SL, lo cual es bueno
        if '-4045' in error_str:
            # No loguear - simplemente hay demasiados SL (protección OK)
            return False
        log(f"⚠️ Error creando SL: {e}")
        return False

def actualizar_trailing_sl(client):
    """Monitorea posiciones y actualiza SL con trailing 1.5%"""
    global posiciones_tracking
    
    try:
        positions = client.futures_position_information()
        
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
            
            # Actualizar mejor precio y trailing SL
            if side == 'LONG':
                if precio_actual > tracking['best_price']:
                    tracking['best_price'] = precio_actual
                    nuevo_sl = precio_actual * (1 - TRAILING_SL_PERCENT)
                    
                    # Solo actualizar SL si es mejor que el anterior y está en ganancia
                    if nuevo_sl > tracking['entry'] and (tracking['last_sl'] is None or nuevo_sl > tracking['last_sl']):
                        cancelar_ordenes_sl(client, symbol)
                        if crear_orden_sl(client, symbol, 'SELL', nuevo_sl, abs(cantidad)):
                            tracking['last_sl'] = nuevo_sl
                            ganancia_pct = ((nuevo_sl - entry_price) / entry_price) * 100
                            log(f"📈 Trailing SL ajustado ({symbol}): ${nuevo_sl:.4f} (+{ganancia_pct:.2f}% asegurado)")
            
            else:  # SHORT
                if precio_actual < tracking['best_price']:
                    tracking['best_price'] = precio_actual
                    nuevo_sl = precio_actual * (1 + TRAILING_SL_PERCENT)
                    
                    if nuevo_sl < tracking['entry'] and (tracking['last_sl'] is None or nuevo_sl < tracking['last_sl']):
                        cancelar_ordenes_sl(client, symbol)
                        if crear_orden_sl(client, symbol, 'BUY', nuevo_sl, abs(cantidad)):
                            tracking['last_sl'] = nuevo_sl
                            ganancia_pct = ((entry_price - nuevo_sl) / entry_price) * 100
                            log(f"📉 Trailing SL ajustado ({symbol}): ${nuevo_sl:.4f} (+{ganancia_pct:.2f}% asegurado)")
                        
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
        positions = client.futures_position_information()
        
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
            
            # Log de monitoreo (V2.8: Solo si PNL es significativo > 5%)
            elif LOG_DETALLADO and abs(pnl_porcentaje) > 0.05:
                estado = "🟢" if pnl_porcentaje > 0 else "🔴"
                log(f"{estado} Guardián monitoreando {symbol}: {pnl_porcentaje*100:.2f}% (PNL: ${unrealized_pnl:.2f})")
                
    except Exception as e:
        log(f"⚠️ Error en Guardián: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# VERIFICAR QUE EXISTAN ÓRDENES SL EN BINANCE
# ═══════════════════════════════════════════════════════════════════════════════
def verificar_ordenes_sl_existen(client):
    """
    V3.4: Verifica que cada posición tenga una orden SL activa. Si no, la crea.
    Usa set global para trackear SLs ya creados y evitar spam de logs.
    """
    global _sl_creados  # Track de SLs ya verificados/creados
    
    # Inicializar set si no existe
    if '_sl_creados' not in globals():
        global _sl_creados
        _sl_creados = set()
    
    try:
        positions = client.futures_position_information()
        
        for pos in positions:
            symbol = pos['symbol']
            cantidad = float(pos.get('positionAmt', 0))
            
            if cantidad == 0:
                # Si la posición se cerró, quitar del tracking
                if symbol in _sl_creados:
                    _sl_creados.discard(symbol)
                continue
            
            # Si ya verificamos/creamos SL para este symbol, no repetir
            if symbol in _sl_creados:
                continue
            
            # V3.4: Verificar SL en AMBOS endpoints con búsqueda más amplia
            try:
                tiene_sl = False
                
                # 1. Buscar en Algo Orders
                try:
                    algo_ordenes = client.futures_get_open_algo_orders()
                    if algo_ordenes:
                        tiene_sl = any(
                            o.get('symbol') == symbol and (
                                o.get('type') in ['STOP_MARKET', 'STOP', 'STOP_LOSS', 'STOP_LOSS_MARKET'] or
                                'stop' in o.get('type', '').lower() or
                                o.get('stopPrice') or 
                                o.get('triggerPrice')
                            )
                            for o in algo_ordenes
                        )
                except Exception:
                    pass
                
                # 2. Buscar en órdenes tradicionales
                if not tiene_sl:
                    try:
                        ordenes_tradicionales = client.futures_get_open_orders(symbol=symbol)
                        if ordenes_tradicionales:
                            tiene_sl = any(
                                o.get('type') in ['STOP_MARKET', 'STOP', 'STOP_LOSS', 'STOP_LOSS_MARKET'] or
                                'stop' in o.get('type', '').lower() or
                                o.get('stopPrice') or
                                o.get('triggerPrice')
                                for o in ordenes_tradicionales
                            )
                    except Exception:
                        pass
                
                if tiene_sl:
                    # Marcar como verificado
                    _sl_creados.add(symbol)
                else:
                    # Crear SL de emergencia
                    entry_price = float(pos['entryPrice'])
                    side = 'LONG' if cantidad > 0 else 'SHORT'
                    
                    if side == 'LONG':
                        sl_precio = entry_price * (1 + MAX_PERDIDA_PERMITIDA)
                        sl_side = 'SELL'
                    else:
                        sl_precio = entry_price * (1 - MAX_PERDIDA_PERMITIDA)
                        sl_side = 'BUY'
                    
                    log(f"⚠️ {symbol} SIN orden SL. Creando SL de emergencia a ${sl_precio:.4f}")
                    
                    if crear_orden_sl(client, symbol, sl_side, sl_precio, abs(cantidad)):
                        log(f"✅ SL de emergencia creado para {symbol}")
                        _sl_creados.add(symbol)  # Marcar como creado
                    else:
                        # Si falla por -4045 o cualquier razón, asumir que ya existe
                        _sl_creados.add(symbol)
                    
            except Exception as e:
                if LOG_DETALLADO:
                    log(f"⚠️ Error verificando SL de {symbol}: {e}")
                    
    except Exception as e:
        log(f"⚠️ Error en verificar_ordenes_sl_existen: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# PROTECCIÓN FUNDING FEES - CIERRE POR TIEMPO MÁXIMO
# ═══════════════════════════════════════════════════════════════════════════════
def verificar_tiempo_posiciones(client):
    """Cierra posiciones que excedan MAX_DIAS_POSICION días"""
    try:
        positions = client.futures_position_information()
        
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
        positions = client.futures_position_information()
        
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
        positions = client.futures_position_information()
        
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
                        info = client.futures_exchange_info()
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
            info = client.futures_exchange_info()
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
            except: pass
            
            # Stop Loss inicial (será reemplazado por trailing)
            try:
                sl_side = 'SELL' if side == 'BUY' else 'BUY'
                # Usar Algo Order API con triggerPrice (parámetro correcto desde Dic 2025)
                client.futures_create_algo_order(
                    symbol=symbol,
                    side=sl_side,
                    type='STOP_MARKET',
                    triggerPrice=str(sl),
                    closePosition=True
                )
                log(f"   📉 SL inicial: ${sl} (Trailing activo)")
            except: pass
        
        return True, order_id
        
    except Exception as e:
        log(f"   ❌ Error ejecutando orden: {e}")
        return False, str(e)

# ═══════════════════════════════════════════════════════════════════════════════
# VERIFICAR POSICIONES CERRADAS (P&L)
# ═══════════════════════════════════════════════════════════════════════════════
posiciones_notificadas = set()

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
            if len(posiciones_notificadas) > 100:
                posiciones_notificadas = set(list(posiciones_notificadas)[-50:])
            
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
    Verifica si es viernes a las 18:00 (hora local).
    
    Retorna:
        bool: True si es viernes y la hora está entre 18:00 y 18:59
    
    Ejemplo de uso:
        if es_viernes_18h():
            enviar_resumen_semanal(client)
    """
    ahora = datetime.now()
    # weekday() retorna: 0=Lunes, 1=Martes, ..., 4=Viernes, 5=Sábado, 6=Domingo
    es_viernes = ahora.weekday() == 4  # 4 = Viernes
    es_hora_18 = ahora.hour == 18      # Hora 18 (6 PM)
    return es_viernes and es_hora_18

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
        fecha_actual = datetime.now().strftime("%d/%m/%Y")
        
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
        # CONSTRUIR MENSAJE DE TELEGRAM
        # ═══════════════════════════════════════════════════════════════════
        mensaje = f"""📊 *RESUMEN SEMANAL BINANCE V3.0*
📅 Fecha: {fecha_actual}

━━━━━━━━━━━━━━━━━━━━━━━
� *RENDIMIENTO TOTAL DEL PROYECTO*
━━━━━━━━━━━━━━━━━━━━━━━
💰 *Balance Inicial (04/01):* `${BALANCE_INICIAL_PROYECTO:.2f}`
💵 *Balance Actual:* `${balance_actual:.2f}`
{emoji_total} *Ganancia Total:* `${ganancia_total:.2f}`
📊 *ROI Total:* `{roi_total:.2f}%`

━━━━━━━━━━━━━━━━━━━━━━━
� *ESTA SEMANA*
━━━━━━━━━━━━━━━━━━━━━━━
✅ *Trades Ganados:* `{stats_semanales['ganados']}`
❌ *Trades Perdidos:* `{stats_semanales['perdidos']}`
💰 *Ganancias:* `+${stats_semanales['monto_ganado']:.2f}`
� *Pérdidas:* `-${stats_semanales['monto_perdido']:.2f}`
🛡️ *Cierres Guardian:* `{stats_semanales['cierres_guardian']}`
{emoji_semana} *Resultado Semana:* `${resultado_semana:.2f}`
� *ROI Semanal:* `{roi_semanal:.2f}%`

━━━━━━━━━━━━━━━━━━━━━━━
🤖 Bot Binance V3.0 Activo ✅"""
        
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
        stats_semanales["ultimo_resumen"] = datetime.now()  # Marcar timestamp del resumen
        
    except Exception as e:
        log(f"⚠️ Error enviando resumen semanal: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO PRINCIPAL DE TRADING (Gemini 2.0 + Fear & Greed) - NEW SDK
# ═══════════════════════════════════════════════════════════════════════════════
def ejecutar_trading(client, gemini_client):
    log("\n" + "="*60)
    log("🧠 GEMINI 2.0 + FEAR & GREED: Iniciando ciclo de análisis...")
    log("="*60)
    
    # Verificar posiciones cerradas
    verificar_posiciones_cerradas(client)
    
    # Actualizar Trailing SL de posiciones existentes
    actualizar_trailing_sl(client)
    
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
                # Obtener velas con temporalidad 1h para análisis inicial
                velas = obtener_velas(client, symbol, '1h', VELAS_CANTIDAD)
                if not velas or len(velas) < 50:
                    continue
                
                log(f"🧠 Analizando: {symbol}")
                
                # ═══════════════════════════════════════════════════════════════════
                # V3.0: CALCULAR TODOS LOS INDICADORES TÉCNICOS
                # ═══════════════════════════════════════════════════════════════════
                # Convertir velas a formato para la función analizar_indicadores_completo
                klines_format = [[v['timestamp'], v['open'], v['high'], v['low'], v['close'], v['volume']] for v in velas]
                indicadores = analizar_indicadores_completo(klines_format)
                
                if not indicadores:
                    log(f"   ⚠️ No se pudieron calcular indicadores para {symbol}")
                    continue
                
                precio_actual = indicadores['precio_actual']
                precios = [v['close'] for v in velas[-100:]]
                precio_max = max(precios)
                precio_min = min(precios)
                volatilidad = ((precio_max - precio_min) / precio_actual) * 100
                posicion_rango = ((precio_actual - precio_min) / (precio_max - precio_min) * 100) if precio_max != precio_min else 50
                
                # ═══════════════════════════════════════════════════════════════════
                # V3.0: PROMPT MEJORADO CON INDICADORES TÉCNICOS
                # ═══════════════════════════════════════════════════════════════════
                # Este prompt incluye todos los indicadores calculados para que la IA
                # tome decisiones más precisas basadas en análisis técnico real
                prompt = f"""Eres un trader profesional de criptomonedas. Tu objetivo es lograr ROI 100% en 4 meses (~1% diario).
REGLA PRINCIPAL: SER OPORTUNISTA - Capturar movimientos tanto alcistas como bajistas.

═══════════════════════════════════════════════════════════════════
DATOS DEL MERCADO GLOBAL
═══════════════════════════════════════════════════════════════════
🎭 Fear & Greed Index: {fg_valor}/100 ({fg_clasificacion})
- 0-20: Extreme Fear → LONG AGRESIVO (mercado sobrevendido, ¡OPORTUNIDAD!)
- 21-40: Fear → LONGs en soportes
- 41-60: Neutral → Seguir tendencia EMA
- 61-80: Greed → SHORTs cerca de resistencias
- 81-100: Extreme Greed → SHORT AGRESIVO (mercado sobrecomprado)

═══════════════════════════════════════════════════════════════════
INDICADORES TÉCNICOS DE {symbol}
═══════════════════════════════════════════════════════════════════
📊 PRECIO Y RANGO:
- Precio actual: ${precio_actual}
- Máximo (100 velas): ${precio_max}
- Mínimo (100 velas): ${precio_min}
- Posición en rango: {posicion_rango:.1f}%
- Volatilidad: {volatilidad:.2f}%

📈 RSI(14): {indicadores['rsi']}
- RSI > 70: Sobrecompra → SHORT
- RSI < 30: Sobreventa → LONG
- RSI 30-70: Zona neutral

📉 EMAs (Tendencia):
- EMA 20: ${indicadores['ema20']}
- EMA 50: ${indicadores['ema50']}
- EMA 200: ${indicadores['ema200'] if indicadores['ema200'] else 'N/A'}
- Tendencia: {indicadores['tendencia_ema']}

📊 MACD:
- MACD: {indicadores['macd']['macd']}
- Signal: {indicadores['macd']['signal']}
- Histograma: {indicadores['macd']['histograma']} ({'BULLISH' if indicadores['macd']['histograma'] > 0 else 'BEARISH'})

📉 BOLLINGER BANDS:
- Superior: ${indicadores['bollinger']['superior']}
- Media: ${indicadores['bollinger']['media']}
- Inferior: ${indicadores['bollinger']['inferior']}
- Posición en banda: {indicadores['bollinger']['posicion']}%
- Ancho (volatilidad): {indicadores['bollinger']['ancho']}%

📊 ATR (Volatilidad):
- ATR: ${indicadores['atr']} ({indicadores['atr_percent']}% del precio)

📈 VOLUMEN:
- Volumen Relativo: {indicadores['volumen_relativo']}x (1.0 = promedio)

🎯 SOPORTES/RESISTENCIAS:
- Resistencia: ${indicadores['resistencia']} (+{indicadores['dist_resistencia']}%)
- Soporte: ${indicadores['soporte']} (-{indicadores['dist_soporte']}%)

═══════════════════════════════════════════════════════════════════
REGLAS V3.3 - TRADING OPORTUNISTA
═══════════════════════════════════════════════════════════════════
🔴 REGLAS PARA SHORT (ganar en caídas):
1. Tendencia EMA BAJISTA fuerte → SHORT (¡aprovechar la caída!)
2. RSI > 70 (sobrecompra) → SHORT
3. Fear & Greed > 75 → SHORT
4. Precio cerca de resistencia + rechazo → SHORT

🟢 REGLAS PARA LONG (ganar en subidas):
5. Fear & Greed < 25 → LONG (Extreme Fear = OPORTUNIDAD de compra)
6. RSI < 30 (sobreventa) → LONG
7. Precio en soporte + rebote → LONG
8. Precio en banda inferior Bollinger → LONG

⚡ REGLA ESPECIAL EXTREME FEAR (Fear < 20):
- IGNORAR tendencia EMA bajista
- PREFERIR LONG aunque EMA sea bajista
- El mercado ya cayó mucho, es hora de COMPRAR

⚡ REGLA ESPECIAL TENDENCIA BAJISTA FUERTE:
- Si EMA bajista + MACD negativo + Volumen alto → SHORT agresivo
- Ganar dinero mientras el mercado cae

❌ SOLO usar WAIT si:
- Volumen < 0.5x (mercado sin movimiento)
- RSI entre 45-55 y tendencia LATERAL
- NO usar WAIT solo porque hay indicadores mixtos

TEMPORALIDADES:
- 15m: scalping (volatilidad >5%)
- 30m: swing corto (volatilidad 3-5%)
- 1h: intraday (volatilidad 2-3%)
- 4h: swing largo (volatilidad <2%)

JSON (solo esto, sin explicación adicional):
{{"ACCION": "LONG/SHORT/WAIT", "CONFIANZA": 0.75, "TEMPORALIDAD": "1h", "RAZON": "explicacion breve con indicadores clave"}}"""
                
                # Llamada al nuevo SDK google-genai
                response = gemini_client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt
                )
                respuesta = response.text
                data = json.loads(respuesta.replace("```json","").replace("```","").strip())
                
                accion = data.get('ACCION', 'WAIT')
                confianza = float(data.get('CONFIANZA', 0))
                temporalidad = data.get('TEMPORALIDAD', '1h')
                razon = data.get('RAZON', 'Sin razón')
                
                # Normalizar confianza
                if confianza > 1:
                    confianza = confianza / 100
                
                # Validar temporalidad
                if temporalidad not in TEMPORALIDADES:
                    temporalidad = '1h'
                
                conf_pct = int(confianza * 100)
                log(f"   📊 IA: {accion} | Confianza: {conf_pct}% | Temp: {temporalidad}")
                log(f"   💭 {razon[:60]}...")
                
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
                        'indicadores': indicadores  # V3.0: Guardamos indicadores para ATR SL
                    })
                    log(f"   ✨ Oportunidad guardada!")
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
                    # V3.0: Ya no se envía Telegram individual por cada orden
                    # La estadística se acumula en stats_semanales y se envía el viernes
                    log(f"   ✅ Orden ejecutada exitosamente: {symbol} {accion}")
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
    reporte = f"""🤖 *BINANCE BOT V3.4 ONLINE*
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

🆕 *FUNCIONES V3.4:*
📊 **RESUMEN DIARIO:** Activado ✅
📍 Trailing SL: `1.5% activo` ✅
⏱️ Temporalidades: `15m, 30m, 1h, 4h`
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
log("🚀 Iniciando Bot Binance Futuros V3.4...")
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

# Inicializar tracking de posiciones existentes
pos_iniciales = contar_posiciones_abiertas(client)
if pos_iniciales > 0:
    log(f"🛡️ {pos_iniciales} posiciones existentes detectadas. Activando Guardian + Trailing SL...")
    guardian_posiciones(client)  # Primero verificar emergencias
    verificar_ordenes_sl_existen(client)  # Verificar que tengan SL
    actualizar_trailing_sl(client)
else:
    log("✅ Sin posiciones abiertas. Listo para operar.")

log("✅ Bot V3.0 iniciado. Guardian System + Resumen Semanal + Weekly Summary activos...")

# ═══════════════════════════════════════════════════════════════════════════════
# BUCLE PRINCIPAL - 24/7 CON MONITOREO CONTINUO + GUARDIAN + RESUMEN SEMANAL
# ═══════════════════════════════════════════════════════════════════════════════
# Contador de ciclos para decidir cuándo hacer análisis completo
ciclo_analisis = 0
# Cada 4 ciclos de monitoreo (4 * 60s = 4 min) hacer análisis completo de mercado
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
        # GUARDIAN SYSTEM - Monitoreo cada ciclo (protección de emergencia)
        # Cierra posiciones automáticamente si la pérdida supera -10%
        # El Guardian SIEMPRE corre, incluso si el bot está pausado por drawdown
        # ═════════════════════════════════════════════════════════════════════
        if GUARDIAN_ACTIVO:
            guardian_posiciones(client)       # Verificar pérdidas excesivas
            verificar_ordenes_sl_existen(client)  # Verificar que existan órdenes SL
        
        # ═════════════════════════════════════════════════════════════════════
        # TRAILING STOP LOSS + ESTADÍSTICAS
        # Actualiza trailing SL y acumula stats de posiciones cerradas
        # ═════════════════════════════════════════════════════════════════════
        actualizar_trailing_sl(client)        # Mover SL hacia arriba si hay ganancia
        verificar_posiciones_cerradas(client)  # Acumular stats en stats_semanales
        
        # ═════════════════════════════════════════════════════════════════════
        # RESUMEN SEMANAL - Solo viernes a las 18:00 (V3.0)
        # Envía un único mensaje por Telegram con el resumen de la semana
        # ═════════════════════════════════════════════════════════════════════
        if es_viernes_18h():
            # Verificar que no hayamos enviado resumen en esta hora
            if not resumen_enviado_esta_hora:
                enviar_resumen_semanal(client)
                resumen_enviado_esta_hora = True  # Marcar como enviado
        else:
            # Resetear la bandera cuando ya no sea viernes 18h
            resumen_enviado_esta_hora = False
        
        # Protección contra Funding Fees
        if FUNDING_PROTECTION:
            verificar_tiempo_posiciones(client)
        
        # ═════════════════════════════════════════════════════════════════════
        # V3.0: TRADING - Solo si NO estamos pausados por drawdown
        # ═════════════════════════════════════════════════════════════════════
        # Cada N ciclos, hacer análisis completo de mercado
        if ciclo_analisis >= CICLOS_PARA_ANALISIS:
            if puede_operar:
                ejecutar_trading(client, gemini_client)
            else:
                log("⏸️ Trading pausado por protección de drawdown diario")
            ciclo_analisis = 0
        else:
            # V2.8: Log de monitoreo cada 5 min para salvar recursos
            mod_log = (CICLOS_PARA_ANALISIS - ciclo_analisis)
            if ciclo_analisis % LOG_FRECUENCIA_MONITOREO == 0 or ciclo_analisis == 1:
                pos_abiertas = contar_posiciones_abiertas(client)
                log(f"👁️ Monitoreo V3.4... Posiciones: {pos_abiertas}/{MAX_POSICIONES}")
        
        time.sleep(MONITOREO_INTERVALO)
        
    except Exception as e:
        log(f"⚠️ Error en bucle principal: {e}")
        time.sleep(60)
