# 🤖 Bot Binance Futures V5.12 — Scalping Institucional + Protección de Capital

## 📋 Descripción

Bot de trading automatizado para Binance Futures. Utiliza **Gemini 2.5 Flash** para señales de scalping en 15 minutos, **datos macroeconómicos (S&P500)** vía yfinance, y **Criterio de Kelly** para position sizing óptimo.

**Balance Actual:** ~$1,828 USDT (Equity Total)

Opera 24/7 con:
- 🎯 Scalping Institucional en temporalidad 15m
- 🧠 IA + Fear & Greed + Macro S&P500
- 📈 Interés compuesto con Kelly Criterion
- 🛡️ Break-even SL + Trailing SL + Guardian automático
- 💾 Persistencia SQLite para métricas y auditoría

---

## 🚀 Estado del Proyecto (25/03/2026)

| Aspecto         | Estado                                 |
| --------------- | -------------------------------------- |
| **Versión**     | V5.12 (Performance Optimization)       |
| **Plataforma**  | Koyeb (Deploy automático desde GitHub) |
| **Modo**        | PRODUCCIÓN                             |
| **Estado**      | 🟢 Operativo                           |

---

## 📁 Estructura del Proyecto

```text
bot_binance_IA/
├── bot_binance.py        # Módulo único (Trading, IA, Riesgo, Indicadores)
├── persistence.py        # SQLite: trades, balances, decisiones, métricas
├── backtesting.py        # Motor de backtesting con datos históricos
├── tests/
│   └── test_formulas.py  # Unit tests
├── requirements.txt
└── README.md
```

---

## ⚙️ Configuración V5.12

```python
CONFIANZA_MINIMA = 0.65          # 65% mínimo — solo trades de alta calidad
APALANCAMIENTO = 3               # Conservador contra liquidaciones
TOP_ACTIVOS = 30                 # Escanea las 30 criptos con más volumen
MAX_POSICIONES = 10              # Hasta 10 posiciones simultáneas
TRAILING_SL_PERCENT = 0.025      # 2.5% trailing (espacio para respirar con 3x)
MONITOREO_INTERVALO = 30         # Escanea cada 30 segundos

# Kelly Criterion
KELLY_ACTIVO = True
KELLY_FRACCION = 0.5             # Medio-Kelly

# Scalping 15 Minutos
TEMPORALIDADES = ['15m']
TP_SL_CONFIG      = {"15m": {"tp": 0.020, "sl": 0.008}}  # R:R 2.5:1
TP_SL_RANGO_CONFIG = {"15m": {"tp": 0.015, "sl": 0.006}}  # Modo lateral
```

---

## 🧠 Flujo Operativo

```text
1. Obtener Fear & Greed Index + Variación S&P500 (yfinance)
2. Analizar top 30 pares por volumen (velas 15m, 200 velas)
3. Calcular indicadores (RSI, Bollinger, MACD, EMA, ATR)
4. Gemini decide LONG/SHORT con confianza ≥ 65%
5. Kelly Criterion determina tamaño de posición
6. Ejecutar con TP +2.0% / SL -0.8% (R:R 2.5:1)
7. Break-even SL al alcanzar +1.5% de ganancia
8. Trailing SL persigue ganancias con 2.5% de distancia
9. Scalping exit automático al +5% ROI sobre margen
10. Repetir 24/7
```

---

## 🛡️ Sistema de Protección de Capital

| Protección | Descripción |
|-----------|-------------|
| **Break-even SL** | Al +1.5%, SL se mueve a entry +0.1% |
| **Trailing SL** | Se activa al +1.0%, distancia 2.5% |
| **SL de Emergencia** | -1.5% si no hay SL activo |
| **Guardian** | Cierre automático al -10% |
| **Drawdown Diario** | Pausa trading si equity cae -3% en el día |
| **Cierre por Tiempo** | Máx 5 días por posición |
| **Funding vs PNL** | Cierra si fees > ganancias (últimas 48h) |
| **TP Dinámico** | Ajusta TP después de 1 día en ganancia |
| **Scalping Motor** | Cierra al 5% ROI sobre margen |

---

## ✅ Changelog V5.12 (25/03/2026)

### Performance Optimization
- **TP ampliado**: 1.5% → 2.0% (más espacio para crecer)
- **Trailing SL**: 1.5% → 2.5% (evita whipsaws con 3x leverage)
- **Break-even SL**: Nuevo — protege ganadores al mover SL a entry +0.1%
- **CONFIANZA_MINIMA**: 50% → 65% (menos trades, mayor calidad)
- **Fallbacks eliminados**: Removidas señales de 65% que forzaban trades malos
- **SL emergencia**: 3% → 1.5% (corta pérdidas más rápido)
- **Drawdown**: Usa equity total (wallet + unrealized PNL) para evitar falsos positivos

### Bug Fixes (V5.11)
- **TP Dinámico**: Corregida lógica invertida que impedía cerrar posiciones en ganancia
- **Error -4130**: Cooldown de 1h por símbolo + filtro ampliado de órdenes TP
- **Scalping Target**: $60 fijo → 5% ROI sobre margen (antes era inalcanzable)

---

## 📦 Dependencias

```txt
python-binance>=1.0.34
google-genai
python-dotenv
requests
yfinance
```

## 🔧 Variables de Entorno

```env
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET=tu_api_secret
BINANCE_TESTNET=False
API_KEY_GEMINI=tu_gemini_api_key
TELEGRAM_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id
MONITOREO_INTERVALO=30
```

## 🚀 Despliegue

`git push` a `main` → Koyeb detecta y hace Redeploy automático (~2 minutos).

## 📞 Soporte

Repositorio: https://github.com/matamoros90/bot_binance_py
