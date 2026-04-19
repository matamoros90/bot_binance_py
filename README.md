# 🤖 Bot Binance — V9.1 Señal con Contexto

**Estado:** Producción | Binance Futures Demo / Mainnet  
**Filosofía:** Entrar solo cuando el mercado te da la razón — no pelear contra la tendencia.

---

## 🎯 Estrategia V9.1

La señal requiere **4 condiciones simultáneas** para abrir una operación:

### Condiciones de entrada

| # | Condición | LONG | SHORT |
|---|-----------|------|-------|
| 1 | **RSI extremo** | RSI < 38 | RSI > 62 |
| 2 | **Tendencia del par (EMA)** | No BAJISTA_FUERTE | No ALCISTA_FUERTE |
| 3 | **Tendencia macro BTC 1H** | BTC no bajista (evitar comprar en caída) | BTC no alcista (evitar shortar en subida) |
| 4 | **Confirmación de giro RSI** | RSI subiendo vs 3 velas atrás | RSI bajando vs 3 velas atrás |

### Filtros siempre activos
| Filtro | Valor | Motivo |
|--------|-------|--------|
| Volatilidad mínima | ATR% ≥ 0.20% | Evitar mercados dormidos |
| Volumen mínimo | VR ≥ 1.0× (sobre el promedio) | Operar con liquidez real |

### SL / TP
- SL dinámico: ATR × 1.5 (mínimo 0.8% del precio)
- TP siempre = 2 × SL (ratio 2:1 fijo)

### ¿Por qué el filtro BTC macro?
BTC lidera el mercado crypto. Si BTC está en tendencia bajista en 1H, abrir LONGs en altcoins es nadar contra la corriente. Este filtro evitó las pérdidas más comunes del bot en V9.0 (posiciones LONG abiertas durante caída sostenida de BTC).

---

## ⚙️ Configuración

| Parámetro | Valor |
|-----------|-------|
| Pares | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, ADAUSDT, AVAXUSDT, LINKUSDT |
| Apalancamiento | 3x |
| Riesgo por trade | 2% del capital |
| Máx. posiciones | 3 simultáneas |
| Pérdida diaria máx. | 5% (pausa automática hasta el día siguiente) |
| Temporalidad | 15 minutos |
| Ciclo de análisis | 30 segundos |

---

## 🏗️ Arquitectura

```
bot_binance.py      — Bot principal (señal, órdenes, guardián)
dashboard.py        — Dashboard Streamlit en tiempo real
monitor_bot.py      — Watchdog: reinicia el bot si se cae
indicators.py       — Librería de indicadores técnicos (RSI, EMA, MACD, ATR, Bollinger)
persistence.py      — Base de datos SQLite: trades, balances, métricas
capital_manager.py  — Gestión dinámica de capital (escalado y reducción)
backtesting.py      — Motor de backtesting con datos históricos de Binance
check_orders.py     — Utilidad: consultar órdenes abiertas vía API directa
test_pos.py         — Utilidad: ver posiciones y ROI actuales
```

---

## 🚀 Variables de entorno (`.env`)

```env
# Binance
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET=tu_api_secret
BINANCE_TESTNET=true          # true = Demo | false = Mainnet real

# Telegram (opcional)
TELEGRAM_TOKEN=tu_token
TELEGRAM_CHAT_ID=tu_chat_id

# Puerto del health check HTTP (opcional, default 8000)
PORT=8000
```

---

## 🖥️ Ejecución

### Bot principal
```bash
python bot_binance.py
```

### Bot con watchdog (reinicio automático)
```bash
python monitor_bot.py
```

### Dashboard de monitoreo
```bash
streamlit run dashboard.py
```

### Backtesting (últimos 30 días)
```bash
python backtesting.py
python backtesting.py --dias 60
python backtesting.py --symbol BTCUSDT
```

---

## 🚀 Despliegue en VPS (systemd)

### 1. Clonar y configurar
```bash
git clone https://github.com/matamoros90/bot_binance_py.git ~/proyecto
cd ~/proyecto
pip install -r requirements.txt
cp .env.example .env   # editar con tus credenciales
mkdir -p logs
```

### 2. Servicios systemd

**`/etc/systemd/system/bot.service`**
```ini
[Unit]
Description=Bot Binance V9.0
After=network.target

[Service]
User=tu_usuario
WorkingDirectory=/home/tu_usuario/proyecto
ExecStart=/usr/bin/python3 monitor_bot.py
Restart=always
StandardOutput=append:/home/tu_usuario/proyecto/logs/bot.log
StandardError=append:/home/tu_usuario/proyecto/logs/bot.log

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/dashboard.service`**
```ini
[Unit]
Description=Dashboard Bot Binance
After=network.target

[Service]
User=tu_usuario
WorkingDirectory=/home/tu_usuario/proyecto
ExecStart=/usr/bin/python3 -m streamlit run dashboard.py --server.port 8501 --server.headless true
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. Activar servicios
```bash
sudo systemctl daemon-reload
sudo systemctl enable bot dashboard
sudo systemctl start bot dashboard

# Verificar
sudo systemctl status bot
tail -f logs/bot.log
```

---

## 📊 Capital Manager

Escalado automático basado en rendimiento:

| Fase | Condición | Acción |
|------|-----------|--------|
| Validación | < 30 trades o Profit Factor < 1.5 | Capital fijo |
| Escalado | Validado + drawdown < 20% | +20% capital (máx 1x/día) |
| Reducción | Drawdown > 20% | -30% capital + pausa 8h |

---

## 📋 Historial de versiones

### V9.1 — Señal con Contexto (2026-04-19)
- **Filtro macro BTC 1H:** no LONG si BTC bajista, no SHORT si BTC alcista (cache 30 min)
- **Filtro de volumen:** `volumen_relativo ≥ 1.0` — solo operar con participación real del mercado
- **Confirmación de giro RSI:** el RSI debe estar girando del extremo (comparación vs 3 velas atrás), evita entrar en caída/subida libre
- Confianza base subida a 87%/74% (desde 85%/72%)

### V9.0 — Simple y Operativo (2026-04-18)
- Estrategia simplificada a 2 condiciones: RSI extremo + dirección EMA
- Apalancamiento reducido a 3x (conservador), máximo 3 posiciones
- Backtesting alineado con señal V9.0 usando `indicators.py`
- Eliminados módulos sin uso (`expo_push.py`, `google-genai`, `yfinance`)

### V6.7 — Aggressive Scalper (2026-04-12)
- Alta frecuencia 5m/15m, 10x apalancamiento, 10 posiciones
- Eliminación IA Gemini del ciclo de decisiones

### V6.3 — Institutional Edge
- Capital Manager dinámico integrado
- Dashboard Streamlit con monitoreo live

### V6.0 — Elite Edition
- Apalancamiento x10 scalping, múltiples temporalidades

---

**Repo:** https://github.com/matamoros90/bot_binance_py
