import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from textblob import TextBlob
from datetime import datetime

# --- 1. 頁面全域設定 (模擬專業軟體暗黑風格) ---
st.set_page_config(page_title="ProTrade 美股戰情室", layout="wide", page_icon="📈")

# 自定義 CSS
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    h1, h2, h3 {margin-bottom: 0.5rem;}
    .stMetric {background-color: #1E1E1E; padding: 10px; border-radius: 5px; border: 1px solid #333;}
</style>
""", unsafe_allow_html=True)

# --- 2. 側邊欄：全域控制 ---
with st.sidebar:
    st.title("🎛️ 交易控制台")
    ticker = st.text_input("股票代號", "NVDA").upper()
    period = st.selectbox("K線週期", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
    interval = "1d"
    
    st.divider()
    st.subheader("⚙️ 指標參數")
    ma_short = st.number_input("短期均線 (MA)", value=20)
    ma_long = st.number_input("長期均線 (MA)", value=60)
    rsi_len = st.number_input("RSI 週期", value=14)

# --- 3. 核心數據獲取函數 ---
@st.cache_data(ttl=300)
def get_data(symbol, p, i):
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=p, interval=i)
        info = stock.info
        news = stock.news
        return df, info, news, stock
    except Exception:
        return None, None, None, None

df, info, news, stock_obj = get_data(ticker, period, interval)

if df is None or df.empty:
    st.error("無法獲取數據，請檢查股票代號是否正確。")
    st.stop()

# --- 4. 數據處理與指標計算 ---
df['SMA_S'] = ta.sma(df['Close'], length=ma_short)
df['SMA_L'] = ta.sma(df['Close'], length=ma_long)
df['RSI'] = ta.rsi(df['Close'], length=rsi_len)
macd = ta.macd(df['Close'])
df = pd.concat([df, macd], axis=1)
bb = ta.bbands(df['Close'], length=20)
df = pd.concat([df, bb], axis=1)
df['MFI'] = ta.mfi(df['High'], df['Low'], df['Close'], df['Volume'], length=14)
df['OBV'] = ta.obv(df['Close'], df['Volume'])

last = df.iloc[-1]
prev = df.iloc[-2]

# --- 5. 主介面：分頁設計 ---
st.title(f"{info.get('longName', ticker)} ({ticker})")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 綜合看板", "📈 專業圖表", "💰 主力資金", "📑 財報基本面", "🤖 高勝率策略"
])

# Tab 1: 綜合看板
with tab1:
    chg = last['Close'] - prev['Close']
    pct_chg = (chg / prev['Close']) * 100
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("最新價格", f"${last['Close']:.2f}", f"{pct_chg:.2f}%")
    c2.metric("成交量", f"{last['Volume'] / 1e6:.1f}M")
    c3.metric("52週最高", f"${info.get('fiftyTwoWeekHigh', 0):.2f}")
    c4.metric("52週最低", f"${info.get('fiftyTwoWeekLow', 0):.2f}")
    short_pct = info.get('shortPercentOfFloat', 0)
    c5.metric("做空比例", f"{short_pct * 100:.2f}%" if short_pct else "N/A")

    st.divider()
    col_news, col_sent = st.columns([2, 1])
    with col_news:
        st.subheader("📰 最新市場消息")
        if news:
            for n in news[:4]:
                pub = datetime.fromtimestamp(n['providerPublishTime']).strftime('%Y-%m-%d %H:%M')
                st.markdown(f"**[{n['title']}]({n['link']})**")
                st.caption(f"{n['publisher']} • {pub}")
        else: st.info("暫無新聞")

    with col_sent:
        st.subheader("📉 情緒分析")
        if short_pct and short_pct > 0.2: st.error("⚠️ 軋空風險高 (>20%)")
        elif short_pct and short_pct > 0.1: st.warning("⚡ 做空情緒升溫")
        else: st.success("✅ 做空情緒穩定")
        
        sent_sum = 0
        if news:
            for n in news[:5]: sent_sum += TextBlob(n['title']).sentiment.polarity
            avg = sent_sum / len(news[:5])
            st.metric("新聞情緒", f"{avg:.2f}")

# Tab 2: 專業圖表
with tab2:
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.5, 0.15, 0.15, 0.2],
                        subplot_titles=("價格/均線/布林帶", "成交量", "MACD", "RSI"))
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_S'], line=dict(color='orange', width=1), name='MA短期'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_L'], line=dict(color='blue', width=1), name='MA長期'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBU_20_2.0'], line=dict(color='gray', width=0.5, dash='dot'), name='BB上'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBL_20_2.0'], line=dict(color='gray', width=0.5, dash='dot'), name='BB下'), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=['green' if o-c>=0 else 'red' for o,c in zip(df['Open'],df['Close'])], name='Vol'), row=2, col=1)
    if 'MACD_12_26_9' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], line=dict(color='cyan'), name='MACD'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], line=dict(color='orange'), name='Sig'), row=3, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['MACDh_12_26_9'], marker_color='gray'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'), row=4, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=4, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=4, col=1)
    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# Tab 3: 主力資金
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🌊 MFI 資金流量")
        st.write(f"數值: {last['MFI']:.2f}")
        if last['MFI']>80: st.error("資金過熱")
        elif last['MFI']<20: st.success("資金超賣")
        st.line_chart(df['MFI'].tail(50))
    with c2:
        st.subheader("🏔️ OBV 能量潮")
        st.metric("OBV 趨勢", "上升" if last['OBV']>df['OBV'].iloc[-10] else "下降")
        st.line_chart(df['OBV'].tail(50))

# Tab 4: 財報
with tab4:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PE (本益比)", f"{info.get('trailingPE','N/A')}")
    c2.metric("EPS", f"{info.get('trailingEps','N/A')}")
    c3.metric("市值", f"{info.get('marketCap',0)/1e9:.2f}B")
    c4.metric("評級", f"{info.get('recommendationKey','N/A').upper()}")
    st.divider()
    st.write(f"**營收成長:** {info.get('revenueGrowth',0)*100:.2f}% | **毛利率:** {info.get('grossMargins',0)*100:.2f}%")

# Tab 5: 策略
with tab5:
    st.subheader("🤖 智能策略分析")
    score = 50
    sigs = []
    if last['Close'] > last['SMA_L']: score+=10; sigs.append("✅ 趨勢向上 (股價 > 長期均線)")
    else: score-=10; sigs.append("🔻 趨勢向下")
    if last['RSI'] < 30: score+=25; sigs.append("💎 RSI 超賣 (強力買點)")
    elif last['RSI'] > 70: score-=20; sigs.append("⚠️ RSI 超買 (風險高)")
    if last['Close'] < last['BBL_20_2.0']: score+=20; sigs.append("🛡️ 跌破布林下軌 (超跌)")
    
    c1, c2 = st.columns([1, 2])
    c1.metric("AI 勝率評分", f"{score}/100")
    if score>=75: c1.success("強力買入")
    elif score>=55: c1.warning("持有/觀望")
    else: c1.error("賣出/空手")
    
    with c2:
        for s in sigs: st.write(s)
    
    st.info(f"📍 **掛單區間:** ${last['Close']*0.98:.2f} - ${last['Close']:.2f} | **停損:** ${df['Low'].tail(60).min():.2f}")
