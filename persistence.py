"""
V6.2: Módulo de persistencia SQLite + métricas de riesgo + auditoría IA.
Registra trades, calcula Win Rate, Profit Factor, Sharpe Ratio, Max Drawdown.
Nuevo (V6.2):
  - Tabla ia_metricas: snapshots históricos de señales y approval rate.
  - guardar_metricas_ia(): persiste el estado del filtro IA en cada resumen diario.
  - obtener_metricas_ia_periodo(): consulta approval rate por ventana temporal (24h / 7d).
  - Alertas inteligentes: avisa si el filtro IA es demasiado restrictivo o permisivo.
"""
import sqlite3
import os
import math
from datetime import datetime, timedelta

# Directorio base para la base de datos.
# - En local: por defecto, la misma carpeta del proyecto.
# - En Koyeb: configurar la variable de entorno DATA_DIR apuntando al volumen persistente.
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "trades.db")


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
            closed_at TEXT,
            ia_validado INTEGER DEFAULT 0
        )
    """)

    # V6.1: Migración segura — agrega ia_validado si la BD ya existe
    # SQLite no soporta IF NOT EXISTS en ALTER TABLE, usamos try/except.
    try:
        c.execute("ALTER TABLE trades ADD COLUMN ia_validado INTEGER DEFAULT 0")
    except Exception:
        pass  # Columna ya existe — no hacer nada
    
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
    
    # ── V6.2: Tabla de snapshots de métricas IA ─────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS ia_metricas (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp         DATETIME DEFAULT CURRENT_TIMESTAMP,
            senales_total     INTEGER  NOT NULL DEFAULT 0,
            senales_validadas INTEGER  NOT NULL DEFAULT 0,
            approval_rate     REAL     NOT NULL DEFAULT 0.0
        )
    """)

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE TRADES
# ═══════════════════════════════════════════════════════════════════════════════

def registrar_trade_abierto(symbol, side, action, entry_price, quantity, confidence, temporalidad, razon, ia_validado=False):
    """Registra un trade abierto en la base de datos.
    
    Parámetros:
        ia_validado: True si Gemini validó la señal antes de ejecutar el trade.
                     False si el trade se ejecutó sin filtro IA (USAR_IA=False).
    """
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO trades (
            timestamp, symbol, side, action, entry_price, quantity,
            confidence, temporalidad, razon, status, ia_validado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
    """, (
        datetime.now().isoformat(), symbol, side, action,
        entry_price, quantity, confidence, temporalidad, razon,
        1 if ia_validado else 0
    ))
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
        WHERE id = (
            SELECT id FROM trades
            WHERE symbol = ? AND status = 'OPEN'
            ORDER BY id DESC LIMIT 1
        )
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
                UPDATE daily_balances
                SET balance_fin = ?,
                    pnl_dia = CASE
                        WHEN balance_inicio IS NOT NULL THEN ? - balance_inicio
                        ELSE 0
                    END
                WHERE fecha = ?
            """, (balance_fin, balance_fin, fecha))
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

def contar_trades_semana_actual():
    """Cuenta cuántos trades se han abierto desde el lunes de la semana actual."""
    conn = _get_conn()
    c = conn.cursor()
    
    # Calcular el inicio de esta semana (lunes a las 00:00:00)
    hoy = datetime.now()
    inicio_semana = (hoy - timedelta(days=hoy.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    fecha_desde = inicio_semana.isoformat()
    
    c.execute("""
        SELECT count(*) as total FROM trades 
        WHERE timestamp >= ?
    """, (fecha_desde,))
    
    row = c.fetchone()
    conn.close()
    
    return row['total'] if row else 0

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
    
    # ─── Métrica de corto plazo añadida para fase de validación de Capital ───
    def calc_stats(subset: list):
        if not subset:
            return {"win_rate": 0, "profit_factor": 0}
        w = [p for p in subset if p > 0]
        l = [abs(p) for p in subset if p <= 0]
        wr = round((len(w) / len(subset)) * 100, 2)
        pf = round(sum(w) / sum(l), 2) if sum(l) > 0 else (99.9 if sum(w) > 0 else 0)
        return {"win_rate": wr, "profit_factor": pf}

    # Calcula la ventana de los últimos 10 trades cerrados (recientes)
    ultimos_10 = pnls[-10:] if len(pnls) >= 10 else pnls
    stats_10 = calc_stats(ultimos_10)
    
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
        if dd > max_drawdown:
            max_drawdown = dd
    
    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate * 100, 1),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "max_drawdown": round(max_dd, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expected_value": round(expected_value, 2),
        "total_pnl": round(sum(pnls), 2),
        # V6.2: Métricas de los últimos 10 trades para CapitalManager
        "profit_factor_10": stats_10['profit_factor'],
        "win_rate_10": stats_10['win_rate']
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPARATIVA IA vs NO-IA (V6.1)
# ═══════════════════════════════════════════════════════════════════════════════

def _calcular_metricas_grupo(pnls: list) -> dict:
    """Helper interno: calcula win_rate y profit_factor para una lista de PNLs."""
    if not pnls:
        return {"total": 0, "win_rate": 0.0, "profit_factor": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "total_pnl": 0.0}

    ganados  = [p for p in pnls if p > 0]
    perdidos = [p for p in pnls if p <= 0]

    total       = len(pnls)
    win_rate    = round(len(ganados) / total * 100, 1) if total else 0.0

    sum_g = sum(ganados)        if ganados  else 0.0
    sum_p = abs(sum(perdidos))  if perdidos else 0.0

    profit_factor = round(sum_g / sum_p, 2) if sum_p > 0 else (float('inf') if sum_g > 0 else 0.0)
    avg_win  = round(sum_g / len(ganados),  2) if ganados  else 0.0
    avg_loss = round(sum_p / len(perdidos), 2) if perdidos else 0.0

    return {
        "total": total,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "total_pnl": round(sum(pnls), 2),
    }


def comparar_metricas_ia(dias: int = 30) -> dict:
    """V6.1: Compara métricas de trades validados por IA vs trades sin validación IA.

    Útil para auditar si el filtro Gemini realmente mejora los resultados.

    Parámetros:
        dias: Ventana de tiempo hacia atrás (default: 30 días).

    Retorna dict con estructura:
        {
            "con_ia":  { total, win_rate, profit_factor, avg_win, avg_loss, total_pnl },
            "sin_ia":  { total, win_rate, profit_factor, avg_win, avg_loss, total_pnl },
            "ventaja_win_rate":    float  (+X% = IA supera a no-IA)
            "ventaja_profit_factor": float
            "periodo_dias": int
        }
    """
    conn = _get_conn()
    c    = conn.cursor()

    fecha_desde = (datetime.now() - timedelta(days=dias)).isoformat()

    c.execute("""
        SELECT pnl, ia_validado
        FROM trades
        WHERE status = 'CLOSED' AND closed_at >= ?
        ORDER BY closed_at
    """, (fecha_desde,))

    rows = c.fetchall()
    conn.close()

    pnls_ia     = [r['pnl'] for r in rows if r['ia_validado'] == 1]
    pnls_no_ia  = [r['pnl'] for r in rows if r['ia_validado'] == 0]

    metricas_ia    = _calcular_metricas_grupo(pnls_ia)
    metricas_no_ia = _calcular_metricas_grupo(pnls_no_ia)

    ventaja_wr = round(metricas_ia['win_rate'] - metricas_no_ia['win_rate'], 1)
    ventaja_pf = round(
        (metricas_ia['profit_factor'] - metricas_no_ia['profit_factor']),
        2
    ) if metricas_no_ia['profit_factor'] not in (0.0, float('inf')) else 0.0

    return {
        "con_ia":                metricas_ia,
        "sin_ia":               metricas_no_ia,
        "ventaja_win_rate":     ventaja_wr,
        "ventaja_profit_factor": ventaja_pf,
        "periodo_dias":         dias,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENCIA Y ANÁLISIS TEMPORAL DE MÉTRICAS IA (V6.2)
# ═══════════════════════════════════════════════════════════════════════════════

# Umbrales para alertas inteligentes de aprobación IA
_ALERTA_IA_MINIMA = 0.20   # < 20% → filtro demasiado restrictivo
_ALERTA_IA_MAXIMA = 0.70   # > 70% → filtro demasiado permisivo


def guardar_metricas_ia(senales_total: int, senales_validadas: int) -> dict:
    """V6.2: Persiste un snapshot del estado del filtro IA en la tabla ia_metricas.

    Calcula el approval_rate y registra el snapshot con timestamp actual.
    También evalúa alertas y las devuelve como texto para incluir en Telegram.

    Retorna:
        dict con claves:
            - approval_rate: float (fracción, 0.0–1.0)
            - alerta_log:    str o None  (texto para log)
            - alerta_tg:     str o None  (texto formateado para Telegram)
    """
    approval_rate = round(senales_validadas / senales_total, 4) if senales_total > 0 else 0.0

    conn = _get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO ia_metricas (senales_total, senales_validadas, approval_rate)
        VALUES (?, ?, ?)
    """, (senales_total, senales_validadas, approval_rate))
    conn.commit()
    conn.close()

    # ── Evaluar alertas ──────────────────────────────────────────────────────
    alerta_log = None
    alerta_tg  = None

    if senales_total > 0:
        pct = round(approval_rate * 100, 1)
        if approval_rate < _ALERTA_IA_MINIMA:
            alerta_log = (
                f"⚠️ [IA-ALERTA] IA demasiado RESTRICTIVA "
                f"({pct}% sobre {senales_total} señales). "
                "Puede estar perdiendo oportunidades."
            )
            alerta_tg = (
                f"⚠️ *ALERTA IA — Filtro demasiado restrictivo*\n"
                f"`{pct}%` de aprobación sobre `{senales_total}` señales "
                f"(umbral mín: `{int(_ALERTA_IA_MINIMA*100)}%`).\n"
                "📉 Riesgo de pérdida de oportunidades de trading."
            )
        elif approval_rate > _ALERTA_IA_MAXIMA:
            alerta_log = (
                f"⚠️ [IA-ALERTA] IA demasiado PERMISIVA "
                f"({pct}% sobre {senales_total} señales). "
                "Filtro posiblemente inefectivo."
            )
            alerta_tg = (
                f"⚠️ *ALERTA IA — Filtro demasiado permisivo*\n"
                f"`{pct}%` de aprobación sobre `{senales_total}` señales "
                f"(umbral máx: `{int(_ALERTA_IA_MAXIMA*100)}%`).\n"
                "📈 El filtro puede no estar siendo efectivo."
            )

    return {
        "approval_rate": approval_rate,
        "alerta_log":    alerta_log,
        "alerta_tg":     alerta_tg,
    }


def obtener_metricas_ia_periodo(dias: int = 1) -> dict:
    """V6.2: Obtiene métricas agregadas del filtro IA para una ventana temporal.

    Agrega todos los snapshots registrados en ia_metricas dentro del período
    solicitado y calcula el approval_rate resultante.

    Parámetros:
        dias: Número de días hacia atrás. Ejemplos:
              1  → últimas 24 horas
              7  → última semana
              30 → último mes

    Retorna dict con:
        senales_total, senales_validadas, approval_rate, snapshots (número de registros)
    """
    conn = _get_conn()
    c    = conn.cursor()

    fecha_desde = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        SELECT
            COALESCE(SUM(senales_total),     0) AS total,
            COALESCE(SUM(senales_validadas), 0) AS validadas,
            COUNT(*)                            AS snapshots
        FROM ia_metricas
        WHERE timestamp >= ?
    """, (fecha_desde,))

    row = c.fetchone()
    conn.close()

    total     = int(row['total'])     if row else 0
    validadas = int(row['validadas']) if row else 0
    snapshots = int(row['snapshots']) if row else 0
    rate      = round(validadas / total, 4) if total > 0 else 0.0

    return {
        "senales_total":     total,
        "senales_validadas": validadas,
        "approval_rate":     rate,
        "snapshots":         snapshots,
        "periodo_dias":      dias,
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


def generar_resumen_metricas(ia_senales_total: int = 0, ia_senales_validadas: int = 0,
                             alerta_tg: str = None) -> str:
    """V6.2: Genera texto formateado de métricas para Telegram.

    Incluye:
      - Métricas de riesgo (30d)
      - IA Approval Rate de sesión + ventanas 24h y 7d desde DB
      - Comparativa IA vs No-IA
      - Alertas inteligentes si el filtro IA está fuera de rango
      - Evaluación de viabilidad (Win Rate, Profit Factor, Sharpe)

    Parámetros:
        ia_senales_total:     Señales técnicas que llegaron al filtro en la sesión.
        ia_senales_validadas: Señales aprobadas por Gemini en la sesión.
        alerta_tg:            Texto de alerta ya formateado (de guardar_metricas_ia()).
    """
    m = calcular_metricas_riesgo(dias=30)

    if m['total_trades'] == 0:
        return "📊 Sin trades cerrados en los últimos 30 días."

    # ── Evaluación de viabilidad ─────────────────────────────────────────────
    evaluar = []
    evaluar.append("✅ Win Rate > 55%"     if m['win_rate']     >= 55  else f"⚠️ Win Rate {m['win_rate']}% < 55%")
    evaluar.append("✅ Profit Factor > 1.5" if m['profit_factor'] >= 1.5 else f"⚠️ Profit Factor {m['profit_factor']} < 1.5")
    evaluar.append("✅ Sharpe Ratio > 1.0"  if m['sharpe_ratio']  >= 1.0 else f"⚠️ Sharpe Ratio {m['sharpe_ratio']} < 1.0")
    viabilidad = "\n".join(evaluar)

    # ── IA Approval Rate — sesión actual ─────────────────────────────────────
    if ia_senales_total > 0:
        rate_sesion = round((ia_senales_validadas / ia_senales_total) * 100, 1)
        barra = "▓" * int(rate_sesion / 10) + "░" * (10 - int(rate_sesion / 10))
        bloque_approval = f"""
━━━━━━━━━━━━━━━━━━━━━━━
🤖 *IA APPROVAL RATE*
📌 *Sesión:* `{ia_senales_validadas}/{ia_senales_total}` → `{rate_sesion}%` {barra}"""
    else:
        rate_sesion    = None
        bloque_approval = ""

    # ── IA Approval Rate — ventanas temporales desde DB ──────────────────────
    try:
        p24h = obtener_metricas_ia_periodo(dias=1)
        p7d  = obtener_metricas_ia_periodo(dias=7)

        linea_24h = (
            f"📅 *24h:*  `{p24h['senales_validadas']}/{p24h['senales_total']}` → "
            f"`{round(p24h['approval_rate']*100,1)}%`"
            f" _(snapshots: {p24h['snapshots']})_"
            if p24h['senales_total'] > 0 else "📅 *24h:*  sin datos"
        )
        linea_7d = (
            f"📅 *7d:*   `{p7d['senales_validadas']}/{p7d['senales_total']}` → "
            f"`{round(p7d['approval_rate']*100,1)}%`"
            f" _(snapshots: {p7d['snapshots']})_"
            if p7d['senales_total'] > 0 else "📅 *7d:*   sin datos"
        )
        bloque_approval += f"\n{linea_24h}\n{linea_7d}"
    except Exception:
        pass  # No bloquear Telegram si falla la consulta

    # ── Alerta inteligente de calibración ────────────────────────────────────
    bloque_alerta = f"\n\n{alerta_tg}" if alerta_tg else ""

    # ── Comparativa IA vs No-IA (30d desde trades) ───────────────────────────
    cmp = comparar_metricas_ia(dias=30)
    ia  = cmp['con_ia']
    nia = cmp['sin_ia']

    if ia['total'] > 0 and nia['total'] > 0:
        signo_wr = '+' if cmp['ventaja_win_rate'] >= 0 else ''
        signo_pf = '+' if cmp['ventaja_profit_factor'] >= 0 else ''
        bloque_ia = f"""
━━━━━━━━━━━━━━━━━━━━━━━
🏆 *COMPARATIVA IA vs NO-IA (30d)*
┌ Con IA ({ia['total']} trades): WR `{ia['win_rate']}%` | PF `{ia['profit_factor']}`
└ Sin IA ({nia['total']} trades): WR `{nia['win_rate']}%` | PF `{nia['profit_factor']}`
📈 Ventaja: WR `{signo_wr}{cmp['ventaja_win_rate']}%` | PF `{signo_pf}{cmp['ventaja_profit_factor']}`"""
    elif ia['total'] > 0:
        bloque_ia = f"\n📌 Todos los trades ({ia['total']}) fueron validados por IA."
    else:
        bloque_ia = ""

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
💰 *PNL Total:* `${m['total_pnl']}`{bloque_approval}{bloque_ia}{bloque_alerta}

*Evaluación Mainnet:*
{viabilidad}"""
