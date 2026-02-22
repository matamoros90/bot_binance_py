"""
V5.3: Indicadores técnicos puros (sin dependencias externas).
Extraídos de bot_binance.py para que tests y backtesting puedan importar sin Binance SDK.
"""


def calcular_rsi(precios_cierre, periodo=14):
    """Calcula RSI (0-100). >70 sobrecompra, <30 sobreventa."""
    if len(precios_cierre) < periodo + 1:
        return 50
    cambios = [precios_cierre[i] - precios_cierre[i-1] for i in range(1, len(precios_cierre))]
    ganancias = [max(0, c) for c in cambios]
    perdidas = [abs(min(0, c)) for c in cambios]
    avg_ganancia = sum(ganancias[-periodo:]) / periodo
    avg_perdida = sum(perdidas[-periodo:]) / periodo
    if avg_perdida == 0:
        return 100
    rs = avg_ganancia / avg_perdida
    return round(100 - (100 / (1 + rs)), 2)


def calcular_ema(precios_cierre, periodo):
    """Calcula EMA (Exponential Moving Average)."""
    if len(precios_cierre) < periodo:
        return precios_cierre[-1] if precios_cierre else 0
    multiplicador = 2 / (periodo + 1)
    ema = sum(precios_cierre[:periodo]) / periodo
    for precio in precios_cierre[periodo:]:
        ema = (precio - ema) * multiplicador + ema
    return round(ema, 4)


def calcular_macd(precios_cierre, rapida=12, lenta=26, signal=9):
    """Calcula MACD. V5.2: O(n) con EMAs incrementales."""
    if len(precios_cierre) < lenta + signal:
        return {"macd": 0, "signal": 0, "histograma": 0}
    mult_r = 2 / (rapida + 1)
    mult_l = 2 / (lenta + 1)
    mult_s = 2 / (signal + 1)
    ema_r = sum(precios_cierre[:rapida]) / rapida
    ema_l = sum(precios_cierre[:lenta]) / lenta
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
    if len(macd_values) >= signal:
        ema_sig = sum(macd_values[:signal]) / signal
        for val in macd_values[signal:]:
            ema_sig = (val - ema_sig) * mult_s + ema_sig
        signal_line = ema_sig
    else:
        signal_line = macd
    histograma = macd - signal_line
    return {"macd": round(macd, 4), "signal": round(signal_line, 4), "histograma": round(histograma, 4)}


def calcular_bollinger(precios_cierre, periodo=20, desviaciones=2):
    """Calcula Bandas de Bollinger."""
    if len(precios_cierre) < periodo:
        precio_actual = precios_cierre[-1] if precios_cierre else 0
        return {"superior": precio_actual, "media": precio_actual, "inferior": precio_actual, "ancho": 0, "posicion": 50}
    ultimos = precios_cierre[-periodo:]
    sma = sum(ultimos) / periodo
    varianza = sum((p - sma) ** 2 for p in ultimos) / periodo
    std_dev = varianza ** 0.5
    banda_superior = sma + (desviaciones * std_dev)
    banda_inferior = sma - (desviaciones * std_dev)
    ancho = ((banda_superior - banda_inferior) / sma) * 100 if sma > 0 else 0
    precio_actual = precios_cierre[-1]
    rango = banda_superior - banda_inferior
    posicion = ((precio_actual - banda_inferior) / rango) * 100 if rango > 0 else 50
    posicion = max(0, min(100, posicion))
    return {"superior": round(banda_superior, 4), "media": round(sma, 4), "inferior": round(banda_inferior, 4), "ancho": round(ancho, 2), "posicion": round(posicion, 1)}


def calcular_atr(precios_high, precios_low, precios_close, periodo=14):
    """Calcula ATR (Average True Range)."""
    if len(precios_close) < periodo + 1:
        if precios_high and precios_low:
            return precios_high[-1] - precios_low[-1]
        return 0
    true_ranges = []
    for i in range(1, len(precios_close)):
        tr = max(precios_high[i] - precios_low[i],
                 abs(precios_high[i] - precios_close[i-1]),
                 abs(precios_low[i] - precios_close[i-1]))
        true_ranges.append(tr)
    if len(true_ranges) >= periodo:
        atr = sum(true_ranges[-periodo:]) / periodo
    else:
        atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0
    return round(atr, 4)


def calcular_volumen_relativo(volumenes, periodo=20):
    """Calcula volumen relativo vs promedio."""
    if len(volumenes) < periodo:
        return 1.0
    promedio = sum(volumenes[-periodo:]) / periodo
    return round(volumenes[-1] / promedio, 2) if promedio > 0 else 1.0


def detectar_soportes_resistencias(precios_high, precios_low, precios_close, ventana=20):
    """Detecta soporte/resistencia básicos."""
    if not precios_high or not precios_low or len(precios_close) < ventana:
        precio = precios_close[-1] if precios_close else 0
        return {"resistencia": precio, "soporte": precio, "distancia_resistencia": 0, "distancia_soporte": 0}
    resistencia = max(precios_high[-ventana:])
    soporte = min(precios_low[-ventana:])
    precio_actual = precios_close[-1]
    if precio_actual > 0:
        dist_r = ((resistencia - precio_actual) / precio_actual) * 100
        dist_s = ((precio_actual - soporte) / precio_actual) * 100
    else:
        dist_r = dist_s = 0
    return {"resistencia": round(resistencia, 4), "soporte": round(soporte, 4),
            "distancia_resistencia": round(dist_r, 2), "distancia_soporte": round(dist_s, 2)}


def obtener_tendencia_ema(precio_actual, ema20, ema50, ema200=None):
    """Determina tendencia: ALCISTA_FUERTE, ALCISTA, BAJISTA, BAJISTA_FUERTE, LATERAL."""
    if ema200:
        if precio_actual > ema20 > ema50 > ema200:
            return "ALCISTA_FUERTE"
        elif precio_actual < ema20 < ema50 < ema200:
            return "BAJISTA_FUERTE"
    if precio_actual > ema20 > ema50:
        return "ALCISTA"
    elif precio_actual < ema20 < ema50:
        return "BAJISTA"
    return "LATERAL"


def analizar_indicadores_completo(klines):
    """Calcula TODOS los 14 indicadores técnicos a partir de velas."""
    if not klines or len(klines) < 50:
        return None
    precios_high = [float(k[2]) for k in klines]
    precios_low = [float(k[3]) for k in klines]
    precios_close = [float(k[4]) for k in klines]
    volumenes = [float(k[5]) for k in klines]
    precio_actual = precios_close[-1]
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
        "precio_actual": precio_actual, "rsi": rsi, "ema20": ema20, "ema50": ema50,
        "ema200": ema200, "tendencia_ema": tendencia, "macd": macd, "bollinger": bollinger,
        "atr": atr, "atr_percent": round((atr / precio_actual) * 100, 2) if precio_actual > 0 else 0,
        "volumen_relativo": volumen_rel, "soporte": sr["soporte"], "resistencia": sr["resistencia"],
        "dist_soporte": sr["distancia_soporte"], "dist_resistencia": sr["distancia_resistencia"]
    }
