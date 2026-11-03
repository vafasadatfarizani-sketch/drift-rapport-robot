import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai
import asyncio
from playwright.async_api import async_playwright
import io

st.set_page_config(page_title="Driftrapport Voi 3PL", page_icon="⚡", layout="wide")

st.title("⚡ Driftrapport & Prestanda (Voisibility 3PL)")

# Sidopanel för inloggning & val
with st.sidebar:
    st.header("🔑 Voisibility 3PL Inloggning")
    username = st.text_input("Användarnamn / E-post")
    password = st.text_input("Lösenord", type="password")
    
    city = st.selectbox("Välj stad", ["Stockholm", "Uppsala"])
    
    col_d1, col_d2 = st.columns(2)
    start_date = col_d1.date_input("Startdatum")
    end_date = col_d2.date_input("Slutdatum")
    
    st.markdown("---")
    st.header("🤖 Google AI Studio")
    gemini_key = st.text_input("Gemini API-nyckel", type="password")
    
    st.markdown("---")
    fetch_btn = st.button("🔄 Hämta & Uppdatera Data", type="primary")

# Poängberäkningsfunktion
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

# Automatisk hämtning med Playwright
async def fetch_csv_from_voi(user, pwd, selected_city):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Gå till inloggningssidan
        await page.goto("https://voisibility-3pl.voi.com/login")
        await page.wait_for_load_state("networkidle")
        
        # 2. Logga in
        await page.fill("input[type='email'], input[name='username'], input[name='email']", user)
        await page.fill("input[type='password']", pwd)
        await page.click("button[type='submit'], input[type='submit']")
        await page.wait_for_load_state("networkidle")
        
        # 3. Välj rullgardinsmenyer baserat på stad
        if selected_city == "Uppsala":
            partner_val = "Mälaren 3PL"
            city_val = "Uppsala"
        else:
            partner_val = "Stockholm 3PL"
            city_val = "Stockholm"
            
        await page.select_option("select:nth-of-type(1)", label=partner_val)
        await page.select_option("select:nth-of-type(2)", label=city_val)
        
        # 4. Klicka på Fetch CSV och hämta nedladdningen
        async with page.expect_download() as download_info:
            await page.click("button:has-text('Fetch CSV'), input[value='Fetch CSV'], text='Fetch CSV'")
            
        download = await download_info.value
        download_path = await download.path()
        
        with open(download_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        await browser.close()
        return content

# Körs när man trycker på knappen
if fetch_btn:
    if not username or not password:
        st.error("Vänligen ange användarnamn och lösenord.")
    else:
        with st.spinner(f"Loggar in och hämtar CSV för {city}..."):
            try:
                # Kör den asynkrona hämtningen
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                csv_text = loop.run_until_complete(fetch_csv_from_voi(username, password, city))
                
                df_downloaded = pd.read_csv(io.StringIO(csv_text))
                st.session_state['df'] = df_downloaded
                st.success("Datan har hämtats automatiskt!")
            except Exception as err:
                st.warning(f"Kunde inte automatiserat hämta datan direkt. Du kan använda manuell uppladdning nedan. Felkod: {err}")

# Manuell uppladdning som reserv
uploaded_file = st.file_uploader("Eller ladda upp CSV manuellt här:", type=["csv"])
if uploaded_file is not None:
    st.session_state['df'] = pd.read_csv(uploaded_file)

# Visa resultat om data finns
if 'df' in st.session_state:
    summary_df = process_data(st.session_state['df'])
    
    st.markdown("---")
    # Nyckeltal
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aktiva Förare", len(summary_df))
    c2.metric("Totalt Tasks", int(summary_df['Total Tasks'].sum()))
    c3.metric("Totala Poäng", round(summary_df['Poäng'].sum(), 1))
    c4.metric("Snitt Poäng/hr", round(summary_df['Poäng'].sum() / summary_df['Hours Worked'].sum(), 2))
    
    st.markdown("---")
    
    # Diagram
    fig = px.bar(
        summary_df, 
        x='Driver', 
        y='Poäng/hr', 
        title=f"Poäng per Timme ({city})",
        color='Poäng/hr',
        color_continuous_scale='Blues'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabell
    st.subheader("📋 Månadssammanställning")
    st.dataframe(summary_df, use_container_width=True)
    
    # AI-analys via Gemini
    if gemini_key:
        st.subheader("🤖 AI-Analys & Insikter (Gemini)")
        try:
            client = genai.Client(api_key=gemini_key)
            prompt = f"""
            Analysera följande månadsrapport för våra förare i {city}:
            {summary_df.to_string()}
            
            Skriv en kort, professionell rapport på svenska:
            1. Topp 3 prestationer baserat på Poäng/hr.
            2. Vilka förare som utmärkt sig mest.
            3. Rekommendationer för förbättring.
            """
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            st.info(response.text)
        except Exception as e:
            st.error(f"AI-fel: {e}")
