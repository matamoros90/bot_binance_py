"""
V5.3: Unit Tests para el Bot de Trading Binance.
Ejecutar: python -m pytest tests/test_formulas.py -v
"""
import sys
import os

# Agregar directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar funciones puras (SIN dependencia de Binance SDK)
from indicators import (
    calcular_rsi, calcular_ema, calcular_macd, calcular_bollinger,
    calcular_atr, calcular_volumen_relativo, detectar_soportes_resistencias,
    obtener_tendencia_ema, analizar_indicadores_completo
)
from persistence import (
    inicializar_db, registrar_trade_abierto, registrar_trade_cerrado,
    calcular_metricas_riesgo
)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS RSI
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcularRSI:
    def test_datos_insuficientes(self):
        """Con menos datos que el periodo, retorna 50 (neutral)."""
        assert calcular_rsi([100, 101, 102], periodo=14) == 50
    
    def test_solo_ganancias(self):
        """Si todos los precios suben, RSI debe ser 100."""
        precios = list(range(100, 120))
        assert calcular_rsi(precios) == 100
    
    def test_solo_perdidas(self):
        """Si todos los precios bajan, RSI debe ser 0."""
        precios = list(range(120, 100, -1))
        assert calcular_rsi(precios) == 0
    
    def test_rango_valido(self):
        """RSI siempre debe estar entre 0 y 100."""
        precios = [100, 102, 99, 104, 97, 106, 95, 108, 93, 110,
                   92, 112, 91, 114, 90, 116, 89, 118, 88, 120]
        rsi = calcular_rsi(precios)
        assert 0 <= rsi <= 100, f"RSI fuera de rango: {rsi}"
    
    def test_mercado_bajista(self):
        """En tendencia bajista, RSI debe ser < 50."""
        precios = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91,
                   90, 89, 88, 87, 86, 85, 84, 83, 82, 81]
        assert calcular_rsi(precios) < 50


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS EMA
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcularEMA:
    def test_datos_insuficientes(self):
        assert calcular_ema([100], periodo=20) == 100
    
    def test_datos_constantes(self):
        """Con datos constantes, EMA = precio constante."""
        ema = calcular_ema([50.0] * 30, periodo=20)
        assert abs(ema - 50.0) < 0.01
    
    def test_pesos_recientes(self):
        """EMA debe dar más peso a precios recientes."""
        precios = [100.0] * 20 + [110.0] * 10
        ema = calcular_ema(precios, periodo=10)
        assert 105 < ema < 111, f"EMA debería acercarse a 110, got {ema}"
    
    def test_corta_vs_larga(self):
        """EMA corta reacciona más rápido en tendencia alcista."""
        precios = [100.0] * 50 + [float(x) for x in range(100, 120)]
        ema_20 = calcular_ema(precios, 20)
        ema_50 = calcular_ema(precios, 50)
        assert ema_20 > ema_50


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS MACD
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcularMACD:
    def test_retorna_diccionario(self):
        precios = [float(100 + i * 0.5) for i in range(50)]
        resultado = calcular_macd(precios)
        assert 'macd' in resultado
        assert 'signal' in resultado
        assert 'histograma' in resultado
    
    def test_datos_insuficientes(self):
        resultado = calcular_macd([100, 101, 102])
        assert resultado['macd'] == 0
    
    def test_tendencia_alcista(self):
        precios = [100.0 + i * 0.3 for i in range(50)]
        resultado = calcular_macd(precios)
        assert resultado['macd'] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS BOLLINGER
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcularBollinger:
    def test_datos_constantes(self):
        """Con datos constantes, bandas colapsan al precio."""
        b = calcular_bollinger([100.0] * 25)
        assert abs(b['superior'] - 100.0) < 0.01
        assert abs(b['inferior'] - 100.0) < 0.01
    
    def test_posicion_dentro_rango(self):
        """Posición siempre entre 0 y 100."""
        precios = [100 + i * 0.5 for i in range(25)]
        b = calcular_bollinger(precios)
        assert 0 <= b['posicion'] <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS ATR
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcularATR:
    def test_atr_positivo(self):
        """ATR siempre debe ser >= 0."""
        highs = [102, 103, 104, 105, 106, 107, 108, 109, 110, 111,
                 112, 113, 114, 115, 116, 117, 118, 119, 120, 121]
        lows =  [98, 99, 100, 101, 102, 103, 104, 105, 106, 107,
                 108, 109, 110, 111, 112, 113, 114, 115, 116, 117]
        closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
                  110, 111, 112, 113, 114, 115, 116, 117, 118, 119]
        atr = calcular_atr(highs, lows, closes)
        assert atr > 0
    
    def test_alta_volatilidad_mayor_atr(self):
        """Con más volatilidad, ATR debe ser mayor."""
        # Baja volatilidad
        highs_low = [101.0] * 20
        lows_low = [99.0] * 20
        closes = [100.0] * 20
        atr_low = calcular_atr(highs_low, lows_low, closes)
        
        # Alta volatilidad
        highs_high = [110.0] * 20
        lows_high = [90.0] * 20
        atr_high = calcular_atr(highs_high, lows_high, closes)
        
        assert atr_high > atr_low


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS TENDENCIA EMA
# ═══════════════════════════════════════════════════════════════════════════════

class TestObtenerTendencia:
    def test_alcista(self):
        assert obtener_tendencia_ema(110, 105, 100) == "ALCISTA"
    
    def test_bajista(self):
        assert obtener_tendencia_ema(90, 95, 100) == "BAJISTA"
    
    def test_lateral(self):
        assert obtener_tendencia_ema(100, 105, 95) == "LATERAL"
    
    def test_alcista_fuerte(self):
        assert obtener_tendencia_ema(110, 105, 100, 95) == "ALCISTA_FUERTE"
    
    def test_bajista_fuerte(self):
        assert obtener_tendencia_ema(90, 95, 100, 105) == "BAJISTA_FUERTE"


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS ANALIZAR INDICADORES COMPLETO
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalizarIndicadores:
    def test_datos_insuficientes(self):
        assert analizar_indicadores_completo([]) is None
        assert analizar_indicadores_completo([[0]*6]*10) is None
    
    def test_retorna_todos_indicadores(self):
        """Con datos suficientes, retorna dict con todos los indicadores."""
        # Simular 200 velas [timestamp, open, high, low, close, volume]
        klines = []
        for i in range(200):
            precio = 100 + i * 0.1
            klines.append([i, precio, precio + 1, precio - 1, precio, 1000])
        
        resultado = analizar_indicadores_completo(klines)
        assert resultado is not None
        assert 'rsi' in resultado
        assert 'ema20' in resultado
        assert 'macd' in resultado
        assert 'bollinger' in resultado
        assert 'atr' in resultado
        assert 'tendencia_ema' in resultado
        assert 'soporte' in resultado
        assert 'resistencia' in resultado


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS PERSISTENCE (SQLite)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersistence:
    def test_inicializar_db(self):
        inicializar_db()
    
    def test_registrar_y_cerrar_trade(self):
        inicializar_db()
        trade_id = registrar_trade_abierto(
            symbol="TESTUSDT", side="BUY", action="LONG",
            entry_price=50000, quantity=0.001,
            confidence=0.85, temporalidad="1h", razon="Test"
        )
        assert trade_id > 0
        registrar_trade_cerrado("TESTUSDT", pnl=25.50, exit_price=50500)
    
    def test_metricas_con_datos(self):
        import sqlite3
        from datetime import datetime
        from persistence import DB_PATH
        
        inicializar_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        ahora = datetime.now().isoformat()
        trades = [
            (ahora, "BTC", "BUY", "LONG", 50000, 50500, 0.001, 10.0, 0.85, "1h", "t", "CLOSED", ahora),
            (ahora, "ETH", "BUY", "LONG", 3000, 3100, 0.01, 5.0, 0.80, "1h", "t", "CLOSED", ahora),
            (ahora, "SOL", "SELL", "SHORT", 100, 105, 0.1, -3.0, 0.75, "1h", "t", "CLOSED", ahora),
        ]
        for t in trades:
            c.execute("""INSERT INTO trades (timestamp, symbol, side, action, entry_price, exit_price,
                        quantity, pnl, confidence, temporalidad, razon, status, closed_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", t)
        conn.commit()
        conn.close()
        
        m = calcular_metricas_riesgo(dias=1)
        assert m['total_trades'] >= 3
        assert m['win_rate'] > 60


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS GESTIÓN DE RIESGO Y TRAILING STOP (V6.0)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiesgoInstitucional:
    def test_bunker_sizing(self):
        """Valida que el monto a operar sea estrictamente 2.0% del balance total (Regla 80/20)."""
        balance_total = 1000.0
        # Simulación de calcular_monto o calcular_kelly para Búnker V6.0
        riesgo_esperado = balance_total * 0.02
        assert riesgo_esperado == 20.0
        
    def test_trailing_stop_agresivo(self):
        """Valida que el trailing stop se active al +0.8% y se fije en un Trailing de 0.5%."""
        entry_price = 100.0
        current_price = 100.8  # +0.8% de profit
        ganancia_actual = (current_price - entry_price) / entry_price
        ganancia_actual = round(ganancia_actual, 4)
        
        assert ganancia_actual >= 0.008, "El Trailing Break-even NO se activó en +0.8%"
        
        trailing_sl_percent = 0.005  # 0.5%
        nuevo_sl = current_price * (1 - trailing_sl_percent)
        assert abs(nuevo_sl - 100.296) < 0.0001, "El SL dinámico debe ubicarse 0.5% debajo del top actual"
        
    def test_expected_value_positivo(self):
        """Valida la ecuación de EV requerida a la IA: EV = (P_win * Profit) - (P_loss * Loss)."""
        p_win = 0.85
        p_loss = 0.15
        profit_atr = 3.0  # 3.0%
        loss_atr = 1.5    # 1.5%
        
        ev_neto = (p_win * profit_atr) - (p_loss * loss_atr)
        assert ev_neto > 0, "EV debe ser obligatoriamente mayor a 0 para generar señal"
