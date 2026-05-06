import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from .data_fetcher import get_stock_ohlcv, get_macro_data

def calculate_indicators(df: pd.DataFrame, indicators: list):
    """Add technical indicators to the dataframe based on user selection."""
    df = df.copy()
    
    if 'Moving Averages' in indicators:
        for ma in [5, 20, 60, 120]:
            df[f'MA_{ma}'] = df['Close'].rolling(window=ma).mean()
            
    if 'Bollinger Bands' in indicators:
        df['BB_MA20'] = df['Close'].rolling(window=20).mean()
        df['BB_STD20'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_MA20'] + (df['BB_STD20'] * 2)
        df['BB_Lower'] = df['BB_MA20'] - (df['BB_STD20'] * 2)
        
    if 'MACD' in indicators:
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
    if 'RSI' in indicators:
        delta = df['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        df['RSI'] = 100 - (100 / (1 + rs))
        
    return df

def plot_synchronized_charts(selected_stocks: pd.DataFrame, start_date: str, end_date: str, show_macro: bool = False, indicators: list = None):
    """
    Build a multi-row Plotly figure with shared x-axes.
    HTS Style with separated Volume, MACD, RSI and Normalized Macro.
    """
    import datetime
    
    if selected_stocks.empty:
        return None
        
    if indicators is None:
        indicators = []
        
    dt_start = datetime.datetime.strptime(start_date, "%Y%m%d")
    padded_start = (dt_start - datetime.timedelta(days=180)).strftime("%Y%m%d")
    
    raw_tickers = selected_stocks['Ticker'].tolist()
    raw_names = selected_stocks['Name'].tolist()
    
    # 1. 차트 렌더링 누락 버그 수정: 데이터부터 먼저 가져와서 유효한 종목만 필터링
    stock_data = {}
    tickers = []
    names = []
    
    for ticker, name in zip(raw_tickers, raw_names):
        df = get_stock_ohlcv(ticker, padded_start, end_date)
        if not df.empty:
            df = calculate_indicators(df, indicators)
            df = df[df.index >= dt_start]
            if not df.empty:
                stock_data[name] = df
                tickers.append(ticker)
                names.append(name)
                
    num_stocks = len(tickers)
    if num_stocks == 0:
        return None
        
    # X-axis ZigZag 버그 수정을 위한 전체 날짜 수집 및 정렬
    all_dates = set()
    for df in stock_data.values():
        all_dates.update(df.index.strftime('%Y-%m-%d'))
        
    macro_df = pd.DataFrame()
    if show_macro:
        macro_df = get_macro_data(start_date, end_date)
        if not macro_df.empty:
            macro_df.index = macro_df.index.tz_localize(None)
            all_dates.update(macro_df.index.strftime('%Y-%m-%d'))
            
    sorted_dates = sorted(list(all_dates))
    
    # 2. 레이아웃 재도입 (HTS 스타일: 종목 내 밀착, 종목 간 분리)
    has_macd = 'MACD' in indicators
    has_rsi = 'RSI' in indicators
    
    row_heights = [3.0, 1.0] # Performance row, Spacer
    specs = [[{"secondary_y": False}], [None]]
    subplot_titles = ["Normalized Performance (Base=100)", ""]
    
    total_rows = 2
    stock_row_starts = []
    
    for name in names:
        stock_row_starts.append(total_rows + 1)
        # Candle, Volume (7:3 비율 유지)
        row_heights.extend([7.0, 3.0])
        specs.extend([[{"secondary_y": False}], [{"secondary_y": False}]])
        subplot_titles.extend([f"{name} Candle", ""])
        total_rows += 2
        
        if has_macd:
            row_heights.append(3.0)
            specs.append([{"secondary_y": False}])
            subplot_titles.append("")
            total_rows += 1
            
        if has_rsi:
            row_heights.append(3.0)
            specs.append([{"secondary_y": False}])
            subplot_titles.append("")
            total_rows += 1
            
        # 종목 사이 스페이서(Spacer)
        row_heights.append(2.0)
        specs.append([None])
        subplot_titles.append("")
        total_rows += 1
        
    if show_macro:
        macro_row = total_rows + 1
        row_heights.append(4.0)
        specs.append([{"secondary_y": True}])
        subplot_titles.append("Normalized Macro Indicators (Base=100)")
        total_rows += 1
        
    # 같은 종목의 캔들과 거래량은 공백 없이 완전 밀착
    dyn_spacing = 0.005

    fig = make_subplots(
        rows=total_rows, 
        cols=1, 
        shared_xaxes=True,
        vertical_spacing=dyn_spacing,
        row_heights=row_heights,
        specs=specs,
        subplot_titles=subplot_titles
    )

    # 1. Plot Performance
    for name, df in stock_data.items():
        if not df.empty and len(df) > 0:
            base_price = df['Close'].iloc[0]
            if base_price > 0:
                rel_return = (df['Close'] / base_price) * 100
                fig.add_trace(go.Scatter(x=df.index.strftime('%Y-%m-%d'), y=rel_return, mode='lines', name=name), row=1, col=1)
                
    fig.update_yaxes(title_text="Returns", row=1, col=1)

    # 2. Plot Stocks
    color_up = '#ff3333'
    color_down = '#0066cc'
    
    for i, name in enumerate(names):
        if name not in stock_data: continue
        df = stock_data[name]
        
        start_r = stock_row_starts[i]
        str_index = df.index.strftime('%Y-%m-%d')
        
        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=str_index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name=f"{name} Candle", increasing_line_color=color_up, decreasing_line_color=color_down, showlegend=False
            ),
            row=start_r, col=1
        )
        fig.update_yaxes(title_text="Price(KRW)", row=start_r, col=1)
        
        # MAs
        if 'Moving Averages' in indicators:
            ma_colors = ['#f4a261', '#e76f51', '#2a9d8f', '#264653']
            for j, ma in enumerate([5, 20, 60, 120]):
                if f'MA_{ma}' in df.columns:
                    fig.add_trace(go.Scatter(x=str_index, y=df[f'MA_{ma}'], mode='lines', name=f"{name} MA{ma}", line=dict(color=ma_colors[j], width=1), showlegend=False), row=start_r, col=1)
                    
        # Bollinger Bands
        if 'Bollinger Bands' in indicators and 'BB_Upper' in df.columns:
            fig.add_trace(go.Scatter(x=str_index, y=df['BB_Upper'], mode='lines', line=dict(color='rgba(173, 216, 230, 0.5)', width=1, dash='dash'), showlegend=False), row=start_r, col=1)
            fig.add_trace(go.Scatter(x=str_index, y=df['BB_Lower'], mode='lines', fill='tonexty', fillcolor='rgba(173, 216, 230, 0.1)', line=dict(color='rgba(173, 216, 230, 0.5)', width=1, dash='dash'), showlegend=False), row=start_r, col=1)
            fig.add_trace(go.Scatter(x=str_index, y=df['BB_MA20'], mode='lines', line=dict(color='rgba(173, 216, 230, 0.8)', width=1), showlegend=False), row=start_r, col=1)

        # Volume
        vol_r = start_r + 1
        vol_colors = [color_up if row['Close'] >= row['Open'] else color_down for _, row in df.iterrows()]
        fig.add_trace(go.Bar(x=str_index, y=df['Volume'], name=f"{name} Vol", marker_color=vol_colors, opacity=0.8, showlegend=False), row=vol_r, col=1)
        # 볼륨 Y축 단위를 축약형(.2s)으로 지정하여 M, k 등으로 표시
        fig.update_yaxes(title_text="Volume", tickformat=".2s", row=vol_r, col=1)
        
        current_offset = 2
        # MACD
        if has_macd and 'MACD' in df.columns:
            macd_r = start_r + current_offset
            fig.add_trace(go.Scatter(x=str_index, y=df['MACD'], mode='lines', line=dict(color='#ff9900', width=1.5), showlegend=False), row=macd_r, col=1)
            fig.add_trace(go.Scatter(x=str_index, y=df['MACD_Signal'], mode='lines', line=dict(color='#00b3ff', width=1.5), showlegend=False), row=macd_r, col=1)
            macd_colors = ['#ff3333' if val >= 0 else '#0066cc' for val in df['MACD_Hist']]
            fig.add_trace(go.Bar(x=str_index, y=df['MACD_Hist'], marker_color=macd_colors, opacity=0.6, showlegend=False), row=macd_r, col=1)
            fig.update_yaxes(title_text="MACD", row=macd_r, col=1)
            current_offset += 1
            
        # RSI
        if has_rsi and 'RSI' in df.columns:
            rsi_r = start_r + current_offset
            fig.add_trace(go.Scatter(x=str_index, y=df['RSI'], mode='lines', line=dict(color='#d4a373', width=1.5), showlegend=False), row=rsi_r, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=rsi_r, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="blue", row=rsi_r, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=rsi_r, col=1)

    # 3. Macro
    if show_macro and not macro_df.empty:
        str_macro_index = macro_df.index.strftime('%Y-%m-%d')
        for col in macro_df.columns:
            base_val = macro_df[col].dropna().iloc[0] if len(macro_df[col].dropna()) > 0 else 1
            if base_val > 0: macro_df[col] = (macro_df[col] / base_val) * 100
                    
        if 'WTI' in macro_df.columns:
            fig.add_trace(go.Scatter(x=str_macro_index, y=macro_df['WTI'], mode='lines', name='WTI(Normalized)', line=dict(color='orange'), showlegend=True), row=macro_row, col=1, secondary_y=False)
        if 'Gold' in macro_df.columns:
            fig.add_trace(go.Scatter(x=str_macro_index, y=macro_df['Gold'], mode='lines', name='Gold(Normalized)', line=dict(color='gold'), showlegend=True), row=macro_row, col=1, secondary_y=False)
        if 'USD/KRW' in macro_df.columns:
            fig.add_trace(go.Scatter(x=str_macro_index, y=macro_df['USD/KRW'], mode='lines', name='USD/KRW(Normalized)', line=dict(color='#2ca02c'), showlegend=True), row=macro_row, col=1, secondary_y=True)
            
        fig.update_xaxes(title_text="날짜(Date)", row=macro_row, col=1)
        fig.update_yaxes(title_text="정규화 지수(Base=100)", row=macro_row, col=1, secondary_y=False)
        fig.update_yaxes(showgrid=False, secondary_y=True, row=macro_row, col=1)

    # Layout Updates
    height_per_stock = 400
    if has_macd: height_per_stock += 150
    if has_rsi: height_per_stock += 150
    
    fig.update_layout(
        height=200 + (height_per_stock * num_stocks) + (300 if show_macro else 0),
        template='plotly_dark',
        hovermode='x unified',
        margin=dict(l=60, r=40, t=60, b=80),
        xaxis=dict(rangeslider=dict(visible=False), fixedrange=False),
        dragmode='zoom',
        legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5)
    )
    
    fig.update(layout_xaxis_rangeslider_visible=False)
    for i in range(1, total_rows + 1):
        # Skip dummy rows
        if specs[i-1][0] is None:
            continue
            
        fig.update_xaxes(
            type='category', 
            categoryorder='array',
            categoryarray=sorted_dates,
            nticks=10, 
            rangeslider=dict(visible=False),
            fixedrange=False,
            row=i, col=1,
            showline=True, linewidth=1, linecolor='#555', mirror=True
        )
        fig.update_yaxes(
            tickformat=",", 
            showline=True, linewidth=1, linecolor='#555', mirror=True,
            row=i, col=1, secondary_y=False
        )
        if len(specs[i-1]) > 0 and isinstance(specs[i-1][0], dict) and specs[i-1][0].get("secondary_y"):
            fig.update_yaxes(tickformat=",", row=i, col=1, secondary_y=True)

    return fig
