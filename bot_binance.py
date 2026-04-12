"""
BOT BINANCE IA V7.0 — ESTABILIZADO
CORRECCIONES vs V6.7:
  FIX1: Apalancamiento 10x → 3x (evita liquidaciones)
  FIX2: Riesgo 5% × 10 pos → 1.5% × 5 pos (exposición controlada)
  FIX3: Señal triple confirmación EMA+MACD+RSI (menos falsas)
  FIX4: Gemini opcional, no bloquea arranque
  FIX5: ATR SL activado (SL dinámico adaptativo)
  FIX6: EV_MINIMO = 0.0 (solo trades con expectativa positiva)
  FIX7: Watchdog externo para 24/7
  FIX8: Variable de entorno unificada
"""

from binance.client import Client
from binance.enums import *
import time, os, http.server, socketserver, threading, requests, json, sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from persistence import (
    inicializar_db, registrar_trade_abierto, registrar_trade_cerrado,
    registrar_decision, registrar_balance_diario, calcular_metricas_riesgo,
    generar_resumen_metricas, contar_trades_semana_actual
)
from capital_manager import CapitalManager
from indicators import (
    calcular_rsi, calcular_ema, calcular_macd, calcular_bollinger,
    calcular_atr, calcular_volumen_relativo, detectar_soportes_resistencias,
    obtener_tendencia_ema, analizar_indicadores_completo
)

load_dotenv()
sys.stdout.reconfigure(line_buffering=True)

# ═══════════════════════════════════════════════
# CONFIGURACIÓN GLOBAL V7.0
# ═══════════════════════════════════════════════
USAR_TESTNET          = os.getenv("BINANCE_TESTNET", "True").lower() in ("true","1","yes")
BOT_VERSION           = "V7.0 Estabilizado"

# FIX1+FIX2: Riesgo conservador
APALANCAMIENTO        = 3        # era 10x
MAX_POSICIONES        = 5        # era 10
RIESGO_POR_TRADE_PCT  = 0.015   # era 0.05 (5%)
GUARDIAN_ACTIVO       = True

# FIX6: EV positivo obligatorio
EV_MINIMO             = 0.0     # era -10.0

# Señal
CONFIANZA_MINIMA      = 0.65    # era 0.45
TOP_ACTIVOS           = 30
VELAS_CANTIDAD        = 250
TIEMPO_POR_ACTIVO     = 3
TEMPORALIDADES        = ['15m']

# Trailing
TRAILING_SL_PERCENT   = 0.012
UMBRAL_BREAKEVEN      = 0.008
UMBRAL_TRAILING       = 0.015

# TP/SL — ratio mínimo 2:1
TP_SL_CONFIG = {
    "1h":  {"tp": 0.040, "sl": 0.018},
    "15m": {"tp": 0.025, "sl": 0.012},
    "5m":  {"tp": 0.015, "sl": 0.007},
}
TP_SL_RANGO_CONFIG = {
    "1h":  {"tp": 0.020, "sl": 0.009},
    "15m": {"tp": 0.012, "sl": 0.005},
    "5m":  {"tp": 0.008, "sl": 0.004},
}

# FIX5: ATR SL activado
ATR_SL_ACTIVO         = True    # era False
ATR_SL_MULTIPLICADOR  = 1.5
ATR_SL_MINIMO_PERCENT = 0.008

# Drawdown
DRAWDOWN_MAXIMO_DIARIO = 0.05
DRAWDOWN_ACTIVO        = True

# Funding
FUNDING_PROTECTION  = True
MAX_DIAS_POSICION   = 3
TP_DINAMICO_DIAS    = 1
TP_DINAMICO_PERCENT = 0.02

# Guardian
MAX_PERDIDA_PERMITIDA          = -0.06
CIERRE_POR_REVERSION_ACTIVO    = True
GANANCIA_MINIMA_PARA_PROTEGER  = 0.04
REVERSION_MAXIMA_PERMITIDA     = -0.05

# Escudo capital
ESCUDO_SEGURO  = 0.15   # 15% intocable, era 5%
ESCUDO_TRABAJO = 0.85
FACTOR_MONTO_RANGO = 0.8

# Scheduler
MONITOREO_INTERVALO          = 5
INTERVALO_GUARDIAN           = 10
INTERVALO_VERIFICAR_SL       = 15
INTERVALO_TRAILING           = 5
INTERVALO_TRADES_CERRADOS    = 15
INTERVALO_RESUMEN_POSICIONES = 60

# FIX4: Gemini opcional
USAR_IA    = False
IA_MAX_FALLOS = 3

# Fees
FEE_ROUNDTRIP_EST = 0.0012
SLIPPAGE_EST      = 0.0006
LOG_DETALLADO     = os.getenv("LOG_DETALLADO","true").lower() in ("true","1","yes")
BALANCE_INICIAL_PROYECTO = 1000.0

# Noticias
NOTICIAS_PROTECCION_ACTIVA      = True
CRYPTO_PANIC_URL                = "https://cryptopanic.com/api/v1/posts/"
CRYPTO_PANIC_KEY                = os.getenv("CRYPTOPANIC_API_KEY")
PAUSA_NOTICIAS_MINUTOS          = 60
NOTICIAS_CHECK_INTERVALO        = 300
NOTICIAS_KEYWORDS_ALTO_IMPACTO = (
    "sec","hack","exploit","ban","lawsuit","fed","fomc","cpi",
    "liquidation","bankruptcy","crash","etf denied","exchange halted",
    "outage","default","war","sanction"
)

# Horario
HORARIO_PROTEGIDO_ACTIVO = True
try:    TZ_MERCADO = ZoneInfo("America/New_York")
except: TZ_MERCADO = None
try:    TZ_LOCAL = ZoneInfo("America/Guatemala")
except: TZ_LOCAL = None

VENTANA_USA_INICIO_MIN = 8*60+30
VENTANA_USA_FIN_MIN    = 9*60+30
VENTANA_FED_DIA        = 2
VENTANA_FED_INICIO_MIN = 13*60+45
VENTANA_FED_FIN_MIN    = 14*60+30

# Estado global
stats_semanales = {"balance_inicio_semana":0,"ganados":0,"perdidos":0,
                   "monto_ganado":0,"monto_perdido":0,"cierres_guardian":0,"ultimo_resumen":None}
stats_diarias   = {"balance_inicio_dia":0,"trades_ganados":0,"trades_perdidos":0,
                   "monto_ganado":0,"monto_perdido":0,"drawdown_pausado":False,
                   "fecha_actual":None,"pnl_dia":0}
task_last_run        = {}
log_throttle         = {}
_positions_cache     = {"ts":0.0,"data":None}
_exchange_info_cache = {"ts":0.0,"data":None}
_sl_retry_cooldown_until = {}
_tp_dinamico_cooldown    = {}
SL_REINTENTO_COOLDOWN    = 300
TP_DINAMICO_COOLDOWN     = 3600
_ia_senales_total    = 0
_ia_senales_validadas= 0
_resumen_diario_enviado = False
_ultimo_resumen_diario  = {}
_ultimo_resumen_semanal = {}
_servidor_inicio     = time.time()
posiciones_tracking  = {}
posiciones_notificadas = set()
pausa_noticias_hasta = None
ultimo_check_noticias= 0.0
_sl_verificados      = {}
cm = None
client = None

# Expo push (opcional)
try:
    from expo_push import guardar_push_token, enviar_push_notification
    EXPO_DISPONIBLE = True
except Exception:
    EXPO_DISPONIBLE = False
    def guardar_push_token(t): pass
    def enviar_push_notification(t,b,d=None): pass


# ═══════════════════════════════════════════════
# UTILIDADES GENERALES
# ═══════════════════════════════════════════════
def hora_local():
    if TZ_LOCAL:
        return datetime.now(TZ_LOCAL)
    return datetime.now()

def log(msg):
    print(f"[BINANCE] {msg}", flush=True)

def should_run_task(name, interval):
    now = time.time()
    if now - task_last_run.get(name, 0.0) >= interval:
        task_last_run[name] = now
        return True
    return False

def log_throttled(key, msg, cooldown=180):
    now = time.time()
    if now - log_throttle.get(key, 0.0) >= cooldown:
        log_throttle[key] = now
        log(msg)

# ═══════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def enviar_telegram(msg):
    try:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════
# SERVIDOR HTTP (health check + API)
# ═══════════════════════════════════════════════
def servidor_salud():
    PORT = int(os.getenv("PORT", 8000))

    class Handler(http.server.SimpleHTTPRequestHandler):
        def _json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin","*")
            self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers","Content-Type, Accept")
            self.end_headers()

        def do_POST(self):
            if self.path == "/api/register-push-token":
                try:
                    length = int(self.headers.get("Content-Length",0))
                    body   = json.loads(self.rfile.read(length))
                    token  = body.get("token","")
                    if token:
                        guardar_push_token(token)
                        self._json({"ok": True})
                    else:
                        self._json({"ok": False}, 400)
                except Exception as e:
                    self._json({"ok": False, "message": str(e)}, 500)

            elif self.path == "/api/panic":
                try:
                    positions = obtener_posiciones(client)
                    cerradas  = 0
                    for pos in positions:
                        qty = float(pos.get("positionAmt", 0))
                        if qty != 0:
                            sym  = pos["symbol"]
                            side = "SELL" if qty > 0 else "BUY"
                            client.futures_cancel_all_open_orders(symbol=sym)
                            client.futures_create_order(symbol=sym, side=side,
                                type="MARKET", quantity=abs(qty), reduceOnly="true")
                            cerradas += 1
                    stats_diarias["drawdown_pausado"] = True
                    log(f"🚨 PÁNICO: {cerradas} posiciones cerradas.")
                    self._json({"ok": True, "cerradas": cerradas})
                except Exception as e:
                    self._json({"ok": False, "message": str(e)}, 500)
            else:
                self._json({"error": "not found"}, 404)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/status":
                try:
                    posiciones_activas = []
                    if client:
                        for p in obtener_posiciones(client):
                            if float(p.get("positionAmt",0)) != 0:
                                posiciones_activas.append({
                                    "symbol": p["symbol"],
                                    "side": "LONG" if float(p["positionAmt"]) > 0 else "SHORT",
                                    "pnl": round(float(p.get("unRealizedProfit",0)),2)
                                })
                    bal   = obtener_balance(client) if client else 0
                    puede = verificar_drawdown_diario(bal) if client else False
                    self._json({
                        "version": BOT_VERSION, "balance": round(bal,2),
                        "posiciones_abiertas": len(posiciones_activas),
                        "max_posiciones": MAX_POSICIONES,
                        "apalancamiento": APALANCAMIENTO,
                        "riesgo_trade_pct": RIESGO_POR_TRADE_PCT*100,
                        "puede_operar": puede,
                        "uptime_seconds": int(time.time()-_servidor_inicio),
                        "posiciones_detalle": posiciones_activas,
                        "timestamp": hora_local().isoformat()
                    })
                except Exception as e:
                    self._json({"error": str(e)}, 500)

            elif path == "/api/resumen-diario":
                self._json(_ultimo_resumen_diario or {"fecha": hora_local().strftime("%d/%m/%Y")})

            elif path == "/api/resumen-semanal":
                self._json(_ultimo_resumen_semanal or {})

            elif path == "/api/trades":
                try:
                    from persistence import _get_conn
                    conn = _get_conn()
                    c    = conn.cursor()
                    c.execute("""SELECT id,symbol,side,action,pnl,confidence,
                                        temporalidad,razon,closed_at
                                 FROM trades WHERE status='CLOSED' AND pnl!=0
                                 ORDER BY closed_at DESC LIMIT 20""")
                    rows = c.fetchall()
                    conn.close()
                    self._json([dict(r) for r in rows])
                except Exception as e:
                    self._json({"error": str(e)}, 500)

            elif path == "/api/metricas":
                try:
                    self._json(calcular_metricas_riesgo(dias=30))
                except Exception as e:
                    self._json({"error": str(e)}, 500)
            else:
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(f"BOT {BOT_VERSION} OK".encode())

        def log_message(self, *args):
            pass

    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            httpd.serve_forever()
    except Exception:
        pass

threading.Thread(target=servidor_salud, daemon=True).start()


# ═══════════════════════════════════════════════
# BINANCE — CACHÉ Y CONSULTAS
# ═══════════════════════════════════════════════
def obtener_posiciones(client, ttl=3, force=False):
    now = time.time()
    if not force and _positions_cache["data"] is not None and now - _positions_cache["ts"] < ttl:
        return _positions_cache["data"]
    data = client.futures_position_information()
    _positions_cache.update({"ts": now, "data": data})
    return data

def obtener_exchange_info(client, ttl=1800, force=False):
    now = time.time()
    if not force and _exchange_info_cache["data"] is not None and now - _exchange_info_cache["ts"] < ttl:
        return _exchange_info_cache["data"]
    data = client.futures_exchange_info()
    _exchange_info_cache.update({"ts": now, "data": data})
    return data

def obtener_balance(client):
    try:
        for b in client.futures_account_balance():
            if b["asset"] == "USDT":
                return float(b["balance"])
        return 0.0
    except Exception as e:
        log(f"⚠️ Error balance: {e}")
        return 0.0

def obtener_balance_disponible(client):
    try:
        return float(client.futures_account().get("availableBalance", 0))
    except Exception as e:
        log(f"⚠️ Error balance disponible: {e}")
        return 0.0

def obtener_balance_total(client):
    try:
        acc = client.futures_account()
        return float(acc.get("totalWalletBalance",0)) + float(acc.get("totalUnrealizedProfit",0))
    except Exception:
        return obtener_balance(client)

def obtener_velas(client, symbol, interval="15m", limit=250):
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        return [{"timestamp":k[0],"open":float(k[1]),"high":float(k[2]),
                 "low":float(k[3]),"close":float(k[4]),"volume":float(k[5])}
                for k in klines]
    except Exception as e:
        log(f"⚠️ Error velas {symbol}: {e}")
        return None

def obtener_simbolos_futuros(client):
    try:
        info     = obtener_exchange_info(client)
        simbolos = [s["symbol"] for s in info["symbols"]
                    if s["status"]=="TRADING" and s["quoteAsset"]=="USDT"
                    and not s["symbol"].endswith("_PERP")]
        tickers  = client.futures_ticker()
        vol_dict = {t["symbol"]: float(t["quoteVolume"]) for t in tickers}
        ordenados = sorted(simbolos, key=lambda x: vol_dict.get(x,0), reverse=True)
        log(f"📊 {len(ordenados)} pares disponibles → top {TOP_ACTIVOS}")
        return ordenados[:TOP_ACTIVOS]
    except Exception as e:
        log(f"⚠️ Error símbolos: {e}")
        return ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","SOLUSDT"]

def contar_posiciones_abiertas(client):
    try:
        return len([p for p in obtener_posiciones(client) if float(p.get("positionAmt",0)) != 0])
    except Exception:
        return 0

def obtener_simbolos_con_posicion(client):
    try:
        return [p["symbol"] for p in obtener_posiciones(client) if float(p.get("positionAmt",0)) != 0]
    except Exception:
        return []

def configurar_apalancamiento(client, symbol, leverage=3):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
    except Exception as e:
        if "No need to change leverage" not in str(e):
            log(f"⚠️ Leverage {symbol}: {e}")

def calcular_cantidad(client, symbol, monto_usdt, precio_actual):
    try:
        info = obtener_exchange_info(client)
        si   = next((s for s in info["symbols"] if s["symbol"]==symbol), None)
        if not si:
            return None
        qty_precision = int(si["quantityPrecision"])
        cantidad = round(monto_usdt / precio_actual, qty_precision)
        min_qty  = float(next((f["minQty"] for f in si["filters"] if f["filterType"]=="LOT_SIZE"), 0.001))
        return cantidad if cantidad >= min_qty else None
    except Exception as e:
        log(f"⚠️ Error cantidad {symbol}: {e}")
        return None

def inicializar_cache_trades(client):
    global posiciones_notificadas
    try:
        trades = client.futures_account_trades(limit=100)
        for t in trades:
            pnl = float(t.get("realizedPnl", 0))
            if pnl != 0:
                posiciones_notificadas.add(f"{t.get('orderId','')}_{t.get('symbol','')}_{pnl}")
        log(f"✅ Cache trades: {len(posiciones_notificadas)} entradas")
    except Exception as e:
        log(f"⚠️ Error cache trades: {e}")

# ═══════════════════════════════════════════════
# GESTIÓN DE RIESGO
# ═══════════════════════════════════════════════
def verificar_nuevo_dia(balance_actual):
    hoy = hora_local().strftime("%Y-%m-%d")
    if stats_diarias["fecha_actual"] != hoy:
        stats_diarias.update({
            "fecha_actual": hoy, "balance_inicio_dia": balance_actual,
            "trades_ganados": 0, "trades_perdidos": 0,
            "monto_ganado": 0, "monto_perdido": 0,
            "drawdown_pausado": False, "pnl_dia": 0
        })
        log(f"📅 Nuevo día {hoy}. Balance inicio: ${balance_actual:.2f}")
        return True
    return False

def verificar_drawdown_diario(balance_actual):
    if not DRAWDOWN_ACTIVO:
        return True
    if stats_diarias["drawdown_pausado"]:
        log_throttled("dd_msg","⏸️ Bot pausado por drawdown. Esperando nuevo día...",300)
        return False
    inicio = stats_diarias["balance_inicio_dia"]
    if inicio <= 0:
        return True
    dd = (balance_actual - inicio) / inicio
    stats_diarias["pnl_dia"] = balance_actual - inicio
    if dd < -DRAWDOWN_MAXIMO_DIARIO:
        stats_diarias["drawdown_pausado"] = True
        perdida = inicio - balance_actual
        log(f"🛑 DRAWDOWN MÁXIMO: ${perdida:.2f} ({dd*100:.2f}%) — Bot pausado hasta mañana")
        enviar_telegram(f"🛑 *Drawdown diario alcanzado*\nPérdida: ${perdida:.2f} ({dd*100:.2f}%)\nBot pausado hasta mañana.")
        return False
    return True

def calcular_monto(saldo):
    """V7.0: 1.5% del capital por trade (era 5%). Exposición máx = 7.5% con 5 posiciones."""
    capital = cm.get_capital_operativo() if cm is not None else saldo
    monto   = capital * RIESGO_POR_TRADE_PCT
    if LOG_DETALLADO:
        log(f"   💰 Riesgo {RIESGO_POR_TRADE_PCT*100:.1f}%: Base ${capital:.2f} → Monto ${monto:.2f}")
    return max(1.0, round(monto, 2))

def actualizar_stats_trade(pnl):
    if pnl >= 0:
        stats_diarias["trades_ganados"] += 1
        stats_diarias["monto_ganado"]   += pnl
    else:
        stats_diarias["trades_perdidos"] += 1
        stats_diarias["monto_perdido"]   += abs(pnl)

def calcular_ev_neto(confianza, tp_pct, sl_pct, modo="TREND"):
    p = max(0.40, min(0.90, confianza - (0.05 if modo=="RANGE" else 0)))
    return (p*tp_pct - (1-p)*sl_pct) - FEE_ROUNDTRIP_EST - SLIPPAGE_EST, p

def calcular_sl_atr(precio, atr, side):
    """V7.0: ATR activado — SL dinámico que se adapta a la volatilidad real."""
    if not ATR_SL_ACTIVO or atr <= 0:
        pct = ATR_SL_MINIMO_PERCENT
        return round(precio*(1-pct) if side=="BUY" else precio*(1+pct), 4)
    dist = max(atr * ATR_SL_MULTIPLICADOR, precio * ATR_SL_MINIMO_PERCENT)
    return round(precio - dist if side=="BUY" else precio + dist, 4)

# ═══════════════════════════════════════════════
# SEÑAL TÉCNICA V7.0 — TRIPLE CONFIRMACIÓN
# ═══════════════════════════════════════════════
def generar_senal_v7(ind, temp="15m"):
    """
    V7.0: FIX3 — Señal requiere EMA + MACD + RSI confluentes.
    Era: solo RSI >= 65 = SHORT (demasiado simplista → muchas falsas).
    Ahora: los 3 deben coincidir + filtro de volatilidad mínima.
    """
    if not ind:
        return None, 0.0, None, "Sin datos"

    rsi      = float(ind.get("rsi", 50))
    tendencia= (ind.get("tendencia_ema","") or "").upper()
    hist     = float((ind.get("macd") or {}).get("histograma", 0))
    atr_pct  = float(ind.get("atr_percent", 0))
    vol_rel  = float(ind.get("volumen_relativo", 1))

    # Filtro volatilidad mínima — no operar en mercados dormidos
    if atr_pct < 0.30:
        return None, 0.0, None, f"ATR insuficiente ({atr_pct:.2f}%)"

    # ── LONG ──────────────────────────────────────────
    if rsi < 40 and "ALCISTA" in tendencia and hist > 0:
        conf = 0.92 if rsi < 30 else 0.85
        return "LONG", conf, temp, f"Triple LONG: RSI={rsi:.0f} {tendencia} MACD↑"

    if rsi < 45 and "ALCISTA_FUERTE" in tendencia and hist > 0 and vol_rel > 1.2:
        return "LONG", 0.80, temp, f"LONG fuerte+vol: RSI={rsi:.0f} {tendencia}"

    # ── SHORT ──────────────────────────────────────────
    if rsi > 60 and "BAJISTA" in tendencia and hist < 0:
        conf = 0.92 if rsi > 70 else 0.85
        return "SHORT", conf, temp, f"Triple SHORT: RSI={rsi:.0f} {tendencia} MACD↓"

    if rsi > 55 and "BAJISTA_FUERTE" in tendencia and hist < 0 and vol_rel > 1.2:
        return "SHORT", 0.80, temp, f"SHORT fuerte+vol: RSI={rsi:.0f} {tendencia}"

    # ── Extremos RSI como respaldo ───────────────────
    if rsi <= 25 and hist > 0:
        return "LONG",  0.75, temp, f"Sobreventa extrema RSI={rsi:.0f}"
    if rsi >= 75 and hist < 0:
        return "SHORT", 0.75, temp, f"Sobrecompra extrema RSI={rsi:.0f}"

    return None, 0.0, None, "Sin confluencia triple"

# ═══════════════════════════════════════════════
# HORARIO Y NOTICIAS
# ═══════════════════════════════════════════════
def es_horario_protegido():
    if not HORARIO_PROTEGIDO_ACTIVO or not TZ_MERCADO:
        return False, ""
    try:
        et  = datetime.now(TZ_MERCADO)
        min = et.hour*60 + et.minute
        if VENTANA_USA_INICIO_MIN <= min <= VENTANA_USA_FIN_MIN:
            return True, "Apertura USA 08:30-09:30 ET"
        if et.weekday()==VENTANA_FED_DIA and VENTANA_FED_INICIO_MIN <= min <= VENTANA_FED_FIN_MIN:
            return True, "FOMC miércoles"
        return False, ""
    except Exception:
        return False, ""

def en_pausa_por_noticias():
    global pausa_noticias_hasta, ultimo_check_noticias
    if not NOTICIAS_PROTECCION_ACTIVA:
        return False, ""
    now = datetime.now()
    if pausa_noticias_hasta and now < pausa_noticias_hasta:
        mins = int((pausa_noticias_hasta - now).total_seconds()/60)
        return True, f"Pausa noticias ({mins} min)"
    if time.time() - ultimo_check_noticias < NOTICIAS_CHECK_INTERVALO:
        return False, ""
    ultimo_check_noticias = time.time()
    if not CRYPTO_PANIC_KEY:
        return False, ""
    try:
        r = requests.get(CRYPTO_PANIC_URL,
            params={"auth_token":CRYPTO_PANIC_KEY,"kind":"news","public":"true","currencies":"BTC,ETH,SOL,BNB,XRP"},
            timeout=10)
        for post in (r.json() if r.ok else {}).get("results",[])[:15]:
            titulo = (post.get("title") or "").lower()
            if any(kw in titulo for kw in NOTICIAS_KEYWORDS_ALTO_IMPACTO):
                pausa_noticias_hasta = now + timedelta(minutes=PAUSA_NOTICIAS_MINUTOS)
                log(f"📰 Noticia impacto detectada. Pausa {PAUSA_NOTICIAS_MINUTOS}min")
                return True, "Noticia de alto impacto"
    except Exception:
        pass
    return False, ""


# ═══════════════════════════════════════════════
# ÓRDENES SL/TP
# ═══════════════════════════════════════════════
def cancelar_ordenes_sl(client, symbol):
    try:
        for o in client.futures_get_open_orders(symbol=symbol):
            if o["type"] in ["STOP_MARKET","STOP","STOP_LOSS_MARKET"]:
                client.futures_cancel_order(symbol=symbol, orderId=o["orderId"])
    except Exception as e:
        if LOG_DETALLADO:
            log(f"⚠️ Cancelar SL {symbol}: {e}")

def existe_orden_sl_abierta(client, symbol):
    TIPOS = ("STOP","STOP_MARKET","STOP_LOSS","STOP_LOSS_MARKET","TAKE_PROFIT","TAKE_PROFIT_MARKET")
    try:
        for o in client.futures_get_open_orders(symbol=symbol):
            if any(t in (o.get("type","") or "").upper() for t in TIPOS):
                return True
    except Exception:
        pass
    return False

def crear_orden_sl(client, symbol, side, precio, cantidad):
    try:
        info = obtener_exchange_info(client)
        si   = next((s for s in info["symbols"] if s["symbol"]==symbol), None)
        if si:
            precio = round(precio, int(si["pricePrecision"]))
        client.futures_create_order(
            symbol=symbol, side=side, type="STOP_MARKET",
            stopPrice=str(precio), closePosition="true"
        )
        return True, False
    except Exception as e:
        err = str(e)
        if "-4045" in err or "-4130" in err:
            return False, True   # ya protegido
        log(f"   ⚠️ Error SL {symbol}: {e}")
        return False, False

def ejecutar_orden(client, symbol, side, cantidad, tp=None, sl=None):
    try:
        orden    = client.futures_create_order(symbol=symbol, side=side, type="MARKET", quantity=cantidad)
        order_id = orden["orderId"]
        log(f"   ✅ Orden ejecutada ID={order_id}")
        if tp and sl:
            info = obtener_exchange_info(client)
            si   = next((s for s in info["symbols"] if s["symbol"]==symbol), None)
            if si:
                pp = int(si["pricePrecision"])
                tp = round(tp, pp)
                sl = round(sl, pp)
            # Take Profit
            try:
                tp_side = "SELL" if side=="BUY" else "BUY"
                client.futures_create_order(
                    symbol=symbol, side=tp_side, type="TAKE_PROFIT_MARKET",
                    stopPrice=tp, closePosition=True
                )
                log(f"   📈 TP: ${tp}")
            except Exception as e:
                log(f"   ⚠️ TP error: {e}")
            # Stop Loss
            sl_side = "SELL" if side=="BUY" else "BUY"
            ok, _ = crear_orden_sl(client, symbol, sl_side, sl, cantidad)
            if ok:
                log(f"   📉 SL: ${sl}")
            else:
                log(f"   ⚠️ SL no creado — Guardian vigilará")
        return True, order_id
    except Exception as e:
        log(f"⚠️ Error ejecutar orden {symbol}: {e}")
        return False, None

# ═══════════════════════════════════════════════
# TRAILING STOP — V7.0
# ═══════════════════════════════════════════════
def actualizar_trailing_sl(client):
    try:
        for pos in obtener_posiciones(client):
            symbol   = pos["symbol"]
            cantidad = float(pos.get("positionAmt",0))
            if cantidad == 0:
                posiciones_tracking.pop(symbol, None)
                continue
            precio  = float(pos["markPrice"])
            entry   = float(pos["entryPrice"])
            side    = "LONG" if cantidad > 0 else "SHORT"
            if symbol not in posiciones_tracking:
                posiciones_tracking[symbol] = {"side":side,"best_price":precio,"entry":entry,"last_sl":None}
                log(f"📍 Nueva pos detectada: {symbol} {side}")
            t = posiciones_tracking[symbol]
            if side == "LONG":
                if precio > t["best_price"]:
                    t["best_price"] = precio
                g = (t["best_price"] - entry) / entry
                sl_nuevo = None
                if g >= UMBRAL_TRAILING:
                    sl_nuevo = t["best_price"] * (1 - TRAILING_SL_PERCENT)
                elif g >= UMBRAL_BREAKEVEN:
                    sl_nuevo = entry * 1.002
                if sl_nuevo and (t["last_sl"] is None or sl_nuevo > t["last_sl"]):
                    cancelar_ordenes_sl(client, symbol)
                    ok, _ = crear_orden_sl(client, symbol, "SELL", sl_nuevo, abs(cantidad))
                    if ok:
                        t["last_sl"] = sl_nuevo
                        tipo = "Trailing" if g >= UMBRAL_TRAILING else "Break-Even"
                        log(f"📈 {tipo} ({symbol}): ${sl_nuevo:.4f}")
            else:  # SHORT
                if precio < t["best_price"]:
                    t["best_price"] = precio
                g = (entry - t["best_price"]) / entry
                sl_nuevo = None
                if g >= UMBRAL_TRAILING:
                    sl_nuevo = t["best_price"] * (1 + TRAILING_SL_PERCENT)
                elif g >= UMBRAL_BREAKEVEN:
                    sl_nuevo = entry * 0.998
                if sl_nuevo and (t["last_sl"] is None or sl_nuevo < t["last_sl"]):
                    cancelar_ordenes_sl(client, symbol)
                    ok, _ = crear_orden_sl(client, symbol, "BUY", sl_nuevo, abs(cantidad))
                    if ok:
                        t["last_sl"] = sl_nuevo
                        tipo = "Trailing" if g >= UMBRAL_TRAILING else "Break-Even"
                        log(f"📉 {tipo} ({symbol}): ${sl_nuevo:.4f}")
    except Exception as e:
        log(f"⚠️ Error trailing: {e}")

# ═══════════════════════════════════════════════
# GUARDIAN DE POSICIONES
# ═══════════════════════════════════════════════
def guardian_posiciones(client):
    try:
        for pos in obtener_posiciones(client):
            symbol   = pos["symbol"]
            cantidad = float(pos.get("positionAmt",0))
            if cantidad == 0:
                continue
            try:
                entry  = float(pos["entryPrice"])
                mark   = float(pos["markPrice"])
                pnl    = float(pos.get("unRealizedProfit",0))
                side   = "LONG" if cantidad > 0 else "SHORT"
                if entry <= 0:
                    continue
                notional = entry * abs(cantidad)
                pnl_pct  = (pnl / notional) * 100 if notional > 0 else 0
                # Cierre de emergencia
                if pnl_pct / 100 < MAX_PERDIDA_PERMITIDA:
                    log(f"🚨 GUARDIAN: Cerrando {symbol} {side} PNL={pnl_pct:.2f}%")
                    close = "SELL" if cantidad > 0 else "BUY"
                    client.futures_cancel_all_open_orders(symbol=symbol)
                    client.futures_create_order(symbol=symbol, side=close,
                        type="MARKET", quantity=abs(cantidad), reduceOnly="true")
                    stats_semanales["cierres_guardian"] += 1
                    enviar_telegram(f"🚨 *Guardian cerró {symbol}*\nPNL: {pnl_pct:.2f}%")
            except Exception as e:
                log(f"⚠️ Guardian {symbol}: {e}")
    except Exception as e:
        log(f"⚠️ Error guardian: {e}")

def verificar_ordenes_sl_existen(client):
    try:
        for pos in obtener_posiciones(client):
            symbol   = pos["symbol"]
            cantidad = float(pos.get("positionAmt",0))
            if cantidad == 0:
                continue
            now = time.time()
            if now < _sl_retry_cooldown_until.get(symbol, 0):
                continue
            if now - _sl_verificados.get(symbol, 0) < 120:
                continue
            if not existe_orden_sl_abierta(client, symbol):
                entry = float(pos["entryPrice"])
                mark  = float(pos["markPrice"])
                side  = "LONG" if cantidad > 0 else "SHORT"
                PCT   = ATR_SL_MINIMO_PERCENT
                if side == "LONG":
                    sl_p  = min(entry*(1-PCT), mark*0.995)
                    sl_s  = "SELL"
                else:
                    sl_p  = max(entry*(1+PCT), mark*1.005)
                    sl_s  = "BUY"
                ok, already = crear_orden_sl(client, symbol, sl_s, sl_p, abs(cantidad))
                if ok:
                    log(f"⚠️ SL emergencia {symbol}: ${sl_p:.4f}")
                    _sl_verificados[symbol] = now
                elif already:
                    _sl_verificados[symbol] = now + 3600
                else:
                    _sl_retry_cooldown_until[symbol] = now + SL_REINTENTO_COOLDOWN
            else:
                _sl_verificados[symbol] = now
    except Exception as e:
        log(f"⚠️ Error verificar SL: {e}")

def verificar_posiciones_cerradas(client):
    global posiciones_notificadas
    try:
        for trade in client.futures_account_trades(limit=20):
            pnl = float(trade.get("realizedPnl",0))
            if pnl == 0:
                continue
            symbol = trade.get("symbol","")
            key    = f"{trade.get('orderId','')}_{symbol}_{pnl}"
            if key in posiciones_notificadas:
                continue
            posiciones_notificadas.add(key)
            if len(posiciones_notificadas) > 5000:
                posiciones_notificadas = set(list(posiciones_notificadas)[-2500:])
            if pnl > 0:
                stats_semanales["ganados"]      += 1
                stats_semanales["monto_ganado"] += pnl
                log(f"💰 Ganado ({symbol}): +${pnl:.2f}")
            else:
                stats_semanales["perdidos"]       += 1
                stats_semanales["monto_perdido"]  += abs(pnl)
                log(f"💸 Perdido ({symbol}): -${abs(pnl):.2f}")
            actualizar_stats_trade(pnl)
            try:
                registrar_trade_cerrado(symbol, pnl)
            except Exception:
                pass
            if cm is not None:
                try:
                    ev = cm.actualizar(pnl, calcular_metricas_riesgo(dias=30), log_fn=log)
                    if ev.get("reduccion"):
                        enviar_telegram(f"🔴 *Alerta Capital — Reducción*\n{cm.resumen_telegram()}")
                    elif ev.get("escalado"):
                        enviar_telegram(f"📈 *Capital Escalado*\n{cm.resumen_telegram()}")
                except Exception:
                    pass
    except Exception as e:
        if LOG_DETALLADO:
            log(f"⚠️ Error posiciones cerradas: {e}")

def verificar_tiempo_posiciones(client):
    try:
        for pos in obtener_posiciones(client):
            symbol   = pos["symbol"]
            cantidad = float(pos.get("positionAmt",0))
            if cantidad == 0:
                continue
            try:
                trades = client.futures_account_trades(symbol=symbol, limit=50)
                t0     = next((t for t in trades if float(t.get("realizedPnl",0))==0), None)
                if not t0:
                    continue
                dias = (datetime.now() - datetime.fromtimestamp(int(t0["time"])/1000)).days
                if dias >= MAX_DIAS_POSICION:
                    side = "SELL" if cantidad > 0 else "BUY"
                    pnl  = float(pos.get("unRealizedProfit",0))
                    client.futures_create_order(symbol=symbol, side=side, type="MARKET", quantity=abs(cantidad))
                    log(f"⏰ {symbol} cerrado por tiempo ({dias}d). PNL: ${pnl:.2f}")
            except Exception:
                pass
    except Exception as e:
        log(f"⚠️ Error tiempo posiciones: {e}")

def verificar_funding_vs_pnl(client):
    try:
        for pos in obtener_posiciones(client):
            symbol   = pos["symbol"]
            cantidad = float(pos.get("positionAmt",0))
            if cantidad == 0:
                continue
            upnl = float(pos.get("unRealizedProfit",0))
            try:
                start = int((time.time()-48*3600)*1000)
                income= client.futures_income_history(symbol=symbol,incomeType="FUNDING_FEE",startTime=start,limit=20)
                total_fee = sum(float(i.get("income",0)) for i in income)
                if upnl > 0 and abs(total_fee) > upnl:
                    side = "SELL" if cantidad > 0 else "BUY"
                    client.futures_create_order(symbol=symbol,side=side,type="MARKET",quantity=abs(cantidad))
                    log(f"💸 {symbol} cerrado: funding ${total_fee:.2f} > pnl ${upnl:.2f}")
            except Exception:
                pass
    except Exception as e:
        log(f"⚠️ Error funding: {e}")

def ajustar_tp_dinamico(client):
    try:
        for pos in obtener_posiciones(client):
            symbol   = pos["symbol"]
            cantidad = float(pos.get("positionAmt",0))
            if cantidad == 0:
                continue
            upnl  = float(pos.get("unRealizedProfit",0))
            entry = float(pos["entryPrice"])
            mark  = float(pos["markPrice"])
            if upnl <= 0:
                continue
            now = time.time()
            if now < _tp_dinamico_cooldown.get(symbol,0):
                continue
            try:
                trades = client.futures_account_trades(symbol=symbol,limit=50)
                t0     = next((t for t in trades if float(t.get("realizedPnl",0))==0),None)
                if not t0:
                    continue
                dias = (datetime.now()-datetime.fromtimestamp(int(t0["time"])/1000)).days
                if dias < TP_DINAMICO_DIAS:
                    continue
                side = "LONG" if cantidad > 0 else "SHORT"
                if side=="LONG":
                    nuevo_tp = max(entry*(1+TP_DINAMICO_PERCENT), mark*1.003)
                else:
                    nuevo_tp = min(entry*(1-TP_DINAMICO_PERCENT), mark*0.997)
                # Cancelar TPs existentes
                for o in [x for x in client.futures_get_open_orders(symbol=symbol) if x["type"]!="STOP_MARKET"]:
                    client.futures_cancel_order(symbol=symbol,orderId=o["orderId"])
                time.sleep(0.5)
                si = next((s for s in obtener_exchange_info(client)["symbols"] if s["symbol"]==symbol),None)
                if si:
                    nuevo_tp = round(nuevo_tp, int(si["pricePrecision"]))
                tp_side = "SELL" if cantidad > 0 else "BUY"
                client.futures_create_order(symbol=symbol,side=tp_side,type="TAKE_PROFIT_MARKET",
                    stopPrice=nuevo_tp,closePosition=True,timeInForce="GTE_GTC")
                log(f"📈 TP dinámico {symbol}: ${nuevo_tp:.4f}")
                _tp_dinamico_cooldown[symbol] = now + TP_DINAMICO_COOLDOWN
            except Exception as e:
                err = str(e)
                if "-4045" not in err and "-4130" not in err:
                    log(f"⚠️ TP dinámico {symbol}: {e}")
                _tp_dinamico_cooldown[symbol] = now + TP_DINAMICO_COOLDOWN
    except Exception as e:
        log(f"⚠️ Error ajustar TP: {e}")


# ═══════════════════════════════════════════════
# REPORTES
# ═══════════════════════════════════════════════
def es_viernes_18h():
    a = hora_local()
    return a.weekday()==4 and a.hour==18

def es_hora_resumen_diario():
    return hora_local().hour == 22

def enviar_resumen_diario(client):
    global _ultimo_resumen_diario
    try:
        fecha  = hora_local().strftime("%d/%m/%Y")
        bal    = obtener_balance(client)
        registrar_balance_diario(hora_local().strftime("%Y-%m-%d"), balance_fin=bal)
        met    = generar_resumen_metricas(_ia_senales_total, _ia_senales_validadas, None)
        pnl    = stats_diarias.get("pnl_dia", 0)
        emoji  = "📈" if pnl >= 0 else "📉"
        bloque = cm.resumen_telegram() if cm else ""
        msg = (f"📊 *RESUMEN DIARIO {BOT_VERSION}*\n📅 {fecha}\n\n"
               f"💵 *Balance:* `${bal:.2f}`\n{emoji} *PNL Hoy:* `${pnl:+.2f}`\n\n"
               f"{bloque}\n\n{met}\n\n🤖 {BOT_VERSION} Activo ✅")
        enviar_telegram(msg)
        _ultimo_resumen_diario = {"fecha":fecha,"balance":round(bal,2),"pnl_dia":round(pnl,2),"timestamp":hora_local().isoformat()}
        try:
            enviar_push_notification(f"📊 Resumen {fecha}",f"Balance: ${bal:.2f} | PNL: ${pnl:+.2f}",{"type":"resumen_diario"})
        except Exception:
            pass
    except Exception as e:
        log(f"⚠️ Error resumen diario: {e}")

def enviar_resumen_semanal(client):
    global stats_semanales, _ultimo_resumen_semanal
    try:
        bal_actual  = obtener_balance(client)
        met         = calcular_metricas_riesgo(dias=7)
        bal_inicio  = stats_semanales.get("balance_inicio_semana", BALANCE_INICIAL_PROYECTO) or bal_actual
        roi         = ((bal_actual - bal_inicio) / bal_inicio * 100) if bal_inicio > 0 else 0
        wr          = met.get("win_rate", 0.0)
        pf          = met.get("profit_factor", 0.0)
        total       = met.get("total_trades", 0)
        ganados     = int(round(total * wr / 100.0))
        roi_str     = f"+{roi:.2f}%" if roi >= 0 else f"{roi:.2f}%"
        msg = (f"📊 RESUMEN SEMANAL {BOT_VERSION}\n🗓️ {hora_local().strftime('%d/%m/%Y')}\n\n"
               f"💰 Balance inicio: ${bal_inicio:,.2f}\n💸 Balance actual: ${bal_actual:,.2f}\n"
               f"📈 ROI: {roi_str}\n\n✅ Ganados: {ganados}\n❌ Perdidos: {total-ganados}\n"
               f"🎯 WinRate: {wr:.1f}%\n⚖️ Profit Factor: {pf:.2f}\n\n🤖 Estado: ACTIVO")
        enviar_telegram(msg)
        _ultimo_resumen_semanal = {"balance_inicial":round(bal_inicio,2),"balance_actual":round(bal_actual,2),
            "roi_semanal":round(roi,2),"trades_ganados":ganados,"trades_perdidos":total-ganados,
            "win_rate":round(wr,1),"profit_factor":round(pf,2),"timestamp":hora_local().isoformat()}
        stats_semanales.update({"balance_inicio_semana":bal_actual,"ganados":0,"perdidos":0,
            "monto_ganado":0,"monto_perdido":0,"cierres_guardian":0,"ultimo_resumen":hora_local()})
        try:
            enviar_push_notification("📊 Resumen Semanal",f"ROI: {roi_str} | WR: {wr:.1f}%",{"type":"resumen_semanal"})
        except Exception:
            pass
    except Exception as e:
        log(f"⚠️ Error resumen semanal: {e}")

# ═══════════════════════════════════════════════
# CICLO DE TRADING — V7.0
# ═══════════════════════════════════════════════
def ejecutar_trading(client):
    global _ia_senales_total

    log("\n" + "="*60)
    log(f"🧠 {BOT_VERSION}: Iniciando ciclo de análisis...")
    log("="*60)

    try:
        saldo_total      = obtener_balance(client)
        saldo_disponible = obtener_balance_disponible(client)
        if saldo_total < 5:
            log("⚠️ Balance insuficiente")
            return
        log(f"💰 Total: ${saldo_total:.2f} | Libre: ${saldo_disponible:.2f}")

        # Cooldown Capital Manager
        if cm is not None and not cm.puede_operar():
            log_throttled("cm_cool","⏳ COOLDOWN capital — trading bloqueado",300)
            return

        # Escudo de capital (15% intocable)
        reserva = saldo_total * ESCUDO_SEGURO
        if saldo_disponible <= reserva:
            log(f"🛡️ Reserva activa: ${saldo_disponible:.2f} ≤ ${reserva:.2f}")
            return

        pos_abiertas = contar_posiciones_abiertas(client)
        espacios     = MAX_POSICIONES - pos_abiertas
        log(f"📊 Posiciones: {pos_abiertas}/{MAX_POSICIONES} | Espacios: {espacios}")
        if espacios <= 0:
            log("📊 Posiciones llenas. Monitoreando...")
            return

        simbolos_pos = obtener_simbolos_con_posicion(client)
        simbolos     = obtener_simbolos_futuros(client)
        log(f"🔍 Analizando {len(simbolos)} pares...")

        oportunidades = []

        for symbol in simbolos:
            if symbol in simbolos_pos:
                continue
            try:
                # Marco 1H para filtro macro
                velas_1h = obtener_velas(client, symbol, "1h", 250)
                if not velas_1h or len(velas_1h) < 200:
                    continue
                klines_1h = [[v["timestamp"],v["open"],v["high"],v["low"],v["close"],v["volume"]] for v in velas_1h[:-1]]
                ind_1h    = analizar_indicadores_completo(klines_1h)
                if not ind_1h or not ind_1h.get("ema200"):
                    continue
                ema200_1h = float(ind_1h["ema200"])
                precio_1h = float(ind_1h["precio_actual"])

                # Timeframe operativo 15m
                velas_15m = obtener_velas(client, symbol, "15m", VELAS_CANTIDAD)
                if not velas_15m or len(velas_15m) < 200:
                    continue
                klines_15m = [[v["timestamp"],v["open"],v["high"],v["low"],v["close"],v["volume"]] for v in velas_15m[:-1]]
                ind        = analizar_indicadores_completo(klines_15m)
                if not ind:
                    continue

                precio = ind["precio_actual"]
                rv     = float(ind.get("volumen_relativo",1))
                tend   = (ind.get("tendencia_ema","") or "").upper()
                rsi    = float(ind.get("rsi",50))

                # ── Pre-filtros ──────────────────────────────────
                if rv < 0.50:   # Sin liquidez
                    continue
                if "LATERAL" in tend and 47 <= rsi <= 53:   # Mercado plano
                    continue

                # ── Señal V7.0 triple confirmación ───────────────
                accion, conf, temp, razon = generar_senal_v7(ind, "15m")
                if not accion:
                    if LOG_DETALLADO:
                        log(f"   ⏭️ {symbol}: {razon}")
                    continue

                # ── Filtro macro 1H (EMA200) ─────────────────────
                if accion=="LONG" and precio_1h < ema200_1h:
                    if LOG_DETALLADO:
                        log(f"   🚫 {symbol}: LONG bajo EMA200-1H ${ema200_1h:.4f}")
                    continue
                if accion=="SHORT" and precio_1h > ema200_1h:
                    if LOG_DETALLADO:
                        log(f"   🚫 {symbol}: SHORT sobre EMA200-1H ${ema200_1h:.4f}")
                    continue

                if conf < CONFIANZA_MINIMA:
                    continue

                _ia_senales_total += 1

                # Modo mercado
                atr_pct   = ind.get("atr_percent",0)
                boll_ancho= (ind.get("bollinger") or {}).get("ancho",0)
                modo      = "RANGE" if ("LATERAL" in tend and atr_pct<1.2 and boll_ancho<8) else "TREND"

                log(f"   📊 {symbol} | {accion} | Conf={int(conf*100)}% | {razon[:55]}")
                oportunidades.append({
                    "symbol":symbol,"accion":accion,"confianza":conf,
                    "temporalidad":temp or "15m","modo_mercado":modo,
                    "razon":razon,"precio_actual":precio,"indicadores":ind
                })
                try:
                    registrar_decision(symbol,accion,conf,temp or "15m",razon[:200],50,True)
                except Exception:
                    pass

            except Exception as e:
                log(f"   ⚠️ Error {symbol}: {e}")
            time.sleep(TIEMPO_POR_ACTIVO)

        oportunidades.sort(key=lambda x: x["confianza"], reverse=True)
        log(f"\n🎯 Oportunidades: {len(oportunidades)}")

        ejecutadas = 0
        for op in oportunidades:
            if ejecutadas >= espacios:
                break

            # Verificar drawdown antes de cada orden
            if not verificar_drawdown_diario(obtener_balance_total(client)):
                log("🛑 Drawdown detectado. Deteniendo ejecución.")
                break

            symbol  = op["symbol"]
            accion  = op["accion"]
            conf    = op["confianza"]
            temp    = op["temporalidad"]
            precio  = op["precio_actual"]
            modo    = op["modo_mercado"]
            razon   = op["razon"]
            ind     = op["indicadores"]

            monto = calcular_monto(saldo_total)
            if modo == "RANGE":
                monto *= FACTOR_MONTO_RANGO

            # TP/SL
            cfg_src = TP_SL_RANGO_CONFIG if modo=="RANGE" else TP_SL_CONFIG
            cfg     = cfg_src.get(temp, cfg_src.get("15m", {"tp":0.025,"sl":0.012}))
            atr_val = ind.get("atr",0) if ind else 0

            if accion == "LONG":
                sl = calcular_sl_atr(precio, atr_val, "BUY")
                tp = precio * (1 + cfg["tp"])
            else:
                sl = calcular_sl_atr(precio, atr_val, "SELL")
                tp = precio * (1 - cfg["tp"])

            # Verificar ratio R:R mínimo 2:1
            tp_dist = abs(tp - precio)
            sl_dist = abs(sl - precio)
            rr      = tp_dist / sl_dist if sl_dist > 0 else 0
            if rr < 1.8:
                log(f"   ⏭️ {symbol}: R:R={rr:.1f} insuficiente")
                continue

            # Verificar EV positivo
            ev, p_win = calcular_ev_neto(conf, tp_dist/precio, sl_dist/precio, modo)
            if ev < EV_MINIMO:
                log(f"   ⏭️ {symbol}: EV={ev*100:+.3f}% negativo")
                continue

            configurar_apalancamiento(client, symbol, APALANCAMIENTO)
            cantidad = calcular_cantidad(client, symbol, monto * APALANCAMIENTO, precio)

            if not cantidad:
                log(f"   ⚠️ Cantidad mínima no alcanzada: {symbol}")
                continue

            side = "BUY" if accion=="LONG" else "SELL"
            log(f"\n🚀 ORDEN #{ejecutadas+1}: {symbol} {accion}")
            log(f"   💰 ${monto:.2f} × {APALANCAMIENTO}x | Qty={cantidad}")
            log(f"   📈 TP=${tp:.4f} | 📉 SL=${sl:.4f} | R:R={rr:.1f}:1 | EV={ev*100:+.2f}%")

            ok, order_id = ejecutar_orden(client, symbol, side, cantidad, tp, sl)
            if ok:
                ejecutadas += 1
                enviar_telegram(
                    f"🚀 *Nueva operación {BOT_VERSION}*\n"
                    f"📍 {symbol} *{accion}*\n"
                    f"💰 Entrada: `${precio:.4f}`\n"
                    f"📈 TP: `${tp:.4f}` | 📉 SL: `${sl:.4f}`\n"
                    f"⚖️ R:R = {rr:.1f}:1 | EV = {ev*100:+.2f}%\n"
                    f"💡 _{razon[:80]}_"
                )
                try:
                    registrar_trade_abierto(
                        symbol=symbol, side=side, action=accion,
                        entry_price=precio, quantity=cantidad,
                        confidence=conf, temporalidad=temp,
                        razon=razon[:200], ia_validado=False
                    )
                except Exception:
                    pass

        log(f"\n✅ Ciclo completado. {ejecutadas} órdenes ejecutadas.")

    except Exception as e:
        log(f"⚠️ Error en ejecutar_trading: {e}")


# ═══════════════════════════════════════════════
# ARRANQUE PRINCIPAL — V7.0
# ═══════════════════════════════════════════════
log(f"🚀 Iniciando {BOT_VERSION}...")
log(f"   Leverage={APALANCAMIENTO}x | Riesgo={RIESGO_POR_TRADE_PCT*100:.1f}%/trade | MaxPos={MAX_POSICIONES}")
log(f"   ATR SL={'ON' if ATR_SL_ACTIVO else 'OFF'} | EV_MIN={EV_MINIMO} | Conf={CONFIANZA_MINIMA*100:.0f}%")

try:
    api_key    = os.getenv("BINANCE_API_KEY")
    # FIX8: soporta tanto BINANCE_SECRET como BINANCE_API_SECRET
    api_secret = os.getenv("BINANCE_SECRET") or os.getenv("BINANCE_API_SECRET")
    if USAR_TESTNET:
        client = Client(api_key, api_secret, testnet=True)
        log("📡 Conectado a Binance TESTNET")
    else:
        client = Client(api_key, api_secret)
        log("📡 Conectado a Binance PRODUCCIÓN")
    saldo = obtener_balance(client)
    log(f"✅ Balance: ${saldo:.2f} USDT")
except Exception as e:
    log(f"❌ ERROR FATAL Binance: {e}")
    sys.exit(1)

# Capital Manager
try:
    cm = CapitalManager(capital_inicial=saldo)
    cm.inicializar_tabla()
    if cm.cargar_estado():
        cm.sincronizar_con_exchange(saldo, log)
        log(f"💼 Capital restaurado: {cm.resumen_estado()}")
    else:
        cm.guardar_estado()
        log(f"💼 Primera sesión. Capital: ${saldo:.2f}")
except Exception as e:
    log(f"⚠️ Error CapitalManager: {e} — continuando sin él")
    cm = None

# FIX4: Gemini OPCIONAL — no bloquea el bot si falla
gemini_client = None
try:
    gkey = os.getenv("API_KEY_GEMINI","")
    if gkey:
        from google import genai as _genai
        gemini_client = _genai.Client(api_key=gkey)
        log("🧠 Gemini IA conectado ✅")
    else:
        log("🧠 Gemini no configurado — modo técnico puro ✅")
except Exception as e:
    log(f"🧠 Gemini no disponible ({e}) — modo técnico puro ✅")

# Inicialización
stats_semanales["balance_inicio_semana"] = saldo
stats_semanales["ultimo_resumen"]        = None
inicializar_cache_trades(client)
inicializar_db()
log("📦 Base de datos SQLite inicializada")
registrar_balance_diario(hora_local().strftime("%Y-%m-%d"), balance_inicio=saldo)

pos_iniciales = contar_posiciones_abiertas(client)
if pos_iniciales > 0:
    log(f"🛡️ {pos_iniciales} posiciones existentes. Activando Guardian + Trailing...")
    guardian_posiciones(client)
    verificar_ordenes_sl_existen(client)
    actualizar_trailing_sl(client)
else:
    log("✅ Sin posiciones abiertas. Listo para operar.")

enviar_telegram(
    f"🤖 *{BOT_VERSION} ONLINE*\n"
    f"💵 Balance: `${saldo:.2f}`\n"
    f"⚙️ Leverage: `{APALANCAMIENTO}x` | Riesgo: `{RIESGO_POR_TRADE_PCT*100:.1f}%/trade`\n"
    f"📊 Max posiciones: `{MAX_POSICIONES}` | EV mín: `{EV_MINIMO}`\n"
    f"🔄 Modo: `{'TESTNET' if USAR_TESTNET else 'PRODUCCIÓN'}`\n"
    f"✅ _Watchdog 24/7 activo_"
)
log(f"✅ {BOT_VERSION} en marcha. Guardian + Trailing + 24/7 activos...")

# ═══════════════════════════════════════════════
# BUCLE PRINCIPAL 24/7
# ═══════════════════════════════════════════════
ciclo             = 0
CICLOS_ANALISIS   = 6      # 6 × 5s = 30s entre ciclos de trading
resumen_hora      = False
_resumen_diario_enviado = False

while True:
    try:
        ciclo += 1

        bal_actual = obtener_balance(client)
        if cm:
            cm.sincronizar_con_exchange(bal_actual, log)
        bal_equity = obtener_balance_total(client)

        verificar_nuevo_dia(bal_equity)
        puede = verificar_drawdown_diario(bal_equity)

        # ── Scheduler de tareas ──────────────────────────────────
        if GUARDIAN_ACTIVO and should_run_task("guardian", INTERVALO_GUARDIAN):
            guardian_posiciones(client)

        if GUARDIAN_ACTIVO and should_run_task("verif_sl", INTERVALO_VERIFICAR_SL):
            verificar_ordenes_sl_existen(client)

        if should_run_task("trailing", INTERVALO_TRAILING):
            actualizar_trailing_sl(client)

        if should_run_task("trades_cerrados", INTERVALO_TRADES_CERRADOS):
            verificar_posiciones_cerradas(client)

        # ── Resúmenes ────────────────────────────────────────────
        if es_viernes_18h():
            if not resumen_hora:
                enviar_resumen_semanal(client)
                resumen_hora = True
        else:
            resumen_hora = False

        if es_hora_resumen_diario():
            if not _resumen_diario_enviado:
                enviar_resumen_diario(client)
                _resumen_diario_enviado = True
        else:
            _resumen_diario_enviado = False

        # ── Protección funding + TP dinámico ────────────────────
        if FUNDING_PROTECTION and ciclo >= CICLOS_ANALISIS:
            verificar_tiempo_posiciones(client)
            verificar_funding_vs_pnl(client)
            ajustar_tp_dinamico(client)

        # ── Análisis de mercado ──────────────────────────────────
        if ciclo >= CICLOS_ANALISIS:
            if puede:
                en_h, mot_h = es_horario_protegido()
                en_n, mot_n = en_pausa_por_noticias()
                if en_h:
                    log(f"⏸️ Horario protegido: {mot_h}")
                elif en_n:
                    log(f"⏸️ Pausa noticias: {mot_n}")
                else:
                    pos = contar_posiciones_abiertas(client)
                    if pos < MAX_POSICIONES:
                        ejecutar_trading(client)
                    else:
                        log(f"📊 {pos}/{MAX_POSICIONES} posiciones. Monitoreando...")
            else:
                log("⏸️ Trading pausado por drawdown diario")
            ciclo = 0
        else:
            if should_run_task("log_estado", INTERVALO_RESUMEN_POSICIONES):
                pos = contar_posiciones_abiertas(client)
                log(f"💓 {BOT_VERSION} | Pos={pos}/{MAX_POSICIONES} | ${bal_actual:.2f}")

        time.sleep(MONITOREO_INTERVALO)

    except Exception as e:
        log(f"⚠️ Error bucle principal: {e}")
        time.sleep(30)

