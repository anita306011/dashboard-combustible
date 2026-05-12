import streamlit as st
import pandas as pd
import os
import numpy as np

st.set_page_config(layout="wide")
st.title("Dashboard Combustible")

RUTA_MOV = "Movimientos"
RUTA_PRECIOS = "Precios_especiales"
RUTA_TARJETAS = "FICHERO SOLDRED  Y VIA-T 2025 actual.xlsx"


def limpiar_columnas(cols):
    return (
        cols.astype(str)
        .str.replace("º", "", regex=False)
        .str.replace("N°", "N", regex=False)
        .str.replace("Nº", "N", regex=False)
        .str.strip()
        .str.upper()
        .str.replace("Ó", "O", regex=False)
    )


def normalizar_id(serie, quitar_ceros=False):
    serie = (
        serie.astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
    )

    if quitar_ceros:
        serie = serie.str.lstrip("0")

    return serie


@st.cache_data(ttl=3600, show_spinner="Cargando datos...")
def cargar_datos():
    # =========================
    # 1. CARGAR OPERACIONES
    # =========================
    archivos_mov = [
        f for f in os.listdir(RUTA_MOV)
        if f.lower().endswith(".xlsx")
    ]

    if not archivos_mov:
        return None, "No hay archivos .xlsx en Movimientos"

    archivo_mov = archivos_mov[0]
    ruta_archivo_mov = os.path.join(RUTA_MOV, archivo_mov)

    df_mov = pd.read_excel(ruta_archivo_mov)
    df_mov.columns = limpiar_columnas(df_mov.columns)

    df_mov = df_mov.rename(columns={
        "COD_ESTABL": "CODIGO_SOLRED",
        "NUM_TARJET": "NUM_TARJETA"
    })

    df_mov["FECHA"] = pd.to_datetime(
        df_mov["FEC_OPERAC"],
        format="%Y%m%d",
        errors="coerce"
    ).dt.date

    df_mov["NUM_LITROS"] = pd.to_numeric(
        df_mov["NUM_LITROS"],
        errors="coerce"
    )

    df_mov["IMPORTE"] = pd.to_numeric(
        df_mov["IMPORTE"],
        errors="coerce"
    )

    df_mov["CODIGO_SOLRED"] = normalizar_id(df_mov["CODIGO_SOLRED"])
    df_mov["NUM_TARJETA"] = normalizar_id(df_mov["NUM_TARJETA"], quitar_ceros=True)

    # =========================
    # 2. CARGAR TARJETAS
    # =========================
    df_tar = pd.read_excel(RUTA_TARJETAS)
    df_tar.columns = limpiar_columnas(df_tar.columns)

    df_tar = df_tar.rename(columns={
        "N TARJETA": "NUM_TARJETA",
        "MATRICULA": "MATRICULA",
        "MATRÍCULA": "MATRICULA"
    })

    df_tar = df_tar[["NUM_TARJETA", "MATRICULA"]].copy()

    df_tar["NUM_TARJETA"] = normalizar_id(df_tar["NUM_TARJETA"], quitar_ceros=True)
    df_tar["MATRICULA"] = df_tar["MATRICULA"].astype(str).str.strip()

    df_tar = (
        df_tar
        .replace({"NUM_TARJETA": {"nan": np.nan}, "MATRICULA": {"nan": np.nan}})
        .dropna(subset=["NUM_TARJETA", "MATRICULA"])
        .drop_duplicates(subset=["NUM_TARJETA"], keep="first")
    )

    df_mov = df_mov.merge(
        df_tar,
        on="NUM_TARJETA",
        how="left"
    )

    df_mov["MATRICULA"] = df_mov["MATRICULA"].fillna("SIN ASIGNAR")

    # =========================
    # 3. CARGAR PRECIOS
    # =========================
    precios = []

    for file in os.listdir(RUTA_PRECIOS):
        if not file.lower().endswith(".xlsx"):
            continue

        ruta_precio = os.path.join(RUTA_PRECIOS, file)

        df_precio = pd.read_excel(ruta_precio, header=8)
        df_precio.columns = limpiar_columnas(df_precio.columns)

        df_precio = df_precio.rename(columns={
            "CODIGO SOLRED": "CODIGO_SOLRED",
            "PRECIO FINAL (SIN IVA)": "PRECIO_ESPECIAL"
        })

        if "CODIGO_SOLRED" not in df_precio.columns or "PRECIO_ESPECIAL" not in df_precio.columns:
            continue

        df_precio = df_precio[["CODIGO_SOLRED", "PRECIO_ESPECIAL"]].copy()

        df_precio["CODIGO_SOLRED"] = normalizar_id(df_precio["CODIGO_SOLRED"])
        df_precio["PRECIO_ESPECIAL"] = pd.to_numeric(
            df_precio["PRECIO_ESPECIAL"],
            errors="coerce"
        )

        try:
            fecha_archivo = file.split("_")[1][:8]
            df_precio["FECHA"] = pd.to_datetime(
                fecha_archivo,
                format="%Y%m%d",
                errors="coerce"
            ).date()
        except Exception:
            continue

        precios.append(df_precio)

    if precios:
        df_precios = pd.concat(precios, ignore_index=True)
        df_precios = df_precios.drop_duplicates(
            subset=["CODIGO_SOLRED", "FECHA"],
            keep="first"
        )
    else:
        df_precios = pd.DataFrame(columns=["CODIGO_SOLRED", "FECHA", "PRECIO_ESPECIAL"])

    # =========================
    # 4. CLASIFICAR PRODUCTO
    # =========================
    columnas_producto = [c for c in df_mov.columns if "PROD" in c]

    if not columnas_producto:
        return None, "No se encontró ninguna columna de producto"

    col_prod = columnas_producto[0]

    producto = df_mov[col_prod].astype(str).str.strip().str.upper()

    condiciones = [
        producto.str.startswith("DIE") | producto.str.startswith("DSL"),
        producto.str.startswith("ADB"),
        producto.str.startswith("EFI"),
        producto.str.contains("AUTOPISTA", na=False) | producto.str.contains("VIA T", na=False)
    ]

    valores = ["Diésel", "AdBlue", "Gasolina", "Peajes"]

    df_mov["TIPO_GASTO"] = np.select(
        condiciones,
        valores,
        default="Otros"
    )

    # =========================
    # 5. MERGE PRECIOS
    # =========================
    df = df_mov.merge(
        df_precios,
        on=["CODIGO_SOLRED", "FECHA"],
        how="left"
    )

    precio_real = df["IMPORTE"] / df["NUM_LITROS"]
    df["PRECIO_ESPECIAL"] = df["PRECIO_ESPECIAL"].fillna(precio_real)

    # =========================
    # 6. CALCULOS
    # =========================
    df["IMPORTE_CALCULADO"] = df["NUM_LITROS"] * df["PRECIO_ESPECIAL"]

    rappel = 0.015 / 1.21
    devengo = 0.01 / 1.21

    df["DESCUENTO"] = df["NUM_LITROS"] * (rappel + devengo)
    df["IMPORTE_FINAL"] = df["IMPORTE_CALCULADO"] - df["DESCUENTO"]

    return df, None


df, error = cargar_datos()

if error:
    st.error(error)
    st.stop()

# =========================
# 7. FILTRO FECHA
# =========================
fechas = sorted(df["FECHA"].dropna().unique(), reverse=True)

fecha = st.selectbox(
    "Fecha",
    fechas
)

df_f = df[df["FECHA"] == fecha]

# =========================
# 8. METRICAS
# =========================
df_diesel = df_f[df_f["TIPO_GASTO"] == "Diésel"]
df_adblue = df_f[df_f["TIPO_GASTO"] == "AdBlue"]

litros = df_diesel["NUM_LITROS"].sum()
gasto = df_diesel["IMPORTE_FINAL"].sum()
precio = gasto / litros if litros else 0

gasto_adblue = df_adblue["IMPORTE"].sum()

# =========================
# 9. UI
# =========================
c1, c2, c3, c4 = st.columns(4)

c1.metric("Litros Diésel", f"{litros:,.2f}")
c2.metric("Gasto Diésel (€)", f"{gasto:,.2f}")
c3.metric("Precio Medio €/L", f"{precio:,.2f}")
c4.metric("Gasto AdBlue (€)", f"{gasto_adblue:,.2f}")

# =========================
# 10. GRAFICO
# =========================
graf = (
    df_f
    .groupby(["MATRICULA", "TIPO_GASTO"], as_index=False)["NUM_LITROS"]
    .sum()
)

st.bar_chart(
    graf,
    x="MATRICULA",
    y="NUM_LITROS",
    color="TIPO_GASTO"
)

