"""
V5.3: Módulo de persistencia SQLite + métricas de riesgo.
Registra trades, calcula Win Rate, Profit Factor, Sharpe Ratio, Max Drawdown.
"""
import sqlite3
import os
import math
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_db():
    """Crea las tablas si no existen."""
    conn = _get_conn()
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            action TEXT NOT NULL,
            entry_price REAL,
            exit_price REAL,
            quantity REAL,
            pnl REAL DEFAULT 0,
            confidence REAL,
            temporalidad TEXT,
            razon TEXT,
            status TEXT DEFAULT 'OPEN',
            closed_at TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT UNIQUE NOT NULL,
            balance_inicio REAL,
            balance_fin REAL,
            pnl_dia REAL DEFAULT 0,
            trades_ganados INTEGER DEFAULT 0,
            trades_perdidos INTEGER DEFAULT 0
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            confidence REAL,
            temporalidad TEXT,
            razon TEXT,
            fg_valor INTEGER,
            executed INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE TRADES
# ═══════════════════════════════════════════════════════════════════════════════

def registrar_trade_abierto(symbol, side, action, entry_price, quantity, confidence, temporalidad, razon):
    """Registra un trade abierto en la base de datos."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO trades (timestamp, symbol, side, action, entry_price, quantity, confidence, temporalidad, razon, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
    """, (datetime.now().isoformat(), symbol, side, action, entry_price, quantity, confidence, temporalidad, razon))
    conn.commit()
    trade_id = c.lastrowid
    conn.close()
    return trade_id


def registrar_trade_cerrado(symbol, pnl, exit_price=None):
    """Marca un trade como cerrado y registra PNL."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE trades 
        SET status = 'CLOSED', pnl = ?, exit_price = ?, closed_at = ?
        WHERE symbol = ? AND status = 'OPEN'
        ORDER BY id DESC LIMIT 1
    """, (pnl, exit_price, datetime.now().isoformat(), symbol))
    conn.commit()
    conn.close()


def registrar_decision(symbol, action, confidence, temporalidad, razon, fg_valor, executed):
    """Registra cada decisión de la IA (ejecutada o no)."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO decisions (timestamp, symbol, action, confidence, temporalidad, razon, fg_valor, executed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), symbol, action, confidence, temporalidad, razon, fg_valor, 1 if executed else 0))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# BALANCES DIARIOS
# ═══════════════════════════════════════════════════════════════════════════════

def registrar_balance_diario(fecha, balance_inicio=None, balance_fin=None):
    """Registra o actualiza el balance diario."""
    conn = _get_conn()
    c = conn.cursor()
    
    c.execute("SELECT id FROM daily_balances WHERE fecha = ?", (fecha,))
    existe = c.fetchone()
    
    if existe:
        if balance_fin is not None:
            c.execute("""
                UPDATE daily_balances SET balance_fin = ?, pnl_dia = balance_fin - balance_inicio
                WHERE fecha = ?
            """, (balance_fin, fecha))
    else:
        c.execute("""
            INSERT INTO daily_balances (fecha, balance_inicio, balance_fin)
            VALUES (?, ?, ?)
        """, (fecha, balance_inicio or 0, balance_fin or balance_inicio or 0))
    
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# MÉTRICAS DE RIESGO
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_metricas_riesgo(dias=30):
    """Calcula Win Rate, Profit Factor, Sharpe Ratio, Max Drawdown."""
    conn = _get_conn()
    c = conn.cursor()
    
    fecha_desde = (datetime.now() - timedelta(days=dias)).isoformat()
    
    c.execute("""
        SELECT pnl FROM trades 
        WHERE status = 'CLOSED' AND closed_at >= ?
        ORDER BY closed_at
    """, (fecha_desde,))
    
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "expected_value": 0,
            "total_pnl": 0
        }
    
    pnls = [row['pnl'] for row in rows]
    ganados = [p for p in pnls if p > 0]
    perdidos = [p for p in pnls if p <= 0]
    
    total_trades = len(pnls)
    win_rate = len(ganados) / total_trades if total_trades > 0 else 0
    
    sum_ganados = sum(ganados) if ganados else 0
    sum_perdidos = abs(sum(perdidos)) if perdidos else 0
    profit_factor = sum_ganados / sum_perdidos if sum_perdidos > 0 else float('inf') if sum_ganados > 0 else 0
    
    avg_win = sum_ganados / len(ganados) if ganados else 0
    avg_loss = sum_perdidos / len(perdidos) if perdidos else 0
    
    # Expected Value = (win_rate × avg_win) - (loss_rate × avg_loss)
    expected_value = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    # Sharpe Ratio (simplificado, retorno diario)
    mean_pnl = sum(pnls) / len(pnls)
    if len(pnls) > 1:
        variance = sum((p - mean_pnl) ** 2 for p in pnls) / (len(pnls) - 1)
        std_pnl = math.sqrt(variance) if variance > 0 else 1
        sharpe_ratio = (mean_pnl / std_pnl) * math.sqrt(252)  # Anualizado
    else:
        sharpe_ratio = 0
    
    # Max Drawdown
    peak = 0
    max_dd = 0
    cumulative = 0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    
    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate * 100, 1),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "max_drawdown": round(max_dd, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expected_value": round(expected_value, 2),
        "total_pnl": round(sum(pnls), 2)
    }


def obtener_datos_kelly():
    """Obtiene win_rate y ratio ganancia/pérdida para Kelly Criterion."""
    metricas = calcular_metricas_riesgo(dias=30)
    
    if metricas['total_trades'] < 10:
        return None  # No hay suficientes datos
    
    win_rate = metricas['win_rate'] / 100
    if metricas['avg_loss'] > 0:
        win_loss_ratio = metricas['avg_win'] / metricas['avg_loss']
    else:
        win_loss_ratio = 2.0  # Default conservador
    
    return {
        "win_rate": win_rate,
        "win_loss_ratio": win_loss_ratio,
        "total_trades": metricas['total_trades']
    }


def generar_resumen_metricas():
    """Genera texto formateado de métricas para Telegram."""
    m = calcular_metricas_riesgo(dias=30)
    
    if m['total_trades'] == 0:
        return "📊 Sin trades cerrados en los últimos 30 días."
    
    # Evaluación de viabilidad
    evaluar = []
    if m['win_rate'] >= 55:
        evaluar.append("✅ Win Rate > 55%")
    else:
        evaluar.append(f"⚠️ Win Rate {m['win_rate']}% < 55%")
    
    if m['profit_factor'] >= 1.5:
        evaluar.append("✅ Profit Factor > 1.5")
    else:
        evaluar.append(f"⚠️ Profit Factor {m['profit_factor']} < 1.5")
    
    if m['sharpe_ratio'] >= 1.0:
        evaluar.append("✅ Sharpe Ratio > 1.0")
    else:
        evaluar.append(f"⚠️ Sharpe Ratio {m['sharpe_ratio']} < 1.0")
    
    viabilidad = "\n".join(evaluar)
    
    return f"""📈 *MÉTRICAS DE RIESGO (30d)*
━━━━━━━━━━━━━━━━━━━━━━━
📊 *Total trades:* `{m['total_trades']}`
🎯 *Win Rate:* `{m['win_rate']}%`
💰 *Profit Factor:* `{m['profit_factor']}`
📐 *Sharpe Ratio:* `{m['sharpe_ratio']}`
📉 *Max Drawdown:* `${m['max_drawdown']}`
💵 *Avg Win:* `+${m['avg_win']}`
💸 *Avg Loss:* `-${m['avg_loss']}`
🎲 *Expected Value:* `${m['expected_value']}/trade`
💰 *PNL Total:* `${m['total_pnl']}`

*Evaluación Mainnet:*
{viabilidad}"""
