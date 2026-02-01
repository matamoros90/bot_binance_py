# 🤖 Bot Binance Futures V3.0 - Resumen Semanal + Optimización + IA

## 📋 Descripción

Bot de trading automatizado para Binance Futures que utiliza **Gemini 2.0 Flash** como cerebro de IA para tomar decisiones de trading. Opera 24/7 con estrategia de swing trading conservador, **protección automática contra funding fees**, y **resumen semanal por Telegram cada viernes a las 18:00**.

---

## 🚀 Estado del Proyecto (Última actualización: 23/01/2026)

| Aspecto        | Estado                                 |
| -------------- | -------------------------------------- |
| **Versión**    | V3.1.2                                 |
| **Plataforma** | Koyeb (Deploy automático desde GitHub) |
| **Modo**       | TESTNET (Pruebas)                      |
| **Estado**     | 🟢 Operativo                           |

### 💰 Rendimiento Acumulado (TESTNET)

| Período       | Balance Inicial | Balance Actual | Ganancia       | ROI         |
| ------------- | --------------- | -------------- | -------------- | ----------- |
| 04/01 - 07/01 | $5,293.49       | $5,438.59      | +$145.10       | +2.74%      |
| 07/01 - 18/01 | $5,438.59       | $6,576.60      | +$1,138.01     | +20.92%     |
| 18/01 - 23/01 | $6,576.60       | $6,307.20      | -$269.40       | -4.10%      |
| **TOTAL**     | $5,293.49       | **$6,307.20**  | **+$1,013.71** | **+19.15%** |

> [!NOTE]
> Estos resultados son en TESTNET. El rendimiento real puede variar.

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
| Drawdown máximo diario    | -3% máximo, pausar bot     | Protege capital    |
| Correlación de posiciones | No abrir 3 correlacionadas | Diversifica riesgo |
| Win-rate tracking         | Si < 50%, reducir riesgo   | Auto-ajuste        |

> [!IMPORTANT]
> V3.0 está en fase de planificación. Las mejoras se implementarán de forma gradual.

---

## 🆕 Historial de Versiones

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

## ⚙️ Configuración Actual

```python
# Trading
CONFIANZA_MINIMA = 0.70      # 70% mínimo para operar
ESCUDO_TRABAJO = 0.80        # 80% del balance para trading
ESCUDO_SEGURO = 0.20         # 20% protegido
APALANCAMIENTO = 3           # x3 conservador
TOP_ACTIVOS = 15             # Analiza top 15 por volumen
MAX_POSICIONES = 5           # Máximo 5 posiciones (V3.0: 24/01 - diversificación)
TRAILING_SL_PERCENT = 0.015  # 1.5% trailing
MONITOREO_INTERVALO = 60     # 60 segundos (Optimizado V2.8)

# Guardian System V2.7
GUARDIAN_ACTIVO = True       # Protección de emergencia
MAX_PERDIDA_PERMITIDA = -0.10  # -10% cierre obligatorio

# Funding Fees Protection (V2.5+)
FUNDING_PROTECTION = True    # Activar protección
MAX_DIAS_POSICION = 5        # Cerrar después de 5 días
TP_DINAMICO_DIAS = 3         # Ajustar TP después de 3 días
TP_DINAMICO_PERCENT = 0.02   # TP reducido a 2%
```

## 📊 TP/SL por Temporalidad

| Temporalidad | Take Profit | Stop Loss |
| ------------ | ----------- | --------- |
| 15m          | +2%         | -1%       |
| 30m          | +3%         | -1.5%     |
| 1h           | +5%         | -2.5%     |
| 4h           | +8%         | -4%       |

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

El bot envía notificaciones cuando:

- Abre una nueva posición
- Cierra una posición (ganada/perdida)
- Cierra por tiempo máximo (5 días)
- Cierra por funding > PNL
- Ajusta TP dinámico
- Inicia el bot

## 🧠 Flujo de Operación

```
1. Obtener Fear & Greed Index
2. Analizar top 15 pares por volumen
3. Gemini decide: LONG, SHORT o WAIT
4. Si confianza >= 70%, guardar oportunidad
5. Ordenar por confianza
6. Ejecutar las TOP 3 mejores
7. Monitorear Trailing SL cada 30 segundos
8. Verificar protección Funding Fees
9. Repetir cada 2 minutos
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
