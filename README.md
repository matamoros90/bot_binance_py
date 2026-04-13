# 🤖 Bot Binance - V6.7 Aggressive Scalper (Alta Frecuencia)

**Estado:** Producción / Operativa Técnica Pura / Dashboard Streamlit.  
**Perfil:** Algorithmic High-Frequency Scalper / RIESGO ASIMÉTRICO / 100% MATEMÁTICO

**NUEVO ENFOQUE: SCALPING AGRESIVO - OPORTUNIDADES RÁPIDAS**

El bot fue reconfigurado drásticamente de su estado restrictivo (que pasaba horas o semanas sin operar) a un modo de "Cazador de Micro-Movimientos". Ahora aprovecha cruces de RSI y MACD mucho más permisivos para llevar a cabo una multitud de micro-transacciones diarias buscando rentabilidades inmediatas (TPs bajísimos).

Se ha **erradicado por completo a la IA Gemini** del ciclo de decisiones, garantizando latencia ultra-baja y puramente lógica matemática sin reactivaciones "zombies" de IA.

## 📊 Arquitectura y KPIs (V6.7 Aggressive Scalper)

- **Acelerador de Temporalidad (5m/15m):** El sistema escanea en ventanas sumamente rápidas (5 minutos y 15 minutos) para reaccionar a fluctuaciones intratiempo cortas en las criptomonedas y no esperar tendencias macro.
- **Tolerancia Técnica Extrema:** Mínima confianza requerida de **45%** (RSI permisivos y MACD con cruce simple). Aceptando señales sub-óptimas si existen indicios de dirección a favor.
- **Micro-Toma de Ganancias (Micro-TPs):** Configurado con TPs como 0.6% ó 1.0%. En lugar de esperar 8% de un trade prolongado, liquida operaciones el mismo minuto si tocan un centavo arriba.
- **Pérdida Esperada Ignorada (EV < 0 Permitido):** Tolerancia máxima al slippage; si hay una señal operable, se ejecuta de inmediato sin rechazarla por cálculo conservador de fees.
- **Trading Matemático Puro (No Gemini):** Gemini ha sido inhabilitado al 100%, eliminando circuit breakers resurrectores. Toda la confianza depositada en RSI + MACD + ATR.

## 🛡️ Gestión de Riesgo Ofensiva (V6.7)

Todo el tamaño posicional se potenció para exprimir las pequeñas ventajas en el mercado y generar dólares reales:

- **Riesgo Asignado por Trade:** Aumentado significativamente al **5%** por cada operación para darle peso económico a TPs minúsculos.
- **Apalancamiento Potenciado:** Subido a **10x** para amplificar el pnl por cada micro-movimiento porcentual.
- **Exposición Multivariada:** Capacidad para abrir hasta **10 posiciones simultáneas**, esparciendo el riesgo entre los top 50 activos de mayor volumen.
- **Guardián Activo:** Aunque es ultra frecuente, el Stop-Loss y Break-Even se ejecutan velozmente ante cualquier reversión drástica o error de la tendencia.

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

### V6.7.1 - Bugfix Crítico (12/04/2026 - 4 ERRORES SILENCIOSOS ELIMINADOS)

**Bugs identificados en logs de producción y corregidos:**

#### 🐛 Bug #1 — `max_drawdown referenced before assignment` (CRASH en cada trade)
- **Archivo:** `persistence.py` — función `calcular_metricas_riesgo()`
- **Causa:** Variable `max_drawdown` usada sin inicializar. El nombre correcto era `max_dd`.  
- **Efecto:** Error en **cada cierre de trade**, CapitalManager se corrompía y no actualizaba capital.
- **Fix:** ✅ Renombrada referencia incorrecta → `max_dd`.

#### 🐛 Bug #2 — `RESERVA DE CAPITAL INTACTA: Operaciones bloqueadas` (Bot inoperativo)
- **Causa:** `ESCUDO_SEGURO = 0.95` exigía que el margen libre fuera >95% del balance total para operar. Con posiciones abiertas usando margen, esto es **matemáticamente imposible** → el bot bloqueaba TODAS las nuevas operaciones.  
- **Efecto:** Después de abrir las primeras posiciones, el bot quedaba paralizado indefinidamente.
- **Fix:** ✅ Escudo de margen libre comentado. La protección real la ejerce el Guardián (-7% por posición).

#### 🐛 Bug #3 — `RECHAZADO POR RSI` en señales ya validadas (Doble filtro)
- **Causa:** Existía un segundo filtro RSI dentro de la función de ejecución (más restrictivo: LONG RSI ≤45, SHORT RSI ≥55) que rechazaba señales que `generar_senal_fallback()` ya había aprobado con criterios más amplios (MACD, RSI ≤65).
- **Efecto:** Señales válidas como `ETHUSDT LONG (MACD positivo)` o `RAVEUSDT LONG (Tendencia ALCISTA)` eran silenciadas luego de haber pasado el primer filtro.
- **Fix:** ✅ Eliminado el doble filtro. La validación ya viene incorporada en `generar_senal_fallback()`.

#### 🐛 Bug #4 — `CIERRE POR REVERSIÓN` cerrando posiciones ganadoras en pérdida
- **Causa:** `GANANCIA_MINIMA_PARA_PROTEGER = 0.015` (1.5%) se activaba muy pronto con 10x de apalancamiento y `REVERSION_MAXIMA_PERMITIDA = -0.03` era demasiado sensible para scalping. Ejemplo real: `TRADOORUSDT` fue cerrada con PNL `-$1.11` cuando había alcanzado +$2.79 (+6.29% máximo).
- **Fix:** ✅ Umbral de protección subido a `GANANCIA_MINIMA_PARA_PROTEGER = 0.05` (5%). Reversión tolerada hasta `-0.06` (-6% desde máximo) antes de cerrar.

---

### V6.7 - Aggressive Scalper (12/04/2026 - CAMBIO DE PARADIGMA)
**Pivote a Alta Frecuencia:**
- Cambio de estrategia extrema: de Sniper a Cazador por volumen diario.
- Eliminación total del Zombie de IA Gemini (falsa reactivación neutralizada).
- Temporalidades bajadas a `5m/15m`.
- Apalancamiento al `10x` y exposición al `5%`.
- Parámetros de Take Profit Ultra cortos (0.6% a 1.0%).
- Reducción del requerimiento de confianza técnica al 45%, EV mínimo anulado.

### V6.6 - Complete-Rewrite (10/04/2026 - SOLUCIÓN DEFINITIVA)
**ANÁLISIS EXHAUSTIVO REVELÓ PROBLEMA ARQUITECTÓNICO:**

**Problema Raíz**: `generar_senal_fallback()` era brutalmente restrictivo:
- Solo generaba señales en extremos absolutos (RSI <20 o >80)  
- 90% del tiempo retornaba `None`
- **BOT NUNCA OPERABA en 2 semanas**

**Solución**: Reescritura completa con múltiples escenarios:
- ⚡ **Confianza 88%**: Extremos absolutos (RSI ≤20 o ≥80)
- ⚡ **Confianza 86%**: Tendencia FUERTE + RSI extremo
- ⚡ **Confianza 84%**: Tendencia moderada + RSI extremo (35/65)
- ⚡ **Confianza 80%**: Tendencia + RSI confirmación (≤45/≥55)
- ⚡ **Confianza 78%**: RSI sobreventa/sobrecompra nivel 2 (≤25/≥75)
- ⚡ **Confianza 76%**: Tendencia + MACD confirmación
- ⚡ **Confianza 74%**: MACD cruzó sin oposición

**Cambios V6.6:**
- CONFIANZA_MINIMA: 0.75 → **0.74**
- EV_MINIMO: 0.002 → **0.001**
- BOT_VERSION: **"V6.6 Elite (Complete-Rewrite)"**

**Resultado Esperado**: 0 operaciones/2 semanas → **múltiples diarios**

### V6.5 -Fixed-Critical-Bugs (10/04/2026)
- Identificó confianza máxima (75%) < mínima (80%)
- Solución parcial sin abordar causa raíz

### V6.4 - Conservative-Filter Edition (10/04/2026)
- Riesgo 2%→1%, Apalancamiento 10x→5x, RV mínimo 0.50x

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
