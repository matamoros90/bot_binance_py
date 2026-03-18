# 🤖 Bot Binance Futures V5.9 - High Frequency Scalping + World Monitor + Kelly Criterion

## 📋 Descripción

Bot de trading automatizado para Binance Futures súper agresivo. Utiliza **Gemini 2.0 Flash** para generar señales de temporalidad corta, un **algoritmo de scraping de Sentimiento Global en World Monitor**, y un **motor de validación cuantitativa con Criterio de Kelly** para escalar cuentas rápidamente mediante interés compuesto.

Opera 24/7 con:

- Meta de Capital Agresivo: Orientado a Day Trading / Scalping de Alta Frecuencia (15 minutos).
- Inteligencia Mixta: Fusión del Índice Fear & Greed y lectura instantánea del sentimiento Institucional (World-Monitor).
- Gestión de Riesgo Expansiva: Escala tamaños de posición cuando la cuenta entra en racha ganadora usando el Criterio de Kelly (Activado).
- Operaciones en Paralelo: Capacidad para ejecutar hasta 10 operaciones de Scalping en simultáneo escaneando 30 Altcoins.
- Persistencia en SQLite para auditoría y métricas de crecimiento.

---

## 🚀 Estado del Proyecto (Última actualización: 17/03/2026)

| Aspecto         | Estado                                 |
| --------------- | -------------------------------------- |
| **Versión**     | V5.9.1 (Forced AI Scalping)            |
| **Plataforma**  | Koyeb (Deploy automático desde GitHub) |
| **Modo**        | TESTNET / PRODUCCIÓN                   |
| **Estado**      | 🟢 Operativo y Agresivo                  |

---

## 📁 Estructura del Proyecto

```text
bot_binance_IA/
├── bot_binance.py        # Módulo Único Integrado (Trading, Gemini, World Monitor, Riesgo, Indicadores)
├── persistence.py        # SQLite: trades, balances, decisiones, métricas
├── backtesting.py        # Motor de backtesting con datos históricos
├── tests/
│   └── test_formulas.py  # Unit tests
├── requirements.txt
└── README.md
```

---

## ✅ V5.9 — Integración World Monitor + Scalping Masivo

1. **Scraper World Monitor 🌎**
- El bot scrapea la página en tiempo real y detecta palabras clave (surge, buy, bullish vs crash, sell, bearish) para perfilar el sentimiento macro-institucional.
- Gemini usa esta información como último validador para ejecutar operaciones intradiarias con apenas un 60% de certeza, apostando a las reacciones instantáneas del mercado.

2. **Temporalidades Rápidas (15m) + Múltiples Posiciones**
- Escaneo incrementado al **TOP 30 de Criptomonedas**.
- Se permiten mantener hasta **10 posiciones simultáneas**.
- Target de Ganancias ultrarrápido: `Take Profit 1.5%` y `Stop Loss 0.8%`. (Matemática de ganar el doble de lo arriesgado).

3. **Interés Compuesto Agresivo (Kelly Criterion)**
- En vez de usar montos fijos limitados, se activa la matemática de Kelly. Si el bot asesta victorias, aumentará incrementalmente la inversión en las próximas operaciones usando las ganancias acumuladas.

4. **Optimización de Memoria (Koyeb)**
- Se unificaron las matemáticas algorítmicas eliminando 450+ líneas de redundancia lógica (`indicators.py` se ha fusionado indirectamente) para reducir consumo en el servidor y acelerar la IA.

---

## ⚙️ Configuración V5.9 (Agresiva pero Simple)

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

# V5.9 - Scalping Rápido (15 Minutos)
TEMPORALIDADES = ['15m']         # Temporalidad principal (15m). Con 200 velas ≈ 2 días de historia.
VELAS_CANTIDAD = 200             # De esas velas se envían ~120 más recientes a la IA (≈ 30 h, >1 día)
TP_SL_CONFIG = {"15m": {"tp": 0.015, "sl": 0.008}}
TP_SL_RANGO_CONFIG = {"15m": {"tp": 0.010, "sl": 0.006}}
```

---

## 🧠 Flujo Algorítmico de 15 Minutos

```text
1. Obtener Fear & Greed Index (Miedo/Avaricia a Largo Plazo)
2. Scrapear World-Monitor (Sentimiento Institucional de Hoy)
3. Analizar top 30 pares por volumen en velas de 15 minutos (200 velas).
4. Calcular indicadores técnicos (RSI, Bollinger, MACD, etc) en milisegundos.
5. Gemini dictamina **obligatoriamente** LONG o SHORT integrando el contexto mundial (y su probabilidad matemática de acierto).
6. Si IA detecta ventaja, el Criterio de Kelly dictamina cuántos USD se van a arriesgar.
7. Se establece Inserción (Limit o Market) con TP/SL agresivo de 1.5% - 0.8%.
8. Si hay ganancias, el Trailing SL sigue el precio para maximizarlo.
9. Se repite en bucle 24/7 en las 10 posiciones.
```

---

## 🛠️ Troubleshooting y Bugs Resueltos (V5.9)

Durante la transición al modelo de Scalping de Alta Frecuencia (15m), se documentan los siguientes problemas críticos resueltos para referencia futura:

1. **Bug de Temporalidad Hardcodeada (`ind_1h`)**: 
   - **Problema**: El código arrastraba referencias absolutas a `1h` (ej. `ind_1h`, `velas_1h`) en lugar de usar la lista dinámica `TEMPORALIDADES[0]`. Esto provocaba que el bot intentara leer 200 velas de 1 hora mientras las variables internas procesaban los datos de 15 minutos, generando Crash de tipo `name 'ind_1h' is not defined`.
   - **Solución**: Se eliminó todo hardcodeo de `1h`. Ahora toda extracción de variables e indicadores depende de `temp_actual = TEMPORALIDADES[0]` y el sufijo general `ind_actual`.

2. **Bloqueo Constante de la IA (`WAIT` Inexplicable a 70%)**:
   - **Problema**: Gemini estaba programado en el Prompt con la regla *"Asigna confianzas entre el 70% y el 85%"*. Al analizar 15m (un gráfico ruidoso por naturaleza), la IA tenía miedo de emitir señales y decidía `WAIT` constantemente deteniendo todas las órdenes.
   - **Solución**: En la v5.9.1 se ha prohibido explícitamente y eliminado la capacidad de emitir la señal `WAIT` en el prompt a Gemini. Al remover esto y flexibilizar los pre-filtros de salto térmico, el modelo ahora se ve obligado matemáticamente a decidir probabilísticamente si es mejor abrir un `LONG` o un `SHORT` según el momentum, y el threshold de confianza se ha mantenido lo suficientemente bajo como para atrapar esas decisiones intradiarias de forma ágil y ejecutarlas.

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
