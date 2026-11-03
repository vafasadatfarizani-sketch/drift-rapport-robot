import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from google import genai

# Sidaninställningar för mobilskärm
st.set_page_config(page_title="Driftrapport ISMG", page_icon="⚡", layout="wide")

st.title("⚡ Driftrapport & Prestanda")

# Sidopanel för inställningar och inloggning
with st.sidebar:
    st.header("🔑 Inloggningsuppgifter")
    portal_url = st.text_input("Målsajt URL", value="https://example.com/login")
    username = st.text_input("Användarnamn / E-post")
    password = st.text_input("Lösenord", type="password")
    gemini_key = st.text_input("Google AI Studio API-nyckel", type="password")
    
    st.markdown("---")
    update_btn = st.button("🔄 Hämta & Uppdatera Data", type="primary")

# Funktion för poängberäkning
def process_data(df):
    task_cols = ['Battery Swaps', 'Bonus Swaps', 'Deploys', 'Transports', 'Rebalances', 'IFQCs', 'Reparks', 'Rescues']
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
        1.0 * df.get('Rescues', 0)
    )
    
    summary = df.groupby('Driver').agg({
        'Hours Worked': 'sum',
        'Total Tasks': 'sum',
        'Poäng': 'sum',
        'Battery Swaps': 'sum',
        'Bonus Swaps': 'sum',
        'Rebalances': 'sum',
        'IFQCs': 'sum'
    }).reset_index()
    
    summary['Poäng/hr'] = (summary['Poäng'] / summary['Hours Worked']).round(2)
    summary['Tasks/hr'] = (summary['Total Tasks'] / summary['Hours Worked']).round(2)
    summary['Poäng'] = summary['Poäng'].round(1)
    
    return summary.sort_values(by='Poäng', ascending=False)

if update_btn:
    if not username or not password:
        st.error("Vänligen ange användarnamn och lösenord i sidomenyn.")
    else:
        with st.spinner("Kopplar upp mot portalen och hämtar CSV-fil..."):
            try:
                # Inloggningssession mot portalen
                session = requests.Session()
                login_payload = {"username": username, "password": password}
                
                # Anpassa URL utefter er portal
                res = session.post(portal_url, data=login_payload)
                
                # Exempel på CSV-inläsning (ersätts med portalens CSV-nedladdningslänk)
                # csv_url = "https://example.com/export/csv"
                # csv_res = session.get(csv_url)
                # df = pd.read_csv(io.StringIO(csv_res.text))
                
                st.success("Data hämtades framgångsrikt!")
            except Exception as e:
                st.warning("Ett fel uppstod vid inloggning/hämtning. Kontrollera uppgifterna.")

# Ladda upp fil manuellt som reservalternativ
uploaded_file = st.file_uploader("Eller ladda upp CSV-fil manuellt här:", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    summary_df = process_data(df)
    
    # Nyckeltal i toppen
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Aktiva Förare", len(summary_df))
    col2.metric("Totalt Antal Tasks", int(summary_df['Total Tasks'].sum()))
    col3.metric("Totala Poäng", round(summary_df['Poäng'].sum(), 1))
    col4.metric("Snitt Poäng/hr", round(summary_df['Poäng'].sum() / summary_df['Hours Worked'].sum(), 2))
    
    st.markdown("---")
    
    # Stapeldiagram over Poang/hr
    fig = px.bar(
        summary_df, 
        x='Driver', 
        y='Poäng/hr', 
        title="Poäng per Timme (Poäng/hr)",
        color='Poäng/hr',
        color_continuous_scale='Blues'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Detaljerad Tabell
    st.subheader("📋 Månadssammanställning")
    st.dataframe(summary_df, use_container_width=True)
    
    # AI-analys via Gemini
    if gemini_key:
        st.subheader("🤖 AI-Analys & Insikter (Gemini)")
        try:
            client = genai.Client(api_key=gemini_key)
            prompt = f"""
            Analysera följande månadssammanställning för våra förare:
            {summary_df.to_string()}
            
            Skriv en kort, professionell rapport på svenska som täcker:
            1. Topp 3 prestationer baserat på Poäng/hr.
            2. Vilka förare som utmärkt sig positivt.
            3. Rekommendationer för förbättringar.
            """
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            st.info(response.text)
        except Exception as e:
            st.error(f"Kunde inte generera AI-analys: {e}")
