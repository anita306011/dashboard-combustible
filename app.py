import streamlit as st
import pandas as pd
import os

st.set_page_config(layout="wide")

st.title("🚛 Dashboard Combustible")

# =========================
# RUTAS
# =========================
ruta_mov = "Movimientos"
ruta_precios = "Precios_especiales"
ruta_tarjetas = "FICHERO SOLDRED  Y VIA-T 2025 actual.xlsx"

# =========================
# 1. CARGAR OPERACIONES
# =========================
archivos_mov = [f for f in os.listdir(ruta_mov) if f.endswith(".xlsx")]

if len(archivos_mov) == 0:
    st.error("No hay archivos .xlsx en Movimientos")
    st.stop()

archivo_mov = archivos_mov[0]
st.write("📂 Archivo operaciones:", archivo_mov)

df_mov = pd.read_excel(os.path.join(ruta_mov, archivo_mov))

# LIMPIAR COLUMNAS
df_mov.columns = (
    df_mov.columns
    .str.replace("º", "")
    .str.strip()
    .str.upper()
)

# FECHA
df_mov["FECHA"] = pd.to_datetime(
    df_mov["FEC_OPERAC"],
    format="%Y%m%d"
).dt.date

# COD_ESTABL -> CODIGO_SOLRED
df_mov = df_mov.rename(columns={
    "COD_ESTABL": "CODIGO_SOLRED"
})

# CONVERTIR NUM_LITROS A NUMÉRICO
df_mov["NUM_LITROS"] = pd.to_numeric(
    df_mov["NUM_LITROS"],
    errors="coerce"
)

# 🔥 IMPORTANTÍSIMO
df_mov["CODIGO_SOLRED"] = (
    df_mov["CODIGO_SOLRED"]
    .astype(str)
    .str.strip()
)

# NORMALIZAR TARJETA
df_mov = df_mov.rename(columns={"NUM_TARJET": "NUM_TARJETA"})

# =========================
# 2. CARGAR TARJETAS
# =========================
df_tar = pd.read_excel(ruta_tarjetas)

# LIMPIAR NOMBRES DE COLUMNAS
df_tar.columns = (
    df_tar.columns
    .str.replace("º", "")
    .str.replace("N°", "N")
    .str.replace("Nº", "N")
    .str.strip()
    .str.upper()
)

# RENOMBRAR COLUMNAS CLAVE
df_tar = df_tar.rename(columns={
    "N TARJETA": "NUM_TARJETA",
    "MATRÍCULA": "MATRICULA",
    "MATRICULA": "MATRICULA"
})

# NORMALIZAR NUMERO DE TARJETA EN TARJETAS
df_tar["NUM_TARJETA"] = (
    df_tar["NUM_TARJETA"]
    .astype(str)
    .str.strip()
    .str.replace(".0", "", regex=False)
    .str.lstrip("0")          # ← ELIMINA CEROS INICIALES
)

# NORMALIZAR NUMERO DE TARJETA EN OPERACIONES
df_mov["NUM_TARJETA"] = (
    df_mov["NUM_TARJETA"]
    .astype(str)
    .str.strip()
    .str.replace(".0", "", regex=False)
    .str.lstrip("0")          # ← ELIMINA CEROS INICIALES
)

# LIMPIAR MATRICULA
df_tar["MATRICULA"] = (
    df_tar["MATRICULA"]
    .astype(str)
    .str.strip()
)

# ELIMINAR FILAS SIN DATOS
df_tar = df_tar.dropna(subset=["NUM_TARJETA", "MATRICULA"])

# SI HAY TARJETAS DUPLICADAS, QUEDARSE CON LA PRIMERA
df_tar = df_tar.drop_duplicates(subset=["NUM_TARJETA"], keep="first")

# MERGE PARA ASIGNAR MATRÍCULA
df_mov = df_mov.merge(
    df_tar[["NUM_TARJETA", "MATRICULA"]],
    on="NUM_TARJETA",
    how="left"
)

# SI DESPUÉS DEL MERGE LA COLUMNA VIENE COMO MATRICULA_y,
# MATRICULA_x, etc., localizamos automáticamente cuál es
# la columna correcta procedente del fichero de tarjetas.
columnas_matricula = [
    c for c in df_mov.columns
    if "MATRICULA" in c and c != "MATRICULA_x"
]

# TOMAR LA PRIMERA COLUMNA ENCONTRADA
if len(columnas_matricula) > 0:
    df_mov = df_mov.rename(
        columns={columnas_matricula[0]: "MATRICULA"}
    )
else:
    # SI NO EXISTE NINGUNA, CREARLA VACÍA
    df_mov["MATRICULA"] = None

# RELLENAR VACÍOS
df_mov["MATRICULA"] = df_mov["MATRICULA"].fillna("SIN ASIGNAR")

# =========================
# 3. CARGAR PRECIOS
# =========================
lista = []

for file in os.listdir(ruta_precios):
    if file.endswith(".xlsx"):

        df = pd.read_excel(
        os.path.join(ruta_precios, file),
        header=8
        )

        # RENOMBRAR PRIMERO
        df = df.rename(columns={"Código Solred": "CODIGO_SOLRED"})

        df["CODIGO_SOLRED"] = (
            df["CODIGO_SOLRED"]
            .astype(str)
            .str.strip()
        )

        # LIMPIAR COLUMNAS
        df.columns = (
            df.columns
            .str.strip()
            .str.upper()
            .str.replace("Ó", "O")
        )

        df = df.rename(columns={
            "PRECIO FINAL (SIN IVA)": "PRECIO_ESPECIAL"
        })

        fecha = file.split("_")[1][:8]
        df["FECHA"] = pd.to_datetime(
            fecha,
            format="%Y%m%d"
        ).date()

        lista.append(df)

df_precios = pd.concat(lista, ignore_index=True)

# ELIMINAR DUPLICADOS PRECIOS
df_precios = df_precios.drop_duplicates(
    subset=["CODIGO_SOLRED", "FECHA"]
)

# =========================
# 4. CLASIFICAR PRODUCTO
# =========================

def tipo(x):

    if pd.isna(x):
        return "Otros"

    x = str(x).strip().upper()

    # DIESEL (incluye DIE+ y DSL de Portugal)
    if x.startswith("DIE") or x.startswith("DSL"):
        return "Diésel"

    # ADBLUE
    elif x.startswith("ADB"):
        return "AdBlue"

    # GASOLINA
    elif x.startswith("EFI"):
        return "Gasolina"

    # PEAJES
    elif "AUTOPISTA" in x or "VIA T" in x:
        return "Peajes"

    else:
        return "Otros"

# DETECTAR COLUMNA PRODUCTO
col_prod = [c for c in df_mov.columns if "PROD" in c][0]

# CREAR TIPO_GASTO
df_mov["TIPO_GASTO"] = df_mov[col_prod].apply(tipo)


# =========================
# 5. MERGE PRECIOS
# =========================

# NORMALIZAR
df_mov["CODIGO_SOLRED"] = (
    df_mov["CODIGO_SOLRED"]
    .astype(str)
    .str.strip()
)

df_precios["CODIGO_SOLRED"] = (
    df_precios["CODIGO_SOLRED"]
    .astype(str)
    .str.strip()
)

# FECHAS SOLO DIA
df_mov["FECHA"] = pd.to_datetime(df_mov["FECHA"]).dt.date
df_precios["FECHA"] = pd.to_datetime(df_precios["FECHA"]).dt.date

# MERGE
df = pd.merge(
    df_mov,
    df_precios[
        ["CODIGO_SOLRED", "FECHA", "PRECIO_ESPECIAL"]
    ],
    on=["CODIGO_SOLRED", "FECHA"],
    how="left"
)

# SI NO HAY PRECIO ESPECIAL → USAR IMPORTE REAL
df["PRECIO_ESPECIAL"] = df["PRECIO_ESPECIAL"].fillna(
    df["IMPORTE"] / df["NUM_LITROS"]
)

# =========================
# 6. CALCULOS
# =========================
df["IMPORTE_CALCULADO"] = df["NUM_LITROS"] * df["PRECIO_ESPECIAL"]

rappel = 0.015 / 1.21
devengo = 0.01 / 1.21

df["DESCUENTO"] = df["NUM_LITROS"] * (rappel + devengo)

df["IMPORTE_FINAL"] = df["IMPORTE_CALCULADO"] - df["DESCUENTO"]

# =========================
# 7. FILTRO FECHA
# =========================
fecha = st.selectbox(
    "📅 Fecha",
    sorted(df["FECHA"].dropna().unique(), reverse=True)
)

df_f = df[df["FECHA"] == fecha]


# =========================
# 8. MÉTRICAS
# =========================
df_diesel = df_f[df_f["TIPO_GASTO"] == "Diésel"]
df_adblue = df_f[df_f["TIPO_GASTO"] == "AdBlue"]

litros = df_diesel["NUM_LITROS"].sum()
gasto = df_diesel["IMPORTE_FINAL"].sum()
precio = gasto / litros if litros != 0 else 0

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
# 10. GRÁFICO
# =========================
graf = df_f.groupby(["MATRICULA", "TIPO_GASTO"])["NUM_LITROS"].sum().reset_index()

st.bar_chart(
    graf,
    x="MATRICULA",
    y="NUM_LITROS",
    color="TIPO_GASTO"
)
