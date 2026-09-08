import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import io

from src.utils.config import DEFAULT_TICKERS, STOCK_UNIVERSES, SUPPORTED_INTERVALS
from src.utils.logger import log_info, log_error
from src.data.data_processor import DataProcessor
from src.database.database import DatabaseManager
from src.analysis.technical_indicators import TechnicalIndicators
from src.analysis.market_analyzer import MarketAnalyzer
from src.data.symbol_resolver import SymbolResolver
from src.analysis.market_scanner import MarketScanner

# Set page config
st.set_page_config(
    page_title="AI Market Data Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern visual styling
st.markdown("""
<style>
    .reportview-container {
        background: #0f172a;
    }
    .metric-card {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        font-weight: 500;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 5px 0;
    }
    .metric-delta {
        font-size: 0.95rem;
        font-weight: 600;
    }
    .delta-green {
        color: #10b981;
    }
    .delta-red {
        color: #ef4444;
    }
    .disclaimer-box {
        background-color: #1e293b;
        border-left: 5px solid #eab308;
        padding: 15px;
        border-radius: 4px;
        font-size: 0.85rem;
        color: #cbd5e1;
        margin-top: 30px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize application components
@st.cache_resource
def get_components():
    db_manager = DatabaseManager()
    data_processor = DataProcessor()
    market_analyzer = MarketAnalyzer()
    symbol_resolver = SymbolResolver()
    market_scanner = MarketScanner()
    return db_manager, data_processor, market_analyzer, symbol_resolver, market_scanner

db_manager, data_processor, market_analyzer, symbol_resolver, market_scanner = get_components()

# --- PAGE NAVIGATION & STATE ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "🏠 Market Scanner"
if "current_symbol" not in st.session_state:
    st.session_state.current_symbol = None
if "market_data" not in st.session_state:
    st.session_state.market_data = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None
if "failed_stocks" not in st.session_state:
    st.session_state.failed_stocks = []
if "skipped_count" not in st.session_state:
    st.session_state.skipped_count = 0

st.sidebar.markdown("### Navigation")
page_options = ["🏠 Market Scanner", "📊 Stock Analysis"]
default_idx = page_options.index(st.session_state.current_page) if st.session_state.current_page in page_options else 0

selected_page = st.sidebar.radio(
    "Select Screen",
    options=page_options,
    index=default_idx,
    key="nav_radio"
)

if selected_page != st.session_state.current_page:
    st.session_state.current_page = selected_page
    st.rerun()

# --- RENDER PAGES ---
if st.session_state.current_page == "🏠 Market Scanner":
    # --- PAGE 1: MARKET SCANNER HOME PAGE ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Scanner Control")
    
    # Universe selection widget
    selected_universe_name = st.sidebar.selectbox(
        "Select Stock Universe",
        options=list(STOCK_UNIVERSES.keys()),
        index=0,
        key="selected_universe_name"
    )
    selected_universe = STOCK_UNIVERSES[selected_universe_name]
    
    refresh_scanner = st.sidebar.button("🔄 Refresh Scanner", use_container_width=True)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.markdown(
        f"This scanner screens the chosen stock universe ({selected_universe_name}), calculates indicators locally, "
        "and classifies them into Bullish, Bearish, and Neutral lists."
    )
    
    # Scanner Logic
    if "scan_universe_name" not in st.session_state:
        st.session_state.scan_universe_name = selected_universe_name
        
    # If the user changed the universe in the selectbox, clear past results to trigger fresh scan
    if st.session_state.scan_universe_name != selected_universe_name:
        st.session_state.scan_results = None
        st.session_state.scan_universe_name = selected_universe_name
        
    should_scan = refresh_scanner or st.session_state.scan_results is None
    
    if should_scan:
        with st.spinner(f"Scanning market stock universe ({selected_universe_name})..."):
            progress_bar = st.progress(0.0)
            status_text = st.empty()
            
            def progress_update(current, total):
                percent = current / total
                progress_bar.progress(percent)
                status_text.text(f"Scanning market: {current} / {total} stocks analyzed")
                
            try:
                results = market_scanner.scan_universe(
                    universe=selected_universe,
                    db_manager=db_manager,
                    data_processor=data_processor,
                    force_refresh=refresh_scanner,
                    progress_callback=progress_update
                )
                
                # Group and rank
                ranked_results = market_scanner.rank_results(results)
                st.session_state.scan_results = ranked_results
                st.session_state.failed_stocks = market_scanner.failed_stocks
                st.session_state.skipped_count = market_scanner.skipped_count
                st.session_state.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                st.error(f"Scanner error occurred: {str(e)}")
                log_error("app", "ScannerError", f"Market scanner failed: {str(e)}", "Display error in UI", exc_info=True)
            finally:
                progress_bar.empty()
                status_text.empty()
                
    # RENDER SCANNER UI
    st.subheader("🏠 Market Scanner Dashboard")
    if st.session_state.last_scan_time:
        st.caption(f"⏱️ Last market scan completed at: **{st.session_state.last_scan_time}** (UTC)")
        
    if st.session_state.scan_results:
        # Display Scan Summary
        st.markdown("### 📊 Scan Summary")
        success_count = sum(len(st.session_state.scan_results.get(cat, [])) for cat in ["Bullish", "Bearish", "Neutral"])
        skipped_count = st.session_state.skipped_count
        total_failed_stage = len(st.session_state.failed_stocks)
        failed_count = max(0, total_failed_stage - skipped_count)
        
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        current_uni_name = st.session_state.get("scan_universe_name", "NIFTY 50 (India)")
        col1.metric("Total Universe", len(STOCK_UNIVERSES.get(current_uni_name, DEFAULT_TICKERS)))
        col2.metric("Analyzed", success_count)
        col3.metric("🟢 Bullish", len(st.session_state.scan_results.get("Bullish", [])))
        col4.metric("🔴 Bearish", len(st.session_state.scan_results.get("Bearish", [])))
        col5.metric("🟡 Neutral", len(st.session_state.scan_results.get("Neutral", [])))
        col6.metric("🔴 Failed", failed_count)
        col7.metric("⚠️ Skipped", skipped_count)
        
        st.markdown("---")
        
        # Categories: Bullish, Bearish, Neutral
        tab_bullish, tab_bearish, tab_neutral = st.tabs([
            "🟢 Bullish Stocks",
            "🔴 Bearish Stocks",
            "🟡 Neutral Stocks"
        ])
        
        categories = [
            ("Bullish", tab_bullish, "🟢 Top Bullish Stocks"),
            ("Bearish", tab_bearish, "🔴 Top Bearish Stocks"),
            ("Neutral", tab_neutral, "🟡 Top Neutral Stocks")
        ]
        
        for cat_name, tab_obj, title_text in categories:
            with tab_obj:
                st.markdown(f"#### {title_text}")
                items = st.session_state.scan_results.get(cat_name, [])
                
                # Check if there are any stocks in this category before displaying search
                if not items:
                    if cat_name == "Bullish":
                        st.info("🟢 No bullish stocks detected in the current scan.")
                    elif cat_name == "Bearish":
                        st.info("🔴 No bearish stocks detected in the current scan.")
                    else:
                        st.info("🟡 No neutral stocks detected in the current scan.")
                else:
                    # Filter box
                    filter_term = st.text_input(
                        f"🔍 Search/Filter {cat_name} Stocks",
                        key=f"filter_{cat_name}",
                        value=""
                    ).strip().upper()
                    
                    filtered_items = items
                    if filter_term:
                        filtered_items = [
                            item for item in items
                            if filter_term in item["symbol"].upper() or filter_term in item.get("company_name", "").upper()
                        ]
                        
                    if not filtered_items:
                        if filter_term:
                            st.info(f"No {cat_name.lower()} stocks found matching '{filter_term}'.")
                        else:
                            # Fallback if filtered_items evaluates to empty with an empty filter
                            if cat_name == "Bullish":
                                st.info("🟢 No bullish stocks detected in the current scan.")
                            elif cat_name == "Bearish":
                                st.info("🔴 No bearish stocks detected in the current scan.")
                            else:
                                st.info("🟡 No neutral stocks detected in the current scan.")
                    else:
                        # Build sortable table
                        table_rows = []
                        for item in filtered_items:
                            symbol = item["symbol"]
                            currency_prefix = "₹" if (symbol.endswith(".NS") or symbol.startswith("^")) else "$"
                            
                            price_formatted = f"{currency_prefix}{item['latest_price']:,.2f}"
                            change_val = item.get("price_change_pct", 0.0)
                            change_formatted = f"{change_val:+.2f}%"
                            
                            vol_val = item.get("volume")
                            vol_formatted = f"{vol_val:,.0f}" if vol_val is not None else "N/A"
                            
                            table_rows.append({
                                "Rank": item["rank"],
                                "Stock Symbol": symbol,
                                "Company Name": item.get("company_name", symbol),
                                "Current Price": price_formatted,
                                "Price Change %": change_formatted,
                                "Volume": vol_formatted,
                                "RSI": f"{item['rsi_value']:.1f}" if item['rsi_value'] is not None else "N/A",
                                "SMA Trend": item.get("sma_ema_status", "N/A"),
                                "MACD Signal": item.get("macd_status", "N/A"),
                                "Volatility": item.get("volatility", "N/A"),
                                "Overall Signal/Classification": item.get("trend", "N/A")
                            })
                        
                        df_table = pd.DataFrame(table_rows)
                        st.dataframe(df_table, use_container_width=True, hide_index=True)
                        
                        # Stock Selection Dropdown
                        st.markdown("---")
                        st.markdown("##### Stock Selection Analysis")
                        symbols_options = [item["symbol"] for item in filtered_items]
                        selected_sym = st.selectbox(
                            f"Select a {cat_name.lower()} stock to view details:",
                            options=symbols_options,
                            format_func=lambda x: next((f"{i.get('company_name', x)} ({x})" for i in filtered_items if i["symbol"] == x), x),
                            key=f"sel_{cat_name}"
                        )
                        
                        if st.button(f"📊 Analyze Selected Stock ({selected_sym})", key=f"btn_{cat_name}", use_container_width=True):
                            st.session_state.search_query = selected_sym
                            st.session_state.current_page = "📊 Stock Analysis"
                            st.session_state.market_data = None
                            st.session_state.analysis = None
                            st.rerun()
                            
        # Expandable diagnostics for failed stocks at the bottom of the scanner results
        st.markdown("---")
        with st.expander("⚠️ Failed Stocks & Diagnostics"):
            if st.session_state.failed_stocks:
                # Build diagnostic table
                diag_rows = []
                for f_stock in st.session_state.failed_stocks:
                    reason = f_stock["reason"]
                    status = "Skipped" if "Insufficient historical data" in reason else "Failed"
                    diag_rows.append({
                        "Stock Symbol": f_stock["symbol"],
                        "Status": status,
                        "Failure Stage": f_stock["stage"],
                        "Error Reason": reason
                    })
                df_diags = pd.DataFrame(diag_rows)
                st.dataframe(df_diags, use_container_width=True, hide_index=True)
            else:
                st.success("🎉 No stock failures or validation errors occurred during the scan.")
    else:
        st.warning("No market data has been scanned yet. Please click 'Refresh Scanner' to scan.")
        
else:
    # --- PAGE 2: INDIVIDUAL STOCK ANALYSIS ---
    # Stock Selection Input
    search_query = st.sidebar.text_input(
        "Search Stock Ticker or Name",
        value=st.session_state.get("search_query", "RELIANCE.NS")
    ).strip()
    
    # Resolve Symbol
    symbol = ""
    suggestions = []
    if search_query:
        symbol, suggestions = symbol_resolver.resolve(search_query)
        
    # Display suggestions if any
    if suggestions:
        st.sidebar.markdown("**Did you mean?**")
        for sug in suggestions[:3]:
            if st.sidebar.button(f"🔍 {sug['name']} ({sug['symbol']})", key=f"sug_{sug['symbol']}"):
                st.session_state.search_query = sug['symbol']
                st.rerun()
                
    # Date Range Selection
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=365))
    with col2:
        end_date = st.date_input("End Date", value=datetime.today())
        
    # Interval Selection
    interval = st.sidebar.selectbox(
        "Data Interval",
        options=list(SUPPORTED_INTERVALS.keys()),
        format_func=lambda x: SUPPORTED_INTERVALS[x],
        index=0
    )
    
    # Fetch Buttons
    fetch_button = st.sidebar.button("📊 Fetch & Analyze", use_container_width=True)
    refresh_button = st.sidebar.button("🔄 Refresh Data", use_container_width=True)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.markdown(
        "This dashboard fetches historical and current stock data, calculates key indicators, "
        "and visualizes trends. The data is cached locally in SQLite."
    )
    
    # Trigger fetch logic
    # Fetch if either button clicked OR symbol changed from what we currently analyzed
    trigger_fetch = (
        fetch_button or 
        refresh_button or 
        (st.session_state.market_data is None and symbol != "") or 
        (st.session_state.current_symbol != symbol and symbol != "")
    )
    
    if trigger_fetch:
        if not symbol:
            st.error("Please enter or select a valid stock symbol.")
        elif not symbol_resolver.validate_symbol(symbol, db_manager):
            st.error("Stock not found or no market data is available.\nPlease check the company name or ticker symbol.")
            log_error(
                "app",
                "ValidationError",
                f"Symbol validation failed for: {symbol}",
                "Display user-friendly message"
            )
        else:
            with st.spinner(f"Retrieving and processing data for {symbol}..."):
                try:
                    start_str = start_date.strftime("%Y-%m-%d")
                    end_str = end_date.strftime("%Y-%m-%d")
                    
                    df = None
                    fallback_used = False
                    
                    try:
                        df = data_processor.process_market_data(symbol, start_str, end_str, interval)
                    except Exception as fetch_err:
                        log_error(
                            "app", "NetworkError",
                            f"Fetching failed for {symbol}: {str(fetch_err)}. Attempting SQLite fallback.",
                            "Query local database"
                        )
                        df = db_manager.get_market_data(symbol, interval, f"{start_str} 00:00:00", f"{end_str} 23:59:59")
                        if df is not None and not df.empty:
                            fallback_used = True
                        else:
                            raise fetch_err
                            
                    if df is not None and not df.empty:
                        if not fallback_used:
                            db_manager.save_market_data(df, symbol, interval)
                            
                        df_with_indicators = TechnicalIndicators.calculate_indicators(df)
                        analysis_res = market_analyzer.analyze(df_with_indicators, symbol)
                        
                        db_manager.save_analysis_result(
                            symbol=analysis_res["symbol"],
                            analysis_date=analysis_res["analysis_date"],
                            trend=analysis_res["trend"],
                            rsi=analysis_res["rsi_value"],
                            macd=analysis_res["macd_value"],
                            volatility=analysis_res["volatility"],
                            signal=analysis_res["signal"]
                        )
                        
                        st.session_state.current_symbol = symbol
                        st.session_state.market_data = df_with_indicators
                        st.session_state.analysis = analysis_res
                        st.session_state.fallback_used = fallback_used
                        
                        if fallback_used:
                            st.warning("⚠️ Network connection failed. Displaying cached data from local database.")
                        else:
                            st.success(f"Successfully fetched and analyzed data for {symbol}!")
                    else:
                        st.error(f"No records found for ticker {symbol} during this period.")
                except Exception as e:
                    st.error(f"Failed to load market data: {str(e)}")
                    log_error("app", "AppError", f"Error in app execution for {symbol}: {str(e)}", "Show error in UI", exc_info=True)
                    
    # Display Dashboard if data is available
    if st.session_state.market_data is not None and st.session_state.analysis is not None:
        df_data = st.session_state.market_data
        analysis = st.session_state.analysis
        symbol_display = st.session_state.current_symbol
        
        # 1. METRIC OVERVIEW ROW
        st.markdown("### Market Overview")
        col1, col2, col3, col4 = st.columns(4)
        
        delta_val = analysis["price_change_pct"]
        delta_class = "delta-green" if delta_val >= 0 else "delta-red"
        delta_symbol = "+" if delta_val >= 0 else ""
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">LATEST CLOSE</div>
                <div class="metric-value">₹{analysis['latest_price']:,.2f}</div>
                <div class="metric-delta {delta_class}">{delta_symbol}{delta_val:.2f}% (Daily)</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            trend_color = "#10b981" if analysis["trend"] == "Bullish" else "#ef4444" if analysis["trend"] == "Bearish" else "#94a3b8"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">TREND CLASSIFICATION</div>
                <div class="metric-value" style="color: {trend_color};">{analysis['trend']}</div>
                <div class="metric-delta" style="color: #cbd5e1;">Score-based logic</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            vol_color = "#ef4444" if analysis["volatility"] == "High" else "#eab308" if analysis["volatility"] == "Medium" else "#10b981"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">MARKET VOLATILITY</div>
                <div class="metric-value" style="color: {vol_color};">{analysis['volatility']}</div>
                <div class="metric-delta" style="color: #cbd5e1;">Hist Vol: {analysis['volatility_value']:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            rsi_val = analysis['rsi_value']
            rsi_display = f"{rsi_val:.1f}" if rsi_val is not None else "N/A"
            rsi_color = "#eab308" if (rsi_val and (rsi_val > 70 or rsi_val < 30)) else "#cbd5e1"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">RSI 14 / MOMENTUM</div>
                <div class="metric-value" style="color: {rsi_color};">{rsi_display}</div>
                <div class="metric-delta" style="color: #cbd5e1;">{analysis['rsi_status']}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        
        # 2. CHARTS SECTIONS (Tabs)
        st.markdown("### Technical Charts & Visualization")
        tab_charts, tab_data, tab_logs = st.tabs(["📊 Technical Indicators", "📋 Processed Data", "📝 Error & System Logs"])
        
        with tab_charts:
            if len(df_data) < 2:
                st.warning("Insufficient data points to plot interactive charts.")
            else:
                col_sel1, col_sel2 = st.columns(2)
                with col_sel1:
                    overlays = st.multiselect(
                        "Moving Average Overlays",
                        options=["SMA 20", "SMA 50", "EMA 20", "EMA 50"],
                        default=["SMA 20", "EMA 20"]
                    )
                with col_sel2:
                    show_bbands = st.checkbox("Show Bollinger Bands", value=True)
                    
                fig = make_subplots(
                    rows=4, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=[0.5, 0.15, 0.17, 0.18],
                    subplot_titles=(
                        f"Price & Overlays ({symbol_display})",
                        "Volume",
                        "RSI 14",
                        "MACD"
                    )
                )
                
                fig.add_trace(
                    go.Candlestick(
                        x=df_data['date'],
                        open=df_data['open'],
                        high=df_data['high'],
                        low=df_data['low'],
                        close=df_data['close'],
                        name="OHLC Price"
                    ),
                    row=1, col=1
                )
                
                if "SMA 20" in overlays and "sma_20" in df_data.columns:
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['sma_20'], name="SMA 20", line=dict(color="#38bdf8", width=1.5)), row=1, col=1)
                if "SMA 50" in overlays and "sma_50" in df_data.columns:
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['sma_50'], name="SMA 50", line=dict(color="#3b82f6", width=1.5)), row=1, col=1)
                if "EMA 20" in overlays and "ema_20" in df_data.columns:
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['ema_20'], name="EMA 20", line=dict(color="#a855f7", width=1.5)), row=1, col=1)
                if "EMA 50" in overlays and "ema_50" in df_data.columns:
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['ema_50'], name="EMA 50", line=dict(color="#ec4899", width=1.5)), row=1, col=1)
                    
                if show_bbands and "bb_upper" in df_data.columns and "bb_lower" in df_data.columns:
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['bb_upper'], name="Bollinger Upper", line=dict(color="#10b981", width=1, dash="dash")), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['bb_lower'], name="Bollinger Lower", line=dict(color="#ef4444", width=1, dash="dash"), fill='tonexty', fillcolor='rgba(255, 0, 0, 0.05)'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['bb_mid'], name="Bollinger Mid", line=dict(color="#eab308", width=1)), row=1, col=1)
                    
                colors = ['#10b981' if df_data['close'].iloc[i] >= df_data['open'].iloc[i] else '#ef4444' for i in range(len(df_data))]
                fig.add_trace(
                    go.Bar(
                        x=df_data['date'],
                        y=df_data['volume'],
                        name="Volume",
                        marker_color=colors,
                        opacity=0.8
                    ),
                    row=2, col=1
                )
                
                if "rsi_14" in df_data.columns:
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['rsi_14'], name="RSI 14", line=dict(color="#f97316", width=2)), row=3, col=1)
                    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", annotation_text="Overbought (70)", row=3, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="#10b981", annotation_text="Oversold (30)", row=3, col=1)
                    fig.update_yaxes(range=[10, 90], row=3, col=1)
                    
                if "macd" in df_data.columns and "macd_signal" in df_data.columns:
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['macd'], name="MACD", line=dict(color="#06b6d4", width=1.5)), row=4, col=1)
                    fig.add_trace(go.Scatter(x=df_data['date'], y=df_data['macd_signal'], name="Signal", line=dict(color="#f43f5e", width=1.5)), row=4, col=1)
                    hist_colors = ['#10b981' if val >= 0 else '#ef4444' for val in df_data['macd_hist'].fillna(0)]
                    fig.add_trace(
                        go.Bar(
                            x=df_data['date'],
                            y=df_data['macd_hist'],
                            name="Histogram",
                            marker_color=hist_colors,
                            opacity=0.7
                        ),
                        row=4, col=1
                    )
                    
                fig.update_layout(
                    height=900,
                    xaxis_rangeslider_visible=False,
                    margin=dict(l=50, r=50, t=50, b=50),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(30, 41, 59, 0.5)",
                    font=dict(color="#f8fafc"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                fig.update_xaxes(gridcolor="#334155", zeroline=False)
                fig.update_yaxes(gridcolor="#334155", zeroline=False)
                
                st.plotly_chart(fig, use_container_width=True)
                
        with tab_data:
            st.markdown(f"### Processed Historical Market Data: {symbol_display}")
            st.markdown("Below is the cleaned dataset displaying calculated indicators and standardized columns.")
            
            df_display = df_data.sort_values(by='date', ascending=False)
            st.dataframe(df_display, use_container_width=True)
            
            csv_buffer = io.StringIO()
            df_data.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            st.download_button(
                label="📥 Download Data as CSV",
                data=csv_data,
                file_name=f"{symbol_display}_market_data.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with tab_logs:
            st.markdown("### Log Viewer")
            st.markdown("Inspect application logs for errors or debugging purposes.")
            
            try:
                with open("logs/app.log", "r", encoding="utf-8") as f:
                    logs_content = f.read()
                st.text_area("Latest Logs", value=logs_content[-10000:] if len(logs_content) > 10000 else logs_content, height=400)
            except FileNotFoundError:
                st.info("No logs are currently recorded in the log file.")
                
        st.markdown("---")
        st.markdown("### Analysis Summary")
        st.info(f"**Technical Verdict**: {analysis['signal']}")
        st.markdown(f"""
        <div class="disclaimer-box">
            <strong>Disclaimer:</strong> {analysis['disclaimer']}
        </div>
        """, unsafe_allow_html=True)
        
    else:
        st.info("👈 Enter a Stock symbol or select one from the sidebar and click 'Fetch & Analyze' to display results.")
