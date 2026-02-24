# 🤖 Bot Binance Futures V5.4 - Multi-Timeframe + SQLite + Riesgo Cuantitativo

## 📋 Descripción

Bot de trading automatizado para Binance Futures que usa **Gemini 2.0 Flash** para generar señales y un **motor de validación cuantitativa en código** para ejecutar solo operaciones con riesgo controlado.

Opera 24/7 con:
- análisis multi-timeframe (1h + 4h),
- protección de riesgo (Guardian, drawdown diario, SL/TP),
- persistencia SQLite,
- métricas de rendimiento para evaluar viabilidad.

---

## 🚀 Estado del Proyecto (Última actualización: 24/02/2026)

| Aspecto         | Estado                                 |
| --------------- | -------------------------------------- |
| **Versión**     | V5.4                                   |
| **Plataforma**  | Koyeb (Deploy automático desde GitHub) |
| **Modo**        | TESTNET (Pruebas)                      |
| **Estado**      | 🟢 Operativo                           |
| **Unit Tests**  | ✅ 26/26 passing                       |
| **Backtesting** | ✅ Disponible                          |

---

## 📁 Estructura del Proyecto

```text
bot_binance_IA/
├── bot_binance.py        # Bot principal (trading, Gemini, riesgo, ejecución)
├── indicators.py         # Indicadores técnicos puros (sin Binance SDK)
├── persistence.py        # SQLite: trades, balances, decisiones, métricas
├── backtesting.py        # Motor de backtesting con datos históricos
├── tests/
│   └── test_formulas.py  # 26 unit tests (indicadores + persistencia)
├── requirements.txt
└── README.md
```

---

## ✅ V5.4 (24/02/2026) — Desbloqueo de Ejecución + Filtro Financiero

Mejoras aplicadas para resolver ciclos en `WAIT` y reducir trades de baja calidad.

### 1) Lógica de ejecución: reglas duras → score dinámico

Antes:
- Fear extremo bloqueaba SHORT de forma rígida.
- Tendencia contraria bloqueaba LONG/SHORT de forma absoluta.

Ahora:
- Se usa un **score de ajuste de confianza** con penalizaciones/bonificaciones según contexto.
- Se permite operar en casos válidos con penalización en vez de bloqueo total.

### 2) Régimen de mercado: `TREND` y `RANGE`

Se clasifica el mercado por tendencia/volatilidad y se adapta la operación:
- `TREND`: TP/SL estándar de continuación.
- `RANGE`: TP/SL más cortos + menor tamaño de posición.

### 3) Filtro de Valor Esperado Neto (EV)

Antes de ejecutar una orden, se calcula:

- EV bruto = `p(win)*TP - p(loss)*SL`
- EV neto = `EV bruto - costos (fees + slippage)`

Solo se ejecuta si `EV neto >= umbral mínimo`.

### 4) Stop Loss obligatorio de seguridad

Si una orden abre posición pero falla la creación de SL:
- se reintenta creación de SL,
- si sigue fallando, **se cierra la posición inmediatamente**.

Con esto se evita quedar expuesto sin protección real.

### 5) Correcciones de coherencia diaria

- Cambio de día ahora con `hora_local()` (zona horaria consistente en Koyeb).
- Corrección de cálculo de `pnl_dia` en SQLite (`daily_balances`).

---

## ✅ V5.3 (22/02/2026) — Arquitectura Completa

1. Análisis dual 1h + 4h con 14 indicadores.
2. 200 velas crudas para detección de patrones por IA.
3. Pre-filtro para reducir llamadas a Gemini.
4. Persistencia SQLite de trades, decisiones y balances.
5. Métricas automáticas: Win Rate, Profit Factor, Sharpe, Drawdown, EV.
6. Unit tests y módulo de indicadores desacoplado.

---

## ✅ V5.2 (22/02/2026) — Interés Compuesto + Fix SL

1. Fix de loop por error `-4045` (max stop orders).
2. Precisión SL por `pricePrecision`.
3. Position sizing con interés compuesto.
4. Proyecciones compuestas en resumen semanal.
5. Optimización MACD a O(n).

## ✅ V5.0/V5.1 (18/02/2026) — Reset Inteligente

- Vuelta al prompt base de alto rendimiento en enero.
- Filtro anti-tendencia en código.
- TP/SL estilo enero.
- Pausa por noticias de alto impacto y ventanas macro.

---

## ⚙️ Configuración Actual (V5.4)

```python
CONFIANZA_MINIMA = 0.70
ESCUDO_TRABAJO = 0.80
APALANCAMIENTO = 3
TOP_ACTIVOS = 15
MAX_POSICIONES = 3
TRAILING_SL_PERCENT = 0.015
MONITOREO_INTERVALO = 30
VELAS_CANTIDAD = 200

# Guardian
GUARDIAN_ACTIVO = True
MAX_PERDIDA_PERMITIDA = -0.07

# Funding protection
MAX_DIAS_POSICION = 5
TP_DINAMICO_DIAS = 3

# V5.4 - Régimen + EV
TP_SL_CONFIG = {"1h": {"tp": 0.035, "sl": 0.025}, "4h": {"tp": 0.06, "sl": 0.035}}
TP_SL_RANGO_CONFIG = {"1h": {"tp": 0.02, "sl": 0.015}, "4h": {"tp": 0.03, "sl": 0.02}}
FACTOR_MONTO_RANGO = 0.70
FEE_ROUNDTRIP_EST = 0.0012
SLIPPAGE_EST = 0.0006
EV_MINIMO = 0.0008
```

## 📊 TP/SL por Régimen

| Régimen | 1h TP/SL | 4h TP/SL | Uso |
| ------- | -------- | -------- | ---- |
| TREND   | +3.5% / -2.5% | +6.0% / -3.5% | Continuación de tendencia |
| RANGE   | +2.0% / -1.5% | +3.0% / -2.0% | Mercados laterales/congestión |

---

## 🧠 Flujo de Operación V5.4

```text
1. Obtener Fear & Greed Index
2. Analizar top 15 pares por volumen
3. Descargar velas 1h (200) + 4h (100)
4. Calcular indicadores técnicos completos
5. Pre-filtro de mercado sin señal
6. Gemini propone: LONG / SHORT / WAIT
7. Validación post-IA por score (tendencia, fear, confirmación 4h)
8. Clasificar régimen: TREND o RANGE
9. Calcular EV neto y filtrar operaciones con expectativa baja
10. Ejecutar orden con TP/SL
11. Si SL falla: cierre inmediato de seguridad
12. Monitoreo continuo + guardian + reportes diarios/semanales
```

---

## 🧪 Testing

```bash
# Unit tests
python -m pytest tests/test_formulas.py -v

# Backtesting
python backtesting.py
python backtesting.py --dias 60
python backtesting.py --symbol BTCUSDT --dias 90
```

---

## 📦 Dependencias

```txt
python-binance>=1.0.34
google-genai
python-dotenv
requests
```

## 🔧 Variables de Entorno

```env
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET=tu_api_secret
BINANCE_TESTNET=True
API_KEY_GEMINI=tu_gemini_api_key
TELEGRAM_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id
CRYPTOPANIC_API_KEY=tu_cryptopanic_key
MONITOREO_INTERVALO=30
LOG_DETALLADO=true
```

## 🚀 Despliegue

`git push` a `main` en GitHub -> Koyeb redespliega automáticamente.

## ⚠️ Advertencias

- El bot está en TESTNET por defecto.
- Trading real implica riesgo; no existe estrategia sin pérdidas.
- Usar métricas de riesgo (PF, WR, Drawdown, EV) antes de pasar a mainnet.

## 📞 Soporte

Repositorio: https://github.com/matamoros90/bot_binance_py
