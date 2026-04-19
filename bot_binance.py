"""
BOT BINANCE V9.1 — SEÑAL CON CONTEXTO
=======================================
MEJORAS V9.1:
  1. Filtro macro BTC 1H — no LONG en mercado bajista, no SHORT en alcista
  2. Confirmación de volumen — solo operar con volumen > media (VR ≥ 1.0)
  3. Confirmación de reversión RSI — RSI debe estar rebotando del extremo
     (no entrar en caída libre, esperar el giro real)

REGLAS BASE V9.0:
  1. Solo 8 pares con liquidez real
  2. Señal: RSI extremo + dirección EMA
  3. SL dinámico ATR, TP = 2x SL siempre
  4. Máximo 3 posiciones, 2% capital por trade
  5. Guardian cierra si pierde más de 5%
"""

from binance.client import Client
from binance.enums import *
import time, os, sys, json, threading
import http.server, socketserver, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from persistence import (
    inicializar_db, registrar_trade_abierto, registrar_trade_cerrado,
    registrar_decision, registrar_balance_diario, calcular_metricas_riesgo,
    generar_resumen_metricas, contar_trades_semana_actual
)
from capital_manager import CapitalManager
from indicators import analizar_indicadores_completo, calcular_rsi

load_dotenv()
sys.stdout.reconfigure(line_buffering=True)

# ══════════════════════════════════════════
# CONFIGURACIÓN — SIMPLE Y CLARA
# ══════════════════════════════════════════
BOT_VERSION   = "V9.1 Señal con Contexto"
USAR_TESTNET  = os.getenv("BINANCE_TESTNET", "true").lower() in ("true","1","yes")

# Pares seguros con liquidez real
PARES = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT",
         "XRPUSDT","ADAUSDT","AVAXUSDT","LINKUSDT"]

# Riesgo
APALANCAMIENTO       = 3      # 3x — conservador
MAX_POSICIONES       = 3      # máximo 3 abiertas
RIESGO_PCT           = 0.02   # 2% del capital por trade
MAX_PERDIDA_DIARIA   = 0.05   # parar si pierde 5% en el día
MAX_PERDIDA_POSICION = 0.06   # cerrar si posición pierde 6%

# Señal — SIMPLE
RSI_SOBREVENTA  = 38   # comprar cuando RSI < 38
RSI_SOBRECOMPRA = 62   # vender cuando RSI > 62

# SL/TP
ATR_MULT_SL = 1.5     # SL = 1.5 × ATR
TP_RATIO    = 2.0     # TP = 2 × SL siempre

# Tiempos
CICLO_SEG        = 30   # analizar cada 30 segundos
TIEMPO_PAR_SEG   = 2    # espera entre pares

# Fees
FEE_TOTAL = 0.0018

# ══════════════════════════════════════════
# ESTADO GLOBAL
# ══════════════════════════════════════════
stats = {
    "balance_inicio_dia": 0,
    "pnl_dia": 0,
    "pausado": False,
    "fecha": None,
    "ganados": 0,
    "perdidos": 0,
}
_servidor_inicio  = time.time()
_cache_pos        = {"ts": 0, "data": None}
_cache_info       = {"ts": 0, "data": None}
_cache_btc_trend  = {"ts": 0, "data": "LATERAL"}
_notificadas      = set()
_sl_log           = {}
client            = None
cm                = None

# ══════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════
def log(msg):
    print(f"[BOT] {msg}", flush=True)

def tg(msg):
    """Envía mensaje a Telegram."""
    try:
        token   = os.getenv("TELEGRAM_TOKEN","")
        chat_id = os.getenv("TELEGRAM_CHAT_ID","")
        if token and chat_id:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=8
            )
    except Exception:
        pass

def hora():
    from zoneinfo import ZoneInfo
    try:
        return datetime.now(ZoneInfo("America/Guatemala"))
    except Exception:
        return datetime.now()

# ══════════════════════════════════════════
# BINANCE — FUNCIONES BASE
# ══════════════════════════════════════════
def posiciones(force=False):
    now = time.time()
    if not force and _cache_pos["data"] and now - _cache_pos["ts"] < 3:
        return _cache_pos["data"]
    data = client.futures_position_information()
    _cache_pos.update({"ts": now, "data": data})
    return data

def exchange_info(force=False):
    now = time.time()
    if not force and _cache_info["data"] and now - _cache_info["ts"] < 1800:
        return _cache_info["data"]
    data = client.futures_exchange_info()
    _cache_info.update({"ts": now, "data": data})
    return data

def balance():
    try:
        for b in client.futures_account_balance():
            if b["asset"] == "USDT":
                return float(b["balance"])
        return 0.0
    except Exception:
        return 0.0

def balance_disponible():
    try:
        return float(client.futures_account().get("availableBalance", 0))
    except Exception:
        return 0.0

def velas(symbol, interval="15m", limit=200):
    try:
        k = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        return [{"timestamp":x[0],"open":float(x[1]),"high":float(x[2]),
                 "low":float(x[3]),"close":float(x[4]),"volume":float(x[5])}
                for x in k]
    except Exception as e:
        log(f"⚠️ Velas {symbol}: {e}")
        return None

def pos_abiertas():
    try:
        return [p for p in posiciones() if float(p.get("positionAmt",0)) != 0]
    except Exception:
        return []

def simbolos_con_pos():
    return [p["symbol"] for p in pos_abiertas()]

def precision_precio(symbol):
    try:
        info = exchange_info()
        si = next((s for s in info["symbols"] if s["symbol"]==symbol), None)
        return int(si["pricePrecision"]) if si else 4
    except Exception:
        return 4

def cantidad(symbol, monto_usdt, precio):
    try:
        info = exchange_info()
        si   = next((s for s in info["symbols"] if s["symbol"]==symbol), None)
        if not si:
            return None
        qp  = int(si["quantityPrecision"])
        qty = round(monto_usdt / precio, qp)
        mq  = float(next((f["minQty"] for f in si["filters"] if f["filterType"]=="LOT_SIZE"), 0.001))
        return qty if qty >= mq else None
    except Exception:
        return None

def set_leverage(symbol, lev):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=lev)
    except Exception as e:
        if "No need" not in str(e):
            log(f"⚠️ Leverage {symbol}: {e}")

# ══════════════════════════════════════════
# TENDENCIA MACRO BTC 1H (cache 30 min)
# ══════════════════════════════════════════
def btc_tendencia_1h():
    """Retorna la tendencia de BTC en 1H para filtrar entradas contra el mercado."""
    now = time.time()
    if now - _cache_btc_trend["ts"] < 1800:
        return _cache_btc_trend["data"]
    try:
        v = velas("BTCUSDT", "1h", 200)
        if not v or len(v) < 100:
            return "LATERAL"
        klines = [[x["timestamp"], x["open"], x["high"], x["low"], x["close"], x["volume"]]
                  for x in v[:-1]]
        ind = analizar_indicadores_completo(klines)
        trend = (ind.get("tendencia_ema", "LATERAL") or "LATERAL").upper() if ind else "LATERAL"
        _cache_btc_trend.update({"ts": now, "data": trend})
        log(f"📈 BTC 1H macro: {trend}")
        return trend
    except Exception as e:
        log(f"⚠️ btc_tendencia_1h: {e}")
        return "LATERAL"

# ══════════════════════════════════════════
# GESTIÓN DE RIESGO DIARIO
# ══════════════════════════════════════════
def check_nuevo_dia(bal):
    hoy = hora().strftime("%Y-%m-%d")
    if stats["fecha"] != hoy:
        stats.update({"fecha": hoy, "balance_inicio_dia": bal,
                      "pnl_dia": 0, "pausado": False})
        log(f"📅 Nuevo día {hoy}. Balance inicio: ${bal:.2f}")

def puede_operar(bal):
    check_nuevo_dia(bal)
    if stats["pausado"]:
        return False
    inicio = stats["balance_inicio_dia"]
    if inicio <= 0:
        return True
    dd = (bal - inicio) / inicio
    stats["pnl_dia"] = bal - inicio
    if dd < -MAX_PERDIDA_DIARIA:
        stats["pausado"] = True
        log(f"🛑 Pérdida diaria {dd*100:.1f}% — bot pausado hasta mañana")
        tg(f"🛑 Pérdida diaria alcanzada: {dd*100:.1f}%\nBot pausado hasta mañana.")
        return False
    return True

# ══════════════════════════════════════════
# SEÑAL V9.1 — RSI + EMA + CONTEXTO
# ══════════════════════════════════════════
def senal(ind, rsi_prev=None, btc_trend="LATERAL"):
    """
    V9.1 — Tres filtros adicionales sobre la señal base:
      1. Filtro macro BTC: no LONG si BTC 1H es bajista, no SHORT si es alcista
      2. Volumen: volumen_relativo >= 1.0 (operamos con participación real)
      3. Reversión RSI: el RSI debe estar girando del extremo (no en caída/subida libre)
    """
    if not ind:
        return None, 0.0, "Sin datos"

    rsi     = float(ind.get("rsi", 50))
    tend    = (ind.get("tendencia_ema", "") or "").upper()
    hist    = float((ind.get("macd") or {}).get("histograma", 0))
    atr_pct = float(ind.get("atr_percent", 0))
    vol_rel = float(ind.get("volumen_relativo", 1.0))

    # ── Filtro volatilidad ──
    if atr_pct < 0.20:
        return None, 0.0, f"Sin volatilidad (ATR={atr_pct:.2f}%)"

    # ── Filtro volumen ──
    if vol_rel < 1.0:
        return None, 0.0, f"Volumen bajo (VR={vol_rel:.2f}x — esperar participación)"

    # ── LONG ──
    if rsi < RSI_SOBREVENTA:
        if tend == "BAJISTA_FUERTE":
            return None, 0.0, f"RSI={rsi:.0f} pero par BAJISTA_FUERTE — skip"
        # Filtro macro: no comprar si BTC cae en 1H
        if btc_trend in ("BAJISTA_FUERTE", "BAJISTA"):
            return None, 0.0, f"RSI={rsi:.0f} sobrevendido pero BTC 1H {btc_trend} — no LONG"
        # Reversión: RSI debe estar subiendo (giro real, no caída libre)
        if rsi_prev is not None and rsi <= rsi_prev:
            return None, 0.0, f"RSI={rsi:.0f} sin giro alcista aún (prev={rsi_prev:.0f}) — esperar"
        conf = 0.87 if hist > 0 else 0.74
        razon = (f"RSI={rsi:.0f}↑ giro | tend={tend} | BTC={btc_trend} | "
                 f"VR={vol_rel:.1f}x | conf={int(conf*100)}%")
        return "LONG", conf, razon

    # ── SHORT ──
    if rsi > RSI_SOBRECOMPRA:
        if tend == "ALCISTA_FUERTE":
            return None, 0.0, f"RSI={rsi:.0f} pero par ALCISTA_FUERTE — skip"
        # Filtro macro: no shortar si BTC sube en 1H
        if btc_trend in ("ALCISTA_FUERTE", "ALCISTA"):
            return None, 0.0, f"RSI={rsi:.0f} sobrecomprado pero BTC 1H {btc_trend} — no SHORT"
        # Reversión: RSI debe estar cayendo (giro real, no subida libre)
        if rsi_prev is not None and rsi >= rsi_prev:
            return None, 0.0, f"RSI={rsi:.0f} sin giro bajista aún (prev={rsi_prev:.0f}) — esperar"
        conf = 0.87 if hist < 0 else 0.74
        razon = (f"RSI={rsi:.0f}↓ giro | tend={tend} | BTC={btc_trend} | "
                 f"VR={vol_rel:.1f}x | conf={int(conf*100)}%")
        return "SHORT", conf, razon

    return None, 0.0, f"RSI={rsi:.0f} — zona neutral"

# ══════════════════════════════════════════
# SL Y TP BASADO EN ATR
# ══════════════════════════════════════════
def calcular_sl_tp(precio, atr, side, pp):
    dist_sl = max(atr * ATR_MULT_SL, precio * 0.008)  # mínimo 0.8%
    dist_tp = dist_sl * TP_RATIO                        # siempre 2:1

    if side == "BUY":
        sl = round(precio - dist_sl, pp)
        tp = round(precio + dist_tp, pp)
    else:
        sl = round(precio + dist_sl, pp)
        tp = round(precio - dist_tp, pp)

    return sl, tp

# ══════════════════════════════════════════
# EJECUTAR ORDEN
# ══════════════════════════════════════════
def abrir_posicion(symbol, side, qty, sl, tp):
    try:
        # Orden de mercado
        ord = client.futures_create_order(
            symbol=symbol, side=side, type="MARKET", quantity=qty
        )
        log(f"   ✅ Orden {side} {qty} {symbol} — ID={ord['orderId']}")

        pp = precision_precio(symbol)
        sl = round(sl, pp)
        tp = round(tp, pp)

        # Take Profit
        tp_side = "SELL" if side == "BUY" else "BUY"
        try:
            client.futures_create_order(
                symbol=symbol, side=tp_side,
                type="TAKE_PROFIT_MARKET",
                stopPrice=tp, closePosition=True
            )
            log(f"   📈 TP: ${tp}")
        except Exception as e:
            log(f"   ⚠️ TP error: {e}")

        # Stop Loss
        try:
            client.futures_create_order(
                symbol=symbol, side=tp_side,
                type="STOP_MARKET",
                stopPrice=sl, closePosition="true"
            )
            log(f"   📉 SL: ${sl}")
        except Exception as e:
            log(f"   ⚠️ SL error: {e}")

        return True
    except Exception as e:
        log(f"⚠️ Error abriendo {symbol}: {e}")
        return False

# ══════════════════════════════════════════
# GUARDIAN — cierra posiciones en pérdida extrema
# ══════════════════════════════════════════
def guardian():
    try:
        for p in pos_abiertas():
            symbol = p["symbol"]
            qty    = float(p.get("positionAmt", 0))
            entry  = float(p.get("entryPrice", 0))
            mark   = float(p.get("markPrice", 0))
            pnl    = float(p.get("unRealizedProfit", 0))
            side   = "LONG" if qty > 0 else "SHORT"

            if entry <= 0:
                continue

            notional = entry * abs(qty)
            pnl_pct  = (pnl / notional) if notional > 0 else 0

            if pnl_pct < -MAX_PERDIDA_POSICION:
                log(f"🚨 GUARDIAN cerrando {symbol} {side} — PNL={pnl_pct*100:.1f}%")
                close = "SELL" if qty > 0 else "BUY"
                try:
                    client.futures_cancel_all_open_orders(symbol=symbol)
                    client.futures_create_order(
                        symbol=symbol, side=close,
                        type="MARKET", quantity=abs(qty),
                        reduceOnly="true"
                    )
                    tg(f"🚨 Guardian cerró {symbol}\nPNL: {pnl_pct*100:.1f}% (${pnl:.2f})")
                except Exception as e:
                    log(f"⚠️ Error guardian {symbol}: {e}")
    except Exception as e:
        log(f"⚠️ Error guardian: {e}")

# ══════════════════════════════════════════
# MONITOREO DE TRADES CERRADOS
# ══════════════════════════════════════════
def trades_cerrados():
    global _notificadas
    try:
        trades = client.futures_account_trades(limit=20)
        for t in trades:
            pnl = float(t.get("realizedPnl", 0))
            if pnl == 0:
                continue
            sym = t.get("symbol","")
            key = f"{t.get('orderId','')}_{sym}_{pnl}"
            if key in _notificadas:
                continue
            _notificadas.add(key)
            if len(_notificadas) > 3000:
                _notificadas = set(list(_notificadas)[-1500:])

            stats["pnl_dia"] = stats.get("pnl_dia", 0) + pnl
            if pnl > 0:
                stats["ganados"] = stats.get("ganados", 0) + 1
                log(f"💰 Ganado ({sym}): +${pnl:.2f}")
            else:
                stats["perdidos"] = stats.get("perdidos", 0) + 1
                log(f"💸 Perdido ({sym}): -${abs(pnl):.2f}")

            try:
                registrar_trade_cerrado(sym, pnl)
            except Exception:
                pass

            if cm:
                try:
                    cm.actualizar(pnl, calcular_metricas_riesgo(dias=30), log_fn=log)
                except Exception:
                    pass
    except Exception as e:
        log(f"⚠️ trades_cerrados: {e}")

# ══════════════════════════════════════════
# CICLO PRINCIPAL DE ANÁLISIS
# ══════════════════════════════════════════
def analizar():
    bal       = balance()
    bal_disp  = balance_disponible()

    if not puede_operar(bal):
        return

    pos_act   = pos_abiertas()
    n_pos     = len(pos_act)
    espacios  = MAX_POSICIONES - n_pos
    syms_pos  = simbolos_con_pos()

    log(f"💰 ${bal:.2f} | Pos={n_pos}/{MAX_POSICIONES} | Espacios={espacios}")

    if espacios <= 0:
        log("📊 Posiciones llenas — monitoreando")
        return

    # Calcular capital disponible para operar (85% del total)
    capital_op = (cm.get_capital_operativo() if cm else bal) * 0.85
    monto      = capital_op * RIESGO_PCT
    monto      = max(5.0, round(monto, 2))

    log(f"🔍 Analizando {len(PARES)} pares | Monto/trade: ${monto:.2f}")

    # Tendencia macro BTC — se consulta una vez por ciclo (cache 30 min)
    btc_trend = btc_tendencia_1h()

    for symbol in PARES:
        if espacios <= 0:
            break
        if symbol in syms_pos:
            continue

        try:
            # Obtener velas 15m
            v = velas(symbol, "15m", 200)
            if not v or len(v) < 100:
                continue

            # Calcular indicadores sobre velas completas (excluyendo vela en curso)
            klines = [[x["timestamp"],x["open"],x["high"],x["low"],x["close"],x["volume"]]
                      for x in v[:-1]]
            ind = analizar_indicadores_completo(klines)
            if not ind:
                continue

            precio = float(ind["precio_actual"])
            atr    = float(ind.get("atr", 0))

            # RSI de 3 velas atrás para confirmar reversión (giro real, no impulso)
            precios_cierre = [float(k[4]) for k in klines]
            rsi_prev = calcular_rsi(precios_cierre[:-3]) if len(precios_cierre) > 20 else None

            # Señal V9.1 con contexto
            accion, conf, razon = senal(ind, rsi_prev, btc_trend)
            if not accion:
                log(f"   ⏭️ {symbol}: {razon}")
                continue

            log(f"   ✅ {symbol} {accion} | {razon}")

            # Calcular SL y TP
            pp = precision_precio(symbol)
            sl, tp = calcular_sl_tp(precio, atr, "BUY" if accion=="LONG" else "SELL", pp)

            # Verificar ratio R:R
            dist_sl = abs(precio - sl)
            dist_tp = abs(precio - tp)
            rr = dist_tp / dist_sl if dist_sl > 0 else 0
            if rr < 1.8:
                log(f"   ⏭️ {symbol}: R:R={rr:.1f} insuficiente")
                continue

            # Verificar EV
            sl_pct = dist_sl / precio
            tp_pct = dist_tp / precio
            p_win  = max(0.45, min(0.85, conf))
            ev     = (p_win * tp_pct) - ((1-p_win) * sl_pct) - FEE_TOTAL
            if ev <= 0:
                log(f"   ⏭️ {symbol}: EV={ev*100:.2f}% negativo")
                continue

            # Configurar apalancamiento y calcular cantidad
            set_leverage(symbol, APALANCAMIENTO)
            side = "BUY" if accion == "LONG" else "SELL"
            qty  = cantidad(symbol, monto * APALANCAMIENTO, precio)

            if not qty:
                log(f"   ⚠️ {symbol}: cantidad mínima no alcanzada")
                continue

            log(f"\n🚀 {symbol} {accion} | Entrada=${precio:.4f} | SL=${sl} | TP=${tp} | R:R={rr:.1f}:1")

            ok = abrir_posicion(symbol, side, qty, sl, tp)
            if ok:
                espacios -= 1
                tg(f"🚀 *{BOT_VERSION} — Nueva operación*\n"
                   f"📍 {symbol} *{accion}*\n"
                   f"💰 Entrada: `${precio:.4f}`\n"
                   f"📉 SL: `${sl}` | 📈 TP: `${tp}`\n"
                   f"⚖️ R:R = {rr:.1f}:1 | EV = {ev*100:.2f}%\n"
                   f"💡 _{razon}_")
                try:
                    registrar_trade_abierto(
                        symbol=symbol, side=side, action=accion,
                        entry_price=precio, quantity=qty,
                        confidence=conf, temporalidad="15m",
                        razon=razon[:200], ia_validado=False
                    )
                except Exception:
                    pass

        except Exception as e:
            log(f"   ⚠️ Error {symbol}: {e}")

        time.sleep(TIEMPO_PAR_SEG)

# ══════════════════════════════════════════
# SERVIDOR HTTP — health check
# ══════════════════════════════════════════
def servidor_salud():
    PORT = int(os.getenv("PORT", 8000))
    class H(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            try:
                bal = balance() if client else 0
                data = {
                    "version": BOT_VERSION,
                    "balance": round(bal, 2),
                    "posiciones": len(pos_abiertas()),
                    "max_posiciones": MAX_POSICIONES,
                    "pnl_dia": round(stats.get("pnl_dia",0), 2),
                    "pausado": stats.get("pausado", False),
                    "uptime": int(time.time() - _servidor_inicio),
                    "testnet": USAR_TESTNET,
                    "timestamp": hora().isoformat()
                }
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
        def log_message(self, *a): pass
    try:
        with socketserver.TCPServer(("",PORT), H) as s:
            s.serve_forever()
    except Exception:
        pass

# ══════════════════════════════════════════
# ARRANQUE
# ══════════════════════════════════════════
log(f"🚀 Iniciando {BOT_VERSION}...")
log(f"   Leverage={APALANCAMIENTO}x | Riesgo={RIESGO_PCT*100:.0f}%/trade | MaxPos={MAX_POSICIONES}")
log(f"   RSI_LONG<{RSI_SOBREVENTA} | RSI_SHORT>{RSI_SOBRECOMPRA} | TP_RATIO={TP_RATIO}:1")

# Conexión Binance
try:
    api_key    = os.getenv("BINANCE_API_KEY","")
    api_secret = os.getenv("BINANCE_SECRET","") or os.getenv("BINANCE_API_SECRET","")
    if USAR_TESTNET:
        client = Client(api_key, api_secret, testnet=True)
        log("📡 Conectado a Binance TESTNET")
    else:
        client = Client(api_key, api_secret)
        log("📡 Conectado a Binance PRODUCCIÓN")
    bal_inicio = balance()
    log(f"✅ Balance: ${bal_inicio:.2f} USDT")
except Exception as e:
    log(f"❌ Error Binance: {e}")
    sys.exit(1)

# Capital Manager
try:
    cm = CapitalManager(capital_inicial=bal_inicio)
    cm.inicializar_tabla()
    if cm.cargar_estado():
        cm.sincronizar_con_exchange(bal_inicio, log)
        log(f"💼 Capital: {cm.resumen_estado()}")
    else:
        cm.guardar_estado()
except Exception as e:
    log(f"⚠️ CapitalManager: {e}")
    cm = None

# Base de datos
try:
    inicializar_db()
    registrar_balance_diario(hora().strftime("%Y-%m-%d"), balance_inicio=bal_inicio)
except Exception:
    pass

# Inicializar stats diarios
check_nuevo_dia(bal_inicio)

# Cache de trades existentes
try:
    trades_hist = client.futures_account_trades(limit=100)
    for t in trades_hist:
        pnl = float(t.get("realizedPnl",0))
        if pnl != 0:
            _notificadas.add(f"{t.get('orderId','')}_{t.get('symbol','')}_{pnl}")
    log(f"✅ Cache: {len(_notificadas)} trades previos")
except Exception:
    pass

# Servidor HTTP en background
threading.Thread(target=servidor_salud, daemon=True).start()

# Notificar inicio
tg(f"🤖 *{BOT_VERSION} ONLINE*\n"
   f"💵 Balance: `${bal_inicio:.2f}`\n"
   f"⚙️ {APALANCAMIENTO}x | {RIESGO_PCT*100:.0f}%/trade | {MAX_POSICIONES} pos máx\n"
   f"🎯 RSI LONG<{RSI_SOBREVENTA} | SHORT>{RSI_SOBRECOMPRA}\n"
   f"🔄 {'TESTNET' if USAR_TESTNET else 'PRODUCCIÓN'}")

log(f"✅ {BOT_VERSION} listo. Analizando cada {CICLO_SEG}s...")

# ══════════════════════════════════════════
# BUCLE PRINCIPAL
# ══════════════════════════════════════════
ciclo = 0
_guardian_last = 0
_trades_last   = 0
_resumen_enviado = False

while True:
    try:
        ciclo += 1
        now = time.time()

        bal_actual = balance()
        if cm:
            try:
                cm.sincronizar_con_exchange(bal_actual, log)
            except Exception:
                pass

        # Guardian cada 10s
        if now - _guardian_last >= 10:
            guardian()
            _guardian_last = now

        # Revisar trades cerrados cada 15s
        if now - _trades_last >= 15:
            trades_cerrados()
            _trades_last = now

        # Resumen diario a las 22:00
        if hora().hour == 22 and not _resumen_enviado:
            tg(f"📊 *Resumen diario {BOT_VERSION}*\n"
               f"💵 Balance: ${bal_actual:.2f}\n"
               f"📈 PNL hoy: ${stats.get('pnl_dia',0):+.2f}\n"
               f"✅ Ganados: {stats.get('ganados',0)} | ❌ Perdidos: {stats.get('perdidos',0)}")
            _resumen_enviado = True
        elif hora().hour != 22:
            _resumen_enviado = False

        # Análisis de mercado cada CICLO_SEG
        if ciclo % 1 == 0:
            puede = puede_operar(bal_actual)
            if puede:
                analizar()
            else:
                log(f"⏸️ Pausado por pérdida diaria | PNL={stats.get('pnl_dia',0):+.2f}")

        # Heartbeat cada 5 minutos
        if ciclo % 10 == 0:
            log(f"💓 {BOT_VERSION} | ${bal_actual:.2f} | Pos={len(pos_abiertas())}/{MAX_POSICIONES} | PNL={stats.get('pnl_dia',0):+.2f}")

        time.sleep(CICLO_SEG)

    except Exception as e:
        log(f"⚠️ Error bucle: {e}")
        time.sleep(30)