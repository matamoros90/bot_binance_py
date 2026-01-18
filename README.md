# 🤖 Bot Binance Futures V2.5 - Trading con IA + Funding Protection

## 📋 Descripción

Bot de trading automatizado para Binance Futures que utiliza **Gemini 2.0 Flash** como cerebro de IA para tomar decisiones de trading. Opera 24/7 con estrategia de swing trading conservador y **protección automática contra funding fees**.

## 🆕 Características V2.5 (Actualizado 18/01/2026)

| Funcionalidad                | Descripción                                                         |
| ---------------------------- | ------------------------------------------------------------------- |
| **Trailing Stop Loss 1.5%**  | SL que se mueve automáticamente cuando la posición está en ganancia |
| **Fear & Greed Index**       | Integración con API para análisis de sentimiento del mercado        |
| **Temporalidades Dinámicas** | 15m, 30m, 1h, 4h - La IA elige según volatilidad                    |
| **3 Posiciones Simultáneas** | Máximo 3 operaciones abiertas a la vez                              |
| **Cierre por Tiempo**        | Cierra posiciones automáticamente después de 5 días                 |
| **Funding vs PNL**           | Cierra si los funding fees superan las ganancias                    |
| **TP Dinámico**              | Reduce el Take Profit después de 3 días para asegurar ganancias     |

## ⚙️ Configuración

```python
# Trading
CONFIANZA_MINIMA = 0.70      # 70% mínimo para operar
ESCUDO_TRABAJO = 0.80        # 80% del balance para trading
ESCUDO_SEGURO = 0.20         # 20% protegido
APALANCAMIENTO = 3           # x3 conservador
TOP_ACTIVOS = 15             # Analiza top 15 por volumen
MAX_POSICIONES = 3           # Máximo 3 posiciones
TRAILING_SL_PERCENT = 0.015  # 1.5% trailing

# Funding Fees Protection (V2.5)
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

## 📈 Rendimiento Histórico (04/01 - 07/01/2026)

| Fecha          | Balance   | Ganancia |
| -------------- | --------- | -------- |
| 04/01 (Inicio) | $5,293.49 | Base     |
| 05/01          | ~$5,300   | +$7      |
| 06/01          | $5,388.63 | +$95     |
| 07/01          | $5,438.59 | +$145    |

**Rendimiento 4 días: +$145.10 (+2.74%)**

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
8. Repetir cada 2 minutos
```

## 📝 Notas de Desarrollo

- **04/01/2026**: Upgrade a V2.0 con Trailing SL, Fear & Greed, y temporalidades dinámicas
- Se eliminó el "Modo Lotes" que bloqueaba el bot
- Se implementó lógica para llenar las 3 posiciones en un solo ciclo

## ⚠️ Advertencias

- Este bot opera en TESTNET por defecto
- Cambiar `BINANCE_TESTNET=False` para producción real
- El trading conlleva riesgos - usa solo capital que puedas perder

## 📞 Soporte

Repositorio: https://github.com/matamoros90/bot_binance_py
