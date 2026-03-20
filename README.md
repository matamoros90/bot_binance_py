# 🤖 Bot Binance Futures V5.10 - High Frequency Scalping + Macro Tradicional (yfinance) + Kelly Criterion

## 📋 Descripción

Bot de trading automatizado para Binance Futures súper agresivo. Utiliza **Gemini 2.5 Flash** para generar señales de temporalidad corta, una **integración con datos macroeconómicos tradicionales (S&P500) vía yfinance**, y un **motor de validación cuantitativa con Criterio de Kelly** para escalar cuentas rápidamente mediante interés compuesto.

Opera 24/7 con:

- Meta de Capital Agresivo: Orientado a Day Trading / Scalping de Alta Frecuencia (15 minutos).
- Inteligencia Mixta: Fusión del Índice Fear & Greed y lectura instantánea del comportamiento macro (Mercado Tradicional/S&P500).
- Gestión de Riesgo Expansiva: Escala tamaños de posición cuando la cuenta entra en racha ganadora usando el Criterio de Kelly (Activado).
- Operaciones en Paralelo: Capacidad para ejecutar hasta 10 operaciones de Scalping en simultáneo escaneando 30 Altcoins.
- Persistencia en SQLite para auditoría y métricas de crecimiento.

---

## 🚀 Estado del Proyecto (Última actualización: 19/03/2026)

| Aspecto         | Estado                                 |
| --------------- | -------------------------------------- |
| **Versión**     | V5.10 (Macro Integration + Hotfix)     |
| **Plataforma**  | Koyeb (Deploy automático desde GitHub) |
| **Modo**        | TESTNET / PRODUCCIÓN                   |
| **Estado**      | 🟢 Operativo y Agresivo                  |

---

## 📁 Estructura del Proyecto

```text
bot_binance_IA/
├── bot_binance.py        # Módulo Único Integrado (Trading, Gemini, Macroeconomía, Riesgo, Indicadores)
├── persistence.py        # SQLite: trades, balances, decisiones, métricas
├── backtesting.py        # Motor de backtesting con datos históricos
├── tests/
│   └── test_formulas.py  # Unit tests
├── requirements.txt
└── README.md
```

---

## ✅ V5.10 — Integración Macro (yfinance) + Scalping Masivo

1. **Macro Tradicional S&P500 🌎**
- El bot extrae el comportamiento del mercado tradicional (S&P500) a través de Yahoo Finance (`yfinance`) de manera más robusta que con scraping.
- Gemini usa esta información como apoyo direccional macroeconómico para entender si el mercado global tiene aversión o apetito por el riesgo.

2. **Temporalidades Rápidas (15m) + Múltiples Posiciones**
- Escaneo incrementado al **TOP 30 de Criptomonedas**.
- Se permiten mantener hasta **10 posiciones simultáneas**.
- Target de Ganancias ultrarrápido: `Take Profit 1.5%` y `Stop Loss 0.8%`. (Matemática de ganar el doble de lo arriesgado).

3. **Interés Compuesto Agresivo (Kelly Criterion)**
- En vez de usar montos fijos limitados, se activa la matemática de Kelly. Si el bot asesta victorias, aumentará incrementalmente la inversión en las próximas operaciones usando las ganancias acumuladas.

4. **Optimización de Memoria (Koyeb)**
- Se unificaron las matemáticas algorítmicas eliminando 450+ líneas de redundancia lógica (`indicators.py` se ha fusionado indirectamente) para reducir consumo en el servidor y acelerar la IA.

---

## ⚙️ Configuración V5.10 (Agresiva pero Simple)

```python
CONFIANZA_MINIMA = 0.50          # 50% - Umbral más bajo para generar más operaciones
ESCUDO_TRABAJO = 1.00            # Se evalúa el 100% del balance para Kelly / monto fijo
APALANCAMIENTO = 3               # Seguro y evasivo contra liquidaciones relámpago
TOP_ACTIVOS = 30                 # Rastrea las 30 criptos más movidas
MAX_POSICIONES = 10              # Hasta 10 trades en simultáneo
TRAILING_SL_PERCENT = 0.015      # Persigue ganancias en 1.5%
MONITOREO_INTERVALO = 30         # Escanea cada 30 segundos

# Gestión del Kelly
KELLY_ACTIVO = True              # Inversión matemática escalable
KELLY_FRACCION = 0.5             # Medio-Kelly para evitar quemar cuentas en días laterales

# V5.10 - Scalping Rápido (15 Minutos)
TEMPORALIDADES = ['15m']         # Temporalidad principal (15m). Con 200 velas ≈ 2 días de historia.
VELAS_CANTIDAD = 200             # De esas velas se envían ~120 más recientes a la IA (≈ 30 h, >1 día)
TP_SL_CONFIG = {"15m": {"tp": 0.015, "sl": 0.008}}
TP_SL_RANGO_CONFIG = {"15m": {"tp": 0.010, "sl": 0.006}}
```

---

## 🧠 Flujo Algorítmico de 15 Minutos

```text
1. Obtener Fear & Greed Index (Miedo/Avaricia a Largo Plazo)
2. Obtener Variación del S&P500 (yfinance) para medir apetito de riesgo Institucional
3. Analizar top 30 pares por volumen en velas de 15 minutos (200 velas).
4. Calcular indicadores técnicos (RSI, Bollinger, MACD, etc) en milisegundos.
5. Gemini dictamina **obligatoriamente** LONG o SHORT integrando el contexto mundial (y su probabilidad matemática de acierto).
6. Si IA detecta ventaja, el Criterio de Kelly dictamina cuántos USD se van a arriesgar.
7. Se establece Inserción (Limit o Market) con TP/SL agresivo de 1.5% - 0.8%.
8. Si hay ganancias, el Trailing SL sigue el precio para maximizarlo.
9. Se repite en bucle 24/7 en las 10 posiciones.
```

---

## 🛠️ Troubleshooting y Bugs Resueltos

### V5.10 Hotfix (19/03/2026) — Errores en TP Dinámico y Logs Spam

Durante el monitoreo en producción de Koyeb se detectaron los siguientes errores que afectaban la estabilidad y calidad de los logs:

1. **`APIError(-4130)`: TP Dinámico duplicado (5x cada 2 minutos)**
   - **Problema**: La función `ajustar_tp_dinamico()` intentaba cancelar el Take Profit existente con un `except: pass`, silenciando errores de cancelación. Si la cancelación fallaba, el bot seguía adelante e intentaba crear un **segundo** TP con `closePosition=True`, lo que Binance rechaza con `-4130` porque solo puede existir uno por dirección.
   - **Solución**: Se eliminó el `except: pass`. Ahora el bot verifica explícitamente si la cancelación fue exitosa (`tp_cancelado_ok`). Si falla, salta ese símbolo y reintenta en el siguiente ciclo (30s). Se agrega `time.sleep(0.4)` para que Binance procese la cancelación antes de crear la nueva orden.

2. **`APIError(-2021)`: TP ya traspasado por el precio de mercado**
   - **Problema**: Para posiciones SHORT muy rentables (>15%), el `nuevo_tp = entry_price * 0.98` podía quedar muy cerca o por encima del `mark_price` actual (ya que el precio bajó agresivamente). Binance rechaza TP que activarían de inmediato.
   - **Solución**: Se agrega un margen de seguridad de ±0.15% sobre el `mark_price` actual (`mark_price * 0.9985` para SHORT, `mark_price * 1.0015` para LONG), garantizando siempre que el TP quede a una distancia operacional segura del precio en vivo.

3. **Spam de log `"Bot pausado por drawdown diario"` cada 30 segundos**
   - **Problema**: Cuando el drawdown diario se activaba, la función `verificar_drawdown_diario()` llamaba a `log()` directamente sin control de frecuencia, imprimiendo el mensaje en cada ciclo de bucle (30 segundos).
   - **Solución**: Reemplazado por `log_throttled("drawdown_pausado_msg", ..., cooldown=300)`, limitando el mensaje a 1 vez cada 5 minutos.

4. **Cierre por Funding Fees: posición quedaba parcialmente abierta (`QUICKUSDT`)**
   - **Problema A**: La función `verificar_funding_vs_pnl()` calculaba el funding con `limit=100` sin filtro de fecha, acumulando todo el historial desde apertura (meses). Esto generaba **falsos positivos**: la comparación `abs(total_funding) > unrealized_pnl` era verdadera incluso cuando los fees recientes eran menores al PNL.
   - **Problema B**: El cierre de mercado no usaba `reduceOnly=True`, lo que podía invertir la posición en vez de cerrarla en casos de discrepancia de cantidad.
   - **Solución**: Se filtra el historial de funding a las **últimas 48 horas** usando `startTime`. Se agrega `reduceOnly=True` a la orden de cierre para garantizar que solo cierra sin posibilidad de inversión accidental.

---

### V5.9 (17/03/2026) — Bugs Resueltos

1. **Bug de Temporalidad Hardcodeada (`ind_1h`)**:
   - **Problema**: El código arrastraba referencias absolutas a `1h` (ej. `ind_1h`, `velas_1h`) en lugar de usar la lista dinámica `TEMPORALIDADES[0]`. Esto provocaba que el bot intentara leer 200 velas de 1 hora mientras las variables internas procesaban los datos de 15 minutos, generando Crash de tipo `name 'ind_1h' is not defined`.
   - **Solución**: Se eliminó todo hardcodeo de `1h`. Ahora toda extracción de variables e indicadores depende de `temp_actual = TEMPORALIDADES[0]` y el sufijo general `ind_actual`.

2. **Bloqueo Constante de la IA (`WAIT` Inexplicable a 70%)**:
   - **Problema**: Gemini estaba programado en el Prompt con la regla *"Asigna confianzas entre el 70% y el 85%"*. Al analizar 15m (un gráfico ruidoso por naturaleza), la IA tenía miedo de emitir señales y decidía `WAIT` constantemente deteniendo todas las órdenes.
   - **Solución**: En la v5.9.1 se ha prohibido explícitamente y eliminado la capacidad de emitir la señal `WAIT` en el prompt a Gemini. Al remover esto y flexibilizar los pre-filtros de salto térmico, el modelo ahora se ve obligado matemáticamente a decidir probabilísticamente si es mejor abrir un `LONG` o un `SHORT` según el momentum.

3. **Error `float division by zero` en Ciclo de Trading (Kelly)**:
   - **Problema**: El bot arrojaba un error matemático interrumpiendo el flujo operativo cuando el "Monto Ganado" caía a $0, provocando que en la fórmula del Criterio de Kelly el ratio `b` intentara dividir por cero.
   - **Solución**: Se integró una validación dura para prevenir el valor $0. Si `b <= 0`, el ratio es obligado a volver al formato estándar de seguridad (`1.5`).

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
BINANCE_TESTNET=True               # Cambiar a False cuando pase de Prueba a Producción
DATA_DIR=/data/trades              # Ruta del volumen persistente en Koyeb (ejemplo)
API_KEY_GEMINI=tu_gemini_api_key
TELEGRAM_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id
CRYPTOPANIC_API_KEY=tu_cryptopanic_key
MONITOREO_INTERVALO=30
```

## 🚀 Despliegue

`git push` a `main` en GitHub -> Koyeb detecta y lanza `Redeploy` para arrancar la recolección automática en 2 minutos.

## 📞 Soporte

Repositorio: https://github.com/matamoros90/bot_binance_py
