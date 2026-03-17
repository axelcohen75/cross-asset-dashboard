# Cross-Asset Market Dashboard
Link : https://cross-asset-dashboard-axel-cohen-skema.streamlit.app/

This project was developed as part of **Semester 1** of my **Master in Financial Markets & Investment**.  
The initial objective was to build a cross-asset market dashboard in Python, but the project naturally evolved toward a **strong focus on commodities and futures markets**, which is where the main value of the tool lies.

---

## Motivation

While working on commodities, I repeatedly faced the same issue:  
it is surprisingly difficult to find simple, accessible tools that allow users to visualize futures term structures and compare them across different dates.

Most platforms either hide term structure data behind paywalls, or make cross-date comparisons unnecessarily complex and unintuitive.

Since I still didn't save enough money to afford a bloomberg, I used this project as an opportunity to build the tool I was missing.

---

## Project Overview

The dashboard provides a unified view of major asset classes:
- Equity indices
- Macro and rates
- Commodities (spot, futures, spreads)

It is built using **Streamlit** and relies on **Yahoo Finance**, **FRED**, and **TradingView widgets** for live data and macro context.

---

## Main Features

### Overview
- Interactive watchlist including:
  - Major equity indices (S&P 500, NASDAQ 100, Euro Stoxx 50, etc.)
  - Key macro assets (US Dollar Index, US 10Y T-Note)
  - Core commodities (Gold, WTI, Wheat)
- Multi-asset selection with automatic normalization
- Flexible performance horizons (1D, 1W, 1M, YTD, etc.)
- Embedded TradingView widgets:
  - Economic calendar
  - Latest macro and market news

---

### Macro
- OECD 10Y government bond yields:
  - Historical time series
  - Cross-country snapshot
- United States focus:
  - Yield curve with two-date comparison
  - 2Y vs 10Y yield history
- Key macro indicators:
  - Fed Funds rate
  - CPI (YoY)
  - Core CPI (YoY)
  - Real GDP growth (latest)

---

### Commodities (Core Focus)

This is the central part of the project.

#### Spot Price Analysis
- Spot price visualization
- Optional benchmark comparison
- Technical indicators:
  - SMA 20
  - SMA 50
  - RSI 14
- Automatic switch to percentage performance when a benchmark is selected

#### Futures Term Structure
- Front-month futures curves built from Yahoo Finance contract chains
- Comparison of term structures at **two different dates**
- Clear maturity labeling and spacing
- Designed to quickly identify contango and backwardation regimes

#### Prompt Spread
- Prompt spread time series (M2 − M1)
- Optional date markers when comparing curves
- Useful for assessing short-term market tightness

#### Energy Spreads
- Crack spreads for energy markets:
  - 1:1 RBOB
  - 1:1 Heating Oil
  - 3:2:1 crack spread
- Converted into consistent USD per barrel terms
- Simple proxy for refining margins

#### Seasonality
- Average monthly returns computed over the full available dataset
- Helps highlight recurring seasonal patterns in commodity markets

---

## Tech Stack

- Python
- Streamlit
- pandas, numpy
- plotly
- yfinance
- FRED API
- TradingView embedded widgets

---

## How to Run

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

## Notes

This project is intended as an academic and practical exploration of market visualization rather than a trading system.
Data accuracy and availability depend on public data sources and their limitations.
