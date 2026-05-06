import streamlit as st
import datetime
import pandas as pd
from src.metrics import calculate_theme_rankings, get_stocks_in_theme
from src.charts import plot_synchronized_charts
from src.data_fetcher import get_all_theme_stocks
from src.utils import get_chosung

st.set_page_config(page_title="Multi-Stock Theme Analysis", layout="wide", initial_sidebar_state="expanded")

# Custom CSS Injection for HTS style layout
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3 {
        color: #f4a261 !important;
    }
    .stDataFrame {
        font-family: 'Inter', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("📈 Multi-Stock Theme Analysis Dashboard")
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("Settings")
        timeframe = st.selectbox("Quick Select", options=["1W", "1M", "3M", "YTD"], index=1)
        
        today = datetime.datetime.today().date()
        if timeframe == '1W':
            default_start = today - datetime.timedelta(days=7)
        elif timeframe == '1M':
            default_start = today - datetime.timedelta(days=30)
        elif timeframe == '3M':
            default_start = today - datetime.timedelta(days=90)
        else: # YTD
            default_start = datetime.date(today.year, 1, 1)
            
        date_range = st.date_input("Select Date Range", value=(default_start, today), max_value=today)
        
        if len(date_range) == 2:
            start_date_obj, end_date_obj = date_range
        else:
            start_date_obj, end_date_obj = date_range[0], date_range[0]
            
        start_date = start_date_obj.strftime("%Y%m%d")
        end_date = end_date_obj.strftime("%Y%m%d")
        
        show_macro = st.checkbox("Overlay Macro Indicators", value=False, help="Show USD/KRW, WTI, Gold")
        
        st.subheader("Technical Indicators")
        indicators = st.multiselect(
            "Select Indicators",
            options=['Moving Averages', 'Bollinger Bands', 'MACD', 'RSI'],
            default=['Moving Averages']
        )
        
        st.caption(f"Period: {start_date} ~ {end_date}")
        
    # --- Main Content ---
    st.header(f"🏆 Theme Rankings ({timeframe})")
    
    # 2. Search stock to inverse-filter themes
    stocks_df = get_all_theme_stocks()
    search_options = ["All"]
    for _, row in stocks_df.iterrows():
        name = row['Name']
        ticker = row['Ticker']
        chosung = get_chosung(name)
        search_options.append(f"[{chosung}] {name} ({ticker})")
        
    selected_search = st.selectbox(
        "🔍 Search Stock to Filter Themes (초성 검색 지원, 예: ㅅㅅㅈㅈ)", 
        options=search_options
    )
    
    with st.spinner("Calculating theme rankings..."):
        theme_df = calculate_theme_rankings(start_date, end_date)
        
    if theme_df.empty:
        st.warning("No data available for the selected period or market.")
        return
        
    # 4. Finviz 스타일의 히트맵(Treemap) 뼈대 준비
    with st.expander("🗺️ Market Theme Heatmap (Finviz Style)", expanded=True):
        import plotly.express as px
        if not theme_df.empty:
            fig_tree = px.treemap(
                theme_df,
                path=[px.Constant("All Themes"), 'Theme'],
                values='Num Stocks',
                color='Avg Return (%)',
                color_continuous_scale='RdYlGn',
                color_continuous_midpoint=0,
                hover_data=['Avg Return (%)']
            )
            fig_tree.update_layout(margin=dict(t=20, l=10, r=10, b=10), height=400)
            st.plotly_chart(fig_tree, use_container_width=True)
            
    if selected_search != "All":
        ticker_str = selected_search.split("(")[1].split(")")[0]
        # Filter theme_df to only include themes that have the selected ticker
        theme_df = theme_df[theme_df['Tickers'].apply(lambda x: ticker_str in x)]
        if theme_df.empty:
            st.warning("선택한 종목이 포함된 테마가 없습니다.")
            return
        
    # Display Theme Rankings
    st.dataframe(
        theme_df.drop(columns=['Tickers']), 
        use_container_width=True, 
        hide_index=True,
        height=600,
        column_config={
            "Avg Return (%)": st.column_config.NumberColumn(format="%.2f%%")
        }
    )
    
    # Theme Selection
    st.markdown("---")
    st.header("📋 Stocks in Theme")
    selected_theme = st.selectbox("Select a Theme to view stocks:", options=theme_df['Theme'].tolist())
    
    if selected_theme:
        # Get tickers for selected theme
        theme_row = theme_df[theme_df['Theme'] == selected_theme].iloc[0]
        tickers = theme_row['Tickers']
        
        with st.spinner(f"Loading stocks for {selected_theme}..."):
            stocks_df = get_stocks_in_theme(tickers, start_date, end_date)
            
        if not stocks_df.empty:
            # Add Select column for checkboxes
            stocks_df.insert(0, "Select", False)
            
            st.write("Select stocks below to view their charts:")
            # Use data_editor for multi-select
            edited_df = st.data_editor(
                stocks_df,
                hide_index=True,
                use_container_width=True,
                height=800,
                column_config={
                    "Select": st.column_config.CheckboxColumn("Select", default=False),
                    "Price(KRW)": st.column_config.NumberColumn(format="%,d"),
                    "Return(%)": st.column_config.NumberColumn(format="%.2f%%"),
                    "Volume": st.column_config.NumberColumn(format="%,d"),
                    "Market Cap(KRW)": st.column_config.NumberColumn(format="%,d")
                },
                disabled=["Ticker", "Name", "Price(KRW)", "Return(%)", "Volume", "Market Cap(KRW)"]
            )
            
            # Filter selected stocks
            selected_stocks = edited_df[edited_df['Select']]
            
            if not selected_stocks.empty:
                st.markdown("---")
                st.header("📊 Multi-Charts Analysis")
                
                # 상태 캐싱: 차트 조건이 변경되었을 때만 재연산 (검색창 타이핑 시 버벅임 방지)
                current_chart_hash = str(selected_stocks['Ticker'].tolist()) + start_date + end_date + str(show_macro) + str(indicators)
                
                if 'last_chart_hash' not in st.session_state or st.session_state.last_chart_hash != current_chart_hash:
                    with st.spinner("Rendering charts..."):
                        fig = plot_synchronized_charts(
                            selected_stocks, 
                            start_date=start_date, 
                            end_date=end_date, 
                            show_macro=show_macro,
                            indicators=indicators
                        )
                        st.session_state.last_fig = fig
                        st.session_state.last_chart_hash = current_chart_hash
                else:
                    fig = st.session_state.last_fig
                    
                if fig:
                        st.plotly_chart(fig, use_container_width=True, theme="streamlit", config={'scrollZoom': True, 'displayModeBar': True})
            else:
                st.info("Check the boxes next to the stocks above to display their charts.")

if __name__ == "__main__":
    main()
