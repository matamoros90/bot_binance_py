# 🤖 Bot Binance Futures V5.3 - Multi-Timeframe + SQLite + Métricas de Riesgo

## 📋 Descripción

Bot de trading automatizado para Binance Futures que utiliza **Gemini 2.0 Flash** como cerebro de IA para tomar decisiones de trading. Opera 24/7 con estrategia basada en el prompt simple que logró **19.11% ROI en 19 días** (enero 2026), con **protecciones de seguridad** en código y **filtro anti-tendencia** automático.

---

## 🚀 Estado del Proyecto (Última actualización: 22/02/2026)

| Aspecto         | Estado                                 |
| --------------- | -------------------------------------- |
| **Versión**     | V5.3                                   |
| **Plataforma**  | Koyeb (Deploy automático desde GitHub) |
| **Modo**        | TESTNET (Pruebas)                      |
| **Estado**      | 🟢 Operativo                           |
| **Unit Tests**  | ✅ 26/26 passing                       |
| **Backtesting** | ✅ Disponible                          |

---

## 📁 Estructura del Proyecto

```
bot_binance_IA/
├── bot_binance.py      # Bot principal (trading, Gemini, Telegram)
├── indicators.py       # Indicadores técnicos (RSI, EMA, MACD, Bollinger, ATR...)
├── persistence.py      # SQLite: trades, balances, decisiones, métricas
├── backtesting.py      # Motor de backtesting con datos históricos
├── tests/
│   └── test_formulas.py  # 26 unit tests (indicadores + persistencia)
├── requirements.txt
└── README.md
```

---

## ✅ V5.3 (22/02/2026) — Arquitectura Completa

Mejora de arquitectura con **4 pilares**: análisis multi-timeframe, persistencia SQLite, métricas profesionales, y testing.

### 🧠 Multi-Timeframe + Prompt Enriquecido

1. **Análisis dual 1h + 4h**: 14 indicadores calculados para ambas temporalidades.
2. **200 velas crudas** enviadas a Gemini para detección de patrones (dojis, envolventes, divergencias).
3. **Pre-filtro inteligente**: Descarta símbolos sin señal clara antes de llamar a Gemini (~50% menos API calls).
4. **Penalización cruzada**: Si 4h contradice 1h → confianza -30%.

### 💾 SQLite + Persistencia (`persistence.py`)

5. **Base de datos local**: Registra trades, decisiones de Gemini, y balances diarios. Datos sobreviven reinicios.
6. **Resumen diario automático**: Telegram a las 22:00 (hora Guatemala) con balance, PNL y métricas.
7. **Timezone corregido**: `hora_local()` con `ZoneInfo("America/Guatemala")` para horarios correctos en Koyeb (UTC).

### 📊 Métricas de Riesgo Profesionales

8. **Métricas calculadas automáticamente** desde la BD:
   - **Win Rate** — % de trades ganadores
   - **Profit Factor** — ganancias / pérdidas (>1.5 = viable)
   - **Sharpe Ratio** — retorno ajustado por riesgo (>1.0 = bueno)
   - **Max Drawdown** — mayor caída pico a valle
   - **Expected Value** — valor esperado por trade
9. **Evaluación Mainnet**: El resumen indica si el bot cumple mínimos para dinero real.

### 🧪 Unit Tests + Backtesting (`indicators.py`, `backtesting.py`)

10. **26 unit tests** cubriendo RSI, EMA, MACD, Bollinger, ATR, tendencia EMA, indicadores completos, y SQLite.
11. **`indicators.py`**: Funciones matemáticas puras extraídas del bot — sin dependencia de Binance SDK.
12. **Backtesting**: Simula la estrategia con datos históricos de Binance (descarga automática).

```bash
# Ejecutar unit tests
python -m pytest tests/test_formulas.py -v

# Ejecutar backtesting (últimos 30 días)
python backtesting.py

# Backtesting custom
python backtesting.py --dias 60
python backtesting.py --symbol BTCUSDT --dias 90
```

---

## ✅ V5.2 (22/02/2026) — Interés Compuesto + Fix SL

1. **Fix loop infinito error -4045**: Bot ya no cicla intentando crear SL cuando Binance dice "max stop orders".
2. **Precisión SL para tokens baratos**: Usa `pricePrecision` del exchange.
3. **Interés compuesto en position sizing**: Balance crece → posiciones escalan (hasta 1.5x). Balance baja → reduce (mín 0.5x).
4. **ROI con interés compuesto**: Proyecciones a 30, 90 y 365 días en resumen semanal.
5. **MACD optimizado de O(n²) a O(n)**: EMAs incrementales.

## ✅ V5.0/V5.1 (18/02/2026) — Reset Inteligente

- Vuelve al prompt simple que generó 19% ROI en enero.
- Filtro anti-tendencia en código (rechaza trades contra EMA).
- TP/SL estilo enero: 1h +3.5%/-2.5%, 4h +6%/-3.5%.
- V5.1: Pausa automática por noticias de alto impacto + horarios de protección USA/FED.

---

## ⚙️ Configuración Actual (V5.3)

```python
CONFIANZA_MINIMA = 0.70      # 70% mínimo para operar
ESCUDO_TRABAJO = 0.80        # 80% del balance para trading
APALANCAMIENTO = 3           # x3 conservador
TOP_ACTIVOS = 15             # Analiza top 15 por volumen
MAX_POSICIONES = 3           # Máximo 3 posiciones simultáneas
TRAILING_SL_PERCENT = 0.015  # 1.5% trailing
MONITOREO_INTERVALO = 30     # 30 segundos
VELAS_CANTIDAD = 200         # 200 velas por análisis

# Guardian System
GUARDIAN_ACTIVO = True
MAX_PERDIDA_PERMITIDA = -0.07  # -7% cierre obligatorio

# Funding Fees Protection
MAX_DIAS_POSICION = 5        # Cerrar después de 5 días
TP_DINAMICO_DIAS = 3         # Ajustar TP después de 3 días
```

## 📊 TP/SL por Temporalidad

| Temporalidad | Take Profit | Stop Loss | R:R   | Con x3  |
| ------------ | ----------- | --------- | ----- | ------- |
| 1h           | +3.5%       | -2.5%     | 1.4:1 | ±7-10%  |
| 4h           | +6.0%       | -3.5%     | 1.7:1 | ±10-18% |

---

## 🧠 Flujo de Operación V5.3

```
1. Obtener Fear & Greed Index
2. Analizar top 15 pares por volumen
3. Descargar 200 velas 1h + 100 velas 4h
4. Calcular 14 indicadores × 2 temporalidades (via indicators.py)
5. Pre-filtro: skip si RSI neutral + lateral + rango medio
6. Prompt enriquecido → Gemini decide: LONG, SHORT o WAIT
7. Penalización cruzada: 4h contradice → -30% confianza
8. Registrar decisión en SQLite (persistence.py)
9. Si confianza >= 70%, ejecutar trade + registrar en BD
10. Monitorear Trailing SL cada 30 segundos
11. A las 22:00 GT: resumen diario por Telegram
12. Viernes 18:00 GT: resumen semanal con proyecciones
```

---

## 📦 Dependencias

```txt
python-binance==1.0.19
google-genai
python-dotenv
requests
pytest  # Solo para desarrollo
```

## 🔧 Variables de Entorno

```env
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET=tu_api_secret
BINANCE_TESTNET=True
API_KEY_GEMINI=tu_gemini_api_key
TELEGRAM_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id
CRYPTOPANIC_API_KEY=tu_cryptopanic_key  # Opcional
```

## 🚀 Despliegue

Push a GitHub → Koyeb redespliega automáticamente. Health check en puerto 8000.

## ⚠️ Advertencias

- Este bot opera en TESTNET por defecto
- Cambiar `BINANCE_TESTNET=False` para producción real
- El trading conlleva riesgos — usa solo capital que puedas perder

## 📞 Soporte

Repositorio: https://github.com/matamoros90/bot_binance_py
