# 🤖 Bot Binance IA - V6.4 Elite (Conservative-Filter Edition)

**Estado:** Producción / Gestión de Capital Dinámica / Dashboard Streamlit.  
**Perfil:** Algorithmic Quant Trader / Máxima Selectividad y Protección del Capital

Este bot opera como un "Sniper Ultra-Selectivo", buscando únicamente convergencias algorítmicas de altísima convicción técnica. Está diseñado para correr 24/7 en un VPS con énfasis en **selectividad sobre volumen de operaciones**. Viene acompañado de un potente Dashboard de lectura para monitoreo remoto.

## 📊 Arquitectura y KPIs (V6.4 Conservative)

- **Filtro Macro y Bloqueo Direccional (1H):** El sistema exige alineación total. No opera contra la EMA200 medida en velas cerradas de 1 Hora. Si un target va en contra de la macrotendencia, es rechazado automáticamente.
- **Filtro de Liquidez Institucional:** Requerimiento de Volumen Relativo (RV) mínimo elevado a `>= 0.50x` (V6.4). **Rechaza pares sin liquidez significativa** como ARIAUSDT que generaban pérdidas.
- **Filtro de Lateralidad Extrema:** Bloqueo absoluto si RSI está en zona neutra (40 - 60). Solo entra si RSI < 40 (LONG sobreventa) o RSI > 60 (SHORT sobrecompra).
- **Confianza Técnica Mínima:** Aumentada a **80%** (V6.4, antes 70%). Rechaza señales débiles.
- **Trading Técnico Puro:** Estrategia basada en indicadores paramétricos (EMA200 macro 1H, RSI, ATR, Bollinger) en temporalidades limpias (1H y 15m).
- **Circuit Breakers Asíncronos:** Desactiva llamadas al API en caso de timeouts para evitar latencias.

## 🛡️ Gestión de Riesgo Institucional (V6.4 - Potenciada)

Todo el tamaño posicional está controlado por protecciones multicapa:

- **Riesgo Ultra-Conservador:** Reducido a **1%** por cada operación (V6.4, antes 2%).
- **Apalancamiento Reducido:** De 10x a **5x** (V6.4) — menor slippage, menor riesgo de liquidación.
- **Defensa de Posición (Break-Even):** Candado algorítmico que arrastra SL al +0.1% casi inmediatamente si se toca +0.6% ROI.
- **Acoso Dinámico (Trailing SL 1%):** Al llegar a +1.0% de ganancia, trailing stop automático.
- **Drawdown Cooldown:** Pausa técnica (8h) si se cruza 20% de drawdown máximo.
- **Límite Semanal:** Aumentado a **30 trades máx/semana** (V6.4, antes 10). Con filtros más restrictivos, se espera menos volumen pero mejor calidad.

## 🎯 Cambios V6.4 - Optimización por Pérdidas

**Problema diagnosticado:** Las primeras 10 operaciones perdieron dinero por:
- ✗ Filtro RV (0.15x) permitía activos basura como ARIAUSDT
- ✗ Confianza mínima (70%) aceptaba señales débiles
- ✗ Apalancamiento 10x amplificaba slippage
- ✗ Riesgo 2% erosionaba capital rápidamente

**Soluciones implementadas:**
- ✅ RV mínima: 0.15x → **0.50x** (rechaza pares sin volumen)
- ✅ Confianza mínima: 70% → **80%** (solo señales de altísima convicción)
- ✅ Zona RSI neutra: 45-55 → **40-60** (más restrictivo)
- ✅ Validación RSI LONG: ≤45 → **≤40** (RSI más extremo)
- ✅ Validación RSI SHORT: ≥55 → **≥60** (RSI más extremo)
- ✅ Apalancamiento: 10x → **5x** (menos amplificación de costos)
- ✅ Riesgo por trade: 2% → **1%** (mayor protección)

## 🖥️ Central de Monitorización (Streamlit Dashboard)

El ecosistema cuenta con un portal visual en tiempo real de tipo "Hedge Fund" (`dashboard.py`).

1. **Visibilidad Total de Posiciones (Live API):** Sincronización pasiva cada 30 segundos directamente desde Binance Futures.
2. **ReadOnly & Seguro:** Lee desde `trades.db` sin intervenir en operaciones activas.
3. **Indicadores Duales:** Curva de Capital (Dinámico vs Máx. Histórico), Win Rate puro y semáforos de Drawdown (Verde/Amarillo/Rojo).

## 🚀 Despliegue de Grado Producción en VPS (systemd)

El sistema soporta daemon threads a través de `systemctl` para Ubuntu/Debian. Para que opere indefinidamente y reviva frente a apantallamientos se usan dos servicios integrados. 

### 1. Variables de entorno locales (`.env`)
Asegúrate de dejarlas en la raíz del proyecto para uso general:

```env
# BINANCE
BINANCE_API_KEY=tu_binance_key
SECRET=tu_binance_secret
BINANCE_TESTNET=False          # Cambiar a True para TESTNET (False = MAINNET real)

# GEMINI IA (Filtro únicamente)
API_KEY_GEMINI=tu_gemini_key
USAR_IA=false                  # V6.4: IA desactivada por defecto
IA_MODO=FILTRO

# REPORTE TELEGRAM
TELEGRAM_TOKEN=tu_tg_token
TELEGRAM_CHAT_ID=tu_tg_id

# RUTAS & CONFIGURACIÓN
DATA_DIR=./
LOG_DETALLADO=true             # Activa logs verbosos
MONITOREO_INTERVALO=30         # Segundos entre ciclos de análisis

# CONFIGURACIÓN DE RIESGO (V6.4)
RIESGO_POR_TRADE=0.01           # V6.4: 1% por operación (antes 2%)
APALANCAMIENTO=5                # V6.4: Reducido de 10x a 5x
CONFIANZA_MINIMA=0.80           # V6.4: 80% de confianza técnica mínimaa
VOLUMEN_RELATIVO_MIN=0.50       # V6.4: 0.50x liquidez mínima (antes 0.15x)
MAX_OPERACIONES=5               # Máximas posiciones simultáneas
LIMITE_TRADES_SEMANAL=30        # V6.4: 30 trades máx/semana (antes 10)
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

## 📋 Changelog Versiones

### V6.4 - Conservative-Filter Edition (10/04/2026)
**Cambios principales tras diagnóstico de pérdidas iniciales:**
- 🔧 **Riesgo**: 2% → 1% (protección capital)
- 🔧 **Apalancamiento**: 10x → 5x (reduce slippage)
- 🔧 **Confianza mínima**: 70% → 80% (más selectivo)
- 🔧 **Volumen Relativo (RV) mínimo**: 0.15x → 0.50x (rechaza activos sin liquidez)
- 🔧 **Zona RSI neutra**: 45-55 → 40-60 (filtro más restrictivo)
- 🔧 **RSI LONG**: ≤45 → ≤40 (solo sobreventa extrema)
- 🔧 **RSI SHORT**: ≥55 → ≥60 (solo sobrecompra extrema)
- 🔧 **Límite semanal**: 10 → 30 trades (con filtros más restrictivos, esperar menos volumen pero mejor calidad)
- ✅ Rechaza pares problemáticos como ARIAUSDT (baja liquidez)
- ✅ Solo entra en señales de altísima convicción técnica

### V6.3 - Institutional Edge
- Gestión de capital dinámica integrada
- Dashboard Streamlit con monitoreo live
- Circuit breakers de IA mejorados

### V6.0 - Elite Edition
- Apalancamiento x10 scalping
- Múltiples temporalidades (1H, 15m)
- Filtro EMA200 macro 1H

---
**Soporte / Dev Repo:** https://github.com/matamoros90/bot_binance_py
