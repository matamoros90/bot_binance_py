"""
V6.2: Módulo de Gestión Dinámica de Capital.

Implementa tres fases de control de capital:
  Fase 1 - Validación:  ≥30 trades + Profit Factor ≥ 1.5 antes de escalar.
  Fase 2/3 - Escalado:  +20% de capital si el sistema está validado (1×/día máx).
  Regla de Oro:         −30% de capital si el drawdown supera el 20%.

Diseñado para integrarse SIN modificar la lógica de señales ni de IA.
Solo afecta el tamaño del capital base que usa calcular_monto().

Uso típico en bot_binance.py:
    from capital_manager import CapitalManager
    cm = CapitalManager(capital_inicial=saldo)
    cm.cargar_estado()        # Restaura desde DB si existe
    ...
    monto = cm.get_capital_operativo() * RIESGO_POR_TRADE
    ...
    # Después de cada trade cerrado:
    cm.actualizar(pnl, metricas)
"""

import sqlite3
import os
import logging
from datetime import datetime, timedelta, date
from typing import Optional

# ─── Directorio de BD (compatible con DATA_DIR de persistence.py) ────────────
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(DATA_DIR, "trades.db")


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES CONFIGURABLES
# ═══════════════════════════════════════════════════════════════════════════════

RIESGO_POR_TRADE    = 0.02   # 2% por operación (consistente con calcular_monto)
MAX_DRAWDOWN        = 0.20   # 20% → activa reducción de capital
UMBRAL_MIN_TRADES   = 30     # Mínimo de trades para validar el sistema
UMBRAL_PROFIT_FACTOR = 1.5   # PF mínimo para autorizar escalado
ESCALADO_INCREMENTO = 0.20   # +20% del capital al escalar
REDUCCION_DRAWDOWN  = 0.30   # −30% del capital al activar regla de oro

# Cuántos días entre dos escalados consecutivos (evita escalado compuesto descontrolado)
DIAS_ENTRE_ESCALADOS = 1


# ═══════════════════════════════════════════════════════════════════════════════
# CLASE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

class CapitalManager:
    """Gestor dinámico de capital para el bot de Binance Futures.

    Estado interno:
        capital_actual          Capital disponible para trading en este momento.
        capital_maximo_historico Máximo alcanzado — referencia para calcular drawdown.
        capital_inicial         Balance al arrancar el bot (referencia fija).
        _ultimo_escalado        Fecha del último escalado (control de frecuencia).
        trading_pausado         True cuando el drawdown dispara una pausa opcional.
    """

    def __init__(self, capital_inicial: float):
        self.capital_inicial           = round(capital_inicial, 2)
        self.capital_actual            = round(capital_inicial, 2)
        self.capital_maximo_historico  = round(capital_inicial, 2)
        self._ultimo_escalado: Optional[datetime] = None
        self.trading_pausado           = False
        self._timestamp_reduccion: Optional[datetime] = None

    # ─── Propiedades calculadas ───────────────────────────────────────────────

    @property
    def drawdown(self) -> float:
        """Drawdown actual como fracción (0.0–1.0)."""
        if self.capital_maximo_historico <= 0:
            return 0.0
        return (self.capital_maximo_historico - self.capital_actual) / self.capital_maximo_historico

    @property
    def drawdown_pct(self) -> float:
        """Drawdown actual como porcentaje (0.0–100.0)."""
        return round(self.drawdown * 100, 2)

    def get_capital_operativo(self) -> float:
        """Capital efectivo disponible para sizing de posiciones."""
        return self.capital_actual

    def puede_operar(self) -> bool:
        """Determina si el bot puede abrir nuevas operaciones (Cooldown)."""
        if self._timestamp_reduccion is None:
            return True
        # Cooldown de 8 horas después de una reducción drástica
        if datetime.now() < self._timestamp_reduccion + timedelta(hours=8):
            return False
        return True

    def sincronizar_con_exchange(self, balance_real: float, log_fn=None):
        """
        Asegura sincronización estricta: capital_actual nunca debe superar el balance real.
        Si es mayor, se ajusta automáticamente (min(capital_db, balance_real)).
        """
        _log = log_fn if log_fn else print
        if self.capital_actual > balance_real:
            capital_antes = self.capital_actual
            self.capital_actual = round(balance_real, 2)
            _log(f"[CAPITAL] Ajuste por sincronización con balance real aplicado (${capital_antes:.2f} → ${self.capital_actual:.2f})")
            
            # Guardamos el estado silenciosamente tras el ajuste
            try:
                self.guardar_estado()
            except Exception:
                pass

    # ─── Actualización después de cada trade ─────────────────────────────────

    def actualizar(self, pnl: float, metricas: dict, log_fn=None) -> dict:
        """Procesa el PnL de un trade cerrado y evalúa escalado/protección.

        Parámetros:
            pnl:      PnL realizado del trade (positivo = ganancia).
            metricas: Dict con 'total_trades' y 'profit_factor' de calcular_metricas_riesgo().
            log_fn:   Función de log del bot (opcional). Si no se pasa, usa print.

        Retorna dict con eventos ocurridos:
            { 'escalado': bool, 'reduccion': bool, 'alerta_log': str|None,
              'estado': str }
        """
        _log = log_fn if log_fn else print
        eventos = {"escalado": False, "reduccion": False, "alerta_log": None, "estado": ""}

        # 1. Actualizar capital con el PnL
        self.capital_actual = round(self.capital_actual + pnl, 2)

        # 2. Actualizar máximo histórico
        if self.capital_actual > self.capital_maximo_historico:
            self.capital_maximo_historico = self.capital_actual

        # 3. Regla de oro — protección por drawdown (tiene prioridad sobre escalado)
        if self.drawdown >= MAX_DRAWDOWN:
            eventos["reduccion"] = True
            capital_antes = self.capital_actual
            self.capital_actual = round(self.capital_actual * (1 - REDUCCION_DRAWDOWN), 2)
            self.trading_pausado = True
            self._timestamp_reduccion = datetime.now()

            msg = (
                f"🔴 [CAPITAL] REGLA DE ORO — REDUCCIÓN DE CAPITAL\n"
                f"   📉 Drawdown: {self.drawdown_pct:.1f}% ≥ umbral {int(MAX_DRAWDOWN*100)}%\n"
                f"   💸 Capital: ${capital_antes:.2f} → ${self.capital_actual:.2f} "
                f"(−{int(REDUCCION_DRAWDOWN*100)}%)\n"
                f"   ⚠️ Trading pausado (Cooldown de 8 horas activo)"
            )
            _log(msg)
            eventos["alerta_log"] = msg

        # 4. Escalado progresivo (solo si no hay reducción activa)
        elif self._puede_escalar(metricas):
            eventos["escalado"] = True
            self.trading_pausado = False
            capital_antes = self.capital_actual
            self.capital_actual = round(self.capital_actual * (1 + ESCALADO_INCREMENTO), 2)
            # Actualizar máximo histórico si el escalado lo supera
            if self.capital_actual > self.capital_maximo_historico:
                self.capital_maximo_historico = self.capital_actual
            self._ultimo_escalado = datetime.now()

            msg = (
                f"📈 [CAPITAL] ESCALADO DE CAPITAL ACTIVADO\n"
                f"   ✅ Trades: {metricas.get('total_trades',0)} | "
                f"PF: {metricas.get('profit_factor',0)}\n"
                f"   💰 Capital: ${capital_antes:.2f} → ${self.capital_actual:.2f} "
                f"(+{int(ESCALADO_INCREMENTO*100)}%)"
            )
            _log(msg)
            eventos["alerta_log"] = msg

        else:
            # Operación sin cambio de fase
            if self.trading_pausado and self.drawdown < MAX_DRAWDOWN * 0.5:
                # Reactivar si el drawdown se redujo a menos del 50% del umbral
                self.trading_pausado = False
                _log("🟢 [CAPITAL] Trading reactivado — drawdown recuperado")

        # 5. Guardar estado en BD
        try:
            self.guardar_estado()
        except Exception:
            pass  # No bloquear el bot por fallo de BD

        eventos["estado"] = self.resumen_estado()
        return eventos

    # ─── Evaluación de fases ──────────────────────────────────────────────────

    def evaluar_validacion(self, metricas: dict) -> bool:
        """Fase 1: ¿El sistema está validado para escalar?

        Condiciones:
            - total_trades ≥ UMBRAL_MIN_TRADES
            - profit_factor ≥ UMBRAL_PROFIT_FACTOR
            - profit_factor_10 ≥ 1.2 (ventana corto plazo)
            - win_rate_10 ≥ 50% (ventana corto plazo)
        """
        total = metricas.get("total_trades", 0)
        pf    = metricas.get("profit_factor", 0.0)
        pf_10 = metricas.get("profit_factor_10", 0.0)
        wr_10 = metricas.get("win_rate_10", 0.0)
        
        hist_ok = (total >= UMBRAL_MIN_TRADES and pf >= UMBRAL_PROFIT_FACTOR)
        rec_ok = (pf_10 >= 1.2 and wr_10 >= 50.0)
        return hist_ok and rec_ok

    def _puede_escalar(self, metricas: dict) -> bool:
        """Verifica validación + rate-limit de 24 horas."""
        if not self.evaluar_validacion(metricas):
            return False
        if self._ultimo_escalado is None:
            return True
        # Solo permitir escalado si han pasado al menos 24 horas
        return datetime.now() >= self._ultimo_escalado + timedelta(hours=24)

    # ─── Estado y logging ─────────────────────────────────────────────────────

    def resumen_estado(self) -> str:
        """Texto compacto del estado actual para logs."""
        return (
            f"💰 Capital: ${self.capital_actual:.2f} | "
            f"📈 Máx histórico: ${self.capital_maximo_historico:.2f} | "
            f"📉 Drawdown: {self.drawdown_pct:.1f}%"
        )

    def resumen_telegram(self) -> str:
        """Bloque formateado para incluir en resúmenes de Telegram."""
        estado = "🟢 Activo" if not self.trading_pausado else "🔴 Pausado"
        validado = "✅ Validado" if self.capital_actual > self.capital_inicial * 1.05 else "⏳ En validación"

        dd_emoji = "📉" if self.drawdown_pct > 10 else "✅"
        return (
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💼 *GESTIÓN DE CAPITAL (V6.2)*\n"
            f"💵 *Capital operativo:* `${self.capital_actual:.2f}`\n"
            f"📈 *Máx histórico:* `${self.capital_maximo_historico:.2f}`\n"
            f"{dd_emoji} *Drawdown:* `{self.drawdown_pct:.1f}%` "
            f"(umbral: `{int(MAX_DRAWDOWN*100)}%`)\n"
            f"🔄 *Estado:* {estado} | {validado}"
        )

    # ─── Persistencia en BD ───────────────────────────────────────────────────

    def _get_conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def inicializar_tabla(self):
        """Crea la tabla capital_estado si no existe y asegura nuevas columnas."""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS capital_estado (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp               DATETIME DEFAULT CURRENT_TIMESTAMP,
                capital_inicial         REAL NOT NULL,
                capital_actual          REAL NOT NULL,
                capital_maximo_historico REAL NOT NULL,
                drawdown_pct            REAL NOT NULL DEFAULT 0.0,
                ultimo_escalado         TEXT,
                trading_pausado         INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Migración automática segura para columna timestamp_reduccion
        try:
            c.execute("ALTER TABLE capital_estado ADD COLUMN timestamp_reduccion TEXT")
        except sqlite3.OperationalError:
            pass # Columna ya existe
        conn.commit()
        conn.close()

    def guardar_estado(self):
        """Persiste el estado actual en BD."""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO capital_estado
                (capital_inicial, capital_actual, capital_maximo_historico,
                 drawdown_pct, ultimo_escalado, trading_pausado, timestamp_reduccion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            self.capital_inicial,
            self.capital_actual,
            self.capital_maximo_historico,
            self.drawdown_pct,
            self._ultimo_escalado.isoformat() if self._ultimo_escalado else None,
            1 if self.trading_pausado else 0,
            self._timestamp_reduccion.isoformat() if self._timestamp_reduccion else None
        ))
        conn.commit()
        conn.close()

    def cargar_estado(self) -> bool:
        """Restaura el último estado guardado en BD."""
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("""
                SELECT * FROM capital_estado
                ORDER BY id DESC LIMIT 1
            """)
            row = c.fetchone()
            conn.close()

            if not row:
                return False

            self.capital_actual           = float(row["capital_actual"])
            self.capital_maximo_historico = float(row["capital_maximo_historico"])
            self.trading_pausado          = bool(row["trading_pausado"])
            ult = row["ultimo_escalado"]
            self._ultimo_escalado = datetime.fromisoformat(ult) if ult else None
            # Soporte de retrocompatibilidad
            if "timestamp_reduccion" in row.keys() and row["timestamp_reduccion"]:
                self._timestamp_reduccion = datetime.fromisoformat(row["timestamp_reduccion"])
                
            return True

        except Exception:
            return False
