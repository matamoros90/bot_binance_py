"""
V6.1: Motor de Backtesting Realista.
Simula la estrategia del bot con datos históricos de Binance.
Incluye fees y slippage reales para resultados más precisos.

Uso:
    python backtesting.py                    # Últimos 30 días
    python backtesting.py --dias 60          # Últimos 60 días
    python backtesting.py --symbol BTCUSDT   # Solo un símbolo
"""
import sys
import os
import json
import math
import argparse
from datetime import datetime, timedelta

# Importar funciones del bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("BINANCE_TESTNET", "True")
os.environ.setdefault("TELEGRAM_TOKEN", "")
os.environ.setdefault("TELEGRAM_CHAT_ID", "")

from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
# V6.1: COSTOS REALISTAS DE TRADING (Binance Futures)
# ═══════════════════════════════════════════════════════════════
# Fee de Binance Futures (maker + taker round-trip estimado).
# Taker fee = 0.04% por lado × 2 = 0.08%. Añadimos 0.04% extra por margen.
FEE = 0.0012       # 0.12% round-trip (entrada + salida) con fee taker
# Slippage estimado por diferencia entre precio teórico y precio de ejecución real.
SLIPPAGE = 0.0005  # 0.05% slippage promedio en Futures líquidos


def conectar_binance():
    """Conecta a Binance (testnet o mainnet según configuración)."""
    usar_testnet = os.getenv("BINANCE_TESTNET", "True").lower() in ("true", "1", "yes")
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_SECRET", "")
    
    client = Client(api_key, api_secret, testnet=usar_testnet)
    modo = "TESTNET" if usar_testnet else "MAINNET"
    print(f"✅ Conectado a Binance ({modo})")
    return client


def obtener_velas_historicas(client, symbol, intervalo, dias):
    """Descarga velas históricas de Binance."""
    try:
        start_str = f"{dias} days ago UTC"
        klines = client.futures_klines(
            symbol=symbol,
            interval=intervalo,
            startStr=start_str,
            limit=1000
        )
        velas = []
        for k in klines:
            velas.append({
                'timestamp': k[0],
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            })
        return velas
    except Exception as e:
        print(f"⚠️ Error obteniendo velas de {symbol}: {e}")
        return []


def simular_estrategia(velas, config):
    """
    Simula trades usando la estrategia del bot sobre datos históricos.
    
    Recorre las velas y en cada ventana de 200 velas:
    1. Calcula los 14 indicadores
    2. Aplica las mismas reglas del bot (RSI, EMA, pre-filtro)
    3. Simula entrada/salida con TP/SL reales
    """
    from bot_binance import (
        calcular_rsi, calcular_ema, calcular_macd,
        calcular_bollinger, calcular_atr,
        obtener_tendencia_ema, CONFIANZA_MINIMA
    )
    
    trades = []
    posicion_activa = None
    
    ventana = 200  # Misma ventana que el bot
    
    for i in range(ventana, len(velas), 4):  # Paso de 4 velas (simular análisis cada 4h)
        # Tomar ventana de 200 velas
        ventana_actual = velas[i - ventana:i]
        precios_cierre = [v['close'] for v in ventana_actual]
        
        if len(precios_cierre) < ventana:
            continue
        
        precio_actual = precios_cierre[-1]
        
        # Calcular indicadores (exactamente como el bot)
        rsi = calcular_rsi(precios_cierre)
        ema_20 = calcular_ema(precios_cierre, 20)
        ema_50 = calcular_ema(precios_cierre, 50)
        macd_data = calcular_macd(precios_cierre)
        
        tendencia = obtener_tendencia_ema(precio_actual, ema_20, ema_50,
                                           calcular_ema(precios_cierre, 200))
        
        precios_100 = precios_cierre[-100:]
        precio_max = max(precios_100)
        precio_min = min(precios_100)
        posicion_rango = ((precio_actual - precio_min) / (precio_max - precio_min) * 100) if precio_max != precio_min else 50
        
        # ATR para SL dinámico
        highs = [v['high'] for v in ventana_actual]
        lows = [v['low'] for v in ventana_actual]
        closes = precios_cierre
        atr = calcular_atr(highs, lows, closes)
        
        # ═══════════════════════════════════════════════════════════════════
        # VERIFICAR POSICIÓN ACTIVA — ¿Tocó TP o SL?
        # ═══════════════════════════════════════════════════════════════════
        if posicion_activa:
            vela = velas[i]
            hit_tp = False
            hit_sl = False
            
            if posicion_activa['side'] == 'LONG':
                if vela['high'] >= posicion_activa['tp']:
                    hit_tp = True
                if vela['low'] <= posicion_activa['sl']:
                    hit_sl = True
            else:  # SHORT
                if vela['low'] <= posicion_activa['tp']:
                    hit_tp = True
                if vela['high'] >= posicion_activa['sl']:
                    hit_sl = True
            
            if hit_sl:  # SL hit primero (peor caso)
                pnl_pct_bruto = -abs(posicion_activa['entry'] - posicion_activa['sl']) / posicion_activa['entry'] * 100
                # V6.1: Descontar fee round-trip + slippage de salida
                costos_pct = (FEE + SLIPPAGE) * 100
                pnl_pct = pnl_pct_bruto - costos_pct
                trades.append({
                    'entry_time': posicion_activa['entry_time'],
                    'exit_time': vela['timestamp'],
                    'side': posicion_activa['side'],
                    'entry': posicion_activa['entry'],
                    'exit': posicion_activa['sl'],
                    'pnl_pct': round(pnl_pct, 2),
                    'result': 'LOSS',
                    'razon': posicion_activa['razon']
                })
                posicion_activa = None
            elif hit_tp:
                pnl_pct_bruto = abs(posicion_activa['tp'] - posicion_activa['entry']) / posicion_activa['entry'] * 100
                # V6.1: Descontar fee round-trip + slippage de salida
                costos_pct = (FEE + SLIPPAGE) * 100
                pnl_pct = pnl_pct_bruto - costos_pct
                trades.append({
                    'entry_time': posicion_activa['entry_time'],
                    'exit_time': vela['timestamp'],
                    'side': posicion_activa['side'],
                    'entry': posicion_activa['entry'],
                    'exit': posicion_activa['tp'],
                    'pnl_pct': round(pnl_pct, 2),
                    'result': 'WIN',
                    'razon': posicion_activa['razon']
                })
                posicion_activa = None
            
            continue  # No abrir nueva posición si hay una activa
        
        # ═══════════════════════════════════════════════════════════════════
        # PRE-FILTRO (igual que V5.3)
        # ═══════════════════════════════════════════════════════════════════
        tendencia_str = tendencia.upper() if tendencia else ''
        if 40 < rsi < 60 and 'LATERAL' in tendencia_str and 35 < posicion_rango < 65:
            continue
        
        # ═══════════════════════════════════════════════════════════════════
        # DECISIÓN DE TRADING (simulada, sin Gemini)
        # Usa las mismas reglas que el bot impone post-IA
        # ═══════════════════════════════════════════════════════════════════
        accion = None
        razon = ""
        confianza = 0
        
        # Señal LONG
        if rsi < 35 and 'ALCISTA' in tendencia_str and posicion_rango < 30:
            accion = 'LONG'
            confianza = 0.80
            razon = f"RSI sobreventa ({rsi:.0f}), tendencia alcista, rango bajo ({posicion_rango:.0f}%)"
        elif rsi < 25 and posicion_rango < 20:
            accion = 'LONG'
            confianza = 0.85
            razon = f"RSI extremo ({rsi:.0f}), precio en mínimos ({posicion_rango:.0f}%)"
        
        # Señal SHORT
        elif rsi > 65 and 'BAJISTA' in tendencia_str and posicion_rango > 70:
            accion = 'SHORT'
            confianza = 0.80
            razon = f"RSI sobrecompra ({rsi:.0f}), tendencia bajista, rango alto ({posicion_rango:.0f}%)"
        elif rsi > 75 and posicion_rango > 80:
            accion = 'SHORT'
            confianza = 0.85
            razon = f"RSI extremo ({rsi:.0f}), precio en máximos ({posicion_rango:.0f}%)"
        
        # MACD confirma
        if accion and macd_data['histograma'] != 0:
            if accion == 'LONG' and macd_data['histograma'] > 0:
                confianza += 0.05
            elif accion == 'SHORT' and macd_data['histograma'] < 0:
                confianza += 0.05
        
        # Validar contra tendencia
        if accion == 'SHORT' and 'ALCISTA' in tendencia_str:
            accion = None
        if accion == 'LONG' and 'BAJISTA' in tendencia_str:
            accion = None
        
        if not accion or confianza < CONFIANZA_MINIMA:
            continue
        
        # ═══════════════════════════════════════════════════════════════════
        # ABRIR POSICIÓN SIMULADA
        # ═══════════════════════════════════════════════════════════════════
        tp_pct = config.get('tp', 0.035)
        sl_pct = config.get('sl', 0.025)
        
        # SL dinámico con ATR
        if atr > 0:
            sl_distance = max(atr * 1.5, precio_actual * 0.015)
        else:
            sl_distance = precio_actual * sl_pct
        
        if accion == 'LONG':
            # V6.1: Aplicar slippage de entrada (precio real = precio_actual + slippage)
            precio_entrada = precio_actual * (1 + SLIPPAGE)
            tp_price = precio_entrada * (1 + tp_pct)
            sl_price = precio_entrada - sl_distance
        else:
            # V6.1: Aplicar slippage de entrada para SHORT (ejecución a precio menor)
            precio_entrada = precio_actual * (1 - SLIPPAGE)
            tp_price = precio_entrada * (1 - tp_pct)
            sl_price = precio_entrada + sl_distance
        
        posicion_activa = {
            'side': accion,
            'entry': precio_entrada,  # V6.1: precio con slippage aplicado
            'tp': tp_price,
            'sl': sl_price,
            'entry_time': velas[i]['timestamp'],
            'razon': razon
        }
    
    return trades


def generar_reporte(trades, symbol, dias):
    """V6.1: Genera un reporte formateado incluyendo costos reales de fees y slippage."""
    
    print(f"\n{'='*60}")
    print(f"📊 REPORTE BACKTESTING V6.1 (Fees+Slippage) — {symbol}")
    print(f"📅 Período: últimos {dias} días")
    print(f"💸 Fee Round-Trip: {FEE*100:.2f}% | Slippage: {SLIPPAGE*100:.3f}%")
    print(f"{'='*60}")
    
    if not trades:
        print("❌ No se generaron trades en este período.")
        print("   Esto puede significar que los filtros son muy estrictos.")
        return None
    
    wins = [t for t in trades if t['result'] == 'WIN']
    losses = [t for t in trades if t['result'] == 'LOSS']
    
    total = len(trades)
    win_rate = len(wins) / total * 100 if total > 0 else 0
    
    sum_wins = sum(t['pnl_pct'] for t in wins)
    sum_losses = abs(sum(t['pnl_pct'] for t in losses))
    profit_factor = sum_wins / sum_losses if sum_losses > 0 else float('inf')
    
    avg_win = sum_wins / len(wins) if wins else 0
    avg_loss = sum_losses / len(losses) if losses else 0
    
    total_pnl = sum(t['pnl_pct'] for t in trades)
    
    # Sharpe Ratio simplificado
    pnls = [t['pnl_pct'] for t in trades]
    mean_pnl = total_pnl / total
    if total > 1:
        variance = sum((p - mean_pnl) ** 2 for p in pnls) / (total - 1)
        std_pnl = math.sqrt(variance) if variance > 0 else 1
        sharpe = (mean_pnl / std_pnl) * math.sqrt(252)
    else:
        sharpe = 0
    
    # Max Drawdown
    peak = 0
    max_dd = 0
    cumulative = 0
    for t in trades:
        cumulative += t['pnl_pct']
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    
    # Expected Value
    ev = (win_rate/100 * avg_win) - ((100 - win_rate)/100 * avg_loss)
    
    print(f"\n📊 RESULTADOS:")
    print(f"   Total trades: {total}")
    print(f"   ✅ Ganados: {len(wins)} ({win_rate:.1f}%)")
    print(f"   ❌ Perdidos: {len(losses)} ({100 - win_rate:.1f}%)")
    print(f"\n💰 RENDIMIENTO:")
    print(f"   PNL Total: {total_pnl:+.2f}%")
    print(f"   Avg Win: +{avg_win:.2f}%")
    print(f"   Avg Loss: -{avg_loss:.2f}%")
    print(f"\n📐 MÉTRICAS DE RIESGO:")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print(f"   Sharpe Ratio: {sharpe:.2f}")
    print(f"   Max Drawdown: -{max_dd:.2f}%")
    print(f"   Expected Value: {ev:+.3f}% / trade")
    
    print(f"\n🎯 EVALUACIÓN MAINNET:")
    checks = []
    if win_rate >= 55:
        checks.append(f"   ✅ Win Rate {win_rate:.1f}% >= 55%")
    else:
        checks.append(f"   ❌ Win Rate {win_rate:.1f}% < 55%")
    
    if profit_factor >= 1.5:
        checks.append(f"   ✅ Profit Factor {profit_factor:.2f} >= 1.5")
    else:
        checks.append(f"   ❌ Profit Factor {profit_factor:.2f} < 1.5")
    
    if sharpe >= 1.0:
        checks.append(f"   ✅ Sharpe Ratio {sharpe:.2f} >= 1.0")
    else:
        checks.append(f"   ❌ Sharpe Ratio {sharpe:.2f} < 1.0")
    
    if max_dd < 10:
        checks.append(f"   ✅ Max Drawdown {max_dd:.2f}% < 10%")
    else:
        checks.append(f"   ❌ Max Drawdown {max_dd:.2f}% >= 10%")
    
    for c in checks:
        print(c)
    
    passed = sum(1 for c in checks if '✅' in c)
    print(f"\n   📋 {passed}/4 criterios cumplidos")
    if passed >= 3:
        print("   🟢 VIABLE para Mainnet (con precaución)")
    elif passed >= 2:
        print("   🟡 PARCIALMENTE viable — necesita ajustes")
    else:
        print("   🔴 NO viable — la estrategia necesita mejoras")
    
    # Últimos 5 trades
    print(f"\n📝 ÚLTIMOS 5 TRADES:")
    for t in trades[-5:]:
        emoji = '✅' if t['result'] == 'WIN' else '❌'
        fecha = datetime.fromtimestamp(t['entry_time'] / 1000).strftime('%m/%d %H:%M')
        print(f"   {emoji} {fecha} | {t['side']:5s} | Entry: ${t['entry']:.4f} → Exit: ${t['exit']:.4f} | {t['pnl_pct']:+.2f}%")
        print(f"      └─ {t['razon'][:70]}")
    
    print(f"\n{'='*60}\n")
    
    return {
        'total_trades': total,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'sharpe': sharpe,
        'max_drawdown': max_dd,
        'total_pnl': total_pnl,
        'ev': ev
    }


def main():
    parser = argparse.ArgumentParser(description='Backtesting Bot Binance V5.3')
    parser.add_argument('--dias', type=int, default=30, help='Días de datos históricos (default: 30)')
    parser.add_argument('--symbol', type=str, default=None, help='Símbolo específico (ej: BTCUSDT)')
    args = parser.parse_args()
    
    print(f"\n🔬 BACKTESTING BOT BINANCE V5.3")
    print(f"📅 Período: últimos {args.dias} días")
    print(f"{'='*60}\n")
    
    client = conectar_binance()
    
    # Símbolos a analizar
    if args.symbol:
        symbols = [args.symbol.upper()]
    else:
        # Top 5 por defecto para backtesting rápido
        symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
    
    config = {
        'tp': 0.035,   # +3.5% (misma config que el bot 1h)
        'sl': 0.025,   # -2.5%
    }
    
    resultados_globales = []
    
    for symbol in symbols:
        print(f"📥 Descargando {args.dias} días de {symbol}...")
        velas = obtener_velas_historicas(client, symbol, '1h', args.dias)
        
        if len(velas) < 200:
            print(f"⚠️ {symbol}: Insuficientes velas ({len(velas)}), saltando")
            continue
        
        print(f"   ✅ {len(velas)} velas descargadas. Simulando...")
        trades = simular_estrategia(velas, config)
        resultado = generar_reporte(trades, symbol, args.dias)
        
        if resultado:
            resultado['symbol'] = symbol
            resultados_globales.append(resultado)
    
    # Resumen global
    if len(resultados_globales) > 1:
        print(f"\n{'='*60}")
        print(f"📊 RESUMEN GLOBAL — {len(resultados_globales)} símbolos")
        print(f"{'='*60}")
        
        total_trades = sum(r['total_trades'] for r in resultados_globales)
        avg_wr = sum(r['win_rate'] for r in resultados_globales) / len(resultados_globales)
        avg_pf = sum(r['profit_factor'] for r in resultados_globales) / len(resultados_globales)
        total_pnl = sum(r['total_pnl'] for r in resultados_globales)
        
        print(f"   Total trades: {total_trades}")
        print(f"   Win Rate promedio: {avg_wr:.1f}%")
        print(f"   Profit Factor promedio: {avg_pf:.2f}")
        print(f"   PNL Total acumulado: {total_pnl:+.2f}%")


if __name__ == '__main__':
    main()
