# 🤖 Bot Binance IA - V6.0 Sniper Mode

**Estado:** Preservación de Capital Extrema y Operación de Alta Precisión (Francotirador).
**Perfil:** Senior Quant Trader / Gestión de Riesgo por Alta Convicción.

## 📊 Objetivos de Desempeño (KPIs)

- **Target ROI Semanal/Mensual:** Acumulativo de fuerte impacto (Meta del ~85% en pocas manos).
- **Frecuencia Absoluta:** Límite máximo de **3 operaciones por semana** para recortar todo ruido del mercado.
- **Eficiencia de Recursos:** Sistema de "Hibernación" de la Inteligencia Artificial al llegar a la cuota semanal.
- **Profit Factor:** > 1.80 (Optimización de la esperanza matemática).

---

## 🛡️ Protocolo de Gestión de Riesgo (Búnker Institucional)

- **Reserva de Seguridad (Untouchable):** **80%** del balance total blindado ante quiebres de mercado.
- **Capital Operativo Máximo:** **20%** del balance total destinado a trading activo.
- **Rango Sniper:** **10.0%** del pool asignado en *cada posición* buscando el golpe fuerte por trade.
- **Apalancamiento Agresivo:** **10x** para magnificar la zona segura de target.

---

## 🧠 Estrategia Maestra: High-Precision Sniper Trading

### 1. Filtrado de Ruido y Análisis de Temporalidad (1H)
- Se operan solo temporalidades rígidas (1H) con lectura contextual de divergencias en 200 iteraciones (velas japonesas) por análisis.
- Validación de liquidez con **Volumen Relativo (RV) > 0.2x**.

### 2. Take Profit y Stop Loss Dinámicos (R:R Agresivo)
- **Top de Ganancia (TP):** Límite fijo inicial en +8.5% (85% apalancado).
- **Suelo de Contención (SL):** Límite en -3.5% (35% apalancado).
- **Trailing Stop Loss Activo:** En lugar de break-even estático, el Trailing del **1.0%** persigue toda subida de ganancia consolidada.

### 3. Motor IA (Gemini 2.0 Flash)
- **Límite IA Cero Ruido (ZNL):** Si se excedió la meta de 3 ingresos a la semana, la IA suspende las peticiones ahorrando CPU, RAM y latencia en el API al 100%. Solo queda orbitando tareas vitales (cierre).

---

## 🚀 Instalación VPS / Servidor

- **Infraestructura Sugerida:** Oracle Cloud (Always Free ARM 24GB) o GCP.
- **Entorno Local:** Python 3.10+ / macOS / Linux.
- **Requisitos de Variables (`.env`)**:

```env
BINANCE_API_KEY=xxx
BINANCE_SECRET=xxx
GEMINI_API_KEY=xxx
TELEGRAM_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
```

## 🛠️ Ejecución
Debes cargar localmente tus variables en `.env` antes de ejecutar.
En terminal:
```bash
pip install -r requirements.txt
python bot_binance.py
```

## 📞 Soporte

Repositorio: https://github.com/matamoros90/bot_binance_py
