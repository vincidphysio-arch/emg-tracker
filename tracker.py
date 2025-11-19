import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

# --- CONFIGURATION ---
SHEET_NAME = 'Tugolov combined questionnaire(Responses)'
CREDENTIALS_FILE = 'credentials.json'

# --- CONNECT TO GOOGLE ---
# 1. We cache the CONNECTION so we don't log in every time (Fast)
@st.cache_resource
def get_connection():
    try:
        if "gcp_json" in st.secrets:
            creds_dict = json.loads(st.secrets["gcp_json"])
            gc = gspread.service_account_from_dict(creds_dict)
        else:
            gc = gspread.service_account(filename=CREDENTIALS_FILE)
        return gc
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.stop()

# 2. We DO NOT cache the data, so it updates instantly
def get_data():
    gc = get_connection()
    sh = gc.open(SHEET_NAME)
    worksheet = sh.get_worksheet(0) 
    return worksheet.get_all_records()

# --- DASHBOARD ---
def main():
    st.set_page_config(page_title="EMG Dashboard", layout="wide")
    
    # Button to force reload
    if st.sidebar.button("🔄 FORCE REFRESH DATA"):
        st.cache_data.clear()
        st.rerun()

    data = get_data()
    df = pd.DataFrame(data)

    st.title("📊 Live EMG Earnings")

    if not df.empty:
        # 1. CLEAN DATES
        if 'name' in df.columns:
            df = df[df['name'].astype(str).str.strip() != ""]
        
        # Convert dates
        df['Date Object'] = pd.to_datetime(df['Date seen'], dayfirst=True, errors='coerce')
        
        # WARNING SYSTEM: Check for missing dates
        missing_dates = df[df['Date Object'].isna()]
        if not missing_dates.empty:
            st.warning(f"⚠️ Warning: {len(missing_dates)} patients have a missing or broken 'Date seen'. They are hidden.")
            with st.expander("See patients with missing dates"):
                st.dataframe(missing_dates)

        df = df.dropna(subset=['Date Object'])

        # 2. CALC FEES
        def calc_fee(row):
            t = str(row.get("Type of encounter", "")).lower()
            if "new consult" in t: return 85.00
            if "non cts" in t: return 65.00
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

            st.markdown(f"### 📅 {selected_month}")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("🗓️ 1st - 15th", f"${period_1['Fee'].sum():,.2f}", f"{len(period_1)} patients")
            m2.metric("🗓️ 16th - End", f"${period_2['Fee'].sum():,.2f}", f"{len(period_2)} patients")
            m3.metric("💰 Month Total", f"${monthly_df['Fee'].sum():,.2f}", "Gross Income")

            st.divider()
            
            # TABLE
            wanted_cols = ["Date seen", "name", "Type of encounter", "Fee", "finalized report ?"]
            final_cols = [c for c in wanted_cols if c in monthly_df.columns]
            
            st.dataframe(monthly_df.sort_values(by="Date Object", ascending=False)[final_cols], use_container_width=True, hide_index=True)
        else:
            st.warning("No valid dates found.")
    else:
        st.info("No data found.")

if __name__ == "__main__":
    main()
