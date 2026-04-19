# 🤖 Bot Binance — V9.0 Simple y Operativo

**Estado:** Producción | Binance Futures Demo / Mainnet  
**Filosofía:** Menos filtros = más trades = más oportunidades de ganar.

---

## 🎯 Estrategia

Señal simple con 2 condiciones (RSI + dirección EMA):

| Dirección | Condición de entrada | Filtro de exclusión |
|-----------|---------------------|---------------------|
| **LONG**  | RSI < 38 (sobrevendido) | No entrar si tendencia EMA es BAJISTA_FUERTE |
| **SHORT** | RSI > 62 (sobrecomprado) | No entrar si tendencia EMA es ALCISTA_FUERTE |

- SL dinámico basado en ATR × 1.5 (mínimo 0.8% del precio)
- TP siempre = 2 × SL (ratio 2:1 fijo)
- Filtro mínimo de volatilidad: ATR% ≥ 0.20%

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

### V9.0 — Simple y Operativo (2026-04-18)
- Estrategia simplificada a 2 condiciones: RSI extremo + dirección EMA
- Sin bloqueo por mercado lateral
- Apalancamiento reducido a 3x (conservador)
- Máximo 3 posiciones simultáneas
- Backtesting alineado con señal V9.0 usando `indicators.py`
- Eliminados módulos sin uso (`expo_push.py`)
- Eliminadas dependencias sin uso (`google-genai`, `yfinance`)

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
