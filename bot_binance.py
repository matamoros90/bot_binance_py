# ═══════════════════════════════════════════════════════════════════════════════
# 🤖 BOT BINANCE FUTURES - GEMINI 2.0 FLASH
# Trading 24/7 de Criptomonedas con IA
# V2.6 - Trailing SL + Fear & Greed + Funding Fees Protection + New GenAI SDK
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
CONFIANZA_MINIMA = 0.70   # 70% - Solo operaciones de alta certeza
ESCUDO_TRABAJO = 0.80     # 80% del balance disponible para trading
ESCUDO_SEGURO = 0.20      # 20% protegido
TIEMPO_POR_ACTIVO = 10    # Segundos entre análisis de cada activo
VELAS_CANTIDAD = 200      # Cantidad de velas a obtener
APALANCAMIENTO = 3        # Apalancamiento conservador x3
TOP_ACTIVOS = 15          # Activos a analizar por volumen
MAX_POSICIONES = 3        # Máximo 3 posiciones simultáneas

# ═══════════════════════════════════════════════════════════════════════════════
# TRAILING STOP LOSS CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
TRAILING_SL_PERCENT = 0.015  # 1.5% - distancia del trailing
MONITOREO_INTERVALO = 30     # Segundos entre monitoreo de posiciones

# ═══════════════════════════════════════════════════════════════════════════════
# PROTECCIÓN CONTRA FUNDING FEES (V2.5)
# ═══════════════════════════════════════════════════════════════════════════════
FUNDING_PROTECTION = True       # Activar protección de funding
MAX_DIAS_POSICION = 5           # Cerrar posiciones después de 5 días
TP_DINAMICO_DIAS = 3            # Después de 3 días, ajustar TP
TP_DINAMICO_PERCENT = 0.02      # TP reducido a 2% después de X días

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
            self.wfile.write(b"BINANCE BOT V2.6 ALIVE - NEW GENAI SDK + FUNDING PROTECTION")
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
    except:
        pass

def crear_orden_sl(client, symbol, side, precio, cantidad):
    """Crea una nueva orden Stop Loss"""
    try:
        # Obtener precisión del precio
        info = client.futures_exchange_info()
        symbol_info = next((s for s in info['symbols'] if s['symbol'] == symbol), None)
        if symbol_info:
            price_precision = int(symbol_info['pricePrecision'])
            precio = round(precio, price_precision)
        
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type='STOP_MARKET',
            stopPrice=precio,
            quantity=cantidad
        )
        return True
    except Exception as e:
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
                    
                    enviar_telegram(f"""⏰ *CIERRE POR TIEMPO* BINANCE
*Par:* `{symbol}`
*Días abierto:* `{dias_abierto}` (máx: {MAX_DIAS_POSICION})
*Entry:* `${entry_price:.4f}`
*Exit:* `${mark_price:.4f}`
*PNL estimado:* `${pnl:.2f}`
*Razón:* Protección funding fees V2.5""")
                    
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
                    
                    enviar_telegram(f"""💸 *CIERRE FUNDING > PNL* BINANCE
*Par:* `{symbol}`
*Unrealized PNL:* `${unrealized_pnl:.2f}`
*Funding pagado:* `${total_funding:.2f}`
*Entry:* `${entry_price:.4f}`
*Exit:* `${mark_price:.4f}`
*Razón:* Fees superan ganancias V2.5""")
                    
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
                        enviar_telegram(f"""📈 *TP DINÁMICO AJUSTADO*
*Par:* `{symbol}`
*Días abierto:* `{dias_abierto}`
*Nuevo TP:* `${nuevo_tp:.4f}`
*PNL actual:* `${unrealized_pnl:.2f}`
*Razón:* Asegurar ganancias V2.5""")
                        
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
                client.futures_create_order(
                    symbol=symbol,
                    side=sl_side,
                    type='STOP_MARKET',
                    stopPrice=sl,
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
    """Verifica posiciones cerradas recientemente y notifica el resultado"""
    global posiciones_notificadas
    try:
        trades = client.futures_account_trades(limit=20)
        
        for trade in trades:
            order_id = trade.get('orderId', '')
            symbol = trade.get('symbol', '')
            side = trade.get('side', '')
            pnl = float(trade.get('realizedPnl', 0))
            qty = trade.get('qty', '')
            
            if pnl == 0:
                continue
            
            unique_key = f"{order_id}_{symbol}_{pnl}"
            if unique_key in posiciones_notificadas:
                continue
            
            posiciones_notificadas.add(unique_key)
            
            if len(posiciones_notificadas) > 100:
                posiciones_notificadas = set(list(posiciones_notificadas)[-50:])
            
            if pnl > 0:
                emoji = "💰"
                estado = "GANADA"
            else:
                emoji = "💸"
                estado = "PERDIDA"
            
            log(f"{emoji} Posición cerrada ({symbol}): {estado} ${abs(pnl):.2f}")
            
            mensaje = f"""{emoji} *{estado}* BINANCE
*Par:* `{symbol}`
*Lado:* `{side}`
*Cantidad:* `{qty}`
*P&L:* `${pnl:.2f}`
*Trailing SL:* Activo ✅"""
            enviar_telegram(mensaje)
            
    except Exception as e:
        pass

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
                
                precio_actual = velas[-1]['close']
                precios = [v['close'] for v in velas[-100:]]
                precio_max = max(precios)
                precio_min = min(precios)
                volatilidad = ((precio_max - precio_min) / precio_actual) * 100
                posicion_rango = ((precio_actual - precio_min) / (precio_max - precio_min) * 100) if precio_max != precio_min else 50
                
                # Prompt mejorado con Fear & Greed y temporalidades
                prompt = f"""Eres un trader profesional de criptomonedas con análisis técnico y fundamental.

DATOS DEL MERCADO GLOBAL:
🎭 Fear & Greed Index: {fg_valor}/100 ({fg_clasificacion})
- 0-25: Extreme Fear (oportunidad de compra agresiva)
- 26-45: Fear (considerar LONGs en soportes)
- 46-55: Neutral
- 56-75: Greed (precaución con LONGs)
- 76-100: Extreme Greed (preferir SHORTs o WAIT)

DATOS TÉCNICOS DE {symbol}:
- Precio actual: ${precio_actual}
- Máximo (100 velas): ${precio_max}
- Mínimo (100 velas): ${precio_min}
- Volatilidad: {volatilidad:.2f}%
- Posición en rango: {posicion_rango:.1f}%

TEMPORALIDADES DISPONIBLES: 15m, 30m, 1h, 4h
- 15m: scalping rápido (volatilidad alta >5%)
- 30m: trades cortos (volatilidad media 3-5%)
- 1h: intraday (volatilidad normal 2-3%)
- 4h: swing (volatilidad baja <2%)

REGLAS ESTRICTAS:
1. Confianza mínima: 70%
2. Si Fear < 30, PREFERIR LONGs en soportes
3. Si Greed > 70, PREFERIR SHORTs o WAIT
4. Si precio está en 20% inferior del rango → considerar LONG
5. Si precio está en 80% superior del rango → considerar SHORT
6. Si está en medio (30%-70%) → WAIT a menos que Fear/Greed sea extremo
7. Elige la temporalidad según la volatilidad actual

JSON (solo esto, sin explicación adicional):
{{"ACCION": "LONG/SHORT/WAIT", "CONFIANZA": 0.75, "TEMPORALIDAD": "1h", "RAZON": "explicacion breve"}}"""
                
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
                        'volatilidad': volatilidad
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
            
            symbol = op['symbol']
            accion = op['accion']
            confianza = op['confianza']
            temporalidad = op['temporalidad']
            precio_actual = op['precio_actual']
            razon = op['razon']
            
            conf_pct = int(confianza * 100)
            monto = calcular_monto(saldo, confianza)
            
            # Obtener TP/SL según temporalidad
            config = TP_SL_CONFIG.get(temporalidad, TP_SL_CONFIG["1h"])
            
            if accion == "LONG":
                tp = precio_actual * (1 + config["tp"])
                sl = precio_actual * (1 - config["sl"])
            else:  # SHORT
                tp = precio_actual * (1 - config["tp"])
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
                    enviar_telegram(f"""🚀 *ORDEN BINANCE V2.0*
*Par:* `{symbol}`
*Acción:* `{accion}`
*Confianza:* `{conf_pct}%`
*Temporalidad:* `{temporalidad}`
*Monto:* `${monto}`
*Cantidad:* `{cantidad}`
*TP:* `${tp:.4f}`
*SL inicial:* `${sl:.4f}`
*Trailing SL:* `1.5% activo` ✅
*Fear/Greed:* `{fg_valor} ({fg_clasificacion})`
*Razón:* _{razon[:100]}_""")
            else:
                log(f"   ⚠️ Cantidad mínima no alcanzada para {symbol}")
        
        log(f"\n✅ Ciclo completado. {ejecutadas} órdenes ejecutadas.")
        
    except Exception as e:
        log(f"⚠️ Error en ciclo de trading: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTE DE INICIO
# ═══════════════════════════════════════════════════════════════════════════════
def generar_reporte_inicio(saldo, status_gemini, fg_valor, fg_clasificacion):
    modo = "TESTNET (PRUEBA)" if USAR_TESTNET else "PRODUCCIÓN"
    funding_status = "🟢 ACTIVA" if FUNDING_PROTECTION else "🔴 DESACTIVADA"
    
    reporte = f"""🤖 BINANCE BOT V2.6 ONLINE
🚀 BINANCE FUTUROS: 🟢 CONECTADO

💰 BALANCE DETECTADO:
💵 USDT Disponible: ${saldo:.2f}
🛡️ Escudo 80/20 %
👨🏻‍💻 Trabajo 80%
🛟 Seguro 20%

⚙️ CONFIGURACIÓN:
🔧 Modo: {modo}
📊 Apalancamiento: x{APALANCAMIENTO}
🎯 Confianza mínima: {int(CONFIANZA_MINIMA*100)}%
📈 Top activos: {TOP_ACTIVOS}
📉 Max posiciones: {MAX_POSICIONES}

🆕 FUNCIONES V2.6:
📍 Trailing SL: {TRAILING_SL_PERCENT*100}% activo
⏱️ Temporalidades: 15m, 30m, 1h, 4h
🎭 Fear & Greed: {fg_valor} ({fg_clasificacion})

💸 PROTECCIÓN FUNDING FEES: {funding_status}
⏰ Cierre por tiempo: {MAX_DIAS_POSICION} días máx
📈 TP dinámico: Después de {TP_DINAMICO_DIAS} días
💵 Funding vs PNL: Auto-cierre si fees > ganancias

🧠 CEREBRO IA:
🤖 Gemini 2.0 Flash (New SDK): {status_gemini}

⏰ HORARIO: 24/7 (Sin pausas)
🔄 Monitoreo: cada {MONITOREO_INTERVALO}s"""
    
    return reporte

# ═══════════════════════════════════════════════════════════════════════════════
# ARRANQUE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
log("🚀 Iniciando Bot Binance Futuros V2.6...")
log("📍 Trailing SL + Fear & Greed + Funding Protection + New GenAI SDK")

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

# Reporte de inicio
reporte = generar_reporte_inicio(saldo, status_gemini, fg_valor, fg_clasificacion)
log(reporte)
enviar_telegram(reporte)

# Inicializar tracking de posiciones existentes
pos_iniciales = contar_posiciones_abiertas(client)
if pos_iniciales > 0:
    log(f"� {pos_iniciales} posiciones existentes detectadas. Activando Trailing SL...")
    actualizar_trailing_sl(client)
else:
    log("✅ Sin posiciones abiertas. Listo para operar.")

log("✅ Bot V2.6 iniciado. Operando 24/7 con Trailing SL + Funding Protection + New GenAI SDK...")

# ═══════════════════════════════════════════════════════════════════════════════
# BUCLE PRINCIPAL - 24/7 CON MONITOREO CONTINUO
# ═══════════════════════════════════════════════════════════════════════════════
ciclo_analisis = 0
CICLOS_PARA_ANALISIS = 4  # Cada 4 ciclos de monitoreo (4 * 30s = 2 min) hacer análisis completo

while True:
    try:
        ciclo_analisis += 1
        
        # Siempre actualizar Trailing SL
        actualizar_trailing_sl(client)
        verificar_posiciones_cerradas(client)
        
        # Protección contra Funding Fees (cada ciclo)
        if FUNDING_PROTECTION:
            verificar_tiempo_posiciones(client)
            verificar_funding_vs_pnl(client)
            ajustar_tp_dinamico(client)
        
        # Cada N ciclos, hacer análisis completo de mercado
        if ciclo_analisis >= CICLOS_PARA_ANALISIS:
            ejecutar_trading(client, gemini_client)
            ciclo_analisis = 0
        else:
            pos_abiertas = contar_posiciones_abiertas(client)
            if pos_abiertas > 0:
                log(f"👁️ Monitoreo V2.5... Posiciones: {pos_abiertas}/{MAX_POSICIONES}")
            else:
                log(f"👁️ Sin posiciones. Próximo análisis en {(CICLOS_PARA_ANALISIS - ciclo_analisis) * MONITOREO_INTERVALO}s...")
        
        time.sleep(MONITOREO_INTERVALO)
        
    except Exception as e:
        log(f"⚠️ Error en bucle principal: {e}")
        time.sleep(60)
