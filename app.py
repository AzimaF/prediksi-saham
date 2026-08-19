import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date
import warnings
warnings.filterwarnings("ignore")

# ─── Google Sheets Config ────────────────────────────────────────────────────
SPREADSHEET_ID  = "1NXkbSNfIPVLIHYAynesY20jzNpboBSzpquVrOE08gXM"
SPREADSHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit?gid=0#gid=0"


def _get_gsheet_client():
    """
    Buat koneksi ke Google Sheets menggunakan service account credentials
    yang disimpan di st.secrets.[gcp_service_account].
    Return None jika credentials tidak tersedia (mode tanpa API).
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception:
        return None


def save_to_gsheet(ticker: str, close: float, model_name: str, horizon: int,
                   fdf: pd.DataFrame, prob_up: float, prob_down: float) -> tuple:
    """
    Simpan hasil prediksi ke Google Spreadsheet.
    fdf: DataFrame prediksi dengan index=Tanggal, kolom=[Hari, Prediksi Harga, ...]
    Return: (success: bool, message: str)
    """
    client = _get_gsheet_client()
    if client is None:
        return False, "credentials_missing"

    try:
        sh  = client.open_by_key(SPREADSHEET_ID)

        # Cari / buat sheet bernama ticker (misal "BBCA")
        sheet_name = ticker.replace(".JK", "")
        try:
            ws = sh.worksheet(sheet_name)
        except Exception:
            ws = sh.add_worksheet(title=sheet_name, rows="500", cols="10")
            # Header
            header = [
                "Disimpan", "Model", "Horizon",
                "Harga Saat Ini", "Prob Naik (%)", "Prob Turun (%)",
                "Tanggal Prediksi", "Hari", "Prediksi Harga (Rp)",
                "Batas Bawah CI95% (Rp)", "Batas Atas CI95% (Rp)", "Perubahan %"
            ]
            ws.append_row(header, value_input_option="USER_ENTERED")

        saved_at = datetime.now().strftime("%d %b %Y %H:%M")
        rows_to_add = []
        fdf_reset = fdf.reset_index()

        for _, row in fdf_reset.iterrows():
            tanggal = str(row.get("Tanggal", ""))
            hari    = str(row.get("Hari", ""))
            pred    = float(row.get("Prediksi Harga", 0))
            lower   = float(row.get("Batas Bawah (CI 95%)", 0)) if "Batas Bawah (CI 95%)" in row else ""
            upper   = float(row.get("Batas Atas (CI 95%)", 0))  if "Batas Atas (CI 95%)"  in row else ""
            pct     = str(row.get("Perubahan %", ""))           if "Perubahan %"           in row else ""
            rows_to_add.append([
                saved_at, model_name, f"{horizon} hari",
                round(close, 0), round(prob_up * 100, 1), round(prob_down * 100, 1),
                tanggal, hari, round(pred, 0),
                round(lower, 0) if lower != "" else "",
                round(upper, 0) if upper != "" else "",
                pct
            ])

        # Tambahkan pemisah kosong sebelum batch baru
        ws.append_row(["" ] * 12, value_input_option="USER_ENTERED")
        ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")
        return True, f"✅ {len(rows_to_add)} baris prediksi berhasil disimpan ke sheet '{sheet_name}'!"

    except Exception as e:
        return False, f"error: {str(e)}"

# ─── Indonesia Stock Exchange (BEI) Holidays ────────────────────────────────────
def get_indonesia_holidays(year: int) -> set:
    """
    Daftar hari libur resmi BEI (Bursa Efek Indonesia).
    Sumber: Pengumuman resmi BEI. Mencakup 2025-2026.
    """
    holidays_2025 = {
        date(2025, 1, 1),   # Tahun Baru 2025
        date(2025, 1, 27),  # Isra Mi'raj
        date(2025, 1, 28),  # Cuti Bersama Isra Mi'raj
        date(2025, 1, 29),  # Tahun Baru Imlek
        date(2025, 3, 28),  # Hari Raya Nyepi
        date(2025, 3, 29),  # Cuti Bersama Nyepi
        date(2025, 3, 31),  # Hari Raya Idul Fitri
        date(2025, 4, 1),   # Hari Raya Idul Fitri
        date(2025, 4, 2),   # Cuti Bersama Idul Fitri
        date(2025, 4, 3),   # Cuti Bersama Idul Fitri
        date(2025, 4, 4),   # Cuti Bersama Idul Fitri
        date(2025, 4, 7),   # Cuti Bersama Idul Fitri
        date(2025, 4, 18),  # Wafat Isa Almasih (Good Friday)
        date(2025, 5, 1),   # Hari Buruh Internasional
        date(2025, 5, 12),  # Hari Raya Waisak
        date(2025, 5, 13),  # Cuti Bersama Waisak
        date(2025, 5, 29),  # Kenaikan Isa Almasih
        date(2025, 6, 1),   # Hari Lahir Pancasila
        date(2025, 6, 6),   # Idul Adha
        date(2025, 6, 27),  # Tahun Baru Islam 1447H
        date(2025, 8, 17),  # HUT Kemerdekaan RI
        date(2025, 9, 5),   # Maulid Nabi Muhammad SAW
        date(2025, 12, 25), # Hari Rnatal
        date(2025, 12, 26), # Cuti Bersama Natal
    }
    holidays_2026 = {
        date(2026, 1, 1),   # Tahun Baru 2026
        date(2026, 1, 16),  # Isra Mi'raj
        date(2026, 1, 17),  # Tahun Baru Imlek
        date(2026, 3, 19),  # Hari Raya Nyepi
        date(2026, 3, 20),  # Hari Raya Idul Fitri (perkiraan)
        date(2026, 3, 23),  # Cuti Bersama Idul Fitri
        date(2026, 3, 24),  # Cuti Bersama Idul Fitri
        date(2026, 3, 25),  # Cuti Bersama Idul Fitri
        date(2026, 3, 26),  # Cuti Bersama Idul Fitri
        date(2026, 4, 2),   # Hari Raya Wafat Isa Almasih
        date(2026, 5, 1),   # Hari Buruh Internasional
        date(2026, 5, 14),  # Kenaikan Isa Almasih
        date(2026, 5, 27),  # Hari Raya Waisak
        date(2026, 5, 28),  # Idul Adha (perkiraan)
        date(2026, 6, 1),   # Hari Lahir Pancasila
        date(2026, 8, 17),  # HUT Kemerdekaan RI
        date(2026, 9, 16),  # Maulid Nabi Muhammad SAW
        date(2026, 12, 25), # Hari Natal
        date(2026, 12, 24), # Cuti Bersama Natal
    }
    all_holidays = holidays_2025 | holidays_2026
    return {h for h in all_holidays if h.year == year}


def is_trading_day(d: date) -> bool:
    """Returns True jika hari d adalah hari trading BEI (Senin-Jumat, bukan libur)."""
    if d.weekday() >= 5:  # Sabtu=5, Minggu=6
        return False
    holidays = get_indonesia_holidays(d.year)
    return d not in holidays


def get_trading_days(start_date: datetime, periods: int) -> pd.DatetimeIndex:
    """
    Menghasilkan DatetimeIndex berisi hari-hari trading BEI mulai dari start_date,
    sebanyak `periods` hari trading (tidak termasuk weekend dan hari libur nasional).
    """
    trading_days = []
    current = start_date.date() if isinstance(start_date, datetime) else start_date
    checked = 0
    max_iter = periods * 3  # batasan iterasi untuk menghindari infinite loop
    while len(trading_days) < periods and checked < max_iter:
        if is_trading_day(current):
            trading_days.append(current)
        current += timedelta(days=1)
        checked += 1
    return pd.DatetimeIndex([pd.Timestamp(d) for d in trading_days])

# ─── Constants ──────────────────────────────────────────────────────────────────
IDX_STOCK_LISTS = {
    "LQ45": ["AMMN.JK", "ANTM.JK", "ARTO.JK", "ASII.JK", "BBCA.JK", "BBNI.JK", "BBRI.JK", "BBTN.JK", "BMRI.JK", "BRIS.JK", "BRPT.JK", "BUKA.JK", "CPIN.JK", "EMTK.JK", "ESSA.JK", "EXCL.JK", "GGRM.JK", "GOTO.JK", "HRUM.JK", "ICBP.JK", "INCO.JK", "INDF.JK", "INKP.JK", "INTP.JK", "ISAT.JK", "ITMG.JK", "KLBF.JK", "MAPI.JK", "MBMA.JK", "MDKA.JK", "MEDC.JK", "MTEL.JK", "PGAS.JK", "PGEO.JK", "PTBA.JK", "PTPP.JK", "SIDO.JK", "SMGR.JK", "SRTG.JK", "TLKM.JK", "TOWR.JK", "TPIA.JK", "UNTR.JK", "UNVR.JK", "WIKA.JK"],
    "IDX30": ["AMMN.JK", "ANTM.JK", "ARTO.JK", "ASII.JK", "BBCA.JK", "BBNI.JK", "BBRI.JK", "BBTN.JK", "BMRI.JK", "BRIS.JK", "BRPT.JK", "CPIN.JK", "ESSA.JK", "EXCL.JK", "GOTO.JK", "HRUM.JK", "ICBP.JK", "INCO.JK", "INDF.JK", "INKP.JK", "ISAT.JK", "KLBF.JK", "MAPI.JK", "MDKA.JK", "MEDC.JK", "PGAS.JK", "PTBA.JK", "TLKM.JK", "TOWR.JK", "UNVR.JK"],
    "BUMN": ["BBNI.JK", "BBRI.JK", "BBTN.JK", "BMRI.JK", "PGAS.JK", "PTBA.JK", "PTPP.JK", "SMGR.JK", "TLKM.JK", "WIKA.JK", "ANTM.JK", "TINS.JK", "JSMR.JK", "PGEO.JK"]
}


# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="📈 Prediksi Saham Indonesia",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    * { font-family: 'Inter', sans-serif; box-sizing: border-box; }

    .stApp {
        background: linear-gradient(135deg, #060b18 0%, #0a1228 50%, #080e1e 100%);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a1228 0%, #0d1630 100%);
        border-right: 1px solid rgba(99, 179, 237, 0.15);
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stTextInput label,
    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stRadio label {
        color: #64748b !important;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }

    .metric-card {
        background: linear-gradient(135deg, rgba(13,20,40,0.95), rgba(20,30,55,0.8));
        border: 1px solid rgba(99,179,237,0.18);
        border-radius: 16px;
        padding: 18px 22px;
        margin: 5px 0;
        backdrop-filter: blur(12px);
        transition: all 0.35s cubic-bezier(0.4,0,0.2,1);
        box-shadow: 0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
        position: relative;
        overflow: hidden;
        min-height: 90px;
    }
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(99,179,237,0.4), transparent);
    }
    .metric-card:hover {
        border-color: rgba(99,179,237,0.45);
        box-shadow: 0 12px 40px rgba(59,130,246,0.2), inset 0 1px 0 rgba(255,255,255,0.06);
        transform: translateY(-3px);
    }
    .metric-label {
        color: #475569;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 8px;
    }
    .metric-value {
        color: #f1f5f9;
        font-size: 1.25rem;
        font-weight: 700;
        line-height: 1.2;
        word-break: break-word;
    }
    .metric-delta-pos {
        color: #4ade80;
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 6px;
    }
    .metric-delta-neg {
        color: #f87171;
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 6px;
    }

    .section-header {
        background: linear-gradient(90deg, rgba(59,130,246,0.12), rgba(139,92,246,0.06), transparent);
        border-left: 3px solid #3b82f6;
        border-radius: 0 10px 10px 0;
        padding: 10px 20px;
        margin: 28px 0 18px 0;
        color: #e2e8f0;
        font-size: 1rem;
        font-weight: 700;
        letter-spacing: 0.01em;
    }

    .hero-header {
        background: linear-gradient(135deg, rgba(15,30,70,0.7), rgba(30,15,70,0.6));
        border: 1px solid rgba(99,179,237,0.2);
        border-radius: 24px;
        padding: 32px 48px;
        margin-bottom: 24px;
        text-align: center;
        backdrop-filter: blur(20px);
        position: relative;
        overflow: hidden;
        box-shadow: 0 8px 48px rgba(0,0,0,0.5);
    }
    .hero-title {
        color: #f1f5f9;
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #34d399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 8px 0;
        letter-spacing: -0.02em;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(59,130,246,0.15);
        border: 1px solid rgba(59,130,246,0.3);
        color: #93c5fd;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        margin: 0 4px;
    }

    /* IHSG Panel */
    .ihsg-panel {
        background: linear-gradient(135deg, rgba(10,18,40,0.98), rgba(15,25,55,0.95));
        border: 1px solid rgba(99,179,237,0.25);
        border-radius: 20px;
        padding: 24px 30px;
        margin-bottom: 24px;
        backdrop-filter: blur(16px);
        box-shadow: 0 8px 40px rgba(0,0,0,0.5);
        position: relative;
        overflow: hidden;
    }
    .ihsg-panel::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6, #10b981);
    }
    .ihsg-title {
        color: #93c5fd;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 12px;
    }
    .ihsg-price {
        font-size: 2rem;
        font-weight: 800;
        color: #f1f5f9;
        line-height: 1;
        letter-spacing: -0.02em;
    }
    .ihsg-sentiment-bullish {
        background: rgba(34,197,94,0.12);
        border: 1px solid rgba(34,197,94,0.35);
        color: #4ade80;
        padding: 6px 16px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
    }
    .ihsg-sentiment-bearish {
        background: rgba(239,68,68,0.12);
        border: 1px solid rgba(239,68,68,0.35);
        color: #f87171;
        padding: 6px 16px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
    }
    .ihsg-sentiment-neutral {
        background: rgba(245,158,11,0.12);
        border: 1px solid rgba(245,158,11,0.35);
        color: #fbbf24;
        padding: 6px 16px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
    }

    .price-display {
        font-size: 2.4rem;
        font-weight: 800;
        color: #f1f5f9;
        line-height: 1;
        letter-spacing: -0.02em;
    }
    .price-change-pos { font-size: 1rem; font-weight: 600; color: #4ade80; }
    .price-change-neg { font-size: 1rem; font-weight: 600; color: #f87171; }

    .prob-container {
        background: linear-gradient(135deg, rgba(13,20,40,0.95), rgba(20,30,55,0.85));
        border: 1px solid rgba(99,179,237,0.22);
        border-radius: 18px;
        padding: 22px 26px;
        margin: 12px 0;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        position: relative;
        overflow: hidden;
    }
    .prob-container::before {
        content:'';
        position:absolute;
        top:0;left:0;right:0;
        height:2px;
        background:linear-gradient(90deg,#3b82f6,#8b5cf6,#10b981);
    }
    .prob-bar-track {
        background: rgba(15,23,42,0.8);
        border-radius: 999px;
        height: 10px;
        overflow: hidden;
        margin: 8px 0;
    }
    .prob-bar-fill-up      { height:100%; border-radius:999px; background:linear-gradient(90deg,#16a34a,#4ade80); }
    .prob-bar-fill-down    { height:100%; border-radius:999px; background:linear-gradient(90deg,#dc2626,#f87171); }
    .prob-bar-fill-neutral { height:100%; border-radius:999px; background:linear-gradient(90deg,#d97706,#fbbf24); }
    .prob-bar-fill-range   { height:100%; border-radius:999px; background:linear-gradient(90deg,#1d4ed8,#3b82f6,#8b5cf6); }

    .confidence-badge {
        display:inline-flex; align-items:center; gap:6px;
        padding:4px 14px; border-radius:999px;
        font-size:0.75rem; font-weight:700; letter-spacing:0.05em;
        white-space: nowrap;
    }
    .conf-high   { background:rgba(34,197,94,0.15);  border:1px solid rgba(34,197,94,0.4);  color:#4ade80; }
    .conf-medium { background:rgba(245,158,11,0.15); border:1px solid rgba(245,158,11,0.4); color:#fbbf24; }
    .conf-low    { background:rgba(239,68,68,0.15);  border:1px solid rgba(239,68,68,0.4);  color:#f87171; }

    .info-box {
        background: linear-gradient(135deg,rgba(59,130,246,0.08),rgba(139,92,246,0.05));
        border: 1px solid rgba(59,130,246,0.25);
        border-radius: 14px;
        padding: 14px 20px;
        margin: 12px 0;
        color: #93c5fd;
        font-size: 0.83rem;
        line-height: 1.7;
    }
    .warning-box {
        background: rgba(245,158,11,0.08);
        border: 1px solid rgba(245,158,11,0.25);
        border-radius: 14px;
        padding: 12px 18px;
        margin: 10px 0;
        color: #fcd34d;
        font-size: 0.8rem;
    }

    /* Horizon indicator pills */
    .horizon-pill {
        display: inline-block;
        background: rgba(59,130,246,0.18);
        border: 1px solid rgba(59,130,246,0.4);
        color: #93c5fd;
        padding: 4px 14px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        margin: 0 4px 8px 0;
    }
    .horizon-pill-active {
        background: rgba(59,130,246,0.4);
        border: 1px solid #60a5fa;
        color: #fff;
    }

    /* Comparison rows */
    .model-row {
        background: rgba(13,20,40,0.7);
        border: 1px solid rgba(99,179,237,0.15);
        border-radius: 14px;
        padding: 16px 20px;
        margin: 6px 0;
        transition: border-color 0.2s;
    }
    .model-row:hover { border-color: rgba(99,179,237,0.4); }
    .model-row-selected {
        border: 2px solid rgba(59,130,246,0.6) !important;
        background: rgba(17,24,50,0.85) !important;
    }
    .model-grid {
        display: grid;
        grid-template-columns: 1.6fr 1fr 1fr 1fr 0.8fr 0.9fr;
        gap: 14px;
        align-items: center;
    }

    .stButton > button {
        background: linear-gradient(135deg, #1d4ed8 0%, #6d28d9 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important;
        width: 100%;
        padding: 14px !important;
        font-size: 0.95rem !important;
        letter-spacing: 0.01em !important;
        box-shadow: 0 4px 20px rgba(29,78,216,0.3) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 30px rgba(59,130,246,0.5) !important;
    }

    div[data-testid="stDecoration"] { display: none; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    .custom-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(59,130,246,0.3), rgba(139,92,246,0.3), transparent);
        margin: 32px 0;
        border: none;
    }

    /* Responsive grid fix */
    @media (max-width: 768px) {
        .model-grid { grid-template-columns: 1fr 1fr !important; }
        .hero-header { padding: 20px 20px !important; }
        .ihsg-panel { padding: 16px 18px !important; }
    }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def format_number(value, suffix="", decimals=2):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    if abs(value) >= 1e12:
        return f"{value/1e12:.{decimals}f}T{suffix}"
    elif abs(value) >= 1e9:
        return f"{value/1e9:.{decimals}f}B{suffix}"
    elif abs(value) >= 1e6:
        return f"{value/1e6:.{decimals}f}M{suffix}"
    return f"{value:,.{decimals}f}{suffix}"

def get_safe(d, key, default="N/A"):
    val = d.get(key, default)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return val

def get_safe_num(d, key, default=None):
    val = d.get(key, default)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return val

def _scalar(v):
    if isinstance(v, pd.Series): return float(v.iloc[0])
    return float(v)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_data(ticker_raw: str, period_years: int):
    ticker = ticker_raw.upper()
    if not ticker.endswith(".JK") and not ticker.startswith("^"):
        ticker = ticker + ".JK"
    end   = datetime.today()
    start = end - timedelta(days=365 * period_years)
    try:
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            return None, ticker
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        return df, ticker
    except Exception:
        return None, ticker


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ihsg_data():
    """Fetch IHSG (^JKSE) data for market context."""
    end   = datetime.today()
    start = end - timedelta(days=365)
    try:
        df = yf.download("^JKSE", start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        return df
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_info(ticker: str):
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return {}


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]
    df["MA20"]  = close.rolling(20).mean()
    df["MA50"]  = close.rolling(50).mean()
    df["MA200"] = close.rolling(200).mean()
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    rolling_mean = close.rolling(20).mean()
    rolling_std  = close.rolling(20).std()
    df["BB_upper"] = rolling_mean + 2 * rolling_std
    df["BB_lower"] = rolling_mean - 2 * rolling_std
    df["BB_mid"]   = rolling_mean
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]
    df["Vol_MA20"]    = df["Volume"].rolling(20).mean()
    df["Daily_Return"] = close.pct_change()
    return df


def prepare_features(df: pd.DataFrame, lookback: int = 30,
                     target_horizon: int = 1,
                     recency_weight: float = 1.0):
    """
    Direct multi-step feature preparation.
    target_horizon: how many days AHEAD the model should predict.
      - target_horizon=1  → next-day prediction (old behavior, all horizons look same)
      - target_horizon=N  → model learns to predict price N days from now
    This is the key to making 7-day vs 30-day vs 90-day predictions truly different.
    """
    feature_cols = ["Close", "MA20", "MA50", "RSI", "MACD",
                    "BB_upper", "BB_lower", "Daily_Return", "Volume"]
    available = [c for c in feature_cols if c in df.columns]
    df = df[available].copy().dropna()
    X_list, y_list = [], []
    data = df[available].values
    close_idx = available.index("Close")

    # Each sample: features from [i-lookback, i) → target price at i + target_horizon - 1
    max_i = len(data) - target_horizon
    for i in range(lookback, max_i + 1):
        X_list.append(data[i - lookback:i].flatten())
        y_list.append(data[i + target_horizon - 1][close_idx])  # price N days ahead

    X = np.array(X_list)
    y = np.array(y_list)

    if recency_weight > 1.0 and len(X) > 0:
        weights = np.exp(np.linspace(0, np.log(recency_weight), len(X)))
        weights = weights / weights.sum()
    else:
        weights = None

    return X, y, df, weights



def compute_monte_carlo(future_series, current_price, hist_vol, n_simulations=2000, horizon=None):
    """
    Monte Carlo simulation for probability & confidence intervals.
    horizon is used to scale uncertainty — longer horizon = wider distribution.
    """
    h = len(future_series)
    if horizon is None:
        horizon = h

    # Uncertainty scale: longer horizons have compounding uncertainty
    uncertainty_scale = 1.0 + 0.015 * (horizon / 7)  # grows with horizon
    daily_vol = (hist_vol / np.sqrt(252)) * uncertainty_scale

    model_prices = np.array([current_price] + [float(future_series.iloc[d]) for d in range(h)])
    model_daily_returns = np.diff(np.log(np.maximum(model_prices, 1e-8)))

    simulations = np.zeros((n_simulations, h))
    rng = np.random.default_rng(seed=int(horizon * 137 + n_simulations))  # deterministic but horizon-specific
    for sim in range(n_simulations):
        price = current_price
        for day in range(h):
            shock = rng.normal(0, daily_vol)
            drift = model_daily_returns[day]
            price = price * np.exp(drift + shock)
            simulations[sim, day] = price

    final_prices = simulations[:, -1]
    prob_up   = float(np.mean(final_prices > current_price))
    prob_down = float(1 - prob_up)
    return prob_up, prob_down, {
        "lower_95": np.percentile(simulations, 2.5,  axis=0),
        "upper_95": np.percentile(simulations, 97.5, axis=0),
        "lower_68": np.percentile(simulations, 16,   axis=0),
        "upper_68": np.percentile(simulations, 84,   axis=0),
        "paths":    simulations,
    }


# ─── Models ──────────────────────────────────────────────────────────────────────

def _build_future_direct(model, scaler, df_clean, horizon, lookback, hist_vol):
    """
    Direct multi-step future forecast:
    1. Model was trained to predict price `horizon` days ahead.
    2. Predict the ENDPOINT (price at day horizon) from today's feature window.
    3. Build a smooth daily path from current price → endpoint using
       log-linear interpolation + Brownian motion noise (grows with sqrt(step)).

    This is fundamentally different from rolling prediction:
    - 7-day model  → trained on 7-day-ahead targets → endpoint for 7 days
    - 30-day model → trained on 30-day-ahead targets → endpoint for 30 days
    - 90-day model → trained on 90-day-ahead targets → endpoint for 90 days
    Each model genuinely learns a different distribution, giving different predictions.
    """
    daily_vol = hist_vol / np.sqrt(252)
    rng = np.random.default_rng(seed=horizon * 31 + 7)

    df_work = add_technical_indicators(df_clean.copy())
    current_price = float(df_work["Close"].iloc[-1])

    # Use the horizon-specific model to predict the endpoint
    X_base, _, _, _ = prepare_features(
        df_work, lookback, target_horizon=horizon, recency_weight=1.0
    )
    if len(X_base) == 0:
        return []

    x_last = scaler.transform(X_base[[-1]])
    endpoint = float(model.predict(x_last)[0])
    endpoint = max(endpoint, current_price * 0.3)  # sanity floor

    # Log-linear interpolation from current → endpoint + cumulative Brownian noise
    log_total = np.log(max(endpoint, 1e-8) / max(current_price, 1e-8))
    future_prices = []
    for step in range(1, horizon + 1):
        progress = step / horizon
        base_price = current_price * np.exp(log_total * progress)
        # Brownian noise: std grows as sqrt(step), scaled to daily_vol
        noise = rng.normal(0, daily_vol * np.sqrt(step)) * current_price * 0.30
        step_price = max(base_price + noise, current_price * 0.3)
        future_prices.append(step_price)

    return future_prices


def _finalize(y_test, y_pred_test, y_train, df_clean, horizon, lookback, future_prices):
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    split = len(y_train)
    # When target_horizon=N, the test sample at index i predicts price at i+horizon-1.
    # So the "date" of the prediction is offset by horizon-1 from the feature window end.
    test_feat_start = split + lookback
    target_dates = df_clean.index[test_feat_start + horizon - 1 :
                                   test_feat_start + len(y_test) + horizon - 1]
    actual    = pd.Series(y_test,      index=target_dates[:len(y_test)])
    predicted = pd.Series(y_pred_test, index=target_dates[:len(y_pred_test)])
    future_dates = pd.bdate_range(
        start=df_clean.index[-1] + timedelta(days=1), periods=horizon
    )
    future  = pd.Series(future_prices, index=future_dates[:len(future_prices)])
    metrics = {
        "MAE":  mean_absolute_error(y_test, y_pred_test),
        "RMSE": np.sqrt(mean_squared_error(y_test, y_pred_test)),
        "R2":   r2_score(y_test, y_pred_test),
    }
    return actual, predicted, future, metrics



def predict_linear(df, horizon, lookback=30, hist_vol=0.25):
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    # Train directly for 'horizon' days ahead — different horizon = different model
    X, y, df_clean, sample_weights = prepare_features(
        df, lookback, target_horizon=horizon, recency_weight=2.0
    )
    if len(X) < 60: return None, None, None, None
    split = int(len(X) * 0.8)
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X[:split])
    X_te_s = scaler.transform(X[split:])
    w_train = sample_weights[:split] if sample_weights is not None else None
    model = Ridge(alpha=1.0)
    model.fit(X_tr_s, y[:split], sample_weight=w_train)
    y_pred = model.predict(X_te_s)
    future = _build_future_direct(model, scaler, df_clean, horizon, lookback, hist_vol)
    return _finalize(y[split:], y_pred, y[:split], df_clean, horizon, lookback, future)



def predict_random_forest(df, horizon, lookback=30, hist_vol=0.25):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    # Train directly for 'horizon' days ahead — different horizon = different model
    X, y, df_clean, sample_weights = prepare_features(
        df, lookback, target_horizon=horizon, recency_weight=3.0
    )
    if len(X) < 60: return None, None, None, None
    split = int(len(X) * 0.8)
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X[:split])
    X_te_s = scaler.transform(X[split:])
    w_train = sample_weights[:split] if sample_weights is not None else None
    model = RandomForestRegressor(
        n_estimators=200, max_depth=10, random_state=42, n_jobs=-1
    )
    model.fit(X_tr_s, y[:split], sample_weight=w_train)
    y_pred = model.predict(X_te_s)
    future = _build_future_direct(model, scaler, df_clean, horizon, lookback, hist_vol)
    return _finalize(y[split:], y_pred, y[:split], df_clean, horizon, lookback, future)



def predict_gradient_boosting(df, horizon, lookback=30, hist_vol=0.25):
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    # Train directly for 'horizon' days ahead — different horizon = different model
    X, y, df_clean, sample_weights = prepare_features(
        df, lookback, target_horizon=horizon, recency_weight=3.5
    )
    if len(X) < 60: return None, None, None, None
    split = int(len(X) * 0.8)
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X[:split])
    X_te_s = scaler.transform(X[split:])
    w_train = sample_weights[:split] if sample_weights is not None else None
    # Shorter horizon → higher learning rate (more responsive to recent moves)
    lr = max(0.03, 0.10 - 0.0007 * horizon)
    model = GradientBoostingRegressor(
        n_estimators=300, learning_rate=lr, max_depth=5,
        subsample=0.8, random_state=42
    )
    model.fit(X_tr_s, y[:split], sample_weight=w_train)
    y_pred = model.predict(X_te_s)
    future = _build_future_direct(model, scaler, df_clean, horizon, lookback, hist_vol)
    return _finalize(y[split:], y_pred, y[:split], df_clean, horizon, lookback, future)



def predict_prophet(df, horizon):
    try:
        from prophet import Prophet
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    except ImportError:
        return None, None, None, None, None

    close_vals = df["Close"]
    if isinstance(close_vals.iloc[0], (pd.Series, np.ndarray)):
        close_vals = close_vals.squeeze()
    df_p = pd.DataFrame({"ds": df.index, "y": close_vals.values.flatten()}).dropna()
    split = int(len(df_p) * 0.8)
    train, test = df_p[:split], df_p[split:]
    model = Prophet(daily_seasonality=False, weekly_seasonality=True,
                    yearly_seasonality=True, changepoint_prior_scale=0.1, interval_width=0.95)
    model.fit(train)
    future_df = model.make_future_dataframe(periods=len(test) + horizon, freq="B")
    forecast  = model.predict(future_df)
    tf = forecast[forecast["ds"].isin(test["ds"])]
    y_test  = test["y"].values
    y_pred  = tf["yhat"].values[:len(y_test)]
    metrics = {
        "MAE":  mean_absolute_error(y_test, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_test, y_pred)),
        "R2":   r2_score(y_test, y_pred),
    }
    fo = forecast.tail(horizon)
    future_s = pd.Series(fo["yhat"].values, index=pd.to_datetime(fo["ds"].values))
    ci = fo[["yhat_lower", "yhat_upper"]].copy()
    ci.index = pd.to_datetime(fo["ds"].values)
    return (pd.Series(y_test, index=pd.to_datetime(test["ds"].values)),
            pd.Series(y_pred,  index=pd.to_datetime(test["ds"].values)),
            future_s, metrics, ci)


# ════════════════════════════════════════════════════════════════════════════════
# CHART BUILDERS
# ════════════════════════════════════════════════════════════════════════════════

CHART_LAYOUT = dict(
    plot_bgcolor="rgba(6,11,24,0.0)",
    paper_bgcolor="rgba(6,11,24,0.0)",
    font=dict(color="#64748b", family="Inter"),
    xaxis=dict(gridcolor="rgba(30,41,59,0.6)", showgrid=True, zeroline=False,
               showspikes=True, spikecolor="rgba(99,179,237,0.4)", spikethickness=1),
    yaxis=dict(gridcolor="rgba(30,41,59,0.6)", showgrid=True, zeroline=False),
    legend=dict(bgcolor="rgba(10,18,40,0.85)", bordercolor="rgba(99,179,237,0.25)",
                borderwidth=1, font=dict(size=12)),
    margin=dict(l=0, r=0, t=44, b=0),
    hovermode="x unified",
)


def chart_candlestick(df, ticker):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.75, 0.25])
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="OHLC",
        increasing_line_color="#4ade80", decreasing_line_color="#f87171",
        increasing_fillcolor="#4ade80", decreasing_fillcolor="#f87171",
    ), row=1, col=1)
    for col_name, color, dash in [("MA20","#60a5fa","solid"),("MA50","#fbbf24","solid"),("MA200","#c084fc","dot")]:
        if col_name in df:
            fig.add_trace(go.Scatter(x=df.index, y=df[col_name], name=col_name,
                                      line=dict(color=color, width=1.8, dash=dash)), row=1, col=1)
    if "BB_upper" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_upper"], name="BB Upper",
                                  line=dict(color="rgba(148,163,184,0.3)",width=1), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_lower"], name="BB Lower",
                                  line=dict(color="rgba(148,163,184,0.3)",width=1),
                                  fill="tonexty", fillcolor="rgba(148,163,184,0.04)", showlegend=False), row=1, col=1)
    colors = ["#4ade80" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#f87171" for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=colors, opacity=0.65,
                          name="Volume", showlegend=False), row=2, col=1)
    fig.update_layout(**CHART_LAYOUT,
                      title=dict(text=f"📊 {ticker} — Harga Historis & Volume",
                                 font=dict(size=14, color="#e2e8f0")),
                      height=580, xaxis_rangeslider_visible=False)
    fig.update_yaxes(title_text="Harga (Rp)", row=1, col=1, title_font=dict(size=11, color="#475569"))
    fig.update_yaxes(title_text="Volume",     row=2, col=1, title_font=dict(size=11, color="#475569"))
    return fig


def chart_rsi_macd(df):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=["RSI (14)", "MACD"])
    if "RSI" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI",
                                  line=dict(color="#60a5fa", width=2.2),
                                  fill="tozeroy", fillcolor="rgba(96,165,250,0.05)"), row=1, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(248,113,113,0.5)", row=1, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(74,222,128,0.5)",  row=1, col=1)
        fig.add_hline(y=50, line_dash="dot",  line_color="rgba(100,116,139,0.4)", row=1, col=1)
    if "MACD" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"],        name="MACD",
                                  line=dict(color="#60a5fa",width=2.2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal",
                                  line=dict(color="#fbbf24",width=1.8)), row=2, col=1)
        hc = ["#4ade80" if v >= 0 else "#f87171" for v in df["MACD_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], marker_color=hc, opacity=0.6, name="Hist"), row=2, col=1)
    fig.update_layout(**CHART_LAYOUT, height=420)
    fig.update_annotations(font=dict(color="#64748b", size=12))
    return fig


def chart_ihsg(df_ihsg):
    """Chart IHSG mini with area fill."""
    recent = df_ihsg.iloc[-90:]
    color_up = recent["Close"].iloc[-1] >= recent["Close"].iloc[0]
    line_color = "#4ade80" if color_up else "#f87171"
    fill_color = "rgba(74,222,128,0.08)" if color_up else "rgba(248,113,113,0.08)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=recent.index, y=recent["Close"],
        fill="tozeroy", fillcolor=fill_color,
        line=dict(color=line_color, width=2),
        hovertemplate="<b>IHSG</b><br>%{x|%d %b %Y}: %{y:,.0f}<extra></extra>",
        name="IHSG"
    ))
    # Build layout manually to avoid duplicate 'margin' key from CHART_LAYOUT
    ihsg_layout = {k: v for k, v in CHART_LAYOUT.items() if k not in ("margin", "xaxis", "yaxis")}
    fig.update_layout(
        **ihsg_layout,
        height=180,
        showlegend=False,
        margin=dict(l=0, r=0, t=8, b=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=True,
                   tickfont=dict(size=10, color="#475569")),
        yaxis=dict(showgrid=True, gridcolor="rgba(30,41,59,0.4)", zeroline=False,
                   tickfont=dict(size=10, color="#475569")),
    )
    return fig


def chart_prediction(df, actual, predicted, future, ticker, model_name, horizon, ci=None, mc_ci=None):
    fig = go.Figure()
    ctx = df["Close"].iloc[-min(150, len(df)):]
    fig.add_trace(go.Scatter(x=ctx.index, y=ctx.values, name="Historis",
                              line=dict(color="rgba(100,116,139,0.55)", width=1.8),
                              hovertemplate="<b>Historis</b><br>%{x|%d %b %Y}: Rp %{y:,.0f}<extra></extra>"))

    if mc_ci is not None and future is not None:
        fig.add_trace(go.Scatter(
            x=list(future.index) + list(future.index[::-1]),
            y=list(mc_ci["upper_95"]) + list(mc_ci["lower_95"][::-1]),
            fill="toself", fillcolor="rgba(59,130,246,0.07)",
            line=dict(color="rgba(255,255,255,0)"), name="CI 95%", hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=list(future.index) + list(future.index[::-1]),
            y=list(mc_ci["upper_68"]) + list(mc_ci["lower_68"][::-1]),
            fill="toself", fillcolor="rgba(59,130,246,0.13)",
            line=dict(color="rgba(255,255,255,0)"), name="CI 68%", hoverinfo="skip"))

    if ci is not None and future is not None:
        fig.add_trace(go.Scatter(
            x=list(future.index) + list(future.index[::-1]),
            y=list(ci["yhat_upper"].values) + list(ci["yhat_lower"].values[::-1]),
            fill="toself", fillcolor="rgba(167,139,250,0.10)",
            line=dict(color="rgba(255,255,255,0)"), name="Prophet CI", hoverinfo="skip"))

    if actual is not None:
        fig.add_trace(go.Scatter(x=actual.index, y=actual.values, name="Aktual",
                                  line=dict(color="#4ade80", width=2.2),
                                  hovertemplate="<b>Aktual</b><br>%{x|%d %b %Y}: Rp %{y:,.0f}<extra></extra>"))
    if predicted is not None:
        fig.add_trace(go.Scatter(x=predicted.index, y=predicted.values, name=f"Pred. Test ({model_name})",
                                  line=dict(color="#60a5fa", width=2, dash="dash"),
                                  hovertemplate="<b>Pred. Test</b><br>%{x|%d %b %Y}: Rp %{y:,.0f}<extra></extra>"))
    if future is not None:
        fig.add_trace(go.Scatter(x=future.index, y=future.values, name=f"Prediksi {horizon}H ke Depan",
                                  line=dict(color="#fbbf24", width=2.8),
                                  mode="lines+markers",
                                  marker=dict(size=6, color="#fbbf24", line=dict(color="#0a1228", width=1.5)),
                                  hovertemplate="<b>Prediksi</b><br>%{x|%d %b %Y}: Rp %{y:,.0f}<extra></extra>"))
    if len(df) > 0:
        fig.add_vline(x=df.index[-1], line_dash="dot", line_color="rgba(148,163,184,0.4)",
                      line_width=1.5, annotation_text="Hari Ini",
                      annotation_font_color="#64748b", annotation_font_size=11)
    fig.update_layout(**CHART_LAYOUT,
                      title=dict(text=f"🔮 {ticker} — Prediksi {horizon} Hari ({model_name})",
                                 font=dict(size=14, color="#e2e8f0")),
                      height=520, xaxis_title="Tanggal", yaxis_title="Harga (Rp)")
    return fig


# ════════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def metric_card(label, value, delta=None, delta_positive=True):
    delta_html = ""
    if delta:
        cls   = "metric-delta-pos" if delta_positive else "metric-delta-neg"
        arrow = "▲" if delta_positive else "▼"
        delta_html = f'<div class="{cls}">{arrow} {delta}</div>'
    return (
        f'<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )


def render_ihsg_panel(df_ihsg):
    """Render IHSG market context panel."""
    if df_ihsg is None or df_ihsg.empty:
        st.markdown('<div class="ihsg-panel"><div class="ihsg-title">⚠️ Data IHSG tidak tersedia saat ini</div></div>',
                    unsafe_allow_html=True)
        return

    ihsg_close = _scalar(df_ihsg["Close"].iloc[-1])
    ihsg_prev  = _scalar(df_ihsg["Close"].iloc[-2])
    ihsg_chg   = ihsg_close - ihsg_prev
    ihsg_pct   = (ihsg_chg / ihsg_prev * 100) if ihsg_prev else 0
    is_up      = ihsg_chg >= 0
    chg_color  = "#4ade80" if is_up else "#f87171"
    chg_arrow  = "▲" if is_up else "▼"

    # 30-day trend for sentiment
    df_30 = df_ihsg.iloc[-30:]
    trend_30 = (df_30["Close"].iloc[-1] - df_30["Close"].iloc[0]) / df_30["Close"].iloc[0] * 100
    trend_float = float(trend_30.iloc[0]) if isinstance(trend_30, pd.Series) else float(trend_30)

    # RSI for IHSG
    delta_i = df_ihsg["Close"].diff()
    gain_i  = delta_i.clip(lower=0).rolling(14).mean()
    loss_i  = (-delta_i.clip(upper=0)).rolling(14).mean()
    rsi_s   = 100 - (100 / (1 + gain_i / loss_i.replace(0, np.nan)))
    ihsg_rsi = float(rsi_s.iloc[-1]) if not pd.isna(rsi_s.iloc[-1]) else 50.0

    # MA comparison
    ma20_ihsg = float(df_ihsg["Close"].rolling(20).mean().iloc[-1])
    ma50_ihsg = float(df_ihsg["Close"].rolling(50).mean().iloc[-1])

    # Sentiment
    bullish_signals = sum([
        is_up,
        trend_float > 2,
        ihsg_rsi > 50 and ihsg_rsi < 70,
        ihsg_close > ma20_ihsg,
        ihsg_close > ma50_ihsg,
    ])
    if bullish_signals >= 4:
        sent_cls, sent_lbl, sent_emoji = "ihsg-sentiment-bullish", "BULLISH — Pasar Menguat", "📈"
        market_desc = "Kondisi pasar sedang dalam tren naik. Momentum baik untuk masuk saham berkualitas."
    elif bullish_signals <= 1:
        sent_cls, sent_lbl, sent_emoji = "ihsg-sentiment-bearish", "BEARISH — Pasar Melemah", "📉"
        market_desc = "Kondisi pasar melemah. Pertimbangkan risk management lebih ketat & pilih saham defensif."
    else:
        sent_cls, sent_lbl, sent_emoji = "ihsg-sentiment-neutral", "SIDEWAYS — Pasar Konsolidasi", "↔️"
        market_desc = "Pasar sedang dalam fase konsolidasi. Selektivitas dalam memilih saham sangat penting."

    # 52W high/low
    w52h = float(df_ihsg["Close"].max())
    w52l = float(df_ihsg["Close"].min())
    pos52 = max(0, min(100, (ihsg_close - w52l) / (w52h - w52l) * 100)) if (w52h - w52l) > 0 else 50

    ihsg_date = df_ihsg.index[-1].strftime("%d %b %Y")
    trend_color = "#4ade80" if trend_float >= 0 else "#f87171"
    rsi_color   = "#fbbf24" if ihsg_rsi > 70 else "#4ade80" if ihsg_rsi < 30 else "#93c5fd"

    # Render
    col_left, col_chart = st.columns([1, 2])
    with col_left:
        st.markdown(f"""
        <div class="ihsg-panel" style="height:100%;margin-bottom:0;">
            <div class="ihsg-title">🏛️ IHSG — Indeks Harga Saham Gabungan</div>
            <div style="display:flex;align-items:baseline;gap:14px;margin-bottom:10px;flex-wrap:wrap;">
                <div class="ihsg-price">{ihsg_close:,.2f}</div>
                <div style="font-size:1.1rem;font-weight:700;color:{chg_color};">
                    {chg_arrow} {abs(ihsg_chg):,.2f} ({abs(ihsg_pct):.2f}%)
                </div>
            </div>
            <div style="margin-bottom:14px;">
                <span class="{sent_cls}">{sent_emoji} {sent_lbl}</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px;">
                <div>
                    <div style="font-size:0.65rem;color:#475569;font-weight:600;text-transform:uppercase;">30D Trend</div>
                    <div style="font-size:0.9rem;font-weight:700;color:{trend_color};">{trend_float:+.2f}%</div>
                </div>
                <div>
                    <div style="font-size:0.65rem;color:#475569;font-weight:600;text-transform:uppercase;">RSI(14)</div>
                    <div style="font-size:0.9rem;font-weight:700;color:{rsi_color};">{ihsg_rsi:.1f}</div>
                </div>
                <div>
                    <div style="font-size:0.65rem;color:#475569;font-weight:600;text-transform:uppercase;">Update</div>
                    <div style="font-size:0.8rem;font-weight:600;color:#e2e8f0;">{ihsg_date}</div>
                </div>
            </div>
            <div style="margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;font-size:0.65rem;color:#475569;margin-bottom:4px;">
                    <span>52W Range</span><span style="color:#93c5fd;">{pos52:.0f}% dari Low</span>
                </div>
                <div class="prob-bar-track">
                    <div style="height:100%;border-radius:999px;width:{pos52}%;background:linear-gradient(90deg,#f87171,#fbbf24,#4ade80);"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.62rem;color:#374151;margin-top:3px;">
                    <span>{w52l:,.0f}</span><span>{w52h:,.0f}</span>
                </div>
            </div>
            <div style="margin-top:12px;padding-top:10px;border-top:1px solid rgba(99,179,237,0.1);
                        font-size:0.75rem;color:#64748b;line-height:1.6;">
                💡 {market_desc}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_chart:
        st.markdown('<div class="ihsg-panel" style="margin-bottom:0;padding-bottom:8px;">', unsafe_allow_html=True)
        st.markdown('<div class="ihsg-title">📈 IHSG — Grafik 90 Hari Terakhir</div>', unsafe_allow_html=True)
        st.plotly_chart(chart_ihsg(df_ihsg), use_container_width=True)

        # MA signals inline
        ma_cols = st.columns(3)
        items = [
            ("MA 20", f"{ma20_ihsg:,.0f}", ihsg_close > ma20_ihsg),
            ("MA 50", f"{ma50_ihsg:,.0f}", ihsg_close > ma50_ihsg),
            ("RSI",   f"{ihsg_rsi:.1f}",   ihsg_rsi < 70),
        ]
        for mc, (lbl, val, pos) in zip(ma_cols, items):
            with mc:
                col_v = "#4ade80" if pos else "#f87171"
                st.markdown(f"""
                <div style="background:rgba(13,20,40,0.6);border:1px solid rgba(99,179,237,0.15);
                            border-radius:10px;padding:8px 12px;text-align:center;">
                    <div style="font-size:0.62rem;color:#475569;font-weight:600;text-transform:uppercase;">{lbl}</div>
                    <div style="font-size:0.95rem;font-weight:700;color:{col_v};">{val}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


def render_probability_card(prob_up, prob_down, model_name, future_pct, hist_vol, horizon):
    up_pct   = int(round(prob_up   * 100))
    down_pct = int(round(prob_down * 100))

    if prob_up >= 0.60:
        sig_cls, sig_lbl = "conf-high",   "● NAIK"
        emoji = "📈"
        desc = f"Monte Carlo memprediksi probabilitas <b>naik {up_pct}%</b> dalam {horizon} hari ke depan."
    elif prob_down >= 0.60:
        sig_cls, sig_lbl = "conf-low",    "● TURUN"
        emoji = "📉"
        desc = f"Monte Carlo memprediksi probabilitas <b>turun {down_pct}%</b> dalam {horizon} hari ke depan."
    else:
        sig_cls, sig_lbl = "conf-medium", "● SIDEWAYS"
        emoji = "↔️"
        desc = f"Probabilitas naik/turun relatif seimbang — sinyal <b>sideways / netral</b> dalam {horizon} hari."

    col_fp    = "#4ade80" if future_pct >= 0 else "#f87171"
    vol_label = "Rendah" if hist_vol < 0.25 else "Sedang" if hist_vol < 0.45 else "Tinggi"

    return f"""
<div class="prob-container">
    <div style="font-size:0.7rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:14px;">
        🎲 Probabilitas AI — {model_name} · Monte Carlo (2.000 skenario) · Horizon {horizon} Hari
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:20px;align-items:center;">
        <div>
            <div style="font-size:0.72rem;color:#4ade80;font-weight:700;margin-bottom:6px;">NAIK 📈</div>
            <div class="prob-bar-track"><div class="prob-bar-fill-up" style="width:{up_pct}%"></div></div>
            <div style="font-size:1.6rem;font-weight:800;color:#4ade80;line-height:1.1;">{up_pct}%</div>
        </div>
        <div>
            <div style="font-size:0.72rem;color:#f87171;font-weight:700;margin-bottom:6px;">TURUN 📉</div>
            <div class="prob-bar-track"><div class="prob-bar-fill-down" style="width:{down_pct}%"></div></div>
            <div style="font-size:1.6rem;font-weight:800;color:#f87171;line-height:1.1;">{down_pct}%</div>
        </div>
        <div>
            <div style="font-size:0.72rem;color:#64748b;font-weight:700;margin-bottom:6px;">PROYEKSI {horizon}H</div>
            <div style="font-size:1.6rem;font-weight:800;color:{col_fp};line-height:1.1;">{future_pct:+.2f}%</div>
            <div style="font-size:0.7rem;color:#475569;margin-top:4px;">Volatilitas: {hist_vol*100:.1f}%/yr ({vol_label})</div>
        </div>
        <div style="text-align:center;">
            <div style="font-size:0.7rem;color:#475569;font-weight:700;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.08em;">Sinyal</div>
            <span class="confidence-badge {sig_cls}">{sig_lbl}</span>
            <div style="font-size:2rem;margin-top:8px;">{emoji}</div>
        </div>
    </div>
    <div style="margin-top:16px;padding-top:14px;border-top:1px solid rgba(99,179,237,0.1);font-size:0.78rem;color:#64748b;line-height:1.7;">
        {emoji} {desc} Distribusi probabilitas dihitung dari <b>volatilitas historis</b> dikombinasikan dengan <b>arah prediksi model</b>.
        Semakin jauh horizon, semakin lebar confidence interval (ketidakpastian bertambah).
    </div>
</div>"""


def render_investment_advice(
    ticker, close, last_pred, last_chg_pct,
    prob_up, prob_down, hist_vol,
    horizon, model_choice, r2_score_val,
    rsi_val, macd_val, macd_sig_val,
    ma20_val, ma50_val, ma200_val,
    ihsg_bullish_signals,
    n_model_up, n_models_total,
    mc_ci
):
    """
    Render a comprehensive investment advice panel based on all prediction signals.
    This is for EDUCATIONAL purposes only — not financial advice.
    """

    # ── Scoring system (0-100) ──────────────────────────────────────────────────
    score = 0
    signals = []   # list of (label, positive, detail)
    warnings = []  # risk warnings

    # 1. AI Prediction direction (20 pts)
    if last_chg_pct > 3:
        score += 20
        signals.append(("Proyeksi AI Naik Signifikan", True, f"+{last_chg_pct:.1f}% dalam {horizon}H"))
    elif last_chg_pct > 0:
        score += 12
        signals.append(("Proyeksi AI Sedikit Naik", True, f"+{last_chg_pct:.1f}% dalam {horizon}H"))
    elif last_chg_pct > -3:
        score += 4
        signals.append(("Proyeksi AI Sedikit Turun", False, f"{last_chg_pct:.1f}% dalam {horizon}H"))
    else:
        score += 0
        signals.append(("Proyeksi AI Turun Signifikan", False, f"{last_chg_pct:.1f}% dalam {horizon}H"))

    # 2. Monte Carlo probability (25 pts)
    if prob_up >= 0.70:
        score += 25
        signals.append(("Probabilitas Naik Tinggi", True, f"Monte Carlo: {int(prob_up*100)}% kemungkinan naik"))
    elif prob_up >= 0.55:
        score += 15
        signals.append(("Probabilitas Naik Sedang", True, f"Monte Carlo: {int(prob_up*100)}% kemungkinan naik"))
    elif prob_down >= 0.70:
        score += 0
        signals.append(("Probabilitas Turun Tinggi", False, f"Monte Carlo: {int(prob_down*100)}% kemungkinan turun"))
    else:
        score += 8
        signals.append(("Probabilitas Sideways", False, f"Naik {int(prob_up*100)}% vs Turun {int(prob_down*100)}%"))

    # 3. RSI signal (15 pts)
    if rsi_val is not None:
        if 40 <= rsi_val <= 60:
            score += 10
            signals.append(("RSI Netral (Zona Sehat)", True, f"RSI = {rsi_val:.1f} — tidak overbought/oversold"))
        elif rsi_val < 30:
            score += 15
            signals.append(("RSI Oversold — Peluang Beli", True, f"RSI = {rsi_val:.1f} — potensi rebound"))
        elif 60 < rsi_val <= 70:
            score += 7
            signals.append(("RSI Mendekati Overbought", False, f"RSI = {rsi_val:.1f} — waspadai tekanan jual"))
        elif rsi_val > 70:
            score += 2
            signals.append(("RSI Overbought", False, f"RSI = {rsi_val:.1f} — risiko koreksi tinggi"))
            warnings.append("RSI > 70 menandakan saham sudah jenuh beli — risiko koreksi jangka pendek.")

    # 4. MACD signal (10 pts)
    if macd_val is not None and macd_sig_val is not None:
        if macd_val > macd_sig_val:
            score += 10
            signals.append(("MACD Bullish Crossover", True, f"MACD ({macd_val:.2f}) > Signal ({macd_sig_val:.2f})"))
        else:
            score += 2
            signals.append(("MACD Bearish", False, f"MACD ({macd_val:.2f}) < Signal ({macd_sig_val:.2f})"))

    # 5. Moving averages (10 pts)
    ma_score = 0
    ma_details = []
    if ma20_val and close > ma20_val:
        ma_score += 4; ma_details.append("Di atas MA20")
    else:
        ma_details.append("Di bawah MA20")
    if ma50_val and close > ma50_val:
        ma_score += 4; ma_details.append("Di atas MA50")
    else:
        ma_details.append("Di bawah MA50")
    if ma200_val and close > ma200_val:
        ma_score += 2; ma_details.append("Di atas MA200 (tren bullish jangka panjang)")
    else:
        ma_details.append("Di bawah MA200")
        warnings.append("Harga masih di bawah MA200 — tren jangka panjang masih bearish.")
    score += ma_score
    signals.append(("Moving Average", ma_score >= 6, " · ".join(ma_details)))

    # 6. Model consensus (10 pts)
    consensus_pct = (n_model_up / n_models_total) if n_models_total > 0 else 0.5
    if consensus_pct >= 0.67:
        score += 10
        signals.append((f"Konsensus AI ({n_model_up}/{n_models_total} Model Naik)", True, "Mayoritas model setuju arah naik"))
    elif consensus_pct >= 0.5:
        score += 5
        signals.append((f"Konsensus AI Lemah ({n_model_up}/{n_models_total} Model Naik)", False, "Tidak ada konsensus kuat"))
    else:
        score += 0
        signals.append((f"Konsensus AI Turun ({n_model_up}/{n_models_total} Model Naik)", False, "Mayoritas model prediksi turun"))

    # 7. IHSG market sentiment (10 pts)
    if ihsg_bullish_signals >= 4:
        score += 10
        signals.append(("Sentimen IHSG Bullish", True, f"{ihsg_bullish_signals}/5 indikator IHSG positif"))
    elif ihsg_bullish_signals >= 3:
        score += 6
        signals.append(("Sentimen IHSG Netral", False, f"{ihsg_bullish_signals}/5 indikator IHSG positif"))
    else:
        score += 2
        signals.append(("Sentimen IHSG Bearish", False, f"Hanya {ihsg_bullish_signals}/5 indikator IHSG positif"))
        warnings.append("IHSG dalam tren bearish — saham cenderung ikut tertekan meski fundamental kuat.")

    # ── Volatility risk ──────────────────────────────────────────────────────────
    if hist_vol > 0.50:
        warnings.append(f"Volatilitas sangat tinggi ({hist_vol*100:.0f}%/yr) — fluktuasi harga ekstrem, gunakan stop-loss ketat.")
    elif hist_vol > 0.35:
        warnings.append(f"Volatilitas tinggi ({hist_vol*100:.0f}%/yr) — pertimbangkan ukuran posisi yang lebih kecil.")

    if horizon > 30:
        warnings.append(f"Horizon {horizon} hari cukup panjang — uncertainty tinggi, CI 95% melebar signifikan.")

    if r2_score_val < 0.6:
        warnings.append(f"R² model rendah ({r2_score_val:.2f}) — akurasi historis model tidak ideal, gunakan sebagai referensi saja.")

    # ── Determine action recommendation ─────────────────────────────────────────
    if score >= 75:
        action        = "BELI / BUY"
        action_color  = "#4ade80"
        action_bg     = "rgba(34,197,94,0.12)"
        action_border = "rgba(34,197,94,0.4)"
        action_emoji  = "🟢"
        action_desc   = (
            f"Secara keseluruhan, analisis AI mengindikasikan kondisi <b>POSITIF</b> untuk saham <b>{ticker}</b>. "
            f"Mayoritas sinyal teknikal, probabilitas Monte Carlo, dan konsensus model menunjukkan potensi kenaikan "
            f"<b>+{last_chg_pct:.1f}%</b> dalam <b>{horizon} hari</b>. "
            f"Pertimbangkan untuk masuk posisi dengan manajemen risiko yang baik."
        )
        strategy_html = f"""
        <div style="margin-top:16px;">
            <div style="font-size:0.72rem;color:#475569;font-weight:700;text-transform:uppercase;margin-bottom:10px;">📋 Strategi yang Disarankan</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
                <div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.25);border-radius:10px;padding:12px;">
                    <div style="font-size:0.65rem;color:#4ade80;font-weight:700;text-transform:uppercase;">Entry Zone</div>
                    <div style="font-size:0.85rem;font-weight:700;color:#f1f5f9;margin-top:4px;">Rp {close:,.0f} – Rp {close*0.98:,.0f}</div>
                    <div style="font-size:0.68rem;color:#64748b;margin-top:3px;">Beli di harga saat ini atau saat dip 2%</div>
                </div>
                <div style="background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);border-radius:10px;padding:12px;">
                    <div style="font-size:0.65rem;color:#f87171;font-weight:700;text-transform:uppercase;">Stop-Loss</div>
                    <div style="font-size:0.85rem;font-weight:700;color:#f1f5f9;margin-top:4px;">Rp {mc_ci['lower_95'][min(6,len(mc_ci['lower_95'])-1)]:,.0f}</div>
                    <div style="font-size:0.68rem;color:#64748b;margin-top:3px;">Batas bawah CI 95% minggu pertama</div>
                </div>
                <div style="background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.25);border-radius:10px;padding:12px;">
                    <div style="font-size:0.65rem;color:#fbbf24;font-weight:700;text-transform:uppercase;">Target Profit</div>
                    <div style="font-size:0.85rem;font-weight:700;color:#f1f5f9;margin-top:4px;">Rp {last_pred:,.0f}</div>
                    <div style="font-size:0.68rem;color:#64748b;margin-top:3px;">Target prediksi AI pada {(datetime.today() + timedelta(days=horizon)).strftime("%d %b %Y")}</div>
                </div>
            </div>
        </div>"""
    elif score >= 50:
        action        = "HOLD / TAHAN"
        action_color  = "#fbbf24"
        action_bg     = "rgba(245,158,11,0.12)"
        action_border = "rgba(245,158,11,0.4)"
        action_emoji  = "🟡"
        action_desc   = (
            f"Sinyal campuran — tidak ada arah yang jelas untuk <b>{ticker}</b>. "
            f"Proyeksi AI <b>{last_chg_pct:+.1f}%</b> dalam <b>{horizon} hari</b>, namun probabilitas belum cukup dominan. "
            f"Disarankan untuk <b>menunggu konfirmasi</b> sinyal lebih lanjut sebelum mengambil posisi baru."
        )
        strategy_html = f"""
        <div style="margin-top:16px;">
            <div style="font-size:0.72rem;color:#475569;font-weight:700;text-transform:uppercase;margin-bottom:10px;">📋 Strategi yang Disarankan</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
                <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);border-radius:10px;padding:12px;">
                    <div style="font-size:0.65rem;color:#fbbf24;font-weight:700;text-transform:uppercase;">Aksi</div>
                    <div style="font-size:0.85rem;font-weight:700;color:#f1f5f9;margin-top:4px;">Tahan Posisi</div>
                    <div style="font-size:0.68rem;color:#64748b;margin-top:3px;">Jika sudah pegang, tidak perlu panik jual</div>
                </div>
                <div style="background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);border-radius:10px;padding:12px;">
                    <div style="font-size:0.65rem;color:#f87171;font-weight:700;text-transform:uppercase;">Stop-Loss</div>
                    <div style="font-size:0.85rem;font-weight:700;color:#f1f5f9;margin-top:4px;">Rp {close*0.95:,.0f}</div>
                    <div style="font-size:0.68rem;color:#64748b;margin-top:3px;">Batasi kerugian di -5% dari harga saat ini</div>
                </div>
                <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.25);border-radius:10px;padding:12px;">
                    <div style="font-size:0.65rem;color:#93c5fd;font-weight:700;text-transform:uppercase;">Wait for Signal</div>
                    <div style="font-size:0.85rem;font-weight:700;color:#f1f5f9;margin-top:4px;">RSI / MACD</div>
                    <div style="font-size:0.68rem;color:#64748b;margin-top:3px;">Tunggu konfirmasi bullish crossover</div>
                </div>
            </div>
        </div>"""
    else:
        action        = "JUAL / HINDARI"
        action_color  = "#f87171"
        action_bg     = "rgba(239,68,68,0.12)"
        action_border = "rgba(239,68,68,0.4)"
        action_emoji  = "🔴"
        action_desc   = (
            f"Mayoritas sinyal AI mengindikasikan kondisi <b>NEGATIF</b> untuk <b>{ticker}</b>. "
            f"Proyeksi turun <b>{last_chg_pct:.1f}%</b> dalam <b>{horizon} hari</b>, probabilitas turun dominan. "
            f"Disarankan untuk <b>menghindari pembelian baru</b> atau mempertimbangkan pengurangan posisi."
        )
        strategy_html = f"""
        <div style="margin-top:16px;">
            <div style="font-size:0.72rem;color:#475569;font-weight:700;text-transform:uppercase;margin-bottom:10px;">📋 Strategi yang Disarankan</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
                <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);border-radius:10px;padding:12px;">
                    <div style="font-size:0.65rem;color:#f87171;font-weight:700;text-transform:uppercase;">Aksi</div>
                    <div style="font-size:0.85rem;font-weight:700;color:#f1f5f9;margin-top:4px;">Hindari / Kurangi</div>
                    <div style="font-size:0.68rem;color:#64748b;margin-top:3px;">Jangan beli baru, pertimbangkan jual sebagian</div>
                </div>
                <div style="background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);border-radius:10px;padding:12px;">
                    <div style="font-size:0.65rem;color:#f87171;font-weight:700;text-transform:uppercase;">Stop-Loss Ketat</div>
                    <div style="font-size:0.85rem;font-weight:700;color:#f1f5f9;margin-top:4px;">Rp {close*0.97:,.0f}</div>
                    <div style="font-size:0.68rem;color:#64748b;margin-top:3px;">Cut-loss di -3% jika harga terus turun</div>
                </div>
                <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.25);border-radius:10px;padding:12px;">
                    <div style="font-size:0.65rem;color:#93c5fd;font-weight:700;text-transform:uppercase;">Re-entry Jika</div>
                    <div style="font-size:0.85rem;font-weight:700;color:#f1f5f9;margin-top:4px;">RSI < 35</div>
                    <div style="font-size:0.68rem;color:#64748b;margin-top:3px;">Masuk kembali saat oversold signal muncul</div>
                </div>
            </div>
        </div>"""

    # ── Score bar ────────────────────────────────────────────────────────────────
    score_pct   = min(score, 100)
    score_color = "#4ade80" if score >= 75 else "#fbbf24" if score >= 50 else "#f87171"
    score_grad  = (
        "linear-gradient(90deg,#16a34a,#4ade80)"   if score >= 75 else
        "linear-gradient(90deg,#d97706,#fbbf24)"   if score >= 50 else
        "linear-gradient(90deg,#dc2626,#f87171)"
    )

    # ── Build signals HTML ────────────────────────────────────────────────────────
    # ── Build signal list as individual items (avoid complex slice in f-string) ──
    sig_items = []
    for lbl, pos, detail in signals:
        icon  = "✅" if pos else "❌"
        color = "#4ade80" if pos else "#f87171"
        sig_items.append(
            '<div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;'
            'border-bottom:1px solid rgba(30,41,59,0.5);">'
            f'<div style="font-size:1rem;flex-shrink:0;margin-top:1px;">{icon}</div>'
            '<div>'
            f'<div style="font-size:0.8rem;font-weight:600;color:{color};">{lbl}</div>'
            f'<div style="font-size:0.72rem;color:#475569;margin-top:2px;">{detail}</div>'
            '</div>'
            '</div>'
        )

    # Split signals evenly into two columns
    mid = (len(sig_items) + 1) // 2
    sig_left  = "".join(sig_items[:mid])
    sig_right = "".join(sig_items[mid:])

    # ── Build warnings HTML ────────────────────────────────────────────────────────
    warn_rows = ""
    for w in warnings:
        warn_rows += (
            '<div style="display:flex;align-items:flex-start;gap:8px;margin:6px 0;">'
            '<span style="color:#fbbf24;flex-shrink:0;">⚠️</span>'
            f'<span style="font-size:0.77rem;color:#fbbf24;line-height:1.6;">{w}</span>'
            '</div>'
        )
    warn_html = ""
    if warn_rows:
        warn_html = (
            '<div style="background:rgba(245,158,11,0.07);border:1px solid rgba(245,158,11,0.2);'
            'border-radius:12px;padding:14px 16px;margin-top:16px;">'
            '<div style="font-size:0.68rem;color:#d97706;font-weight:700;text-transform:uppercase;'
            'letter-spacing:0.08em;margin-bottom:8px;">⚠️ Faktor Risiko</div>'
            + warn_rows +
            '</div>'
        )

    # ── Pre-compute all display strings (no expressions inside {}) ─────────────────
    score_pct   = min(score, 100)
    score_color = "#4ade80" if score >= 75 else "#fbbf24" if score >= 50 else "#f87171"
    score_grad  = (
        "linear-gradient(90deg,#16a34a,#4ade80)" if score >= 75 else
        "linear-gradient(90deg,#d97706,#fbbf24)" if score >= 50 else
        "linear-gradient(90deg,#dc2626,#f87171)"
    )
    score_pct_str  = str(score_pct)
    horizon_str    = str(horizon)

    # ── Render: header card ────────────────────────────────────────────────────────
    st.markdown(
        '<div style="background:linear-gradient(135deg,rgba(10,18,40,0.98),rgba(15,25,55,0.95));'
        f'border:1px solid {action_border};'
        'border-radius:20px;padding:26px 30px;margin:16px 0;'
        'box-shadow:0 8px 40px rgba(0,0,0,0.5);position:relative;overflow:hidden;">'
        # Top gradient bar
        f'<div style="position:absolute;top:0;left:0;right:0;height:3px;background:{score_grad};"></div>'
        # Header row
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;'
        'flex-wrap:wrap;gap:16px;margin-bottom:20px;">'
        '<div>'
        '<div style="font-size:0.68rem;color:#475569;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.12em;margin-bottom:6px;">🧠 Saran AI — {ticker} · Horizon {horizon_str} Hari</div>'
        f'<div style="font-size:2rem;font-weight:900;color:{action_color};letter-spacing:-0.01em;">'
        f'{action_emoji} {action}</div>'
        f'<div style="font-size:0.82rem;color:#94a3b8;margin-top:8px;max-width:520px;line-height:1.7;">'
        f'{action_desc}</div>'
        '</div>'
        # Score box
        '<div style="text-align:center;flex-shrink:0;">'
        '<div style="font-size:0.65rem;color:#475569;font-weight:700;text-transform:uppercase;margin-bottom:6px;">Skor AI</div>'
        f'<div style="font-size:2.8rem;font-weight:900;color:{score_color};line-height:1;">{score_pct_str}</div>'
        '<div style="font-size:0.68rem;color:#475569;margin-top:4px;">dari 100</div>'
        '<div style="background:rgba(15,23,42,0.8);border-radius:999px;height:8px;width:80px;overflow:hidden;margin:8px auto 0;">'
        f'<div style="height:100%;border-radius:999px;width:{score_pct_str}%;background:{score_grad};"></div>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # ── Render: signals grid ───────────────────────────────────────────────────────
    st.markdown(
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:0 32px;">'
        '<div>'
        '<div style="font-size:0.68rem;color:#475569;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.08em;margin-bottom:6px;">Sinyal Analisis</div>'
        + sig_left +
        '</div>'
        '<div>'
        '<div style="font-size:0.68rem;color:#475569;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.08em;margin-bottom:6px;">&nbsp;</div>'
        + sig_right +
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # ── Render: strategy + warnings ───────────────────────────────────────────────
    st.markdown(strategy_html + warn_html, unsafe_allow_html=True)

    # ── Render: disclaimer footer + close outer div ────────────────────────────────
    st.markdown(
        '<div style="margin-top:18px;padding-top:14px;border-top:1px solid rgba(30,41,59,0.6);'
        'font-size:0.72rem;color:#64748b;line-height:1.7;">'
        '⚠️ <b>Disclaimer Penting:</b> Saran ini dihasilkan oleh AI berdasarkan analisis data historis '
        'dan model statistik. <b>Bukan merupakan rekomendasi investasi profesional.</b> '
        'Pasar saham mengandung risiko. Selalu lakukan riset mandiri (DYOR) dan konsultasikan '
        'dengan perencana keuangan sebelum berinvestasi.'
        '</div>'
        '</div>',   # close outer card div
        unsafe_allow_html=True
    )

def scan_stock_quick(ticker, horizon):
    """
    Fast scanning for a single ticker.
    Returns a dict with score, prob_up, expected_change, and basic technicals.
    Uses Ridge Regression for speed, with full 6-indicator scoring.
    """
    df, _ = fetch_stock_data(ticker, period_years=1)  # 1y for speed
    if df is None or len(df) < 100:
        return None

    df = add_technical_indicators(df)

    daily_ret = df["Close"].pct_change().dropna()
    hist_vol  = float(daily_ret.std() * np.sqrt(252))

    close  = float(df["Close"].iloc[-1])
    rsi    = float(df["RSI"].iloc[-1])         if "RSI"         in df and not pd.isna(df["RSI"].iloc[-1])         else 50.0
    ma20   = float(df["MA20"].iloc[-1])        if "MA20"        in df and not pd.isna(df["MA20"].iloc[-1])        else close
    ma50   = float(df["MA50"].iloc[-1])        if "MA50"        in df and not pd.isna(df["MA50"].iloc[-1])        else close
    macd   = float(df["MACD"].iloc[-1])        if "MACD"        in df and not pd.isna(df["MACD"].iloc[-1])        else 0.0
    macd_s = float(df["MACD_signal"].iloc[-1]) if "MACD_signal" in df and not pd.isna(df["MACD_signal"].iloc[-1]) else 0.0

    # Fast Ridge Regression prediction
    try:
        r = predict_linear(df, horizon, hist_vol=hist_vol)
        if not r or r[0] is None:
            return None
        _, _, future, _ = r
        last_pred = float(future.iloc[-1])
        chg_pct   = (last_pred - close) / close * 100

        prob_up, prob_down, _ = compute_monte_carlo(
            future, close, hist_vol, 500, horizon=horizon
        )
    except Exception as e:
        import traceback
        print(f"Error in scan_stock_quick for {ticker}: {e}")
        traceback.print_exc()
        return None

    # ── 6-Indicator Scoring ───────────────────────────────────────────────────
    score = 0

    # 1. Monte Carlo probability (30 pts)
    if prob_up >= 0.70:
        score += 30
    elif prob_up >= 0.55:
        score += 18
    elif prob_up >= 0.45:
        score += 8
    else:
        score += 0

    # 2. AI Projection direction (20 pts)
    if chg_pct > 5:
        score += 20
    elif chg_pct > 2:
        score += 14
    elif chg_pct > 0:
        score += 8
    elif chg_pct > -2:
        score += 3
    else:
        score += 0

    # 3. RSI (15 pts)
    if rsi < 30:
        score += 15  # oversold = peluang beli
    elif 30 <= rsi <= 55:
        score += 12
    elif 55 < rsi <= 65:
        score += 7
    elif 65 < rsi <= 70:
        score += 3
    else:  # > 70 overbought
        score += 0

    # 4. MACD (15 pts)
    if macd > macd_s:
        score += 15  # bullish crossover
    else:
        score += 0

    # 5. MA50 position (10 pts)
    if close > ma50:
        score += 10
    else:
        score += 0

    # 6. MA20 momentum (10 pts)
    if close > ma20:
        score += 10
    else:
        score += 0

    score = round(min(score, 100), 1)

    # ── Signal & RSI label ────────────────────────────────────────────────────
    if score >= 65 and prob_up > 0.55 and rsi < 72:
        signal       = "BUY"
        signal_emoji = "📈"
    elif score < 40 or (prob_up < 0.35 and rsi > 68):
        signal       = "AVOID"
        signal_emoji = "📉"
    else:
        signal       = "HOLD"
        signal_emoji = "↔️"

    if rsi > 70:
        rsi_label = "Overbought"
    elif rsi < 30:
        rsi_label = "Oversold"
    elif rsi >= 50:
        rsi_label = "Bullish"
    else:
        rsi_label = "Bearish"

    return {
        "ticker":       ticker,
        "close":        close,
        "rsi":          rsi,
        "rsi_label":    rsi_label,
        "ma20":         ma20,
        "ma50":         ma50,
        "macd":         macd,
        "macd_signal":  macd_s,
        "prob_up":      prob_up,
        "chg_pct":      chg_pct,
        "signal":       signal,
        "signal_emoji": signal_emoji,
        "score":        score,
    }


def render_scanner_tab():
    # Header
    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(10,18,40,0.98),rgba(15,25,55,0.95));
                border:1px solid rgba(99,179,237,0.25);border-radius:20px;
                padding:28px 36px;margin-bottom:24px;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;right:0;height:3px;
                    background:linear-gradient(90deg,#3b82f6,#8b5cf6,#10b981);"></div>
        <div style="font-size:1.6rem;font-weight:900;color:#f1f5f9;margin-bottom:8px;">
            🔍 Market Scanner
        </div>
        <div style="font-size:0.85rem;color:#64748b;line-height:1.7;max-width:700px;">
            Scan otomatis daftar saham pilihan menggunakan <b style="color:#93c5fd;">6 indikator AI + teknikal</b>
            untuk menemukan saham dengan potensi kenaikan terbaik.
            Skor dihitung dari Monte Carlo, proyeksi AI, RSI, Moving Average, MACD, dan Momentum.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Controls
    c1, c2, c3, c4 = st.columns([2.2, 1.2, 1, 1])
    with c1:
        preset = st.selectbox("Daftar Saham", ["LQ45", "IDX30", "BUMN", "Custom (Ketik Ticker)"],
                              key="scanner_preset")
    with c2:
        scan_horizon = st.selectbox("Horizon Prediksi", [7, 14, 30], index=0,
                                    format_func=lambda x: f"{x} Hari", key="scanner_horizon")
    with c3:
        top_n = st.selectbox("Top N", [5, 10, 20], index=1, key="scanner_topn")
    with c4:
        sort_by = st.selectbox("Urutkan", ["Skor AI", "Prob Naik", "Proyeksi %", "RSI"],
                               key="scanner_sort")

    custom_tickers = ""
    if preset == "Custom (Ketik Ticker)":
        custom_tickers = st.text_input(
            "Kode saham (pisah koma)", value="BBCA, BBRI, TLKM, ASII, GOTO, BREN",
            key="scanner_custom"
        )

    scan_col, _ = st.columns([1, 3])
    with scan_col:
        run_scan = st.button("🔍 Mulai Scan", use_container_width=True, key="scanner_run")

    if not run_scan:
        st.markdown("""
        <div style="background:linear-gradient(135deg,rgba(59,130,246,0.07),rgba(139,92,246,0.05));
                    border:1px solid rgba(59,130,246,0.2);border-radius:14px;
                    padding:18px 24px;margin-top:16px;">
            <div style="font-size:0.78rem;color:#93c5fd;font-weight:700;margin-bottom:10px;">💡 Cara Kerja Market Scanner</div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">
                <div style="font-size:0.77rem;color:#64748b;line-height:1.7;">
                    <b style="color:#60a5fa;">🎲 Monte Carlo (30 pt)</b><br>
                    500 simulasi probabilitas naik berdasarkan volatilitas historis.
                </div>
                <div style="font-size:0.77rem;color:#64748b;line-height:1.7;">
                    <b style="color:#60a5fa;">🤖 AI Proyeksi (20 pt)</b><br>
                    Ridge Regression memprediksi harga di akhir horizon yang dipilih.
                </div>
                <div style="font-size:0.77rem;color:#64748b;line-height:1.7;">
                    <b style="color:#60a5fa;">📊 RSI + MA + MACD + Momentum (50 pt)</b><br>
                    Indikator teknikal klasik untuk konfirmasi sinyal arah harga.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Build ticker list
    if preset == "Custom (Ketik Ticker)":
        tickers_to_scan = [t.strip().upper() for t in custom_tickers.split(",") if t.strip()]
        tickers_to_scan = [f"{t}.JK" if not t.endswith(".JK") else t for t in tickers_to_scan]
    else:
        tickers_to_scan = IDX_STOCK_LISTS[preset]

    if not tickers_to_scan:
        st.warning("Daftar saham kosong!")
        return

    # Scan loop
    total     = len(tickers_to_scan)
    my_bar    = st.progress(0, text="⏳ Memulai scan...")
    status_txt = st.empty()
    results   = []
    failed    = []

    for i, tick in enumerate(tickers_to_scan):
        my_bar.progress((i + 0.5) / total, text=f"📡 Scanning {tick}… ({i+1}/{total})")
        status_txt.markdown(
            f'<div style="font-size:0.75rem;color:#475569;">'
            f'Menganalisis <b style="color:#93c5fd;">{tick}</b> — '
            f'6 indikator: Monte Carlo · AI Proyeksi · RSI · MA · MACD · Momentum</div>',
            unsafe_allow_html=True
        )
        res = scan_stock_quick(tick, scan_horizon)
        if res:
            results.append(res)
        else:
            failed.append(tick)

    my_bar.progress(1.0, text=f"✅ Scan selesai! {len(results)}/{total} saham berhasil dianalisis.")
    status_txt.empty()

    if not results:
        st.error("❌ Gagal melakukan scan. Periksa koneksi internet atau ticker.")
        return

    # Sort
    sort_key_map = {
        "Skor AI":    lambda x: x["score"],
        "Prob Naik":  lambda x: x["prob_up"],
        "Proyeksi %": lambda x: x["chg_pct"],
        "RSI":        lambda x: -x["rsi"],
    }
    results.sort(key=sort_key_map.get(sort_by, lambda x: x["score"]), reverse=True)
    top_results = results[:top_n]

    # Summary stats
    n_buy   = sum(1 for r in results if r["signal"] == "BUY")
    n_hold  = sum(1 for r in results if r["signal"] == "HOLD")
    n_avoid = sum(1 for r in results if r["signal"] == "AVOID")
    avg_score   = sum(r["score"] for r in results) / len(results)
    best_ticker = results[0]["ticker"] if results else "-"
    best_score  = results[0]["score"]  if results else 0
    best_score_str = f"{best_score:.0f}"

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(10,18,40,0.98),rgba(15,25,55,0.95));
                border:1px solid rgba(99,179,237,0.2);border-radius:18px;
                padding:22px 28px;margin:20px 0;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;
                    background:linear-gradient(90deg,#3b82f6,#8b5cf6,#10b981);"></div>
        <div style="font-size:0.68rem;color:#475569;font-weight:700;text-transform:uppercase;
                    letter-spacing:0.12em;margin-bottom:16px;">📊 Ringkasan Hasil Scan — {preset} · Horizon {scan_horizon}H</div>
        <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:16px;">
            <div style="text-align:center;">
                <div style="font-size:0.65rem;color:#475569;font-weight:700;text-transform:uppercase;margin-bottom:6px;">Total Scan</div>
                <div style="font-size:1.8rem;font-weight:900;color:#e2e8f0;line-height:1;">{len(results)}</div>
                <div style="font-size:0.65rem;color:#64748b;margin-top:4px;">saham</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:0.65rem;color:#4ade80;font-weight:700;text-transform:uppercase;margin-bottom:6px;">🟢 BUY</div>
                <div style="font-size:1.8rem;font-weight:900;color:#4ade80;line-height:1;">{n_buy}</div>
                <div style="font-size:0.65rem;color:#64748b;margin-top:4px;">skor ≥ 70</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:0.65rem;color:#fbbf24;font-weight:700;text-transform:uppercase;margin-bottom:6px;">🟡 HOLD</div>
                <div style="font-size:1.8rem;font-weight:900;color:#fbbf24;line-height:1;">{n_hold}</div>
                <div style="font-size:0.65rem;color:#64748b;margin-top:4px;">skor 45-69</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:0.65rem;color:#f87171;font-weight:700;text-transform:uppercase;margin-bottom:6px;">🔴 AVOID</div>
                <div style="font-size:1.8rem;font-weight:900;color:#f87171;line-height:1;">{n_avoid}</div>
                <div style="font-size:0.65rem;color:#64748b;margin-top:4px;">skor &lt; 45</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:0.65rem;color:#475569;font-weight:700;text-transform:uppercase;margin-bottom:6px;">Rata Skor</div>
                <div style="font-size:1.8rem;font-weight:900;color:#93c5fd;line-height:1;">{avg_score:.0f}</div>
                <div style="font-size:0.65rem;color:#64748b;margin-top:4px;">dari 100</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:0.65rem;color:#475569;font-weight:700;text-transform:uppercase;margin-bottom:6px;">🏆 Terbaik</div>
                <div style="font-size:1.2rem;font-weight:900;color:#fbbf24;line-height:1.2;">{best_ticker.replace(".JK","")}</div>
                <div style="font-size:0.65rem;color:#64748b;margin-top:4px;">skor {best_score_str}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if failed:
        st.markdown(
            f'<div style="font-size:0.72rem;color:#475569;margin-bottom:8px;">'
            f'⚠️ Gagal scan: {" · ".join(failed)}</div>',
            unsafe_allow_html=True
        )

    # Mini bar chart
    chart_data    = sorted(results, key=lambda x: x["score"])
    chart_tickers = [r["ticker"].replace(".JK", "") for r in chart_data]
    chart_scores  = [r["score"] for r in chart_data]
    bar_colors    = ["#4ade80" if s >= 70 else "#fbbf24" if s >= 45 else "#f87171" for s in chart_scores]
    fig_bar = go.Figure(go.Bar(
        x=chart_scores, y=chart_tickers, orientation="h",
        marker=dict(color=bar_colors, line=dict(color="rgba(0,0,0,0)", width=0)),
        text=[str(s) for s in chart_scores],
        textposition="outside",
        textfont=dict(color="#94a3b8", size=10),
        hovertemplate="<b>%{y}</b><br>Skor: %{x}/100<extra></extra>",
    ))
    base_layout = {k: v for k, v in CHART_LAYOUT.items() if k not in ("margin", "hovermode", "xaxis", "yaxis")}
    fig_bar.update_layout(
        **base_layout,
        height=max(220, len(chart_data) * 28),
        margin=dict(l=0, r=40, t=36, b=0),
        title=dict(text=f"📊 Skor AI — Semua {len(chart_data)} Saham Terscan",
                   font=dict(size=13, color="#e2e8f0")),
        xaxis=dict(range=[0, 108], showgrid=True, gridcolor="rgba(30,41,59,0.6)",
                   zeroline=False, tickfont=dict(color="#475569", size=10)),
        yaxis=dict(showgrid=False, tickfont=dict(color="#94a3b8", size=10)),
        hovermode="y unified",
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # Top 3 Podium
    podium_defs = [
        ("🥇", "GOLD — #1 Terbaik",   "rgba(251,191,36,0.18)",  "rgba(251,191,36,0.5)",  "#fbbf24"),
        ("🥈", "SILVER — #2",         "rgba(148,163,184,0.15)", "rgba(148,163,184,0.4)", "#94a3b8"),
        ("🥉", "BRONZE — #3",         "rgba(180,120,80,0.15)",  "rgba(180,120,80,0.4)",  "#c97c4a"),
    ]
    top3 = top_results[:min(3, len(top_results))]
    if top3:
        st.markdown('<div class="section-header">🏆 Top 3 Saham Terpilih</div>', unsafe_allow_html=True)
        pod_cols = st.columns(len(top3))
        for col, res, (ico, plabel, pbg, pborder, pcolor) in zip(pod_cols, top3, podium_defs):
            ticker_short = res["ticker"].replace(".JK", "")
            sig_color = "#4ade80" if res["signal"] == "BUY" else "#fbbf24" if res["signal"] == "HOLD" else "#f87171"
            chg_color = "#4ade80" if res["chg_pct"] >= 0 else "#f87171"
            score_pct = res["score"]
            prob_pct  = int(res["prob_up"] * 100)
            rsi_c     = "#f87171" if res["rsi"] > 70 else "#4ade80" if res["rsi"] < 30 else "#e2e8f0"
            macd_bull = res["macd"] > res["macd_signal"]
            macd_c    = "#4ade80" if macd_bull else "#f87171"
            macd_txt  = "Bullish ▲" if macd_bull else "Bearish ▼"
            above_ma50 = res["close"] > res["ma50"]
            ma50_c    = "#4ade80" if above_ma50 else "#f87171"
            ma50_txt  = "✅ Di atas MA50" if above_ma50 else "⚠️ Di bawah MA50"
            with col:
                st.markdown(
                    f'<div style="background:{pbg};border:2px solid {pborder};'
                    f'border-radius:20px;padding:24px 20px;text-align:center;position:relative;overflow:hidden;">'
                    f'<div style="position:absolute;top:0;left:0;right:0;height:3px;'
                    f'background:linear-gradient(90deg,transparent,{pcolor},transparent);"></div>'
                    f'<div style="font-size:2.2rem;margin-bottom:4px;">{ico}</div>'
                    f'<div style="font-size:0.62rem;color:{pcolor};font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:10px;">{plabel}</div>'
                    f'<div style="font-size:2rem;font-weight:900;color:#f1f5f9;letter-spacing:-0.02em;">{ticker_short}</div>'
                    f'<div style="font-size:0.85rem;color:#64748b;margin-bottom:16px;">Rp {res["close"]:,.0f}</div>'
                    f'<div style="margin:0 auto 16px auto;width:72px;height:72px;border-radius:50%;'
                    f'border:4px solid {pcolor};display:flex;flex-direction:column;'
                    f'align-items:center;justify-content:center;background:rgba(0,0,0,0.3);">'
                    f'<div style="font-size:1.4rem;font-weight:900;color:{pcolor};line-height:1;">{score_pct}</div>'
                    f'<div style="font-size:0.58rem;color:#475569;">/ 100</div></div>'
                    f'<div style="background:rgba(0,0,0,0.3);border:1px solid {sig_color};'
                    f'border-radius:999px;padding:5px 16px;display:inline-block;'
                    f'font-size:0.85rem;font-weight:800;color:{sig_color};margin-bottom:16px;">'
                    f'{res["signal_emoji"]} {res["signal"]}</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">'
                    f'<div style="background:rgba(0,0,0,0.25);border-radius:10px;padding:8px;">'
                    f'<div style="font-size:0.58rem;color:#475569;font-weight:700;text-transform:uppercase;">Prob Naik</div>'
                    f'<div style="font-size:1rem;font-weight:800;color:#4ade80;">{prob_pct}%</div></div>'
                    f'<div style="background:rgba(0,0,0,0.25);border-radius:10px;padding:8px;">'
                    f'<div style="font-size:0.58rem;color:#475569;font-weight:700;text-transform:uppercase;">Proyeksi</div>'
                    f'<div style="font-size:1rem;font-weight:800;color:{chg_color};">{res["chg_pct"]:+.1f}%</div></div>'
                    f'<div style="background:rgba(0,0,0,0.25);border-radius:10px;padding:8px;">'
                    f'<div style="font-size:0.58rem;color:#475569;font-weight:700;text-transform:uppercase;">RSI</div>'
                    f'<div style="font-size:1rem;font-weight:800;color:{rsi_c};">{res["rsi"]:.0f}</div></div>'
                    f'<div style="background:rgba(0,0,0,0.25);border-radius:10px;padding:8px;">'
                    f'<div style="font-size:0.58rem;color:#475569;font-weight:700;text-transform:uppercase;">MACD</div>'
                    f'<div style="font-size:0.75rem;font-weight:700;color:{macd_c};">{macd_txt}</div></div>'
                    f'</div>'
                    f'<div style="margin-top:10px;font-size:0.68rem;font-weight:700;color:{ma50_c};">{ma50_txt}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

    # Full results table
    st.markdown(
        f'<div class="section-header">📋 Top {len(top_results)} Hasil Scan — Diurutkan: {sort_by}</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div style="display:grid;grid-template-columns:2fr 1.4fr 1fr 1fr 1fr 1fr 1fr 1.2fr;'
        'gap:0;background:rgba(15,23,42,0.9);border:1px solid rgba(99,179,237,0.18);'
        'border-radius:12px 12px 0 0;padding:10px 20px;margin-top:8px;">'
        '<div style="font-size:0.62rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">Saham</div>'
        '<div style="font-size:0.62rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;text-align:center;">Skor AI</div>'
        '<div style="font-size:0.62rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;text-align:center;">Prob Naik</div>'
        '<div style="font-size:0.62rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;text-align:center;">Proyeksi</div>'
        '<div style="font-size:0.62rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;text-align:center;">RSI</div>'
        '<div style="font-size:0.62rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;text-align:center;">MACD</div>'
        '<div style="font-size:0.62rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;text-align:center;">MA50</div>'
        '<div style="font-size:0.62rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;text-align:right;">Sinyal</div>'
        '</div>',
        unsafe_allow_html=True
    )

    for rank, res in enumerate(top_results, 1):
        ticker_short = res["ticker"].replace(".JK", "")
        sig_color    = "#4ade80" if res["signal"] == "BUY" else "#fbbf24" if res["signal"] == "HOLD" else "#f87171"
        sig_bg       = "rgba(34,197,94,0.12)" if res["signal"] == "BUY" else "rgba(245,158,11,0.12)" if res["signal"] == "HOLD" else "rgba(239,68,68,0.12)"
        chg_color    = "#4ade80" if res["chg_pct"] >= 0 else "#f87171"
        prob_color   = "#4ade80" if res["prob_up"] >= 0.6 else "#fbbf24" if res["prob_up"] >= 0.4 else "#f87171"
        rsi_color    = "#f87171" if res["rsi"] > 70 else "#4ade80" if res["rsi"] < 30 else "#e2e8f0"
        macd_bull    = res["macd"] > res["macd_signal"]
        above_ma50   = res["close"] > res["ma50"]
        score_pct    = res["score"]
        score_grad   = "linear-gradient(90deg,#16a34a,#4ade80)" if score_pct >= 70 else "linear-gradient(90deg,#d97706,#fbbf24)" if score_pct >= 45 else "linear-gradient(90deg,#dc2626,#f87171)"
        score_c      = "#4ade80" if score_pct >= 70 else "#fbbf24" if score_pct >= 45 else "#f87171"
        macd_c       = "#4ade80" if macd_bull else "#f87171"
        macd_txt     = "▲ Bull" if macd_bull else "▼ Bear"
        ma50_c       = "#4ade80" if above_ma50 else "#f87171"
        ma50_txt     = "✅ Atas" if above_ma50 else "⚠️ Bawah"
        rank_badge   = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"<span style='color:#475569;font-size:0.75rem;font-weight:700;'>#{rank}</span>"
        is_last      = rank == len(top_results)
        br           = "12px 12px" if is_last else "0 0"
        row_bg       = "rgba(13,22,45,0.95)" if rank % 2 == 0 else "rgba(10,18,40,0.98)"

        st.markdown(
            f'<div style="display:grid;grid-template-columns:2fr 1.4fr 1fr 1fr 1fr 1fr 1fr 1.2fr;'
            f'gap:0;background:{row_bg};border:1px solid rgba(99,179,237,0.12);border-top:none;'
            f'padding:14px 20px;align-items:center;border-radius:0 0 {br};">'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<div style="font-size:1rem;flex-shrink:0;">{rank_badge}</div>'
            f'<div><div style="font-size:1rem;font-weight:800;color:#f1f5f9;">{ticker_short}</div>'
            f'<div style="font-size:0.72rem;color:#475569;">Rp {res["close"]:,.0f}</div></div></div>'
            f'<div style="text-align:center;">'
            f'<div style="font-size:1.1rem;font-weight:900;color:{score_c};">{score_pct}</div>'
            f'<div style="background:rgba(15,23,42,0.8);border-radius:999px;height:5px;'
            f'width:60px;overflow:hidden;margin:4px auto 0;">'
            f'<div style="height:100%;border-radius:999px;width:{score_pct}%;background:{score_grad};"></div>'
            f'</div></div>'
            f'<div style="text-align:center;font-size:0.9rem;font-weight:700;color:{prob_color};">{int(res["prob_up"]*100)}%</div>'
            f'<div style="text-align:center;font-size:0.9rem;font-weight:700;color:{chg_color};">{res["chg_pct"]:+.1f}%</div>'
            f'<div style="text-align:center;font-size:0.9rem;font-weight:700;color:{rsi_color};">{res["rsi"]:.0f}'
            f'<div style="font-size:0.58rem;color:#475569;font-weight:600;">{res["rsi_label"]}</div></div>'
            f'<div style="text-align:center;font-size:0.75rem;font-weight:700;color:{macd_c};">{macd_txt}</div>'
            f'<div style="text-align:center;font-size:0.72rem;font-weight:700;color:{ma50_c};">{ma50_txt}</div>'
            f'<div style="text-align:right;">'
            f'<span style="background:{sig_bg};border:1px solid {sig_color};border-radius:999px;'
            f'padding:4px 12px;font-size:0.78rem;font-weight:800;color:{sig_color};white-space:nowrap;">'
            f'{res["signal_emoji"]} {res["signal"]}</span></div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("""
    <div style="margin-top:16px;padding:12px 18px;
                background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.18);
                border-radius:12px;font-size:0.72rem;color:#64748b;line-height:1.7;">
        ⚠️ <b>Disclaimer:</b> Hasil scan dihasilkan oleh model AI berdasarkan data historis dan indikator teknikal.
        Bukan merupakan rekomendasi investasi. Selalu lakukan riset mandiri (DYOR) sebelum berinvestasi.
    </div>
    """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ════════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="hero-header">
    <p class="hero-title">📈 Prediksi Saham Indonesia</p>
    <div style="margin-top:10px;">
        <span class="hero-badge">Yahoo Finance · Real-time</span>
        <span class="hero-badge">IDX · Bursa Efek Indonesia</span>
        <span class="hero-badge">AI Prediction + Monte Carlo</span>
        <span class="hero-badge">IHSG Market Sentiment</span>
    </div>
    <p style="color:#334155; font-size:0.72rem; margin-top:14px; font-style:italic;">
        ⚠️ Untuk tujuan edukasi &amp; analisis saja. Bukan rekomendasi investasi.
    </p>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:10px 0 20px 0;">
        <div style="font-size:2.4rem;margin-bottom:8px;">📈</div>
        <div style="color:#60a5fa;font-weight:800;font-size:1rem;">Prediksi Saham IDX</div>
        <div style="color:#334155;font-size:0.7rem;margin-top:4px;">AI + Monte Carlo + IHSG</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 🔎 Input Saham")
    saham_input = st.text_input("Kode Saham (pisah koma untuk multi)", value="BBCA",
                                 placeholder="Contoh: BBCA, TLKM, BBRI, GOTO")

    st.markdown("---")
    st.markdown("#### 📅 Data & Prediksi")
    period_years = st.selectbox("Periode Data Historis", [1, 2, 3, 5], index=1,
                                 format_func=lambda x: f"{x} Tahun")
    horizon = st.slider("Horizon Prediksi (Hari)", 7, 90, 30, 7,
                         help="Horizon berbeda menghasilkan prediksi berbeda karena uncertainty meningkat seiring waktu")

    h_label = "Sangat Pendek" if horizon <= 7 else "Pendek" if horizon <= 14 else "Menengah" if horizon <= 30 else "Panjang"
    h_color = "#4ade80" if horizon <= 14 else "#fbbf24" if horizon <= 30 else "#f87171"
    st.markdown(f"""
    <div style="background:rgba(13,20,40,0.7);border:1px solid rgba(99,179,237,0.2);
                border-radius:10px;padding:10px 14px;margin-top:6px;margin-bottom:4px;">
        <div style="font-size:0.65rem;color:#475569;font-weight:600;text-transform:uppercase;">Kategori Horizon</div>
        <div style="font-size:0.9rem;font-weight:700;color:{h_color};">{horizon} Hari — {h_label}</div>
        <div style="font-size:0.68rem;color:#374151;margin-top:3px;">
            {'Akurasi tinggi, volatilitas rendah' if horizon <= 14 else 'Uncertainty meningkat, CI lebih lebar'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 🤖 Model AI")
    model_choice = st.selectbox("Pilih Model", [
        "Gradient Boosting", "Random Forest", "Linear Regression", "Prophet"
    ], index=0, help=(
        "• Gradient Boosting: Paling akurat, direkomendasikan.\n"
        "• Random Forest: Akurat, robust.\n"
        "• Linear Regression: Cepat, baseline.\n"
        "• Prophet: Pola musiman (butuh install prophet)."
    ))

    st.markdown("---")
    st.markdown("#### ⚙️ Tampilan")
    show_tech        = st.checkbox("Indikator Teknikal",   value=True)
    show_fundamental = st.checkbox("Data Fundamental",     value=True)
    show_mc_paths    = st.checkbox("Monte Carlo Paths",    value=False,
                                   help="50 skenario simulasi harga")
    show_ihsg        = st.checkbox("Panel IHSG",           value=True,
                                   help="Tampilkan indeks IHSG & sentimen pasar")

    st.markdown("---")
    run_btn = st.button("🔮 Mulai Prediksi", use_container_width=True)

    st.markdown("""<div class="info-box">
        💡 <b>Tips:</b><br>Data otomatis dari Yahoo Finance.
        Kode saham IDX tanpa .JK (contoh: BBCA, TLKM, GOTO, BREN).<br><br>
        ⏱️ Prediksi horizon berbeda menghasilkan hasil berbeda karena model mempertimbangkan <b>uncertainty yang meningkat</b> seiring waktu.
    </div>""", unsafe_allow_html=True)
    st.markdown("""<div class="warning-box">
        ⚠️ <b>Disclaimer:</b> Bukan rekomendasi investasi. Selalu riset mandiri.
    </div>""", unsafe_allow_html=True)

# ─── Tabs ──────────────────────────────────────────────────────────────────────
tab_analysis, tab_scanner = st.tabs(["📈 Analisis Saham", "🔍 Market Scanner"])

with tab_scanner:
    render_scanner_tab()

with tab_analysis:
    # Landing page (before run_btn)
    if not run_btn:
        if show_ihsg:
            st.markdown('<div class="section-header">🏛️ IHSG — Kondisi Pasar Saat Ini</div>', unsafe_allow_html=True)
            with st.spinner("📡 Mengambil data IHSG..."):
                df_ihsg_land = fetch_ihsg_data()
            render_ihsg_panel(df_ihsg_land)

        st.markdown("""<div class="section-header">📋 Cara Penggunaan</div>""", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        for col, (ico, ttl, dsc) in zip([c1,c2,c3,c4], [
            ("1️⃣","Input Kode Saham",  "Masukkan kode saham IDX di sidebar (BBCA, TLKM, dll)"),
            ("2️⃣","Atur Periode Data", "Pilih berapa tahun data historis yang digunakan"),
            ("3️⃣","Pilih Model AI",    "Gradient Boosting direkomendasikan untuk akurasi terbaik"),
            ("4️⃣","Mulai Prediksi",    "Klik 🔮 dan lihat prediksi + probabilitas naik/turun"),
        ]):
            with col:
                st.markdown(f"""<div class="metric-card" style="text-align:center;min-height:160px;">
                    <div style="font-size:2rem;margin-bottom:12px;">{ico}</div>
                    <div style="color:#60a5fa;font-weight:700;font-size:0.9rem;margin-bottom:8px;">{ttl}</div>
                    <div style="color:#475569;font-size:0.8rem;line-height:1.6;">{dsc}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("""<div class="section-header">🚀 Fitur Unggulan</div>""", unsafe_allow_html=True)
        fc1, fc2, fc3 = st.columns(3)
        for i, (ttl, dsc) in enumerate([
            ("🏛️ Panel IHSG",           "Indeks pasar real-time + sentimen Bullish/Bearish/Sideways."),
            ("🎯 Prediksi Per Horizon", "7 hari vs 30 hari vs 90 hari menghasilkan prediksi berbeda sesuai uncertainty."),
            ("🕯️ Candlestick Chart",   "Grafik OHLC interaktif + MA20/50/200 + Bollinger Bands."),
            ("📐 Indikator Teknikal",  "RSI, MACD, Volume analysis lengkap."),
            ("🎲 Monte Carlo 2.000x",  "Probabilitas naik/turun dari 2.000 skenario simulasi harga."),
            ("📋 Evaluasi Model",      "MAE, RMSE, R² Score — transparan & terukur."),
        ]):
            with [fc1,fc2,fc3][i%3]:
                st.markdown(f"""<div class="metric-card" style="min-height:110px;">
                    <div style="color:#60a5fa;font-weight:700;font-size:0.9rem;margin-bottom:10px;">{ttl}</div>
                    <div style="color:#475569;font-size:0.8rem;line-height:1.6;">{dsc}</div>
                </div>""", unsafe_allow_html=True)
        st.stop()

    # ─── IHSG Panel ────────────────────────────────────────────────────────────
    if show_ihsg:
        st.markdown('<div class="section-header">🏛️ IHSG — Kondisi Pasar Saat Ini</div>', unsafe_allow_html=True)
        with st.spinner("📡 Mengambil data IHSG..."):
            df_ihsg = fetch_ihsg_data()
        render_ihsg_panel(df_ihsg)
        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    # ─── Process tickers ───────────────────────────────────────────────────────
    ticker_list = [t.strip().upper() for t in saham_input.split(",") if t.strip()]
    if not ticker_list:
        st.error("⚠️ Masukkan minimal satu kode saham.")
        st.stop()

    if len(ticker_list) > 1:
        st.markdown(f"""<div class="section-header">🔀 Perbandingan: {' · '.join(ticker_list)}</div>""", unsafe_allow_html=True)
        comp = {}
        with st.spinner("Mengambil data semua saham..."):
            for tk in ticker_list:
                d, ft = fetch_stock_data(tk, period_years)
                if d is not None: comp[tk] = (d, ft)
        if comp:
            palette = ["#60a5fa","#4ade80","#fbbf24","#f87171","#c084fc","#34d399"]
            fig_c = go.Figure()
            for i,(tk,(d,ft)) in enumerate(comp.items()):
                norm = d["Close"] / d["Close"].iloc[0] * 100
                fig_c.add_trace(go.Scatter(x=d.index, y=norm, name=tk, mode="lines",
                                            line=dict(width=2.2, color=palette[i%len(palette)])))
            fig_c.update_layout(**CHART_LAYOUT,
                                title=dict(text="📊 Perbandingan Performa (Normalized=100)",
                                           font=dict(size=14,color="#e2e8f0")),
                                height=380, yaxis_title="Performa (%)", xaxis_title="Tanggal")
            st.plotly_chart(fig_c, use_container_width=True)
        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    # ─── Per-stock analysis ────────────────────────────────────────────────────
    for ticker_raw in ticker_list:
        tru = ticker_raw.upper()
        st.markdown(f"""<div class="section-header">🏦 Analisis: {tru}</div>""", unsafe_allow_html=True)

        with st.spinner(f"📡 Mengambil data {tru}..."):
            df, ticker = fetch_stock_data(ticker_raw, period_years)
            info = fetch_stock_info(ticker if ticker.endswith(".JK") else tru + ".JK")

        if df is None or df.empty:
            st.error(f"❌ Tidak dapat mengambil data **{tru}**. Pastikan kode saham valid.")
            continue

        df = add_technical_indicators(df)
        close      = _scalar(df["Close"].iloc[-1])
        prev_close = _scalar(df["Close"].iloc[-2])
        change     = close - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        is_up      = change >= 0
        color_cls  = "price-change-pos" if is_up else "price-change-neg"

        daily_ret = df["Close"].pct_change().dropna()
        hist_vol  = float(daily_ret.std() * np.sqrt(252))

        # Price header
        cp, ci_col = st.columns([1, 2])
        with cp:
            vol_lbl = "Rendah 🟢" if hist_vol < 0.25 else "Sedang 🟡" if hist_vol < 0.45 else "Tinggi 🔴"
            st.markdown(f"""<div class="metric-card" style="text-align:center;padding:28px 24px;">
                <div class="metric-label">{ticker} · IDX</div>
                <div class="price-display">Rp {close:,.0f}</div>
                <div class="{color_cls}" style="font-size:1.1rem;margin-top:10px;font-weight:700;">
                    {'▲' if is_up else '▼'} Rp {abs(change):,.0f} ({abs(change_pct):.2f}%)
                </div>
                <div style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(99,179,237,0.1);">
                    <div style="display:flex;justify-content:space-between;font-size:0.75rem;">
                        <div><span style="color:#475569;">Volatilitas</span><br>
                             <span style="color:#e2e8f0;font-weight:700;">{hist_vol*100:.1f}%/yr</span><br>
                             <span style="font-size:0.68rem;color:#64748b;">{vol_lbl}</span></div>
                        <div><span style="color:#475569;">Per</span><br>
                             <span style="color:#e2e8f0;font-weight:700;">{df.index[-1].strftime('%d %b %Y')}</span></div>
                        <div><span style="color:#475569;">Data</span><br>
                             <span style="color:#e2e8f0;font-weight:700;">{len(df):,} hari</span></div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

        with ci_col:
            cname  = get_safe(info,"longName",ticker)
            sector = get_safe(info,"sector","N/A")
            indust = get_safe(info,"industry","N/A")
            w52h   = get_safe_num(info,"fiftyTwoWeekHigh")
            w52l   = get_safe_num(info,"fiftyTwoWeekLow")
            avgvol = get_safe_num(info,"averageVolume")
            curr   = get_safe(info,"currency","IDR")
            pos52  = 0.0
            if w52h and w52l and (w52h - w52l) > 0:
                pos52 = max(0, min(100, (close - w52l) / (w52h - w52l) * 100))
            st.markdown(f"""<div class="metric-card" style="padding:22px 26px;">
                <div style="color:#f1f5f9;font-weight:800;font-size:1.15rem;margin-bottom:16px;">{cname}</div>
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:16px;">
                    <div><div class="metric-label">Sektor</div><div style="color:#93c5fd;font-weight:600;font-size:0.82rem;">{sector}</div></div>
                    <div><div class="metric-label">Industri</div><div style="color:#93c5fd;font-weight:600;font-size:0.82rem;">{indust}</div></div>
                    <div><div class="metric-label">Avg Volume</div><div style="color:#e2e8f0;font-weight:600;font-size:0.82rem;">{format_number(avgvol) if avgvol else 'N/A'}</div></div>
                    <div><div class="metric-label">52W High</div><div style="color:#4ade80;font-weight:700;font-size:0.82rem;">Rp {w52h:,.0f}</div></div>
                    <div><div class="metric-label">52W Low</div><div style="color:#f87171;font-weight:700;font-size:0.82rem;">Rp {w52l:,.0f}</div></div>
                    <div><div class="metric-label">Mata Uang</div><div style="color:#e2e8f0;font-weight:600;font-size:0.82rem;">{curr}</div></div>
                </div>
                <div>
                    <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#475569;margin-bottom:5px;">
                        <span>52W Range</span><span style="color:#93c5fd;font-weight:600;">{pos52:.0f}% dari Low</span>
                    </div>
                    <div class="prob-bar-track">
                        <div style="height:100%;border-radius:999px;width:{pos52}%;background:linear-gradient(90deg,#f87171,#fbbf24,#4ade80);"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:0.68rem;color:#374151;margin-top:4px;">
                        <span>Rp {w52l:,.0f}</span><span>Rp {w52h:,.0f}</span>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

        # Fundamental
        if show_fundamental:
            st.markdown("""<div class="section-header">📊 Key Stats — Data Fundamental</div>""", unsafe_allow_html=True)

            def gn(k): return get_safe_num(info, k)

            pe=gn("trailingPE"); fpe=gn("forwardPE"); pb=gn("priceToBook")
            ps=gn("priceToSalesTrailing12Months"); mc=gn("marketCap"); ev=gn("enterpriseValue")
            dy=gn("dividendYield"); pr=gn("payoutRatio"); eps=gn("trailingEps")
            feps=gn("forwardEps"); rev=gn("totalRevenue"); gp=gn("grossProfits")
            ni=gn("netIncomeToCommon"); ta=gn("totalAssets"); td=gn("totalDebt")
            bv=gn("bookValue"); so=gn("sharesOutstanding"); roe=gn("returnOnEquity")
            roa=gn("returnOnAssets"); pm=gn("profitMargins"); eb=gn("ebitda")
            eve=gn("enterpriseToEbitda"); de=gn("debtToEquity"); beta=gn("beta")

            st.markdown("##### 💰 Valuasi")
            cols = st.columns(6)
            for col,(lbl,val) in zip(cols,[
                ("PE Ratio (TTM)",f"{pe:.2f}x" if pe else "N/A"),
                ("Forward PE",f"{fpe:.2f}x" if fpe else "N/A"),
                ("Price/Book",f"{pb:.2f}x" if pb else "N/A"),
                ("Price/Sales",f"{ps:.2f}x" if ps else "N/A"),
                ("EV/EBITDA",f"{eve:.2f}x" if eve else "N/A"),
                ("Beta",f"{beta:.2f}" if beta else "N/A"),
            ]):
                with col: st.markdown(metric_card(lbl,val), unsafe_allow_html=True)

            st.markdown("##### 🏢 Market & Income")
            cols = st.columns(6)
            for col,(lbl,val) in zip(cols,[
                ("Market Cap",format_number(mc) if mc else "N/A"),
                ("Enterprise Val",format_number(ev) if ev else "N/A"),
                ("Revenue TTM",format_number(rev) if rev else "N/A"),
                ("Gross Profit",format_number(gp) if gp else "N/A"),
                ("EBITDA",format_number(eb) if eb else "N/A"),
                ("Net Income",format_number(ni) if ni else "N/A"),
            ]):
                with col: st.markdown(metric_card(lbl,val), unsafe_allow_html=True)

            st.markdown("##### 📈 Per Saham & Dividen")
            cols = st.columns(6)
            for col,(lbl,val) in zip(cols,[
                ("EPS TTM",f"Rp {eps:,.2f}" if eps else "N/A"),
                ("EPS Forward",f"Rp {feps:,.2f}" if feps else "N/A"),
                ("Div Yield",f"{dy*100:.2f}%" if dy else "N/A"),
                ("Payout Ratio",f"{pr*100:.1f}%" if pr else "N/A"),
                ("Shares Out",format_number(so) if so else "N/A"),
                ("Book Val/Share",f"Rp {bv:,.0f}" if bv else "N/A"),
            ]):
                with col: st.markdown(metric_card(lbl,val), unsafe_allow_html=True)

            st.markdown("##### 🏦 Balance Sheet & Rasio")
            cols = st.columns(6)
            for col,(lbl,val) in zip(cols,[
                ("Total Assets",format_number(ta) if ta else "N/A"),
                ("Total Debt",format_number(td) if td else "N/A"),
                ("ROE",f"{roe*100:.1f}%" if roe else "N/A"),
                ("ROA",f"{roa*100:.1f}%" if roa else "N/A"),
                ("Profit Margin",f"{pm*100:.1f}%" if pm else "N/A"),
                ("Debt/Equity",f"{de:.2f}" if de else "N/A"),
            ]):
                with col: st.markdown(metric_card(lbl,val), unsafe_allow_html=True)

        # Candlestick
        st.markdown("""<div class="section-header">🕯️ Grafik Harga Historis</div>""", unsafe_allow_html=True)
        st.plotly_chart(chart_candlestick(df, ticker), use_container_width=True)

        # Technical indicators
        if show_tech:
            st.markdown("""<div class="section-header">📐 Indikator Teknikal</div>""", unsafe_allow_html=True)
            rsi_v = float(df["RSI"].iloc[-1])     if "RSI"         in df and not pd.isna(df["RSI"].iloc[-1])         else None
            macd_v= float(df["MACD"].iloc[-1])    if "MACD"        in df and not pd.isna(df["MACD"].iloc[-1])        else None
            sig_v = float(df["MACD_signal"].iloc[-1]) if "MACD_signal" in df and not pd.isna(df["MACD_signal"].iloc[-1]) else None
            ma20  = float(df["MA20"].iloc[-1])    if "MA20"        in df and not pd.isna(df["MA20"].iloc[-1])        else None
            ma50  = float(df["MA50"].iloc[-1])    if "MA50"        in df and not pd.isna(df["MA50"].iloc[-1])        else None

            t1,t2,t3,t4 = st.columns(4)
            with t1:
                if rsi_v:
                    lbl = "Overbought ⚠️" if rsi_v>70 else "Oversold 🟢" if rsi_v<30 else "Netral ⚪"
                    st.markdown(metric_card("RSI (14)", f"{rsi_v:.1f}", lbl, rsi_v<70), unsafe_allow_html=True)
            with t2:
                if macd_v and sig_v:
                    trend = "Bullish 🟢" if macd_v>sig_v else "Bearish 🔴"
                    st.markdown(metric_card("MACD Signal", trend, f"MACD: {macd_v:.2f}", macd_v>sig_v), unsafe_allow_html=True)
            with t3:
                if ma20:
                    ab = close > ma20
                    st.markdown(metric_card("MA 20", f"Rp {ma20:,.0f}", "Di atas ✅" if ab else "Di bawah ⚠️", ab), unsafe_allow_html=True)
            with t4:
                if ma50:
                    ab50 = close > ma50
                    st.markdown(metric_card("MA 50", f"Rp {ma50:,.0f}", "Di atas ✅" if ab50 else "Di bawah ⚠️", ab50), unsafe_allow_html=True)
            st.plotly_chart(chart_rsi_macd(df), use_container_width=True)

        # Prediction section
        st.markdown('<div style="margin-top:36px;"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-header">🔮 Prediksi Harga — {model_choice} · {horizon} Hari</div>', unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background:rgba(59,130,246,0.07);border:1px solid rgba(59,130,246,0.2);
                    border-radius:12px;padding:12px 18px;margin-bottom:16px;font-size:0.8rem;color:#93c5fd;line-height:1.7;">
            🎯 <b>Horizon {horizon} Hari</b> — Model memperhitungkan <b>uncertainty yang bertambah</b> seiring panjang horizon.
            Prediksi 7 hari memiliki confidence interval lebih sempit dibanding prediksi 30/90 hari.
            Semakin panjang horizon, semakin lebar CI 95% yang ditampilkan di grafik.
        </div>
        """, unsafe_allow_html=True)

        actual = predicted = future = metrics_res = ci = None
        error_msg = None
        with st.spinner(f"🧠 Menjalankan {model_choice} untuk horizon {horizon} hari..."):
            try:
                if model_choice == "Linear Regression":
                    r = predict_linear(df, horizon, hist_vol=hist_vol)
                    if r and r[0] is not None:
                        actual, predicted, future, metrics_res = r
                elif model_choice == "Random Forest":
                    r = predict_random_forest(df, horizon, hist_vol=hist_vol)
                    if r and r[0] is not None:
                        actual, predicted, future, metrics_res = r
                elif model_choice == "Gradient Boosting":
                    r = predict_gradient_boosting(df, horizon, hist_vol=hist_vol)
                    if r and r[0] is not None:
                        actual, predicted, future, metrics_res = r
                elif model_choice == "Prophet":
                    r = predict_prophet(df, horizon)
                    if r and r[0] is not None:
                        actual, predicted, future, metrics_res, ci = r
            except Exception as e:
                error_msg = str(e)

        if error_msg:
            st.error(f"❌ Error saat menjalankan model: {error_msg}")
        elif future is None:
            st.warning("⚠️ Model gagal menghasilkan prediksi. Data mungkin terlalu sedikit atau terjadi error.")
        else:
            # Monte Carlo
            prob_up = prob_down = 0.5
            mc_ci_data = None
            with st.spinner("🎲 Menjalankan Monte Carlo simulation..."):
                try:
                    prob_up, prob_down, mc_ci_data = compute_monte_carlo(
                        future, close, hist_vol, n_simulations=2000, horizon=horizon
                    )
                except Exception:
                    pass

            last_pred    = float(future.iloc[-1])
            last_chg_pct = (last_pred - close) / close * 100

            # Probability card
            st.markdown(render_probability_card(prob_up, prob_down, model_choice, last_chg_pct, hist_vol, horizon),
                        unsafe_allow_html=True)

            # Prediction chart
            st.plotly_chart(
                chart_prediction(df, actual, predicted, future, ticker, model_choice, horizon,
                                 ci=ci, mc_ci=mc_ci_data if not show_mc_paths else mc_ci_data),
                use_container_width=True
            )

            # Model metrics
            if metrics_res:
                st.markdown("""<div class="section-header">📋 Evaluasi Model</div>""", unsafe_allow_html=True)
                m1,m2,m3 = st.columns(3)
                with m1: st.markdown(metric_card("MAE", f"Rp {metrics_res['MAE']:,.2f}"), unsafe_allow_html=True)
                with m2: st.markdown(metric_card("RMSE", f"Rp {metrics_res['RMSE']:,.2f}"), unsafe_allow_html=True)
                with m3: st.markdown(metric_card("R² Score", f"{metrics_res['R2']:.4f}"), unsafe_allow_html=True)

            # IHSG bullish signals count
            ihsg_bullish = 3  # default neutral
            try:
                dfi = fetch_ihsg_data()
                if dfi is not None and not dfi.empty:
                    ic = _scalar(dfi["Close"].iloc[-1])
                    ip = _scalar(dfi["Close"].iloc[-2])
                    dt30 = dfi.iloc[-30:]
                    t30  = (dt30["Close"].iloc[-1] - dt30["Close"].iloc[0]) / dt30["Close"].iloc[0] * 100
                    tf   = float(t30.iloc[0]) if isinstance(t30, pd.Series) else float(t30)
                    di   = dfi["Close"].diff()
                    gi   = di.clip(lower=0).rolling(14).mean()
                    li   = (-di.clip(upper=0)).rolling(14).mean()
                    rs   = 100 - (100 / (1 + gi / li.replace(0, np.nan)))
                    irsi = float(rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else 50.0
                    im20 = float(dfi["Close"].rolling(20).mean().iloc[-1])
                    im50 = float(dfi["Close"].rolling(50).mean().iloc[-1])
                    ihsg_bullish = sum([ic > ip, tf > 2, irsi > 50 and irsi < 70, ic > im20, ic > im50])
            except Exception:
                pass

            # Technical values for advice
            rsi_val   = float(df["RSI"].iloc[-1])          if "RSI"         in df and not pd.isna(df["RSI"].iloc[-1])         else None
            macd_val  = float(df["MACD"].iloc[-1])         if "MACD"        in df and not pd.isna(df["MACD"].iloc[-1])        else None
            macd_sval = float(df["MACD_signal"].iloc[-1])  if "MACD_signal" in df and not pd.isna(df["MACD_signal"].iloc[-1]) else None
            ma20_val  = float(df["MA20"].iloc[-1])         if "MA20"        in df and not pd.isna(df["MA20"].iloc[-1])        else None
            ma50_val  = float(df["MA50"].iloc[-1])         if "MA50"        in df and not pd.isna(df["MA50"].iloc[-1])        else None
            ma200_val = float(df["MA200"].iloc[-1])        if "MA200"       in df and not pd.isna(df["MA200"].iloc[-1])       else None

            # Model consensus (run all 3 ML models quickly for consensus)
            n_up = 1 if last_chg_pct > 0 else 0
            n_total = 1
            try:
                for fn in [predict_linear, predict_random_forest]:
                    r2 = fn(df, horizon, hist_vol=hist_vol)
                    if r2 and r2[2] is not None:
                        n_total += 1
                        if float(r2[2].iloc[-1]) > close:
                            n_up += 1
            except Exception:
                pass

            r2_score_val = metrics_res.get("R2", 0.5) if metrics_res else 0.5

            # ── Multi-model probability comparison ──────────────────────────────
            st.markdown('<div style="margin-top:36px;"></div>', unsafe_allow_html=True)
            st.markdown('<div class="section-header">⚖️ Perbandingan Semua Model</div>', unsafe_allow_html=True)
            
            all_model_probs = {}
            with st.spinner("🎲 Menghitung probabilitas Monte Carlo semua model..."):
                model_funcs = {
                    "Linear Regression": predict_linear,
                    "Random Forest": predict_random_forest,
                    "Gradient Boosting": predict_gradient_boosting,
                }
                # Check if prophet is imported correctly
                try:
                    from prophet import Prophet
                    model_funcs["Prophet"] = predict_prophet
                except ImportError:
                    pass
                
                for mname, mfunc in model_funcs.items():
                    try:
                        if mname == "Prophet":
                            r = mfunc(df, horizon)
                        else:
                            r = mfunc(df, horizon, hist_vol=hist_vol)
                        
                        if r and r[2] is not None:
                            f_series = r[2]
                            p_up, p_dn, _ = compute_monte_carlo(f_series, close, hist_vol, n_simulations=1000, horizon=horizon)
                            chg = (f_series.iloc[-1] - close)/close*100
                            all_model_probs[mname] = {"up": p_up, "down": p_dn, "chg": chg}
                    except Exception:
                        pass
                        
            if all_model_probs:
                cols = st.columns(len(all_model_probs))
                for col, (mname, pdata) in zip(cols, all_model_probs.items()):
                    with col:
                        st.markdown(f'''
                        <div style="background:rgba(30,41,59,0.5);border:1px solid rgba(99,179,237,0.2);border-radius:12px;padding:16px;text-align:center;">
                            <div style="font-size:0.85rem;font-weight:700;color:#94a3b8;margin-bottom:12px;">{mname}</div>
                            <div style="font-size:1.2rem;font-weight:800;color:{"#4ade80" if pdata["chg"]>0 else "#f87171"};margin-bottom:16px;">
                                {pdata["chg"]:+.2f}%
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:0.75rem;">
                                <span style="color:#4ade80;">Naik</span>
                                <span style="font-weight:700;color:#f8fafc;">{pdata["up"]:.1f}%</span>
                            </div>
                            <div style="width:100%;background:rgba(255,255,255,0.1);height:6px;border-radius:3px;margin-bottom:12px;overflow:hidden;">
                                <div style="width:{pdata["up"]}%;background:#4ade80;height:100%;"></div>
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:0.75rem;">
                                <span style="color:#f87171;">Turun</span>
                                <span style="font-weight:700;color:#f8fafc;">{pdata["down"]:.1f}%</span>
                            </div>
                            <div style="width:100%;background:rgba(255,255,255,0.1);height:6px;border-radius:3px;overflow:hidden;">
                                <div style="width:{pdata["down"]}%;background:#f87171;height:100%;"></div>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
            
            # ── Tabel prediksi harga (hanya hari trading BEI) ──────────────────────
            st.markdown('<div style="margin-top:36px;"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="section-header">📋 Tabel Prediksi Harga — {horizon} Hari Trading ke Depan</div>', unsafe_allow_html=True)

            if future is not None and not future.empty:
                # Dapatkan tanggal trading mulai besok
                trading_dates = get_trading_days(
                    datetime.today() + timedelta(days=1),
                    periods=len(future)
                )

                # Sesuaikan panjang array future dengan jumlah trading_dates
                n_td = len(trading_dates)
                future_vals = future.values[:n_td] if len(future.values) >= n_td else future.values

                fdf = pd.DataFrame({
                    "Tanggal":        trading_dates[:len(future_vals)].strftime("%d %b %Y"),
                    "Hari":           [d.strftime("%A").replace("Monday","Senin").replace("Tuesday","Selasa")
                                       .replace("Wednesday","Rabu").replace("Thursday","Kamis")
                                       .replace("Friday","Jumat") for d in trading_dates[:len(future_vals)]],
                    "Prediksi Harga": future_vals,
                })

                if mc_ci_data:
                    lower_arr = mc_ci_data["lower_95"][:len(future_vals)]
                    upper_arr = mc_ci_data["upper_95"][:len(future_vals)]
                    fdf["Batas Bawah (CI 95%)"] = lower_arr
                    fdf["Batas Atas (CI 95%)"] = upper_arr

                    # Kolom sinyal sederhana berdasarkan posisi prediksi
                    fdf["Perubahan %"] = [
                        f"+{((p - close) / close * 100):.2f}%" if p >= close
                        else f"{((p - close) / close * 100):.2f}%"
                        for p in future_vals
                    ]

                fdf.set_index("Tanggal", inplace=True)

                fmt = {"Prediksi Harga": "Rp {:,.0f}"}
                if mc_ci_data:
                    fmt["Batas Bawah (CI 95%)"] = "Rp {:,.0f}"
                    fmt["Batas Atas (CI 95%)"] = "Rp {:,.0f}"

                st.dataframe(fdf.style.format(fmt), use_container_width=True)

                # Info hari yang difilter
                total_cal = horizon
                n_trading  = len(future_vals)
                n_skipped  = total_cal - n_trading
                if n_skipped > 0:
                    st.markdown(
                        f'<div class="info-box" style="margin-top:8px;font-size:0.75rem;">'
                        f'📅 <b>{n_skipped} hari</b> kalender (weekend/libur nasional BEI) '
                        f'disembunyikan dari tabel. Hanya menampilkan <b>{n_trading} hari trading</b> aktif.'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                # ── Simpan ke Google Spreadsheet ────────────────────────────────────
                st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)

                # Cek apakah credentials tersedia
                gsheet_ready = _get_gsheet_client() is not None

                col_save, col_link = st.columns([1, 1])
                with col_save:
                    save_key = f"save_sheet_{ticker}_{horizon}"
                    if gsheet_ready:
                        save_btn = st.button(
                            "📤 Simpan ke Google Spreadsheet",
                            key=save_key,
                            use_container_width=True,
                            help="Simpan tabel prediksi ini langsung ke Google Spreadsheet Anda"
                        )
                        if save_btn:
                            with st.spinner("⏳ Menyimpan ke Google Spreadsheet..."):
                                ok, msg = save_to_gsheet(
                                    ticker, close, model_choice, horizon,
                                    fdf, prob_up, prob_down
                                )
                            if ok:
                                st.success(msg)
                                st.balloons()
                            else:
                                st.error(f"❌ Gagal menyimpan: {msg}")
                    else:
                        st.markdown(
                            '<div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);'
                            'border-radius:10px;padding:12px 16px;font-size:0.78rem;color:#fbbf24;">'
                            '⚙️ <b>Simpan otomatis belum aktif.</b><br>'
                            'Perlu setup Google API di Streamlit Secrets. Lihat panduan di bawah.'
                            '</div>',
                            unsafe_allow_html=True
                        )

                with col_link:
                    st.markdown(
                        f'<a href="{SPREADSHEET_URL}" target="_blank" rel="noopener noreferrer" '
                        f'style="display:flex;align-items:center;justify-content:center;gap:8px;'
                        f'background:linear-gradient(135deg,rgba(34,197,94,0.12),rgba(16,185,129,0.08));'
                        f'border:1px solid rgba(34,197,94,0.35);border-radius:10px;padding:11px 0;'
                        f'color:#4ade80;font-weight:700;font-size:0.85rem;text-decoration:none;'
                        f'height:100%;box-sizing:border-box;">'
                        f'📊 Buka Spreadsheet</a>',
                        unsafe_allow_html=True
                    )

                if not gsheet_ready:
                    with st.expander("📖 Cara Aktifkan Simpan Otomatis ke Google Spreadsheet"):
                        st.markdown("""
**Langkah 1 — Buat Google Cloud Service Account:**
1. Buka [console.cloud.google.com](https://console.cloud.google.com)
2. Buat project baru (atau pilih yang sudah ada)
3. Aktifkan **Google Sheets API** dan **Google Drive API**
4. Buka **IAM & Admin → Service Accounts → Create Service Account**
5. Download file JSON credentials-nya

**Langkah 2 — Bagikan Spreadsheet ke Service Account:**
1. Buka file JSON, cari nilai `client_email` (contoh: `nama@project.iam.gserviceaccount.com`)
2. Buka [Spreadsheet Anda](https://docs.google.com/spreadsheets/d/1NXkbSNfIPVLIHYAynesY20jzNpboBSzpquVrOE08gXM)
3. Klik **Share (Bagikan)** → masukkan email service account → beri akses **Editor**

**Langkah 3 — Tambahkan Secrets di Streamlit Cloud:**
1. Buka [share.streamlit.io](https://share.streamlit.io) → pilih app Anda
2. Klik **Settings → Secrets**
3. Paste isi berikut (ganti dengan isi file JSON Anda):
```toml
[gcp_service_account]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_KEY_ID"
private_key = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "YOUR@project.iam.gserviceaccount.com"
client_id = "YOUR_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
```
4. Klik **Save** → app akan otomatis restart
5. Setelah itu tombol **Simpan ke Spreadsheet** akan aktif ✅
                        """)

            st.markdown("""<div class="section-header">🧠 Saran AI & Rekomendasi</div>""", unsafe_allow_html=True)
            render_investment_advice(
                ticker, close, last_pred, last_chg_pct,
                prob_up, prob_down, hist_vol,
                horizon, model_choice, r2_score_val,
                rsi_val, macd_val, macd_sval,
                ma20_val, ma50_val, ma200_val,
                ihsg_bullish,
                n_up, n_total,
                mc_ci_data if mc_ci_data else {"lower_95": [close * 0.9] * horizon, "upper_95": [close * 1.1] * horizon,
                                                "lower_68": [close * 0.95] * horizon, "upper_68": [close * 1.05] * horizon,
                                                "paths": np.zeros((50, horizon))}
            )

        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)
