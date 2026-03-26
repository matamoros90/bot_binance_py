# 🤖 Bot Binance Futures V5.14 — Scalping Técnico Puro + Fixed Risk

Bot de trading automatizado para Binance Futures. Evolucionado a un sistema de **Scalping Técnico Puro** apoyado en **Gemini 2.5 Flash** para señales en 15 minutos, prescindiendo del ruido macroeconómico para enfocarse totalmente en **Acción del Precio (Price Action)**.

**Balance Actual:** ~$1,780 USDT (Restauración en curso)

Opera 24/7 con:
- 🎯 Scalping Intradía Puro en temporalidad 15m (RSI, EMAs, MACD)
- 🧠 IA Aislada (Vacuum Trading) libre de sesgos macro
- 📈 Fixed Risk Management (5% por operación) para consistencia matemática
- 🛡️ Break-even estricto + Trailing SL al 0.5% + Guardian automático
- 💾 Persistencia SQLite para métricas y auditoría

---

## 🚀 Estado del Proyecto (25/03/2026)

| Aspecto         | Estado                                 |
| --------------- | -------------------------------------- |
| **Versión**     | V5.14 (Pure Technical Scalper)         |
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

# Scalping Técnico y Riesgo Fijo
KELLY_ACTIVO = False               # Se reemplaza por un Fixed Risk del 5.0%
SCALPING_ROI_TARGET = 0.065      # 6.5% ROI sobre margen para no pisar el Limit TP

# Scalping 15 Minutos
TEMPORALIDADES = ['15m']
TP_SL_CONFIG      = {"15m": {"tp": 0.020, "sl": 0.008}}  # R:R 2.5:1
TP_SL_RANGO_CONFIG = {"15m": {"tp": 0.015, "sl": 0.006}}  # Modo lateral
```

---

## 🧠 Flujo Operativo

```text
1. Analizar top 30 pares por volumen (velas 15m crudas)
2. Calcular indicadores puros (RSI, Bollinger, MACD, EMA, ATR)
3. Gemini decide LONG/SHORT con confianza técnica ≥ 65% o Fallback estricto
4. Risk Management asigna tamaño fijo de 5% de cuenta (Fixed Risk)
5. Ejecutar con TP +2.0% / SL original -0.8%
6. Break-even SL amarrado al alcanzar +1.0% de ganancia (+0.15% entry)
7. Trailing SL persigue ganancias a 0.5% por debajo del máximo real
8. Scalping exit automático al +6.5% ROI sobre margen (solo si Limit TP falla)
9. Repetir 24/7
```

---

## 🛡️ Sistema de Protección de Capital

| Protección | Descripción |
|-----------|-------------|
| **Break-even SL** | Al +1.0%, SL se muda a entry +0.15% blindando el trade |
| **Trailing SL** | Activo tras romper +1.5%, se adhiere a 0.5% del pico |
| **SL de Emergencia** | -0.8% (SDK original) o Stop Loss manual IA |
| **Guardian** | Cierre automático al -10% + Limpieza estricta de caché de API |
| **Drawdown Diario** | Pausa trading si equity cae -3% en el día |
| **Cierre por Tiempo** | Máx 5 días por posición |
| **Funding vs PNL** | Cierra si fees > ganancias (últimas 48h) |
| **TP Dinámico** | Ajusta TP después de 1 día en ganancia |
| **Scalping Motor** | Cierra al 6.5% ROI sobre margen |

---

## ✅ Changelog V5.13 & V5.14 (25/03/2026 - Root-Cause Fixes)

Tras sufrir una alta tasa de regresión, se realizó una auditoría estructural revelando colisiones matemáticas algorítmicas que ahora están parchadas:

### V5.14: Transformación a Analista Técnico Puro
- **Amputación Macro (Fear&Greed / WorldMonitor)**: Eliminados por inyectar "alucinaciones de ruido" a la IA para trades cortos de 15m.
- **Fixed Risk 5%**: Pausado el Kelly Criterion. Ahora opera un sólido 5% garantizado por ronda mientras reconstruimos el balance matemático a punta de interés compuesto diario (1% target).
- **Prompt Isolation**: Gemini ahora opera "en vacío", ciego a pánicos macro, enfocado solo en el Price Action para comprar y vender con crueldad probabilística.

### V5.13: Restauración Lógica e Infraestructura
- **Cache API Ghosting (-4509 Bug)**: Purgado automático de `_positions_cache` tras cierres de Guardián, eliminando el bombardeo inútil de órdenes Trailing SL a saldos fantasma.
- **Break-Even y Trailing Matemáticamente Blindados**: Las distancias no pueden volverse negativas, amarrando el BE en +0.15% firme tan pronto el profit local escala 1.0%, y acortando el Trailing a un milimétrico 0.5% del cenit tras superar +1.5%.
- **Fallback Overtrading Asesinado**: Las operaciones de socorro automático ahora urgen divergencias RSI superlativas (<35 y >65), cancelando el operar en las aguas calmas del bloque lateral de 38 a 62.
- **Scalping Target**: Subido de 5.0% a 6.5% para impedir el ahogamiento o devoración del Maker Take-Profit original de la IA (2.0% crudo en activo = 6.0% ROI).

---

## 📜 Historial Anterior (V5.12)

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
