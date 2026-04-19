"""
V9.0: Motor de Backtesting Realista.
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
    Simula trades usando la estrategia V9.0 del bot sobre datos históricos.
    Misma lógica que bot_binance.py: RSI extremo + filtro tendencia EMA.
    """
    from indicators import analizar_indicadores_completo

    # Thresholds V9.0 (iguales a bot_binance.py)
    RSI_SOBREVENTA  = 38
    RSI_SOBRECOMPRA = 62
    ATR_MIN_PCT     = 0.20  # filtro mínimo de volatilidad
    ATR_MULT_SL     = 1.5
    TP_RATIO        = 2.0

    trades = []
    posicion_activa = None
    ventana = 200

    for i in range(ventana, len(velas), 4):
        ventana_actual = velas[i - ventana:i]
        klines = [[v['timestamp'], v['open'], v['high'], v['low'], v['close'], v['volume']]
                  for v in ventana_actual]

        ind = analizar_indicadores_completo(klines)
        if not ind:
            continue

        precio_actual = float(ind['precio_actual'])
        atr           = float(ind.get('atr', 0))
        atr_pct       = float(ind.get('atr_percent', 0))
        rsi           = float(ind.get('rsi', 50))
        tend          = (ind.get('tendencia_ema', '') or '').upper()
        hist          = float((ind.get('macd') or {}).get('histograma', 0))

        # ── VERIFICAR POSICIÓN ACTIVA ──
        if posicion_activa:
            vela = velas[i]
            hit_tp = hit_sl = False

            if posicion_activa['side'] == 'LONG':
                if vela['high'] >= posicion_activa['tp']:
                    hit_tp = True
                if vela['low'] <= posicion_activa['sl']:
                    hit_sl = True
            else:
                if vela['low'] <= posicion_activa['tp']:
                    hit_tp = True
                if vela['high'] >= posicion_activa['sl']:
                    hit_sl = True

            if hit_sl:
                pnl_bruto = -abs(posicion_activa['entry'] - posicion_activa['sl']) / posicion_activa['entry'] * 100
                pnl_pct = pnl_bruto - (FEE + SLIPPAGE) * 100
                trades.append({'entry_time': posicion_activa['entry_time'], 'exit_time': vela['timestamp'],
                                'side': posicion_activa['side'], 'entry': posicion_activa['entry'],
                                'exit': posicion_activa['sl'], 'pnl_pct': round(pnl_pct, 2),
                                'result': 'LOSS', 'razon': posicion_activa['razon']})
                posicion_activa = None
            elif hit_tp:
                pnl_bruto = abs(posicion_activa['tp'] - posicion_activa['entry']) / posicion_activa['entry'] * 100
                pnl_pct = pnl_bruto - (FEE + SLIPPAGE) * 100
                trades.append({'entry_time': posicion_activa['entry_time'], 'exit_time': vela['timestamp'],
                                'side': posicion_activa['side'], 'entry': posicion_activa['entry'],
                                'exit': posicion_activa['tp'], 'pnl_pct': round(pnl_pct, 2),
                                'result': 'WIN', 'razon': posicion_activa['razon']})
                posicion_activa = None
            continue

        # ── SEÑAL V9.0 (idéntica a bot_binance.py) ──
        if atr_pct < ATR_MIN_PCT:
            continue

        accion = razon = None
        confianza = 0.0

        if rsi < RSI_SOBREVENTA:
            if tend == 'BAJISTA_FUERTE':
                continue
            confianza = 0.85 if hist > 0 else 0.72
            accion = 'LONG'
            razon = f"RSI={rsi:.0f} sobrevendido | {tend} | conf={int(confianza*100)}%"
        elif rsi > RSI_SOBRECOMPRA:
            if tend == 'ALCISTA_FUERTE':
                continue
            confianza = 0.85 if hist < 0 else 0.72
            accion = 'SHORT'
            razon = f"RSI={rsi:.0f} sobrecomprado | {tend} | conf={int(confianza*100)}%"

        if not accion:
            continue

        # ── SL/TP con ATR (igual que bot) ──
        dist_sl = max(atr * ATR_MULT_SL, precio_actual * 0.008)
        dist_tp = dist_sl * TP_RATIO

        if accion == 'LONG':
            precio_entrada = precio_actual * (1 + SLIPPAGE)
            sl_price = precio_entrada - dist_sl
            tp_price = precio_entrada + dist_tp
        else:
            precio_entrada = precio_actual * (1 - SLIPPAGE)
            sl_price = precio_entrada + dist_sl
            tp_price = precio_entrada - dist_tp

        posicion_activa = {
            'side': accion,
            'entry': precio_entrada,
            'tp': tp_price,
            'sl': sl_price,
            'entry_time': velas[i]['timestamp'],
            'razon': razon
        }

    return trades


def generar_reporte(trades, symbol, dias):
    """V6.1: Genera un reporte formateado incluyendo costos reales de fees y slippage."""
    
    print(f"\n{'='*60}")
    print(f"📊 REPORTE BACKTESTING V9.0 (Fees+Slippage) — {symbol}")
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
    parser = argparse.ArgumentParser(description='Backtesting Bot Binance V9.0')
    parser.add_argument('--dias', type=int, default=30, help='Días de datos históricos (default: 30)')
    parser.add_argument('--symbol', type=str, default=None, help='Símbolo específico (ej: BTCUSDT)')
    args = parser.parse_args()
    
    print(f"\n🔬 BACKTESTING BOT BINANCE V9.0")
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
