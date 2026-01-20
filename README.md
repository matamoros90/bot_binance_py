# 🤖 Bot Binance Futures V2.7 - Guardian System + Trading con IA

## 📋 Descripción

Bot de trading automatizado para Binance Futures que utiliza **Gemini 2.0 Flash** como cerebro de IA para tomar decisiones de trading. Opera 24/7 con estrategia de swing trading conservador y **protección automática contra funding fees**.

---

## 🚀 Estado del Proyecto (Última actualización: 19/01/2026)

| Aspecto        | Estado                                 |
| -------------- | -------------------------------------- |
| **Versión**    | V2.7                                   |
| **Plataforma** | Koyeb (Deploy automático desde GitHub) |
| **Modo**       | TESTNET (Pruebas)                      |
| **Estado**     | 🟢 Operativo                           |

### 💰 Rendimiento Acumulado (TESTNET)

| Período       | Balance Inicial | Balance Actual | Ganancia       | %           |
| ------------- | --------------- | -------------- | -------------- | ----------- |
| 04/01 - 07/01 | $5,293.49       | $5,438.59      | +$145.10       | +2.74%      |
| 07/01 - 18/01 | $5,438.59       | **$6,576.60**  | +$1,138.01     | +20.92%     |
| **TOTAL**     | $5,293.49       | **$6,576.60**  | **+$1,283.11** | **+24.24%** |

> [!NOTE]
> Estos resultados son en TESTNET. El rendimiento real puede variar.

---

## 🆕 Historial de Versiones

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
MAX_POSICIONES = 3           # Máximo 3 posiciones
TRAILING_SL_PERCENT = 0.015  # 1.5% trailing

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
