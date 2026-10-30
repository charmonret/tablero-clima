from datetime import date, datetime
import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
import streamlit as st

# Diccionario de coordenadas para las ciudades
CIUDADES = {
    "Morelia": (19.7027, -101.1924),
    "Querétaro": (20.5888, -100.3899),
    "Ciudad de México": (19.4326, -99.1332),
    "Guadalajara": (20.6597, -103.3496),
}

# Paleta de colores para las gráficas
CUALI = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

# ─── La consulta, con caché ────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def consultar(ciudad, inicio, fin):
    latitud, longitud = CIUDADES[ciudad]
    respuesta = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": latitud,
            "longitude": longitud,
            "start_date": str(inicio),
            "end_date": str(fin),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "America/Mexico_City",
        },
        timeout=60,
    )
    respuesta.raise_for_status()
    datos = respuesta.json()

    df = pd.DataFrame(datos["daily"])
    df["Fecha"] = pd.to_datetime(df.pop("time"))
    df = df.rename(columns={
        "temperature_2m_max": "TempMax",
        "temperature_2m_min": "TempMin",
        "precipitation_sum": "Lluvia",
    })
    df["Ciudad"] = ciudad
    df["Mes"] = df["Fecha"].dt.month
    return df


# ─── Controles ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filtros")
    ciudades = st.multiselect(
        "Ciudades", list(CIUDADES.keys()),
        default=["Morelia", "Querétaro"], max_selections=4)
    inicio = st.date_input("Desde", date(2024, 1, 1))
    fin = st.date_input("Hasta", date(2025, 12, 31))
    suavizado = st.slider("Días de media móvil", 1, 30, 7)
    st.caption("Fuente: Open-Meteo · Datos abiertos")

if not ciudades:
    st.info("Elige al menos una ciudad en el panel de la izquierda.")
    st.stop()

if inicio >= fin:
    st.error("La fecha inicial debe ser anterior a la final.")
    st.stop()

with st.spinner("Consultando la API..."):
    try:
        df = pd.concat([consultar(c, inicio, fin) for c in ciudades],
                       ignore_index=True)
    except requests.exceptions.RequestException as e:
        st.error(f"No se pudo consultar la API: {e}")
        st.stop()


# ─── Encabezado e indicadores ──────────────────────────────────────────
st.title("Tablero del clima")
st.caption(f"{', '.join(ciudades)} · del {inicio} al {fin} · "
           f"consultado el {datetime.now():%d/%m/%Y %H:%M}")

referencia = df[df["Ciudad"] == ciudades[0]]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Días por ciudad", len(referencia))
c2.metric(f"Máxima promedio · {ciudades[0]}",
          f"{referencia['TempMax'].mean():.1f} °C")
c3.metric(f"Día más caluroso · {ciudades[0]}",
          f"{referencia['TempMax'].max():.1f} °C")
c4.metric(f"Lluvia total · {ciudades[0]}",
          f"{referencia['Lluvia'].sum():.0f} mm")

st.divider()


# ─── Las gráficas, en dos columnas ─────────────────────────────────────
izquierda, derecha = st.columns(2)

with izquierda:
    st.subheader("Temperatura máxima")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    for i, ciudad in enumerate(ciudades):
        serie = df[df["Ciudad"] == ciudad].copy()
        serie["Suave"] = serie["TempMax"].rolling(suavizado).mean()
        ax.plot(serie["Fecha"], serie["Suave"],
                color=CUALI[i % len(CUALI)], linewidth=1.8, label=ciudad)
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Grados centígrados")
    ax.legend(frameon=False)
    st.pyplot(fig)

with derecha:
    st.subheader("Lluvia acumulada por mes")
    mensual = (df.groupby(["Ciudad", "Mes"])["Lluvia"].sum()
                 .reset_index())
    fig, ax = plt.subplots(figsize=(6, 3.5))
    sns.barplot(data=mensual, x="Mes", y="Lluvia", hue="Ciudad",
                palette=CUALI[:len(ciudades)], ax=ax)
    ax.set_xlabel("Mes")
    ax.set_ylabel("Milímetros")
    ax.legend(frameon=False, title=None)
    st.pyplot(fig)


# ─── La tabla y la descarga ────────────────────────────────────────────
with st.expander("Ver y descargar los datos"):
    st.dataframe(df)
    st.download_button(
        "Descargar CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"clima_{inicio}_{fin}.csv",
        mime="text/csv",
    )