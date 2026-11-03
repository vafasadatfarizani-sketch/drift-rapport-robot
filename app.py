import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai

st.set_page_config(page_title="ISMG Driftrapport", page_icon="⚡", layout="wide")

st.title("⚡ ISMG Drift & Prestanda Dashboard")

# Sidopanel för API-nyckel
with st.sidebar:
    st.header("⚙️ Inställningar")
    gemini_key = st.text_input("Google AI Studio API-nyckel", type="password")
    st.info("Klistra in din API-nyckel från Google AI Studio för automatiska AI-analyser.")

# Filuppladdning
st.subheader("📁 Ladda upp CSV-fil")
uploaded_file = st.file_uploader("Släpp din veckorepport eller månads-CSV från Voi här:", type=["csv"])

def process_data(df):
    task_cols = [
        'Battery Swaps', 'Bonus Swaps', 'Deploys', 'Transports', 'Rebalances', 
        'Rescues', 'IFQCs', 'In-Field Repairs', 'Reparks', 'License Plate Swaps', 
        'Marketing Stickers', 'Cleanup Tasks'
    ]
    for col in task_cols + ['Hours Worked', 'Total Tasks']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    df['Regular_Battery_Swaps'] = df['Battery Swaps'] - df['Bonus Swaps']
    
    # Poängmodell: Bonus Swaps = 0.8 p, övriga = 1.0 p
    df['Poäng'] = (
        1.0 * df['Regular_Battery_Swaps'] +
        0.8 * df['Bonus Swaps'] +
        1.0 * df.get('Deploys', 0) +
        1.0 * df.get('Transports', 0) +
        1.0 * df.get('Rebalances', 0) +
        1.0 * df.get('IFQCs', 0) +
        1.0 * df.get('Reparks', 0) +
        1.0 * df.get('Rescues', 0) +
        1.0 * df.get('In-Field Repairs', 0)
    )
    
    if 'Driver' in df.columns:
        df['Driver_Clean'] = df['Driver'].astype(str).str.strip()
    else:
        df['Driver_Clean'] = 'Okänd'
    
    summary = df.groupby('Driver_Clean').agg({
        'Hours Worked': 'sum',
        'Total Tasks': 'sum',
        'Poäng': 'sum',
        'Battery Swaps': 'sum',
        'Bonus Swaps': 'sum',
        'Rebalances': 'sum',
        'IFQCs': 'sum'
    }).reset_index()
    
    summary.rename(columns={'Driver_Clean': 'Driver'}, inplace=True)
    summary['Poäng/hr'] = (summary['Poäng'] / summary['Hours Worked']).round(2)
    summary['Tasks/hr'] = (summary['Total Tasks'] / summary['Hours Worked']).round(2)
    summary['Poäng'] = summary['Poäng'].round(1)
    
    return summary.sort_values(by='Poäng', ascending=False)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    summary_df = process_data(df)
    
    # KPI-kort
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aktiva Förare", len(summary_df))
    c2.metric("Totalt Tasks", int(summary_df['Total Tasks'].sum()))
    c3.metric("Totala Poäng", round(summary_df['Poäng'].sum(), 1))
    c4.metric("Snitt Poäng/hr", round(summary_df['Poäng'].sum() / summary_df['Hours Worked'].sum(), 2))
    
    st.markdown("---")
    
    # Prestandadiagram
    fig = px.bar(
        summary_df, 
        x='Driver', 
        y='Poäng/hr', 
        title="Prestanda: Poäng per Timme (Poäng/hr)",
        color='Poäng/hr',
        color_continuous_scale='Blues'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabell
    st.subheader("📋 Sammanställning per Förare")
    st.dataframe(summary_df, use_container_width=True)
    
    # AI-analys
    if gemini_key:
        st.markdown("---")
        st.subheader("🤖 AI-Analys & Insikter (Google AI Studio)")
        try:
            client = genai.Client(api_key=gemini_key)
            prompt = f"""
            Analysera följande driftrapport för våra förare:
            {summary_df.to_string()}
            
            Skriv en kort, professionell rapport på svenska:
            1. Topp 3 prestationer baserat på Poäng/hr.
            2. Utmärkande förarprestationer.
            3. Rekommendationer och insikter för perioden.
            """
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            st.info(response.text)
        except Exception as e:
            st.error(f"Kunde inte hämta AI-analys: {e}")
else:
    st.info("👆 Ladda upp din CSV-fil ovan för att visa rapporten.")
