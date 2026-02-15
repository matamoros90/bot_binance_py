# 🤖 Bot Binance Futures V5.0 - Reset Inteligente: Prompt Simple + SL Amplio + Anti-Tendencia

## 📋 Descripción

Bot de trading automatizado para Binance Futures que utiliza **Gemini 2.0 Flash** como cerebro de IA para tomar decisiones de trading. Opera 24/7 con estrategia basada en el prompt simple que logró **19.11% ROI en 19 días** (enero 2026), con **protecciones de seguridad** de versiones posteriores y **filtro anti-tendencia** en código.

---

## 🚀 Estado del Proyecto (Última actualización: 14/02/2026)

| Aspecto        | Estado                                 |
| -------------- | -------------------------------------- |
| **Versión**    | V5.0 Reset Inteligente                 |
| **Plataforma** | Koyeb (Deploy automático desde GitHub) |
| **Modo**       | TESTNET (Pruebas)                      |
| **Estado**     | 🟢 Operativo                           |

### 💰 Rendimiento Acumulado (TESTNET)

> [!IMPORTANT]
> **V3.7**: Nuevo inicio desde $4,524.29 después de análisis de pérdidas y fixes críticos.

| Período               | Balance Inicial | Balance Actual | Ganancia | ROI     |
| --------------------- | --------------- | -------------- | -------- | ------- |
| 04/01 - 09/02         | $5,293.49       | $4,524.29      | -$769.20 | -14.53% |
| **NUEVO INICIO V3.7** |                 |                |          |         |
| 09/02 - actual        | **$4,524.29**   | **$4,524.29**  | $0.00    | 0.00%   |

> [!NOTE]
> V3.7 incluye fixes críticos para evitar pérdidas por SL demasiado cercanos y errores de API.

---

## 🎯 Roadmap V3.0 - Optimización para ROI 100% en 4 Meses

### Objetivos V3.0

| Métrica            | Actual            | Objetivo V3.0                   |
| ------------------ | ----------------- | ------------------------------- |
| **ROI en 4 meses** | ~76% (proyectado) | **100%**                        |
| **ROI diario**     | ~1.0%             | **≥1.0%** (mantener o superar)  |
| **Win-Rate**       | ~55% (estimado)   | **≥60%**                        |
| **Risk-Reward**    | 1:1.5 (estimado)  | **≥1:2.5**                      |
| **Prioridad**      | Buscar ganancias  | **Evitar pérdidas > Ganancias** |

### Indicadores Técnicos a Implementar

| Indicador             | Para Qué Sirve                    | Impacto en ROI                |
| --------------------- | --------------------------------- | ----------------------------- |
| RSI(14)               | Detectar sobrecompra/sobreventa   | +15-20% win-rate              |
| EMA 20/50/200         | Confirmar tendencia               | Evita trades contra-tendencia |
| MACD                  | Momentum y cruces                 | Mejores entradas              |
| Bandas Bollinger      | Volatilidad + extremos            | Entradas en retrocesos        |
| ATR                   | Volatilidad real para SL dinámico | SL más inteligentes           |
| Volumen               | Confirmar movimientos             | Evita falsas rupturas         |
| Soportes/Resistencias | Zonas clave                       | Mejor timing                  |

### Gestión de Riesgo Avanzada (Planificado)

| Feature                   | Descripción                | Beneficio          |
| ------------------------- | -------------------------- | ------------------ |
| Position Sizing por Kelly | % óptimo según win-rate    | Maximiza compuesto |
| Drawdown máximo diario    | -5% máximo, pausar bot     | Protege capital    |
| Correlación de posiciones | No abrir 3 correlacionadas | Diversifica riesgo |
| Win-rate tracking         | Si < 50%, reducir riesgo   | Auto-ajuste        |

> [!IMPORTANT]
> V3.0 está en fase de planificación. Las mejoras se implementarán de forma gradual.

---

### V5.0 (14/02/2026) - Reset Inteligente: Prompt Simple + SL Amplio + Anti-Tendencia

> [!IMPORTANT]
> **Análisis forense reveló que las "mejoras" V3.0-V4.0 causaron las pérdidas.** V5.0 vuelve a la fórmula de enero (19% ROI) con protecciones mínimas.

**Problema identificado:** V2.0 (enero) logró 1% diario con un prompt de 25 líneas y 5 datos. V3.0+ lo expandió a 95 líneas con 20+ indicadores y reglas contradictorias. Gemini tomaba peores decisiones con más datos.

- 🧠 **Prompt Simple V5.0**: Vuelve al estilo de enero — solo 7 datos (precio, rango, volatilidad, F&G, tendencia EMA, RSI)
- ⛔ **Filosofía Anti-Tendencia**: De "SER OPORTUNISTA" → "NUNCA operar contra la tendencia EMA"
- 🎯 **TP/SL Realistas**: 1h: +3.5%/-2.5% (SL amplio como enero, TP alcanzable)
- 📉 **Solo 1h y 4h**: Eliminadas temporalidades 15m y 30m (demasiado ruido para x3)
- 🔧 **ATR SL Desactivado**: Volver a SL fijo predecible (ATR causaba inconsistencia)
- 📊 **Kelly Desactivado**: Con historial negativo causaba espiral descendente
- 🛡️ **SL Tradicional**: `STOP_MARKET` como método principal (Algo Order como fallback)
- ⛔ **Filtro Anti-Tendencia en Código**: Rechaza SHORT en alcista y LONG en bajista automáticamente
- ✅ **Conservado**: Guardian System, Trailing SL, Anti-SHORT Extreme Fear, Funding Protection

> [!CAUTION]
> **7 causas raíz de pérdidas identificadas y corregidas.** Fix crítico: TP se destruían al actualizar trailing SL.

- ⛔ **Fix TP Preservation**: `cancelar_ordenes_sl()` ya NO cancela `TAKE_PROFIT_MARKET` (antes los destruía)
- 🛡️ **SL Emergencia -3%**: Reducido de -7% → **-3%** (con x3 = -9% real vs -21% anterior). Guardian mantiene -7% como red final
- 👁️ **Guardian Full Logging**: Ahora logea **TODAS** las posiciones activas (antes solo >5% PNL)
- 📈 **Trailing SL Mejorado**: Se activa con ganancia > 0.5% (antes requería SL > entry price, casi nunca ocurría)
- 📊 **Kelly Semanal**: Usa `stats_semanales` en vez de `stats_diarias` (mín 3 trades, antes 5/día)
- 🎯 **TP/SL Optimizado**: Mejores ratios R:R para todas las temporalidades:
  - 15m: +1.8%/-0.7% (R:R 2.57) | 30m: +3%/-1% (R:R 3.0) | 1h: +5%/-1.8% (R:R 2.78) | 4h: +7%/-2.5% (R:R 2.8)
- 🔄 **SL Fallback Tradicional**: Si Algo Order falla, intenta `STOP_MARKET` tradicional antes de rendirse

### V3.9 (10/02/2026) - SL Coherence + TTL Cache + Position Logging

> [!IMPORTANT]
> **Corrección crítica**: Posiciones podían quedar sin Stop Loss válido indefinidamente.

- ⛔ **Fix `except: pass`**: `ejecutar_orden()` ya no silencia errores de SL. Ahora logea y reintenta con `mark_price`
- 🔄 **SL Cache con TTL**: `_sl_creados` (set permanente) → `_sl_verificados` (dict con TTL 5 min). Re-verifica periódicamente
- 🛡️ **SL Coherencia**: Valida que SL esté del lado correcto (debajo para LONG, arriba para SHORT). Cancela y recrea si es incoherente
- 🔧 **`crear_orden_sl()`**: Retorna tupla `(success, already_protected)` para diferenciar "-4045" de errores reales
- 📋 **Resumen Posiciones**: Nueva función `log_resumen_posiciones()` muestra PNL y estado SL cada ~5 min
- ⚡ **Main Loop Optimizado**: No entra a `ejecutar_trading()` si posiciones están llenas (ahorra 4 llamadas API/ciclo)

### V3.8 (09/02/2026) - Fix SL Emergency + Post-IA Validation + Optimized ROI

> [!IMPORTANT]
> **Corrección crítica**: Eliminado error -2021 que impedía crear SL de emergencia.

- 🔧 **Fix SL Emergencia**: Ahora usa `mark_price` en lugar de `entry_price` (evita -2021)
- ⛔ **Validación Post-IA**: Bloquea SHORT automáticamente si Fear & Greed < 25
- 🛡️ **JSON Safety**: Validación robusta, no crashea si IA devuelve JSON mal formado
- 🎯 **Coherencia RSI**: Reduce confianza 30% si IA dice LONG con RSI > 75 o SHORT con RSI < 25
- 🚨 **Guardian Optimizado**: Reducido de -10% → **-7%** para cortar pérdidas más rápido
- 📈 **TP/SL Optimizado**: TP más rápido, SL más tight para mejor ratio riesgo/recompensa
  - 15m: +1.5%/-0.8% | 30m: +2.5%/-1.2% | 1h: +4%/-2% | 4h: +6%/-3%

### V3.7 (09/02/2026) - Fix ATR SL Mínimo + Retry API + Optimización

- 🔧 **Fix ATR SL Mínimo**: SL mínimo de 1.5% aunque ATR sea muy bajo (evita SL a 0.15%)
- ⚡ **Retry API Gemini**: Reintentos con backoff exponencial para errores 429
- 📉 **Drawdown Reducido**: De -8% → **-5%** para mayor protección
- 🎯 **Confianza Aumentada**: De 65% → **70%** para mayor selectividad
- 💰 **Nuevo Balance Inicial**: $4,524.29 (reinicio después de análisis de pérdidas)
- 📊 **ATR Multiplicador**: Aumentado de 1.5x → **2.0x** para SL más conservador

### V3.6 (05/02/2026) - Drawdown Ajustado + Métrica de Balance Corregida

- 📈 **Drawdown Máximo**: Aumentado de -3% → **-8%** temporalmente
- 🔓 **Problema resuelto**: Bot atrapado en loop por pérdidas no realizadas
- 📊 **Balance Metric**: Cambiado de `availableBalance` → `walletBalance` para ROI preciso
- 💰 **Nuevo Balance Inicial**: $7,497.33 (wallet balance, no Avbl)
- 🎯 **Próxima revisión**: Analizar mañana y ajustar drawdown si es necesario

### V3.5 (03/02/2026) - Monitoreo Rápido + Anti-SHORT Extreme Fear

- ⚡ **Monitoreo 30s**: Reducido de 60s → **30s** (reacción 2x más rápida)
- 🛡️ **Anti-SHORT Extreme Fear**: **PROHIBIDO** hacer SHORT cuando Fear & Greed < 20
- 📈 **Lógica mejorada**: En Extreme Fear solo LONG o WAIT (nunca SHORT)
- 🎯 **Objetivo**: Evitar ir en contra del rebote del mercado (Short Squeeze)

### V3.4 (01/02/2026) - Fix Críticos de Riesgo

- 🔴 **Fix Drawdown**: Verificación ANTES de cada orden (no solo al inicio del ciclo)
- 🔧 **Fix SL Detection**: Búsqueda ampliada + tracking en memoria para evitar spam de logs
- 📉 **MAX_POSICIONES**: Reducido de 5 → **3** (menor exposición simultánea)
- 🎯 **Objetivo**: Prevenir pérdidas masivas por múltiples órdenes simultáneas

### V3.3 (01/02/2026) - Trading Oportunista

- ⚡ **Cambio Mayor**: Prompt de IA completamente rediseñado
- 🟢 **LONG agresivo** cuando Fear & Greed < 20 (Extreme Fear)
- 🔴 **SHORT agresivo** cuando EMA bajista + MACD negativo
- ✅ **Menos WAIT**: Solo espera si volumen < 0.5x o RSI neutral
- 🎯 **Objetivo**: Capturar movimientos alcistas Y bajistas

### V3.2 (01/02/2026) - IA Menos Conservadora

- 🎯 **Cambio**: `CONFIANZA_MINIMA` reducida de 70% → **65%**
- 📈 **Objetivo**: Permitir más operaciones durante Extreme Fear
- 🛡️ **Riesgo**: Bajo - misma lógica de IA, solo umbral más permisivo

### V3.1.3 (01/02/2026) - Fix Dual-Endpoint SL Detection

- 🔧 **Bug Fix**: Verificación de SL ahora consulta AMBOS endpoints (Algo + Tradicional)
- 🔇 **Mejora**: Error `-4045` (max stop orders) se silencia porque indica protección activa
- 📝 **Contexto**: Testnet devuelve órdenes condicionales en endpoints diferentes
- ✅ **Resultado**: Eliminados logs repetitivos "SIN orden SL" y errores `-4045`

### V3.1.2 (31/01/2026) - Fix SL Detection for Algo Orders

- 🔧 **Bug Fix**: Detección de SL ahora usa `futures_get_open_algo_orders()`
- 📝 **Problema**: Endpoint antiguo no mostraba Algo Orders, causando SL duplicados
- ✅ **Resultado**: Ya no se crean SL repetidamente para la misma posición

### V3.1.1 (31/01/2026) - Hotfix triggerPrice

- 🔧 **Bug Fix**: Cambiado parámetro `stopPrice` → `triggerPrice`
- 📝 **Error resuelto**: `-1102` (Mandatory parameter 'triggerprice' was not sent)

### V3.1 (31/01/2026) - Fix Stop Loss API (Algo Order)

- ✅ **Migración Algo Order API**: STOP_MARKET ahora usa `futures_create_algo_order()`
- ✅ **python-binance actualizado**: v1.0.19 → v1.0.34 (soporte Algo Orders)
- 🔧 **Bug Fix**: Resuelto error `-4120` que impedía crear órdenes Stop Loss
- 📝 **Contexto**: Binance migró órdenes condicionales a Algo Order API desde Dic 2025

### V3.0 (24/01/2026) - Resumen Semanal + ROI Objetivo 100%

- ✅ **Resumen Semanal**: 1 solo mensaje cada viernes a las 18:00
- ✅ **ROI Total Visible**: Muestra ganancia desde balance inicial ($5,293.49)
- ✅ **Sin Notificaciones Individuales**: Eliminadas todas las alertas por trade
- ✅ **Indicadores Técnicos V3.0**: RSI, EMA 20/50/200, MACD, Bollinger, ATR, Volumen, S/R
- ✅ **Prompt IA Mejorado**: 13 reglas de trading + todos los indicadores
- ✅ **Drawdown Máximo Diario**: Pausa bot si pérdida > -3% en un día
- ✅ **ATR Stop Loss Dinámico**: SL = 1.5x ATR (se adapta a volatilidad)
- ✅ **Kelly Criterion**: Position sizing óptimo basado en win-rate (50% Kelly)
- ✅ **Max Posiciones 5**: Aumentado de 3 a 5 para mayor diversificación
- 🎯 **Objetivo V3.0**: ROI 100% en 4 meses (≥1% diario)

### V2.8 (19/01/2026) - Resumen Diario + Optimización

- ✅ **Resumen Diario**: 1 solo mensaje al día con PNL neto y estadísticas.
- ✅ **Optimización CPU**: Intervalos de monitoreo a 60s (ahorro 50% recursos).
- ✅ **Logs Silenciosos**: Reducción drástica de logs en consola y Telegram.
- ✅ **Estadísticas**: Tracking intradía de trades ganados/perdidos.

### V2.7 (19/01/2026) - Guardian System

- ✅ **Sistema Guardián**: Monitorea TODAS las posiciones (ganancia y pérdida)
- ✅ **Cierre de emergencia**: Cierra automáticamente si pérdida > 10%
- ✅ **Verificación SL**: Detecta y crea órdenes SL faltantes
- ✅ **Logs mejorados**: Eliminados errores silenciosos (`except: pass`)
- 🎯 **Objetivo**: Evitar pérdidas extremas como TOKENUSDT (-75%)

### V2.6 (18/01/2026) - New GenAI SDK

- ✅ **Migración a `google-genai`**: Eliminado el paquete deprecado `google-generativeai`
- ✅ **Nuevo SDK oficial**: Soporte activo de Google, corrección de bugs y nuevas funciones
- ✅ **Sin warnings de deprecación**: Logs limpios sin advertencias

### V2.5 (18/01/2026) - Funding Fees Protection

- ✅ **Cierre por tiempo máximo**: Posiciones se cierran automáticamente después de 5 días
- ✅ **Funding vs PNL**: Cierra posición si los funding fees superan las ganancias
- ✅ **TP Dinámico**: Reduce Take Profit después de 3 días para asegurar ganancias
- 🎯 **Logro destacado**: FXSUSDT cerrado por tiempo con +$227.92 de ganancia

### V2.0 (04/01/2026) - Trailing SL + Fear & Greed

- ✅ Trailing Stop Loss 1.5%
- ✅ Integración Fear & Greed Index
- ✅ Temporalidades dinámicas (15m, 30m, 1h, 4h)
- ✅ 3 posiciones simultáneas máximo

---

## ⚙️ Configuración Actual (V5.0)

```python
# Trading
CONFIANZA_MINIMA = 0.70      # 70% mínimo para operar
ESCUDO_TRABAJO = 0.80        # 80% del balance para trading
ESCUDO_SEGURO = 0.20         # 20% protegido
APALANCAMIENTO = 3           # x3 conservador
TOP_ACTIVOS = 15             # Analiza top 15 por volumen
MAX_POSICIONES = 3           # Máximo 3 posiciones simultáneas
TRAILING_SL_PERCENT = 0.015  # 1.5% trailing
MONITOREO_INTERVALO = 30     # 30 segundos

# Guardian System
GUARDIAN_ACTIVO = True       # Protección de emergencia
MAX_PERDIDA_PERMITIDA = -0.07  # -7% cierre obligatorio

# V5.0: Desactivados (causaban más daño que beneficio)
ATR_SL_ACTIVO = False        # SL fijo predecible, no dinámico
KELLY_ACTIVO = False         # Position sizing simple, no Kelly

# Funding Fees Protection (V2.5+)
FUNDING_PROTECTION = True    # Activar protección
MAX_DIAS_POSICION = 5        # Cerrar después de 5 días
```

## 📊 TP/SL por Temporalidad (V5.0 — Estilo Enero)

| Temporalidad | Take Profit | Stop Loss | R:R   | Con x3 Apalancamiento |
| ------------ | ----------- | --------- | ----- | --------------------- |
| 1h           | +3.5%       | -2.5%     | 1.4:1 | +10.5% / -7.5%        |
| 4h           | +6.0%       | -3.5%     | 1.7:1 | +18.0% / -10.5%       |

## 🎭 Fear & Greed Index

- **0-25 (Extreme Fear)**: Preferir LONGs en soportes
- **26-45 (Fear)**: Considerar LONGs
- **46-55 (Neutral)**: Análisis técnico puro
- **56-75 (Greed)**: Precaución con LONGs
- **76-100 (Extreme Greed)**: Preferir SHORTs o WAIT

---

## 📦 Dependencias

```txt
python-binance==1.0.19
google-genai              # NUEVO SDK (antes: google-generativeai)
python-dotenv
requests
```

> [!IMPORTANT]
> El paquete `google-generativeai` está **DEPRECADO** desde Noviembre 2025.
> Se migró al nuevo paquete oficial `google-genai` en V2.6.

---

## 🔧 Variables de Entorno Requeridas

```env
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET=tu_api_secret
BINANCE_TESTNET=True  # True para testnet, False para producción
API_KEY_GEMINI=tu_gemini_api_key
TELEGRAM_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id
```

## 🚀 Despliegue

El bot está configurado para desplegarse en **Koyeb**:

1. Push a GitHub → Koyeb redespliega automáticamente
2. Health check en puerto 8000
3. Logs visibles en dashboard de Koyeb

## 📱 Notificaciones Telegram

El bot envía un **resumen semanal** cada viernes a las 18:00 con:

- ROI total del proyecto desde inicio
- Balance actual vs balance inicial
- Trades ganados/perdidos de la semana
- Cierres del Guardian de emergencia

## 🧠 Flujo de Operación

```
1. Obtener Fear & Greed Index
2. Analizar top 15 pares por volumen
3. Calcular indicadores (RSI, EMA)
4. Prompt simple → Gemini decide: LONG, SHORT o WAIT
5. Filtro anti-tendencia en código (rechaza trades contra EMA)
6. Si confianza >= 70%, guardar oportunidad
7. Ordenar por confianza, ejecutar TOP 3
8. Monitorear Trailing SL cada 30 segundos
9. Guardian verifica pérdidas > -7%
10. Repetir cada 2 minutos
```

---

## 📝 Notas Técnicas

### Sobre la migración del SDK (V2.6)

**Antes (deprecado):**

```python
import google.generativeai as genai
genai.configure(api_key="...")
modelo = genai.GenerativeModel('gemini-2.0-flash')
respuesta = modelo.generate_content(prompt).text
```

**Ahora (nuevo):**

```python
from google import genai
client = genai.Client(api_key="...")
response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents=prompt
)
respuesta = response.text
```

### Ventajas del nuevo SDK:

- ✅ Soporte activo de Google
- ✅ Corrección de bugs constante
- ✅ Acceso a nuevos modelos de Gemini
- ✅ Sin warnings de deprecación
- ✅ API más limpia y centralizada

---

## ⚠️ Advertencias

- Este bot opera en TESTNET por defecto
- Cambiar `BINANCE_TESTNET=False` para producción real
- El trading conlleva riesgos - usa solo capital que puedas perder

## 📞 Soporte

Repositorio: https://github.com/matamoros90/bot_binance_py
