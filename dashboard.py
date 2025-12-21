from datetime import date
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go
import requests
from streamlit_option_menu import option_menu
import streamlit.components.v1 as components


st.set_page_config(page_title="Cross-Asset Market Monitor", layout="wide")

### Fixed infos

PLOTLY_TEMPLATE = "plotly_dark"
FRED_API_KEY = "85f2a3a19b2c857b1ba184bd27e73f68"

RANGE_OPTIONS = [
    "Past Week", "Past Month", "Past 3 Months", "Past 6 Months",
    "YTD", "Past Year", "Past 2 Years", "Max", "Custom"
]
PERF_HORIZONS = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y"]

INDICATORS_ALL = ["SMA 20", "SMA 50", "RSI 14"]
INDICATORS_COMMO_EXTRA = ["Seasonality"]


# ====================================================
# CSS / UI
# ====================================================

def inject_css():
    """
    Inject custom CSS to control spacing and visual style.
    The goal is a compact dashboard layout with consistent typography.
    """
    st.markdown(
        """
        <style>
          .block-container { padding-top: 0.6rem; padding-bottom: 1.2rem; }
          header { visibility: hidden; height: 0px; }

          h1, h2, h3 { margin-bottom: 0.15rem !important; }
          h4 { margin-top: 0.15rem !important; margin-bottom: 0.15rem !important; }

          /* reduce whitespace before charts */
          div[data-testid="stPlotlyChart"] { margin-top: -14px; }

          .title {
            font-size: 34px;
            font-weight: 800;
            line-height: 1.05;
            margin-bottom: 2px;
          }
          .muted { color: rgba(255,255,255,0.70); font-size: 13px; }

          hr.sep {
            border: none;
            border-top: 1px solid rgba(255,255,255,0.10);
            margin: 10px 0 14px 0;
          }

          /* date inputs compact */
          div[data-testid="stDateInput"] label { display:none; }
          div[data-testid="stDateInput"] { margin-top: -6px; }

          /* make widgets more compact */
          div[data-testid="stCheckbox"] { margin-bottom: -8px; }
          div[data-testid="stCheckbox"] label { padding-top: 0px; padding-bottom: 0px; }
          div[data-testid="stCheckbox"] label { margin-left: -6px; }

          .note {
            color: rgba(255,255,255,0.55);
            font-style: italic;
            font-size: 12.5px;
            margin-top: 6px;
          }
          .pos { color: #2ecc71; font-weight: 800; }
          .neg { color: #ff4d4f; font-weight: 800; }
          .dim { color: rgba(255,255,255,0.70); }
          .tiny { font-size: 12px; }
        </style>
        """,
        unsafe_allow_html=True
    )

def top_nav():
    """
    Render the top navigation bar and return the selected page.
    """
    st.markdown(
        """
        <div class="title">Cross-Asset Market Monitor</div>
        <div class="muted">Live data from Yahoo Finance &amp; FRED</div>
        """,
        unsafe_allow_html=True
    )

    choice = option_menu(
        menu_title=None,
        options=["Overview", "Macro", "Commodities"],
        icons=["bar-chart-fill", "graph-up-arrow", "grid-3x3-gap-fill"],
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"font-size": "16px"},
            "nav-link": {
                "font-size": "16px",
                "text-align": "center",
                "margin": "0px",
                "padding": "10px 12px",
                "border-radius": "12px",
            },
            "nav-link-selected": {
                "background-color": "rgba(255,255,255,0.10)",
                "font-weight": "800",
            },
        },
    )

    st.markdown('<hr class="sep">', unsafe_allow_html=True)
    return choice


# ====================================================
# TradingView widgets (embed)
# ====================================================

def tv_economic_calendar(height=520):
    """
    Embed TradingView Economic Calendar widget.
    """
    html = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
      {{
        "colorTheme": "dark",
        "isTransparent": true,
        "width": "100%",
        "height": "{height}",
        "locale": "en",
        "importanceFilter": "-1,0,1",
        "currencyFilter": "USD,EUR,GBP,JPY,CHF,AUD,CAD,NZD"
      }}
      </script>
    </div>
    """
    components.html(html, height=height, scrolling=False)

def tv_news(height=520):
    """
    Embed TradingView news timeline widget.
    """
    html = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-timeline.js" async>
      {{
        "colorTheme": "dark",
        "isTransparent": true,
        "displayMode": "regular",
        "width": "100%",
        "height": "{height}",
        "locale": "en"
      }}
      </script>
    </div>
    """
    components.html(html, height=height, scrolling=False)


# ====================================================
# Data helpers
# ====================================================

def download_data(tickers, start_date=None, end_date=None, interval="1d"):
    """
    Download adjusted close prices from Yahoo Finance.
    Returns a DataFrame with one column per ticker.
    """
    data = yf.download(
        tickers, start=start_date, end=end_date, interval=interval,
        auto_adjust=True, progress=False
    )["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame()
    return data

def preprocess(df: pd.DataFrame):
    """
    Forward fill missing values and drop columns that are fully empty.
    """
    return df.ffill().dropna(how="all")

def normalize(prices: pd.DataFrame):
    """
    Convert prices to an index starting at 1 using cumulative returns.
    """
    r = prices.pct_change().fillna(0)
    return (1 + r).cumprod()

def _fmt_num(x, nd=2):
    """
    Safe numeric formatting for tables and metrics.
    """
    try:
        if pd.isna(x):
            return "-"
        return f"{float(x):,.{nd}f}"
    except Exception:
        return "-"

def _asof_value(series: pd.Series, dt: pd.Timestamp):
    """
    Return the last available value at or before a given date.
    """
    s = series.dropna()
    if s.empty:
        return np.nan
    sub = s.loc[:dt]
    if sub.empty:
        return np.nan
    return float(sub.iloc[-1])

def compute_ytd(series: pd.Series):
    """
    Compute year to date performance as a percentage.
    """
    s = series.dropna()
    if s.empty:
        return np.nan
    y0 = pd.Timestamp(s.index[-1].year, 1, 1)
    sub = s.loc[y0:]
    if sub.empty:
        return (s.iloc[-1] / s.iloc[0] - 1) * 100.0
    return (sub.iloc[-1] / sub.iloc[0] - 1) * 100.0

def compute_perf(series: pd.Series, horizon: str):
    """
    Compute performance over a chosen horizon.
    Horizons use a date offset and an as-of lookup.
    """
    s = series.dropna()
    if len(s) < 2:
        return np.nan

    last_dt = s.index[-1]
    last = float(s.iloc[-1])

    if horizon == "1D":
        prev = float(s.iloc[-2])
        return (last / prev - 1) * 100.0

    if horizon == "1W":
        dt = last_dt - pd.DateOffset(weeks=1)
        base = _asof_value(s, dt)
        return (last / base - 1) * 100.0 if pd.notna(base) and base != 0 else np.nan

    if horizon == "1M":
        dt = last_dt - pd.DateOffset(months=1)
        base = _asof_value(s, dt)
        return (last / base - 1) * 100.0 if pd.notna(base) and base != 0 else np.nan

    if horizon == "3M":
        dt = last_dt - pd.DateOffset(months=3)
        base = _asof_value(s, dt)
        return (last / base - 1) * 100.0 if pd.notna(base) and base != 0 else np.nan

    if horizon == "6M":
        dt = last_dt - pd.DateOffset(months=6)
        base = _asof_value(s, dt)
        return (last / base - 1) * 100.0 if pd.notna(base) and base != 0 else np.nan

    if horizon == "1Y":
        dt = last_dt - pd.DateOffset(years=1)
        base = _asof_value(s, dt)
        return (last / base - 1) * 100.0 if pd.notna(base) and base != 0 else np.nan

    if horizon == "YTD":
        return compute_ytd(s)

    return np.nan


# ====================================================
# Range helpers
# ====================================================

def compute_start_end(df_min: pd.Timestamp, rng: str, end_ts: pd.Timestamp, custom_start=None, custom_end=None):
    """
    Convert a UI range selection to a start and end timestamp.
    """
    if rng == "Past Week":
        return end_ts - pd.DateOffset(weeks=1), end_ts
    if rng == "Past Month":
        return end_ts - pd.DateOffset(months=1), end_ts
    if rng == "Past 3 Months":
        return end_ts - pd.DateOffset(months=3), end_ts
    if rng == "Past 6 Months":
        return end_ts - pd.DateOffset(months=6), end_ts
    if rng == "YTD":
        return pd.Timestamp(end_ts.year, 1, 1), end_ts
    if rng == "Past Year":
        return end_ts - pd.DateOffset(years=1), end_ts
    if rng == "Past 2 Years":
        return end_ts - pd.DateOffset(years=2), end_ts
    if rng == "Max":
        return df_min, end_ts

    s = pd.to_datetime(custom_start) if custom_start is not None else df_min
    e = pd.to_datetime(custom_end) if custom_end is not None else end_ts
    return s, e

def range_row_standard(df_min: pd.Timestamp, key_prefix: str, default_range="Past Year"):
    """
    Render the standard Range selector line.
    If Custom is selected, it shows Start and End inputs.
    """
    c1, c2, c3 = st.columns([1.6, 1.2, 1.2], vertical_alignment="bottom")
    with c1:
        rng = st.selectbox("Range", RANGE_OPTIONS, index=RANGE_OPTIONS.index(default_range), key=f"{key_prefix}_rng")

    custom_start = None
    custom_end = None
    end_default = date.today()

    if rng == "Custom":
        with c2:
            st.caption("Start")
            custom_start = st.date_input(
                "Start", value=max(df_min.date(), (pd.Timestamp(end_default) - pd.DateOffset(years=1)).date()),
                key=f"{key_prefix}_start", label_visibility="collapsed"
            )
        with c3:
            st.caption("End")
            custom_end = st.date_input(
                "End", value=end_default, key=f"{key_prefix}_end", label_visibility="collapsed"
            )
    else:
        with c2:
            st.empty()
        with c3:
            st.empty()

    end_ts = pd.to_datetime(custom_end if rng == "Custom" else end_default)
    start_ts, end_ts = compute_start_end(df_min, rng, end_ts, custom_start, custom_end)
    return start_ts, end_ts


# ====================================================
# Plot helpers
# ====================================================

def layout_common(fig, title: str, height: int, y_title: str = ""):
    """
    Apply a consistent Plotly layout across all figures.
    The legend is positioned below the title for reliability.
    """
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        height=height,
        margin=dict(l=40, r=40, t=58, b=86),
        title=dict(text=title, x=0.0, xanchor="left", y=0.98, yanchor="top"),
        legend=dict(
            orientation="h",
            x=0, y=-0.18,
            xanchor="left", yanchor="top",
            title_text="",
            bgcolor="rgba(0,0,0,0)"
        ),
    )
    fig.update_yaxes(title_text=y_title)
    return fig

def plot_lines(df: pd.DataFrame, labels: dict, title: str, height=430, y_title="", y_as_percent=False):
    """
    Plot one or multiple time series as lines.
    """
    fig = go.Figure()
    for col in df.columns:
        name = labels.get(col, col) or col
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col],
            mode="lines",
            name=name,
            line=dict(width=2),
            hovertemplate="%{x}<br>%{y}<extra>" + name + "</extra>"
        ))
    layout_common(fig, title, height, y_title=y_title)
    if y_as_percent:
        fig.update_yaxes(tickformat=".0%")
    return fig

def add_sma(fig, s: pd.Series, window: int, name: str):
    """
    Add a simple moving average to an existing price chart.
    """
    ma = s.rolling(window).mean()
    fig.add_trace(go.Scatter(
        x=ma.index, y=ma.values,
        mode="lines",
        name=name,
        line=dict(width=1),
        opacity=0.9
    ))
    return fig

def rsi_14(s: pd.Series, period=14):
    """
    Compute RSI using a simple moving average of gains and losses.
    """
    delta = s.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    gain = up.rolling(period).mean()
    loss = down.rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def plot_rsi(rsi: pd.Series, height=220):
    """
    Plot RSI as a separate chart with overbought and oversold levels.
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rsi.index, y=rsi.values, mode="lines", name="RSI 14", line=dict(width=2)))
    layout_common(fig, "RSI 14", height, y_title="")
    fig.update_yaxes(range=[0, 100])
    fig.add_hline(y=70, line_width=1, opacity=0.35)
    fig.add_hline(y=30, line_width=1, opacity=0.35)
    return fig


# ====================================================
# FRED helpers
# ====================================================

def fred_get(series_id, start="1990-01-01"):
    """
    Download a FRED time series and return it as a pandas Series.
    """
    r = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "observation_start": start
        },
        timeout=25
    ).json()

    obs = r.get("observations", [])
    if not obs:
        return pd.Series(dtype=float, name=series_id)

    s = pd.Series(
        [float(o["value"]) if o["value"] not in [".", None, ""] else None for o in obs],
        index=pd.to_datetime([o["date"] for o in obs]),
        name=series_id
    ).ffill()
    return s

def latest_value(series_id: str, start="1990-01-01"):
    """
    Convenience wrapper to get the latest value of a FRED series.
    """
    s = fred_get(series_id, start=start).dropna()
    if s.empty:
        return np.nan
    return float(s.iloc[-1])

def pct_yoy(s: pd.Series) -> pd.Series:
    """
    Compute year over year percentage change.
    """
    s = s.dropna()
    if s.empty:
        return s
    return (s / s.shift(12) - 1.0) * 100.0


# ====================================================
# OVERVIEW
# ====================================================

WATCHLIST_GROUPS = {
    "Indices": {
        "S&P 500 (SPX)": "^GSPC",
        "NASDAQ 100 (NDX)": "^NDX",
        "Euro Stoxx 50 (SX5E)": "^STOXX50E",
        "CAC 40 (CAC)": "^FCHI",
        "DAX (DAX)": "^GDAXI",
        "Nikkei 225 (NKY)": "^N225",
        "MSCI EM (EEM)": "EEM",
    },
    "Macro": {
        "US Dollar Index (DXY)": "DX=F",
        "US 10Y T-Note (ZN)": "ZN=F",
    },
    "Commodities": {
        "Gold (GC)": "GC=F",
        "WTI Crude (CL)": "CL=F",
        "Wheat (ZW)": "ZW=F",
    }
}

OVERVIEW_BENCH = {
    "None": None,
    "MSCI World (URTH)": "URTH",
    "S&P 500 (SPX)": "^GSPC",
}

def render_overview():
    """
    Overview page.
    Right side is the watchlist with performance and selection.
    Left side is a chart of one asset or normalized performance for multiple assets.
    """
    tickers = []
    label_by_ticker = {}
    for g, mp in WATCHLIST_GROUPS.items():
        for lbl, t in mp.items():
            tickers.append(t)
            label_by_ticker[t] = lbl
    tickers = list(dict.fromkeys(tickers))

    px = preprocess(download_data(tickers, "2005-01-01", date.today().strftime("%Y-%m-%d")))
    if px.empty:
        st.warning("No data loaded from Yahoo Finance.")
        return

    spx_ticker = "^GSPC"
    spx_key = f"wl_{spx_ticker}"
    if spx_key not in st.session_state:
        st.session_state[spx_key] = True

    # Layout
    left, right = st.columns([3.9, 1.3], vertical_alignment="top")

    with right:
        st.markdown("### Watchlist")
        perf_h = st.selectbox("Performance", PERF_HORIZONS, index=PERF_HORIZONS.index("YTD"), key="wl_perf")

        hdr1, hdr2, hdr3 = st.columns([1.9, 1.0, 1.0], vertical_alignment="center")
        with hdr1:
            st.markdown("<span class='dim tiny'>Symbol</span>", unsafe_allow_html=True)
        with hdr2:
            st.markdown("<div class='dim tiny' style='text-align:right'>Last</div>", unsafe_allow_html=True)
        with hdr3:
            st.markdown(f"<div class='dim tiny' style='text-align:right'>{perf_h}</div>", unsafe_allow_html=True)

        selected = []

        for group_name, mp in WATCHLIST_GROUPS.items():
            st.markdown('<hr class="sep">', unsafe_allow_html=True)
            st.markdown(f"**{group_name}**")

            for lbl, tkr in mp.items():
                if tkr not in px.columns:
                    continue
                s = px[tkr].dropna()
                if s.empty:
                    continue

                last = float(s.iloc[-1])
                perf = compute_perf(s, perf_h)
                perf_cls = "pos" if pd.notna(perf) and perf >= 0 else "neg"
                perf_txt = f"{perf:+.2f}%" if pd.notna(perf) else "-"

                r0, r1, r2 = st.columns([1.9, 1.0, 1.0], vertical_alignment="center")
                with r0:
                    chk = st.checkbox(lbl, key=f"wl_{tkr}")
                with r1:
                    st.markdown(f"<div class='dim' style='text-align:right'>{_fmt_num(last, 2)}</div>", unsafe_allow_html=True)
                with r2:
                    st.markdown(f"<div class='{perf_cls}' style='text-align:right'>{perf_txt}</div>", unsafe_allow_html=True)

                if chk:
                    selected.append((lbl, tkr))

        if not selected:
            st.info("Select one or more assets.")
            return

    with left:
        st.markdown("### Chart")

        top1, top2, top3 = st.columns([1.6, 1.6, 1.3], vertical_alignment="bottom")
        with top1:
            bench_label = st.selectbox("Benchmark (optional)", list(OVERVIEW_BENCH.keys()), index=0, key="ov_bench")
            bench_tkr = OVERVIEW_BENCH[bench_label]
        with top2:
            indicators = st.multiselect("Indicators", INDICATORS_ALL, default=[], key="ov_ind")
        with top3:
            start_used, end_ts = range_row_standard(px.index.min(), key_prefix="ov", default_range="Past Year")

        tickers_sel = [t for _, t in selected]
        df = px[tickers_sel].loc[start_used:end_ts].dropna(how="all")

        if df.empty:
            st.warning("No data on this range.")
            return

    
        # Chart Behavior
        if len(tickers_sel) == 1:
            t = tickers_sel[0]
            fig = plot_lines(df[[t]], {t: label_by_ticker.get(t, t)}, title="", height=620, y_title="")
            raw = df[t].dropna()
            if "SMA 20" in indicators:
                fig = add_sma(fig, raw, 20, "SMA 20")
            if "SMA 50" in indicators:
                fig = add_sma(fig, raw, 50, "SMA 50")
        else:
            norm = normalize(df) * 100.0
            labels = {t: label_by_ticker.get(t, t) for t in tickers_sel}
            fig = plot_lines(norm, labels, title="", height=620, y_title="Index (base 100)")
        st.plotly_chart(fig, use_container_width=True)

        if "RSI 14" in indicators and len(tickers_sel) == 1:
            r = rsi_14(df[tickers_sel[0]].dropna())
            if not r.dropna().empty:
                st.plotly_chart(plot_rsi(r), use_container_width=True)

    st.markdown('<hr class="sep">', unsafe_allow_html=True)
    w1, w2 = st.columns([1.45, 1.0], vertical_alignment="top")
    with w1:
        st.markdown("### Economic Calendar")
        tv_economic_calendar(height=560)
    with w2:
        st.markdown("### Latest News")
        tv_news(height=560)


# ====================================================
# MACRO
# ====================================================

OECD_10Y = {
    "United States": "IRLTLT01USM156N",
    "Germany": "IRLTLT01DEM156N",
    "France": "IRLTLT01FRM156N",
    "Italy": "IRLTLT01ITM156N",
    "United Kingdom": "IRLTLT01GBM156N",
    "Japan": "IRLTLT01JPM156N",
    "Spain": "IRLTLT01ESM156N",
    "Portugal": "IRLTLT01PTM156N",
    "Greece": "IRLTLT01GRM156N",
}

US_YIELDS = ["DGS1MO","DGS3MO","DGS6MO","DGS1","DGS2","DGS3","DGS5","DGS7","DGS10","DGS20","DGS30"]
_US_MAT_YEARS = {
    "DGS1MO":1/12, "DGS3MO":3/12, "DGS6MO":0.5,
    "DGS1":1, "DGS2":2, "DGS3":3, "DGS5":5, "DGS7":7,
    "DGS10":10, "DGS20":20, "DGS30":30
}
_US_LABELS = {
    "DGS1MO":"1M","DGS3MO":"3M","DGS6MO":"6M",
    "DGS1":"1Y","DGS2":"2Y","DGS3":"3Y","DGS5":"5Y","DGS7":"7Y",
    "DGS10":"10Y","DGS20":"20Y","DGS30":"30Y"
}

def fred_download(series, start="1990-01-01"):
    """
    Download multiple FRED series and return a DataFrame.
    """
    if isinstance(series, str):
        series = [series]
    out = []
    for s in series:
        out.append(fred_get(s, start=start))
    if not out:
        return pd.DataFrame()
    return pd.concat(out, axis=1).ffill()

def order_us_curve(df):
    """
    Sort US curve columns by maturity.
    """
    cols = [c for c in df.columns if c in _US_MAT_YEARS]
    return df.loc[:, sorted(cols, key=lambda c: _US_MAT_YEARS[c])]

def asof_row(df: pd.DataFrame, dt: pd.Timestamp):
    """
    Select the last available row at or before a date.
    """
    sub = df.loc[:dt]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.iloc[-1].dropna()

def plot_us_curve_compare(d1: pd.Timestamp, d2: pd.Timestamp):
    """
    Plot US yield curve at two dates for comparison.
    """
    us_df = fred_download(US_YIELDS, start="1990-01-01")
    us_df = order_us_curve(us_df).ffill()

    r1 = asof_row(us_df, d1)
    r2 = asof_row(us_df, d2)

    fig = go.Figure()
    if not r1.empty:
        x1 = [_US_LABELS.get(k, k) for k in r1.index]
        fig.add_trace(go.Scatter(x=x1, y=r1.values, mode="lines+markers", name=d1.strftime("%Y-%m-%d"), line=dict(width=3)))
    if not r2.empty and d2.normalize() != d1.normalize():
        x2 = [_US_LABELS.get(k, k) for k in r2.index]
        fig.add_trace(go.Scatter(x=x2, y=r2.values, mode="lines+markers", name=d2.strftime("%Y-%m-%d"), line=dict(width=3)))

    layout_common(fig, "Yield Curve — United States", 420, y_title="Yield (%)")
    fig.update_xaxes(title_text="Maturity")
    return fig

def plot_us_2y10y_history(start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    """
    Plot US 2Y and 10Y yields as time series.
    """
    df = fred_download(["DGS2", "DGS10"], start="1990-01-01").loc[start_ts:end_ts]
    df = df.dropna(how="all")
    if df.empty:
        return None
    return plot_lines(df, {"DGS2":"2Y", "DGS10":"10Y"}, title="United States — 2Y & 10Y History", height=420, y_title="Yield (%)")

def plot_oecd_timeseries(oecd_df: pd.DataFrame):
    """
    Plot OECD 10Y yields time series for multiple countries.
    """
    fig = go.Figure()
    for c in oecd_df.columns:
        fig.add_trace(go.Scatter(x=oecd_df.index, y=oecd_df[c], mode="lines", name=c, line=dict(width=2)))
    layout_common(fig, "OECD 10Y Yields — Time Series", 420, y_title="Yield (%)")
    return fig

def plot_oecd_snapshot(oecd_df: pd.DataFrame):
    """
    Plot the latest OECD 10Y yields as a bar chart.
    """
    latest = oecd_df.ffill().iloc[-1].dropna().sort_values()
    fig = go.Figure(go.Bar(
        x=latest.index,
        y=latest.values,
        text=[f"{v:.2f}%" for v in latest.values],
        textposition="outside",
        name="",
        showlegend=False
    ))
    layout_common(fig, "OECD 10Y Snapshot (latest)", 420, y_title="10Y Yield (%)")
    return fig

def render_macro():
    """
    Macro page.
    Top section shows OECD 10Y yields as time series and snapshot.
    Bottom section focuses on the United States with yield curve and key macro indicators.
    """
    st.markdown("### Macro")

    start_used, end_ts = range_row_standard(pd.to_datetime("1990-01-01"), key_prefix="macro_oecd", default_range="Past 2 Years")
    oecd_ids = list(OECD_10Y.values())
    oecd_df = fred_download(oecd_ids, start="1990-01-01")
    inv = {v: k for k, v in OECD_10Y.items()}
    oecd_df = oecd_df.rename(columns=inv).loc[start_used:end_ts]

    c1, c2 = st.columns([1.8, 1.0], vertical_alignment="top")
    with c1:
        st.plotly_chart(plot_oecd_timeseries(oecd_df), use_container_width=True)
    with c2:
        st.plotly_chart(plot_oecd_snapshot(oecd_df), use_container_width=True)

    st.markdown('<hr class="sep">', unsafe_allow_html=True)
    st.markdown("#### United States — Curve & Macro")

    dc1, dc2, dc3 = st.columns([0.9, 0.9, 2.2], vertical_alignment="bottom")
    with dc1:
        st.caption("Curve date")
        d1 = st.date_input("us_curve_d1", value=date.today(), key="us_curve_d1", label_visibility="collapsed")
    with dc2:
        st.caption("Compare to")
        d2 = st.date_input("us_curve_d2", value=date.today(), key="us_curve_d2", label_visibility="collapsed")
    with dc3:
        st.empty()

    d1 = pd.to_datetime(d1)
    d2 = pd.to_datetime(d2)

    fedfunds = latest_value("FEDFUNDS", start="1990-01-01")

    cpi = fred_get("CPIAUCSL", start="1950-01-01")
    core = fred_get("CPILFESL", start="1950-01-01")
    cpi_yoy = pct_yoy(cpi).dropna()
    core_yoy = pct_yoy(core).dropna()

    cpi_last = float(cpi_yoy.iloc[-1]) if not cpi_yoy.empty else np.nan
    core_last = float(core_yoy.iloc[-1]) if not core_yoy.empty else np.nan

    gdp_growth = latest_value("A191RL1Q225SBEA", start="1990-01-01")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Fed Funds", _fmt_num(fedfunds, 2))
    k2.metric("CPI (YoY)", f"{_fmt_num(cpi_last, 2)}%")
    k3.metric("Core CPI (YoY)", f"{_fmt_num(core_last, 2)}%")
    k4.metric("Real GDP Growth", f"{_fmt_num(gdp_growth, 2)}%")

    hist_start, hist_end = range_row_standard(pd.to_datetime("1990-01-01"), key_prefix="macro_hist", default_range="Past Year")

    left, right = st.columns([1.3, 1.0], vertical_alignment="bottom")
    with left:
        st.plotly_chart(plot_us_curve_compare(d1, d2), use_container_width=True)
    with right:
        fig_hist = plot_us_2y10y_history(hist_start, hist_end)
        if fig_hist is None:
            st.info("No data.")
        else:
            st.plotly_chart(fig_hist, use_container_width=True)


# ====================================================
# COMMODITIES
# ====================================================

_CHAIN_SPECS = {
    "WTI Crude (CL=F)":     {"root":"CL", "suffix":".NYM"},
    "Brent Crude (BZ=F)":   {"root":"BZ", "suffix":".NYM"},
    "RBOB Gasoline (RB=F)": {"root":"RB", "suffix":".NYM"},
    "Heating Oil (HO=F)":   {"root":"HO", "suffix":".NYM"},
    "Gold (GC=F)":          {"root":"GC", "suffix":".CMX"},
    "Soybeans (ZS=F)":      {"root":"ZS", "suffix":".CBT"},
    "Natural Gas (NG=F)":   {"root":"NG", "suffix":".NYM"},
}

COMMO_MAP = {
    "WTI Crude (CL=F)":     {"spot":"CL=F", "chain": _CHAIN_SPECS["WTI Crude (CL=F)"], "group":"Energy"},
    "Brent Crude (BZ=F)":   {"spot":"BZ=F", "chain": _CHAIN_SPECS["Brent Crude (BZ=F)"], "group":"Energy"},
    "RBOB Gasoline (RB=F)": {"spot":"RB=F", "chain": _CHAIN_SPECS["RBOB Gasoline (RB=F)"], "group":"Energy"},
    "Heating Oil (HO=F)":   {"spot":"HO=F", "chain": _CHAIN_SPECS["Heating Oil (HO=F)"], "group":"Energy"},
    "Natural Gas (NG=F)":   {"spot":"NG=F", "chain": _CHAIN_SPECS["Natural Gas (NG=F)"], "group":"Energy"},
    "Gold (GC=F)":          {"spot":"GC=F", "chain": _CHAIN_SPECS["Gold (GC=F)"], "group":"Metals"},
    "Soybeans (ZS=F)":      {"spot":"ZS=F", "chain": _CHAIN_SPECS["Soybeans (ZS=F)"], "group":"Ags"},
    "Copper (HG=F)":        {"spot":"HG=F", "chain": None, "group":"Metals"},
    "Silver (SI=F)":        {"spot":"SI=F", "chain": None, "group":"Metals"},
    "Sugar 11 (SB=F)":      {"spot":"SB=F", "chain": None, "group":"Ags"},
    "Coffee (KC=F)":        {"spot":"KC=F", "chain": None, "group":"Ags"},
    "Cotton (CT=F)":        {"spot":"CT=F", "chain": None, "group":"Ags"},
    "Wheat (ZW=F)":         {"spot":"ZW=F", "chain": None, "group":"Ags"},
}

BENCHMARK_INDICES = {
    "None": None,
    "Bloomberg Commodity Index (BCOM)": "^BCOM",
    "S&P GSCI (SPGSCI)": "^SPGSCI",
    "CRB Index (CRB)": "^CRB",
}

_FUT_MONTHS = ["F","G","H","J","K","M","N","Q","U","V","X","Z"]
_MONTH_NAME = {
    "F":"Jan","G":"Feb","H":"Mar","J":"Apr","K":"May","M":"Jun",
    "N":"Jul","Q":"Aug","U":"Sep","V":"Oct","X":"Nov","Z":"Dec"
}

def _build_yahoo_contracts(root: str, suffix: str, n_months=30):
    """
    Build Yahoo Finance futures tickers from the current month forward.
    Example output for WTI uses CL + month code + year code + exchange suffix.
    """
    today = date.today()
    start_year2 = today.year % 100
    start_month_idx = today.month - 1
    tickers = []
    for i in range(n_months):
        yy = start_year2 + (start_month_idx + i) // 12
        mm_code = _FUT_MONTHS[(start_month_idx + i) % 12]
        tickers.append(f"{root}{mm_code}{yy:02d}{suffix}")
    return list(dict.fromkeys(tickers))

def _contract_sort_key(ticker: str):
    """
    Sort key used to order contracts by year and month code.
    """
    try:
        core = ticker.split(".")[0]
        yy = int(core[-2:])
        mm_code = core[-3:-2]
        mm = _FUT_MONTHS.index(mm_code) if mm_code in _FUT_MONTHS else 99
        return (yy, mm, ticker)
    except Exception:
        return (999, 999, ticker)

def _parse_contract_label(ticker: str):
    """
    Convert a contract ticker to a readable label like Jan-2026.
    """
    core = ticker.split(".")[0]
    yy = core[-2:]
    mm = core[-3:-2]
    year = 2000 + int(yy)
    mon = _MONTH_NAME.get(mm, "???")
    return f"{mon}-{year}"

def _asof_row(df: pd.DataFrame, dt: pd.Timestamp):
    """
    Get the latest available curve snapshot at or before a date.
    """
    sub = df.loc[:pd.to_datetime(dt)]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.iloc[-1]

def plot_term_structure(curve1: pd.Series, curve2: pd.Series | None, label1: str, label2: str | None, height=420):
    """
    Plot one or two futures curves as a term structure chart.
    X axis shows the contract maturity (month and year).
    """
    fig = go.Figure()

    def add_curve(label, s):
        s = s.dropna()
        if s.empty:
            return []
        s = s.sort_index(key=lambda idx: [_contract_sort_key(x) for x in idx])
        x = [_parse_contract_label(t) for t in s.index]
        fig.add_trace(go.Scatter(
            x=x, y=s.values,
            mode="lines+markers",
            name=label,
            line=dict(width=3),
            marker=dict(size=7),
        ))
        return x

    x_labels = add_curve(label1, curve1)
    if curve2 is not None and label2 is not None:
        add_curve(label2, curve2)

    layout_common(fig, "Futures Term Structure", height, y_title="Price")
    fig.update_xaxes(title_text="Maturity")

    if x_labels:
        tick_idx = list(range(0, len(x_labels), 3))
        fig.update_xaxes(
            tickmode="array",
            tickvals=[x_labels[i] for i in tick_idx],
            ticktext=[x_labels[i] for i in tick_idx],
        )
    return fig

def prompt_spread_timeseries(fut_df: pd.DataFrame) -> pd.Series:
    """
    Compute prompt spread as the difference between second and first nearby contract.
    """
    cols_sorted = sorted(list(fut_df.columns), key=_contract_sort_key)
    if len(cols_sorted) < 2:
        return pd.Series(dtype=float)
    df = fut_df[cols_sorted].copy()
    ps = df.iloc[:, 1] - df.iloc[:, 0]
    ps.name = "PromptSpread"
    return ps.dropna()

def plot_prompt_spread_history(ps: pd.Series, d1: pd.Timestamp, d2: pd.Timestamp, lbl1: str, lbl2: str, height=420):
    """
    Plot prompt spread history and mark the selected curve dates.
    The chart does not display a marker for the latest value.
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ps.index, y=ps.values,
        mode="lines", name="Prompt Spread (M2 − M1)", line=dict(width=2)
    ))

    if d1.normalize() != d2.normalize():
        for lbl, dt in [(lbl1, d1), (lbl2, d2)]:
            sub = ps.loc[:dt]
            if len(sub):
                val = float(sub.iloc[-1])
                fig.add_trace(go.Scatter(
                    x=[pd.to_datetime(dt)], y=[val],
                    mode="markers+text",
                    text=[lbl],
                    textposition="top center",
                    marker=dict(size=10),
                    name=lbl,
                    showlegend=False
                ))

    layout_common(fig, "Prompt Spread History", height, y_title="Price difference")
    return fig

def seasonality_monthly_avg_returns(price_series: pd.Series):
    """
    Compute the average monthly return across the full available dataset.
    """
    s = price_series.dropna()
    if s.empty:
        return pd.DataFrame(), None
    start_date = s.index.min().date()
    m = s.resample("M").last()
    r = m.pct_change().dropna()
    df = pd.DataFrame({"ret": r})
    df["month"] = df.index.month
    avg = df.groupby("month")["ret"].mean() * 100.0
    out = pd.DataFrame({
        "Month": [pd.Timestamp(2000, i, 1).strftime("%b") for i in range(1, 13)],
        "AvgReturnPct": [avg.get(i, np.nan) for i in range(1, 13)]
    })
    return out, start_date

def plot_seasonality(seas_df: pd.DataFrame):
    """
    Plot monthly seasonality as a bar chart.
    Extra headroom avoids text being clipped.
    """
    fig = go.Figure(go.Bar(
        x=seas_df["Month"],
        y=seas_df["AvgReturnPct"],
        text=[f"{v:.2f}%" if pd.notna(v) else "" for v in seas_df["AvgReturnPct"]],
        textposition="outside",
        cliponaxis=False,
        showlegend=False
    ))
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        height=260,
        margin=dict(l=40, r=40, t=58, b=70),
        title=dict(text="Seasonality (Avg monthly returns)", x=0.0, xanchor="left"),
    )
    fig.update_yaxes(title_text="Avg monthly return (%)", automargin=True)
    fig.update_xaxes(title_text="")

    y = seas_df["AvgReturnPct"].astype(float)
    if y.notna().any():
        ymax = float(y.max())
        ymin = float(y.min())
        pad = max(0.8, (ymax - ymin) * 0.15)
        fig.update_yaxes(range=[ymin - pad, ymax + pad])
    return fig

def _bbl_price_from_energy(series: pd.Series, kind: str):
    """
    Convert USD per gallon to USD per barrel for refined products.
    """
    if kind in ["RB", "HO"]:
        return series * 42.0
    return series

def compute_energy_spreads(start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    """
    Compute common crack spreads using front month contracts.
    Values are approximations based on Yahoo Finance futures series.
    """
    px = preprocess(download_data(["CL=F", "RB=F", "HO=F"], start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")))
    if px.empty:
        return pd.DataFrame()

    cl = px["CL=F"]
    rb_bbl = _bbl_price_from_energy(px["RB=F"], "RB")
    ho_bbl = _bbl_price_from_energy(px["HO=F"], "HO")

    crack_11_rb = rb_bbl - cl
    crack_11_ho = ho_bbl - cl
    crack_321 = (2 * rb_bbl + 1 * ho_bbl) - (3 * cl)

    out = pd.DataFrame({
        "Crack 1:1 RBOB": crack_11_rb,
        "Crack 1:1 Heating Oil": crack_11_ho,
        "Crack 3:2:1": crack_321
    }).dropna(how="all")
    return out

def render_commodities():
    """
    Commodities page.
    Shows price with optional benchmark, optional indicators, energy spreads, term structure and prompt spread.
    """
    st.markdown("### Commodities")

    commo_bench = {"None": None}
    for k, v in BENCHMARK_INDICES.items():
        if k != "None":
            commo_bench[k] = v
    for name, cfg in COMMO_MAP.items():
        commo_bench[name] = cfg["spot"]

    r1, r2 = st.columns([2.4, 2.2], vertical_alignment="bottom")
    with r1:
        commo_name = st.selectbox("Commodity", list(COMMO_MAP.keys()), key="commo_name")
    with r2:
        bench_label = st.selectbox("Benchmark (optional)", list(commo_bench.keys()), index=0, key="commo_bench")
        bench_ticker = commo_bench[bench_label]

    cfg = COMMO_MAP[commo_name]
    df_min = pd.to_datetime(date.today()) - pd.DateOffset(years=15)
    end_default = date.today()

    rng = st.session_state.get("commo_rng", "Past Year")
    is_custom = (rng == "Custom")

    if is_custom:
        c_ind, c_rng, c_s, c_e = st.columns([2.4, 1.0, 1.0, 1.0], vertical_alignment="bottom")
    else:
        c_ind, c_rng = st.columns([2.4, 1.0], vertical_alignment="bottom")

    with c_ind:
        indicators = st.multiselect(
            "Indicators",
            INDICATORS_ALL + INDICATORS_COMMO_EXTRA,
            default=[],
            key="commo_ind"
        )
    with c_rng:
        rng = st.selectbox("Range", RANGE_OPTIONS, index=RANGE_OPTIONS.index("Past Year"), key="commo_rng")

    custom_start = None
    custom_end = None
    if rng == "Custom":
        with c_s:
            st.caption("Start")
            custom_start = st.date_input(
                "commo_start",
                value=(pd.Timestamp(end_default) - pd.DateOffset(years=1)).date(),
                label_visibility="collapsed"
            )
        with c_e:
            st.caption("End")
            custom_end = st.date_input(
                "commo_end",
                value=end_default,
                label_visibility="collapsed"
            )

    end_ts = pd.to_datetime(custom_end if rng == "Custom" else end_default)
    start_used, end_ts = compute_start_end(df_min, rng, end_ts, custom_start, custom_end)

    spot_ticker = cfg["spot"]
    chain_spec = cfg["chain"]
    group = cfg["group"]

    st.markdown("#### Price")

    px = preprocess(download_data([spot_ticker], start_used.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")))
    if px.empty:
        st.warning("No price data returned by Yahoo for this ticker.")
        return

    raw_series = px[spot_ticker].dropna()

    if bench_ticker is None:
        fig = plot_lines(px, {spot_ticker: commo_name}, title="", height=420)
        if "SMA 20" in indicators:
            fig = add_sma(fig, raw_series, 20, "SMA 20")
        if "SMA 50" in indicators:
            fig = add_sma(fig, raw_series, 50, "SMA 50")
    else:
        bx = preprocess(download_data([bench_ticker], start_used.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")))
        joined = px.join(bx, how="inner").dropna()
        if joined.empty:
            fig = plot_lines(px, {spot_ticker: commo_name}, title="", height=420)
        else:
            perf = (normalize(joined) - 1.0)
            fig = plot_lines(
                perf,
                {spot_ticker: commo_name, bench_ticker: bench_label},
                title="",
                height=420,
                y_as_percent=True
            )

    st.plotly_chart(fig, use_container_width=True)

    if "RSI 14" in indicators and not raw_series.empty:
        r = rsi_14(raw_series)
        if not r.dropna().empty:
            st.plotly_chart(plot_rsi(r), use_container_width=True)

    if "Seasonality" in indicators:
        full_hist = preprocess(download_data([spot_ticker], "1900-01-01", end_ts.strftime("%Y-%m-%d")))
        if not full_hist.empty and not full_hist[spot_ticker].dropna().empty:
            seas_df, seas_start = seasonality_monthly_avg_returns(full_hist[spot_ticker])
            if not seas_df.empty and not seas_df["AvgReturnPct"].dropna().empty:
                st.plotly_chart(plot_seasonality(seas_df), use_container_width=True)
                st.caption(f"Seasonality computed from available data since {seas_start}.")

    if group == "Energy":
        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown("#### Energy Spreads (front-month)")
        spreads = compute_energy_spreads(start_used, end_ts)
        if spreads.empty:
            st.info("Energy spreads not available (Yahoo data missing).")
        else:
            fig_sp = plot_lines(
                spreads,
                {c: c for c in spreads.columns},
                title="Crack Spreads",
                height=420,
                y_title="USD per bbl (approx.)"
            )
            st.plotly_chart(fig_sp, use_container_width=True)

            st.markdown(
                "<div class='note'>"
                "Notes: RBOB and Heating Oil are converted from USD/gal to USD/bbl using 42 gal per bbl. "
                "Crack 1:1 RBOB = RBOB(bbl) − WTI(bbl). "
                "Crack 1:1 Heating Oil = HO(bbl) − WTI(bbl). "
                "Crack 3:2:1 = 2×RBOB + 1×HO − 3×WTI (refining margin proxy)."
                "</div>",
                unsafe_allow_html=True
            )

    st.markdown('<hr class="sep">', unsafe_allow_html=True)
    st.markdown("#### Futures Term Structure")

    if chain_spec is None:
        st.info("Futures term structure not available on Yahoo Finance for this commodity.")
        return

    dc1, dc2, dc3 = st.columns([0.9, 0.9, 2.2], vertical_alignment="bottom")
    with dc1:
        st.caption("Curve date")
        d1 = st.date_input("curve_d1", value=date.today(), key="curve_d1", label_visibility="collapsed")
    with dc2:
        st.caption("Compare to")
        d2 = st.date_input("curve_d2", value=date.today(), key="curve_d2", label_visibility="collapsed")
    with dc3:
        st.empty()

    d1 = pd.to_datetime(d1)
    d2 = pd.to_datetime(d2)
    lbl1 = d1.strftime("%Y-%m-%d")
    lbl2 = d2.strftime("%Y-%m-%d")

    fut_tickers = _build_yahoo_contracts(chain_spec["root"], chain_spec["suffix"], n_months=30)
    start_hist = min(start_used, min(d1, d2) - pd.DateOffset(days=7))

    fut_df = preprocess(download_data(
        fut_tickers,
        start_hist.strftime("%Y-%m-%d"),
        (end_ts + pd.DateOffset(days=2)).strftime("%Y-%m-%d")
    )).dropna(axis=1, how="all")

    if fut_df.empty or fut_df.shape[1] < 2:
        st.warning("Yahoo is not returning contract chain data for this market.")
        return

    s1 = _asof_row(fut_df, d1).dropna()
    s2 = _asof_row(fut_df, d2).dropna()
    curve2 = None if d1.normalize() == d2.normalize() else s2

    left, right = st.columns([1.65, 1.0], vertical_alignment="bottom")
    with left:
        fig_ts = plot_term_structure(s1, curve2, lbl1, (lbl2 if curve2 is not None else None), height=420)
        st.plotly_chart(fig_ts, use_container_width=True)
    with right:
        ps = prompt_spread_timeseries(fut_df)
        if ps.empty:
            st.info("Prompt spread not available.")
        else:
            fig_ps = plot_prompt_spread_history(ps, d1, d2, lbl1, lbl2, height=420)
            st.plotly_chart(fig_ps, use_container_width=True)


# ====================================================
# MAIN
# ====================================================

inject_css()
page = top_nav()

if page == "Overview":
    render_overview()
elif page == "Macro":
    render_macro()
elif page == "Commodities":
    render_commodities()
