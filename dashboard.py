import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import altair as alt

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE PÁGINA
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Hedge Fund Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 1. AUTO-REFRESH (Cada 5 segundos)
st_autorefresh(interval=5000, key="datarefresh")

# Estilo Premium Dark
st.markdown("""
<style>
    .metric-container {
        pointer-events: none;
    }
    .st-emotion-cache-1wivap2 {
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Institutional Trading Dashboard")
st.markdown("Monitor de Operaciones Algorítmicas V6.2 — **Modo Solo Lectura • Tiempo Real**")
st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# CONEXIÓN A BASE DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DATA_DIR, "trades.db")

def get_db_connection():
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

conn = get_db_connection()

if conn is None:
    st.error(f"⚠️ Base de datos no encontrada en {DB_PATH}. El bot debe ejecutarse al menos una vez.")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# CONSULTAS SQL RAW
# ═══════════════════════════════════════════════════════════════════════════════

def get_capital_status():
    try:
        df = pd.read_sql("SELECT * FROM capital_estado ORDER BY id DESC LIMIT 1", conn)
        return df.iloc[0] if not df.empty else None
    except Exception:
        return None

def get_capital_history():
    try:
        df = pd.read_sql("SELECT timestamp, capital_actual, capital_maximo_historico FROM capital_estado ORDER BY id ASC", conn)
        if df.empty: return None
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception:
        return None

def get_rendimiento_global():
    try:
        df = pd.read_sql("SELECT pnl, ia_validado FROM trades WHERE status = 'CLOSED'", conn)
        total_trades = len(df)
        if total_trades == 0:
            return {"total_trades": 0, "win_rate": 0, "profit_factor": 0, "df": df}
            
        ganadores = df[df['pnl'] > 0]
        perdedores = df[df['pnl'] <= 0]
        
        win_rate = (len(ganadores) / total_trades) * 100
        gross_profit = ganadores['pnl'].sum()
        gross_loss = abs(perdedores['pnl'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0)
        
        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "df": df
        }
    except Exception:
         return {"total_trades": 0, "win_rate": 0, "profit_factor": 0, "df": pd.DataFrame()}

def get_ia_metricas(dias: int):
    try:
        fecha_desde = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        df = pd.read_sql(f"""
            SELECT sum(senales_total) as total, sum(senales_validadas) as validadas 
            FROM ia_metricas WHERE timestamp >= '{fecha_desde}'
        """, conn)
        if df.empty or pd.isna(df.iloc[0]['total']) or df.iloc[0]['total'] == 0:
            return None
        t = int(df.iloc[0]['total'])
        v = int(df.iloc[0]['validadas'])
        return {"total": t, "validadas": v, "rate": round((v/t)*100, 1)}
    except Exception:
        return None

def get_ia_metricas_sesion():
    try:
        df = pd.read_sql("SELECT * FROM ia_metricas ORDER BY id DESC LIMIT 1", conn)
        if df.empty: return None
        return df.iloc[0]
    except Exception: return None

# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT & VISUALIZACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

col1, col2, col3, col4 = st.columns(4)

# ─── 3. ESTADO DEL BOT MÁS CLARO ───
capital = get_capital_status()
estado_bot = "🟢 ACTIVO"
if capital is not None:
    # Lógica para Validando vs Activo
    if capital['capital_actual'] <= capital['capital_inicial'] * 1.05 and capital['drawdown_pct'] < 10:
        estado_bot = "🟡 VALIDANDO"
        
    pausado = bool(capital['trading_pausado'])
    ts_reduccion = capital['timestamp_reduccion']
    
    if pausado:
        estado_bot = "🔴 PAUSADO (Drawdown)"
        if pd.notna(ts_reduccion) and ts_reduccion:
            limit = datetime.fromisoformat(ts_reduccion) + timedelta(hours=8)
            if datetime.now() < limit:
                tiempo_restante = limit - datetime.now()
                # Formatear el timedelta a horas y minutos
                horas, rem = divmod(tiempo_restante.seconds, 3600)
                minutos, _ = divmod(rem, 60)
                estado_bot = f"⏸️ COOLDOWN ({horas}h {minutos}m restantes)"

with col1:
    st.subheader("Estado de Sistema")
    st.info(estado_bot)

# ─── 2. ALERTAS VISUALES DE RIESGO ───
with col2:
    st.subheader("Capital Asignado")
    if capital is not None:
        st.metric("Capital Operativo", f"${capital['capital_actual']:,.2f}")
        
        dd_pct = capital['drawdown_pct']
        if dd_pct >= 20:
             st.error(f"🔴 Drawdown Alto: {dd_pct}% (Max: ${capital['capital_maximo_historico']:,.2f})")
        elif dd_pct >= 10:
             st.warning(f"🟡 Drawdown Moderado: {dd_pct}% (Max: ${capital['capital_maximo_historico']:,.2f})")
        else:
             st.success(f"🟢 Riesgo Controlado: {dd_pct}% (Max: ${capital['capital_maximo_historico']:,.2f})")
    else:
        st.write("Sin datos de capital.")

# ─── BLOQUE RENDIMIENTO ───
rendimiento = get_rendimiento_global()
with col3:
    st.subheader("Rendimiento (All-Time)")
    st.metric("Total Trades", rendimiento["total_trades"])
    cols_rend_1, cols_rend_2 = st.columns(2)
    cols_rend_1.metric("Win Rate", f"{rendimiento['win_rate']}%")
    cols_rend_2.metric("Profit Factor", rendimiento["profit_factor"])

# ─── BLOQUE IA ───
with col4:
    st.subheader("Filtro IA Gemini")
    ia_sesion = get_ia_metricas_sesion()
    
    if ia_sesion is not None and ia_sesion['senales_total'] > 0:
        ap_rate = round((ia_sesion['senales_validadas'] / ia_sesion['senales_total']) * 100, 1)
        st.metric("Approval Rate (Sesión)", f"{ap_rate}%", f"{ia_sesion['senales_validadas']}/{ia_sesion['senales_total']} señales")
    else:
        st.metric("Approval Rate (Sesión)", "N/A")
        
    ia_24h = get_ia_metricas(1)
    ia_7d = get_ia_metricas(7)
    
    if ia_24h:
        st.caption(f"**24h:** {ia_24h['rate']}% ({ia_24h['validadas']}/{ia_24h['total']})")
    if ia_7d:
        st.caption(f"**7d:** {ia_7d['rate']}% ({ia_7d['validadas']}/{ia_7d['total']})")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# 4. MEJORAR GRÁFICA DE CAPITAL
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Curva de Capital y Drawdown")
df_cap = get_capital_history()

if df_cap is not None:
    # Melt el dataframe para permitir coloración distinta en Altair
    df_melted = df_cap.melt(id_vars=['timestamp'], value_vars=['capital_actual', 'capital_maximo_historico'],
                            var_name='Tipo', value_name='Capital')
    
    # Reemplazar nombres para la leyenda
    df_melted['Tipo'] = df_melted['Tipo'].replace({
        'capital_actual': 'Capital Actual',
        'capital_maximo_historico': 'Máximo Histórico'
    })

    # Construir el gráfico con Altair
    line_chart = alt.Chart(df_melted).mark_line(interpolate='step-after').encode(
        x=alt.X('timestamp:T', title='Tiempo'),
        y=alt.Y('Capital:Q', title='Monto (USD)', scale=alt.Scale(zero=False)),
        color=alt.Color('Tipo:N', scale=alt.Scale(domain=['Capital Actual', 'Máximo Histórico'], range=['#00b4d8', '#ff4d4d'])),
        tooltip=['timestamp', 'Tipo', 'Capital']
    ).properties(height=350)
    
    # Agregar área para denotar visualmente el drawdown si se desea
    st.altair_chart(line_chart, use_container_width=True)
else:
    st.warning("No hay suficientes datos de capital para graficar.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# 5. FILTRO DE TRADES Y TABLA
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Historial de Operaciones y Calidad IA")

# Mostrar métricas separadas por grupo de validación (Trades con IA vs Sin IA)
df_all = rendimiento["df"]
if not df_all.empty and 'ia_validado' in df_all.columns:
    df_ia = df_all[df_all['ia_validado'] == 1]
    df_no_ia = df_all[df_all['ia_validado'] == 0]
    
    col_ia1, col_ia2 = st.columns(2)
    
    with col_ia1:
        st.markdown("#### 🤖 Operaciones validadas por IA")
        if len(df_ia) > 0:
            wr_ia = (len(df_ia[df_ia['pnl'] > 0]) / len(df_ia)) * 100
            st.write(f"**Total trades:** {len(df_ia)} | **Win Rate:** {wr_ia:.1f}%")
        else:
            st.write("No hay trades registrados con IA.")
            
    with col_ia2:
        st.markdown("#### ⚙️ Operaciones Sin IA (Técnicas Puras)")
        if len(df_no_ia) > 0:
            wr_no_ia = (len(df_no_ia[df_no_ia['pnl'] > 0]) / len(df_no_ia)) * 100
            st.write(f"**Total trades:** {len(df_no_ia)} | **Win Rate:** {wr_no_ia:.1f}%")
        else:
            st.write("Todos los trades han sido procesados por IA.")

st.markdown("<br>", unsafe_allow_html=True)

try:
    df_trades = pd.read_sql("""
        SELECT closed_at as Fecha, symbol as Activo, action as Dirección, 
               entry_price as Entrada, exit_price as Salida, pnl as PnL, 
               ia_validado as 'IA Filtro' 
        FROM trades 
        WHERE status = 'CLOSED' 
        ORDER BY closed_at DESC LIMIT 20
    """, conn)
    
    if not df_trades.empty:
        # Formatear números
        df_trades['PnL'] = df_trades['PnL'].apply(lambda x: f"${x:.2f}")
        df_trades['Entrada'] = df_trades['Entrada'].apply(lambda x: f"${x:.4f}" if pd.notnull(x) else "")
        df_trades['Salida'] = df_trades['Salida'].apply(lambda x: f"${x:.4f}" if pd.notnull(x) else "")
        df_trades['IA Filtro'] = df_trades['IA Filtro'].apply(lambda x: "✅ IA" if x == 1 else "⚙️ Técnica")
        
        st.dataframe(df_trades, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay trades cerrados registrados en la base de datos.")
except Exception as e:
    st.error(f"No se pudo cargar la tabla de trades: {e}")
