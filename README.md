# 🤖 Bot Binance IA - V6.3 Elite (Institutional Edge)

**Estado:** Producción / Gestión de Capital Dinámica / Dashboard Streamlit.  
**Perfil:** Algorithmic Quant Trader / Gestión Activa del Drawdown

Este bot opera como un "Sniper Técnico", buscando convergencias algorítmicas puras y utilizando inteligencia artificial **exclusivamente como filtro asimétrico** para proteger el margen. Está diseñado para correr 24/7 en un VPS y viene acompañado de un potente Dashboard de lectura para monitoreo remoto.

## 📊 Arquitectura y KPIs (V6.3 Edge)

- **Filtro Macro y Bloqueo Direccional (1H):** El sistema exige alineación total. No opera contra la EMA200 medida en velas cerradas de 1 Hora. Si un target va en contra de la macrotendencia, es rechazado automáticamente.
- **Filtro de Liquidez Estricto:** Requerimiento de Volumen Relativo (RV) mínimo aumentado a `>= 0.15x`. No se opera en mercados muertos.
- **Filtro de Lateralidad:** Bloqueo absoluto de entradas si el oscilador principal (RSI) divaga en la zona de inercia (45 - 55).
- **Trading Técnico Aislado:** Estrategia basada en múltiples indicadores paramétricos (EMA, ATR, RSI, Bollinger) en múltiples temporalidades (1H y 15m).
- **Circuit Breakers Asíncronos:** Desactiva llamadas al API (Google/Binance) a nivel global en caso de timeouts o fallos continuos para no exponer el código a latencias.

## 🛡️ Gestión de Riesgo Institucional (CapitalManager & Garantías)

Todo el tamaño posicional está subyugado a un controlador externo sin fricción:

- **Riesgo Fijo:** Conservador, anclado al **2%** por cada operación.
- **Defensa de Posición (Break-Even):** Un candado algorítmico protege las ganancias flotantes al tocar `+0.6%` de ROI arrastrando de inmediato el Stop Loss por encima del precio de entrada (`+0.1%`) impidiendo que un ganador inicial cierre en pérdida.
- **Acoso Dinámico (Trailing SL 1%):** Al llegar a `+1.0%` de ganancia se suelta un "Sabueso" que protege la posición trailing un 1% por debajo del mejor precio histórico.
- **Drawdown Cooldown:** Penaliza activando un pausado técnico (enfriamiento de 8 horas) si se cruza la barrera del **20% de Drawdown Máximo** o en un límite semanal de volumen.

## 🖥️ Central de Monitorización (Streamlit Dashboard)

El ecosistema ahora cuenta con un portal visual en tiempo real de tipo "Hedge Fund" (`dashboard.py`).

1. **Visibilidad Total de Posiciones (Live API):** El panel consulta y sincroniza las posiciones abiertas de manera estrictamente pasiva obteniendo precios y rendimientos flotantes directamente desde la API de Binance Futures cada 30 segundos, sin inyectar datos huérfanos a la BD ni emitir logs locales (UX Institutional Grade).
2. **ReadOnly & Seguro:** Lee el estado histórico y la gestión de riesgo desde `trades.db` garantizando que el dashboard jamás intervenga ni obstaculice el hilo central del bot.
3. **Indicadores Duales:** Curva de Capital (Capital Dinámico vs Máx. Histórico), Win Rate puro y semáforos activos (Verde, Amarillo, Rojo) acorde al nivel de Drawdown.

## 🚀 Despliegue de Grado Producción en VPS (systemd)

El sistema soporta daemon threads a través de `systemctl` para Ubuntu/Debian. Para que opere indefinidamente y reviva frente a apantallamientos se usan dos servicios integrados. 

### 1. Variables de entorno locales (`.env`)
Asegúrate de dejarlas en la raíz del proyecto para uso general:

```env
# BINANCE
BINANCE_API_KEY=tu_binance_key
SECRET=tu_binance_secret

# GEMINI IA
API_KEY_GEMINI=tu_gemini_key
USAR_IA=true
IA_MODO=FILTRO

# REPORTE TELEGRAM
TELEGRAM_TOKEN=tu_tg_token
TELEGRAM_CHAT_ID=tu_tg_id

# RUTAS & OPERATIVA
DATA_DIR=./
RIESGO_POR_TRADE=0.02
MAX_OPERACIONES=3
```

### 2. Configurar Autostart (Archivos `.service`)

Crea y direcciona los siguientes logs ubicados de antemano en el paquete de actualización alojado en `/deploy/`:
* `deploy/bot.service`
* `deploy/dashboard.service`

Verifica en ambos que las variables `User=ubuntu` y `WorkingDirectory=/home/ubuntu/...` apunten directo al nombre y ruta verídicas en tu VPS remoto. Y trasládalo:

```bash
mkdir -p logs
sudo cp deploy/bot.service /etc/systemd/system/
sudo cp deploy/dashboard.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable bot dashboard
```

### 3. Secuencia de Inicialización

Arrancamos en Background de forma desatendida.
```bash
sudo systemctl start bot
sudo systemctl start dashboard
```

Status Global y Logs:
```bash
sudo systemctl status bot
sudo systemctl status dashboard

tail -f logs/bot.log
```

---
**Soporte / Dev Repo:** https://github.com/matamoros90/bot_binance_py
