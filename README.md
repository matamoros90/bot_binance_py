# 🤖 Bot Binance Futures V5.7 - Day Trader Institucional + SQLite + Riesgo Cuantitativo

## 📋 Descripción

Bot de trading automatizado para Binance Futures que usa **Gemini 2.0 Flash** para generar señales y un **motor de validación cuantitativa en código** para ejecutar solo operaciones con riesgo controlado.

Opera 24/7 con:

- Meta de Capital Asimétrico: Orientado a ganar entre $30 y $60 USDT diarios con un R:R rígido.
- Protección de riesgo cuantitativo (Guardian iterativo, drawdown diario, SL/TP estricto).
- Persistencia inteligente en SQLite para auditoría.
- Optimización de Payload: Envío exclusivo de la temporalidad 1H a la IA para reducir masivamente el consumo de tokens y maximizar el enfoque intradiario.

---

## 🚀 Estado del Proyecto (Última actualización: 09/03/2026)

| Aspecto         | Estado                                 |
| --------------- | -------------------------------------- |
| **Versión**     | V5.7 (Day Trader)                      |
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

## ✅ V5.6 (26/02/2026) — Correcciones Críticas de SL y PnL

1. **Bugfix: Falsos Positivos de SL (Errores -4045/-4130)**

- Se corrigió el loop infinito donde el bot intentaba recrear Stop Loss de emergencia a pesar de que la posición ya contaba con protección desde la UI de Binance.

2. **Bugfix: Coherencia de Trailing SL**

- Se solucionó un problema grave donde el bot cancelaba los Stop Loss rentables (Trailing SL) por considerarlos "incoherentes" al compararlos contra el precio de entrada en lugar del precio de marca (`mark_price`).

3. **Bugfix: Duplicación de Métricas PnL**

- Se optimizó la limpieza de la memoria temporal de posiciones notificadas, evitando un borrado total accidental (`clear()`) que causaba la reconteo de trades recientes y duplicaba las métricas estadísticas semanales de PnL.

---

## ✅ V5.5 (24/02/2026) — Corrección Anti-WAIT + Fallback Técnico

Mejora enfocada en eliminar bloqueos lógicos que devolvían `WAIT` de forma recurrente.

### Cambios V5.5 aplicados

1. **Prompt sin contradicciones duras**

- Se reemplazaron reglas absolutas (`NUNCA SHORT`, `PROHIBIDO`) por reglas de prioridad con condiciones de confirmación.
- Se mantiene control de riesgo, pero se evita bloqueo automático por conflicto simple.

2. **Fallback técnico cuando Gemini responde WAIT**

- Si IA responde `WAIT`, el bot evalúa un setup técnico de respaldo (EMA + RSI + MACD + posición en rango + volatilidad).
- Si detecta ventaja clara, convierte `WAIT` en `LONG` o `SHORT` con confianza controlada.

3. **Penalización Fear extremo ajustada**

- `Fear < 25` ya no bloquea completamente SHORT; ahora penaliza más suave cuando hay confirmación bajista insuficiente.

4. **Versión operativa visible en logs**

- Logs de arranque y monitoreo pasan a mostrar `V5.5` para verificar despliegue real en Koyeb.

5. **Calibración de umbral de ejecución**

- `CONFIANZA_MINIMA` se ajusta de `70%` a `66%` para reducir rechazos marginales (60-69%) sin desactivar filtros de riesgo.

---

## ✅ Ajuste sencillo de riesgo (25/02/2026) — 5% fijo por operación

Simplificación para que el bot sea más fácil de entender y recalibrar:

1. **Tamaño de posición simple**

- Cada operación usa un **5% fijo del balance operativo actual** (compounding natural).
- La confianza de la IA solo decide **si entrar o no**, no escala agresivamente el tamaño.

2. **Umbral de confianza más flexible**

- `CONFIANZA_MINIMA` pasa de `0.66` a `0.60` para permitir más operaciones en entornos mixtos.

3. **EV como métrica informativa**

- `EV_MINIMO` se pone en `0.0`: el EV se sigue calculando y registrando en logs, pero ya **no bloquea** operaciones por sí solo.
- Los filtros de riesgo principales siguen siendo: TP/SL, Guardian y drawdown diario.

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

1. Análisis enfocado en 1H con 14 indicadores.
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

---

## ⚙️ Configuración Actual (V5.6 + ajuste 26/02/2026)

```python
CONFIANZA_MINIMA = 0.60          # 60% - umbral de ejecución
ESCUDO_TRABAJO = 1.00           # 100% del balance como base de cálculo
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

# V5.7 - Régimen + EV
TP_SL_CONFIG = {"1h": {"tp": 0.024, "sl": 0.012}}
TP_SL_RANGO_CONFIG = {"1h": {"tp": 0.02, "sl": 0.015}}
FACTOR_MONTO_RANGO = 0.70
FEE_ROUNDTRIP_EST = 0.0012
SLIPPAGE_EST = 0.0006
EV_MINIMO = 0.0                  # EV solo informativo (no filtro duro)
```

## 📊 TP/SL por Régimen

| Régimen | 1h TP/SL      | Uso                           |
| ------- | ------------- | ----------------------------- |
| TREND   | +2.4% / -1.2% | Day Trading Institucional     |
| RANGE   | +2.0% / -1.5% | Mercados laterales/congestión |

---

## 🧠 Flujo de Operación V5.7

```text
1. Obtener Fear & Greed Index
2. Analizar top 15 pares por volumen
3. Descargar velas 1h (200)
4. Calcular indicadores técnicos completos
5. Pre-filtro de mercado sin señal
6. Gemini propone: LONG / SHORT / WAIT
7. Validación GPS: Bloqueo absoluto usando EMA 200 en 1H como filtro de tendencia.
8. Si IA devuelve WAIT: evaluar fallback técnico anti-bloqueo
9. Clasificar régimen: TREND o RANGE
10. Calcular EV neto evaluando riesgo $30 vs beneficio $60
11. Ejecutar orden con TP/SL
12. Si SL falla: cierre inmediato de seguridad
13. Monitoreo continuo + Guardián (Target de Scalping Rígido $60) + reportes
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
DATA_DIR=/data/trades          # Ruta del volumen persistente en Koyeb (ejemplo)
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
