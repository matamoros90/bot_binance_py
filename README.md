# Bot Binance Futures

Trading bot de criptomonedas para Binance Futuros con IA Gemini 2.0.

## Características

- 🤖 IA: Gemini 2.0 Flash
- 📊 Estrategia: Scalping (trades rápidos)
- ⏰ Horario: 24/7 (sin pausas)
- 🔍 Escaneo: Top 50 pares por volumen

## Variables de Entorno (Koyeb)

```
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET=tu_secret_key
API_KEY_GEMINI=tu_gemini_key
TELEGRAM_TOKEN=tu_telegram_token
TELEGRAM_CHAT_ID=tu_chat_id
```

## Configuración

En `bot_binance.py` línea 19:

- `MODO_TRADING = "TESTNET"` → Modo prueba
- `MODO_TRADING = "REAL"` → Producción

## Deploy en Koyeb

1. Crear nuevo repositorio en GitHub
2. Subir estos archivos
3. En Koyeb: Add Service → Connect GitHub → Seleccionar repo
4. Configurar variables de entorno
5. Deploy
