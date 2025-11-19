import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

# --- CONFIGURATION ---
SHEET_NAME = 'Tugolov combined questionnaire(Responses)'
CREDENTIALS_FILE = 'credentials.json'

# --- CONNECT TO GOOGLE ---
@st.cache_resource
def get_data():
    try:
        if "gcp_json" in st.secrets:
            creds_dict = json.loads(st.secrets["gcp_json"])
            gc = gspread.service_account_from_dict(creds_dict)
        else:
            gc = gspread.service_account(filename=CREDENTIALS_FILE)
            
        sh = gc.open(SHEET_NAME)
        worksheet = sh.get_worksheet(0) 
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.stop()

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="EMG Dashboard", layout="wide")
    
    data = get_data()
    df = pd.DataFrame(data)

    st.sidebar.header("📅 Select Pay Period")
    
    if not df.empty:
        # 1. CLEAN DATES
        if 'name' in df.columns:
            df = df[df['name'].astype(str).str.strip() != ""]
        
        df['Date Object'] = pd.to_datetime(df['Date seen'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Date Object'])

        # 2. CALC FEES
        def calc_fee(row):
            # Convert to lowercase so "NON CTS" becomes "non cts"
            t = str(row.get("Type of encounter", "")).lower()
            
            if "new consult" in t: return 85.00
            if "non cts" in t: return 65.00  # <--- This catches your specific case
            if "follow up" in t: return 65.00
            
            return 0.00

        df['Fee'] = df.apply(calc_fee, axis=1)

        # 3. MONTH SELECTOR
        df['Month_Year'] = df['Date Object'].dt.strftime('%B %Y')
        available_months = sorted(df['Month_Year'].unique(), key=lambda x: datetime.strptime(x, '%B %Y'), reverse=True)
        
        if available_months:
            current_month_str = datetime.now().strftime('%B %Y')
            default_index = available_months.index(current_month_str) if current_month_str in available_months else 0
            
            selected_month = st.sidebar.selectbox("Choose Month", available_months, index=default_index)
            monthly_df = df[df['Month_Year'] == selected_month]

            # 4. SPLIT PAY PERIODS
            period_1 = monthly_df[monthly_df['Date Object'].dt.day <= 15]
            period_2 = monthly_df[monthly_df['Date Object'].dt.day > 15]

            col1, col2 = st.columns([3, 1])
            with col1: st.title(f"📊 Earnings for {selected_month}")
            with col2: 
                if st.button("🔄 REFRESH"): st.rerun()

            st.markdown("### 💸 Paycheck Breakdown")
            m1, m2, m3 = st.columns(3)
            m1.metric("🗓️ 1st - 15th", f"${period_1['Fee'].sum():,.2f}", f"{len(period_1)} patients")
            m2.metric("🗓️ 16th - End", f"${period_2['Fee'].sum():,.2f}", f"{len(period_2)} patients")
            m3.metric("💰 Month Total", f"${monthly_df['Fee'].sum():,.2f}", "Gross Income")

            st.divider()
            
            wanted_cols = ["Date seen", "name", "Type of encounter", "Fee", "finalized report ?"]
            final_cols = [c for c in wanted_
