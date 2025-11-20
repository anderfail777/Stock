import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from textblob import TextBlob
from datetime import datetime, timedelta

# --- 1. 頁面全域設定 ---
st.set_page_config(page_title="🤖 Gemini 智能決策儀表板", layout="wide", page_icon="💡")

# 自定義 CSS 讓介面更簡潔
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    h1, h2, h3 {margin-bottom: 0.5rem;}
    .report-card {background-color: #2F2F2F; padding: 20px; border-radius: 10px; border-left: 5px solid #4CAF50;}
    .metric-container {background-color: #1E1E1E; padding: 10px; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)

# --- 2. 數據獲取與指標計算 ---

@st.cache_data(ttl=300)
def get_data(symbol, period, interval):
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period, interval=interval)
        info = stock.info
        news = stock.news
        
        # 技術指標計算
        df['SMA_20'] = ta.sma(df['Close'], length=20)
        df['SMA_60'] = ta.sma(df['Close'], length=60)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        
        return df, info, news
    except Exception:
        return None, None, None

# --- 3. 核心：Gemini 智能評分函數 ---

def calculate_gemini_score(df, info, news):
    if df is None or df.empty or info is None: return 50, []
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    score = 50
    reasons = []

    # A. 技術動能評估 (佔 50%)
    tech_score = 0
    
    # 1. 趨勢 (長短期均線)
    if last['SMA_20'] > last['SMA_60']:
        tech_score += 20
        reasons.append("📈 **趨勢強勁**：短線均線位於長線均線之上。")
    elif last['SMA_20'] < last['SMA_60'] and last['Close'] > last['SMA_20']:
        tech_score += 10
        reasons.append("🟡 **潛在轉強**：價格回升至短線均線之上。")
    else:
        tech_score -= 10
        reasons.append("🔻 **趨勢轉弱**：短線均線位於長線之下。")

    # 2. RSI (超買超賣)
    if last['RSI'] < 35:
        tech_score += 15
        reasons.append("💎 **RSI超賣**：進入高勝率反彈區間。")
    elif last['RSI'] > 70:
        tech_score -= 15
        reasons.append("⚠️ **RSI超買**：短線回調風險高。")

    # 3. MACD (動能確認)
    if 'MACD_12_26_9' in df.columns:
        if last['MACD_12_26_9'] > last['MACDs_12_26_9'] and prev['MACD_12_26_9'] <= prev['MACDs_12_26_9']:
            tech_score += 15
            reasons.append("🚀 **MACD金叉**：動能由負轉正，啟動訊號。")
        elif last['MACD_12_26_9'] < last['MACDs_12_26_9'] and prev['MACD_12_26_9'] >= prev['MACDs_12_26_9']:
            tech_score -= 15
            reasons.append("🛑 **MACD死叉**：動能減弱，出場訊號。")

    # B. 財務健康評估 (佔 30%)
    fin_score = 0
    
    # 1. 營收成長 (Year over Year)
    revenue_growth = info.get('revenueGrowth', 0)
    if revenue_growth > 0.1: # 10% YOY
        fin_score += 15
        reasons.append(f"💰 **營收強勁**：年增長率達 {revenue_growth*100:.1f}%。")
    elif revenue_growth < -0.05:
        fin_score -= 15
        reasons.append("📉 **營收衰退**：基本面需要警惕。")

    # 2. 債務 (Debt to Equity)
    debt_to_equity = info.get('debtToEquity', 1000) # 預設高值
    if debt_to_equity < 1: # 負債/股東權益 < 100%
        fin_score += 15
        reasons.append("🛡️ **低負債率**：財務結構相對穩健。")
    
    # C. 情緒與做空評估 (佔 20%)
    sent_score = 0
    short_pct = info.get('shortPercentOfFloat', 0)
    if short_pct > 0.2:
        sent_score += 20
        reasons.append("🔥 **潛在軋空**：做空比例高，一旦上漲容易加速。")

    # 綜合計算 (調整至 0-100)
    final_score = 50 + (tech_score * 0.5) + (fin_score * 0.3) + (sent_score * 0.2)
    return max(0, min(100, int(final_score))), reasons

def generate_narrative_summary(score):
    """根據分數生成 Gemini 報告"""
    if score >= 75:
        return "🔥 **Gemini 高度看好：** 技術面、基本面和市場情緒多方共振，具備強烈的向上動能，是高勝率的進場時機。"
    elif score >= 60:
        return "📈 **Gemini 謹慎樂觀：** 趨勢相對穩健，但缺乏爆炸性訊號。可輕倉佈局或等待關鍵回調點位。"
    elif score >= 40:
        return "🟡 **Gemini 觀望中立：** 多空力量膠著，指標分歧，建議等待明確的方向性信號出現再行動，目前不宜重倉。"
    else:
        return "🛑 **Gemini 建議迴避：** 趨勢已轉弱，基本面或市場情緒存在重大風險，應避免買入或考慮出場。"

# --- 4. 主介面：極簡分析儀表板 ---

# UI 輸入控制
with st.sidebar:
    ticker_symbol = st.text_input("輸入美股代號", "TSLA").upper()
    
df, info, news = get_data(ticker_symbol, "1y", "1d")

st.title(f"💡 Gemini 智能報告：{info.get('longName', ticker_symbol)} ({ticker_symbol})")

if df is not None and not df.empty and info is not None:
    
    # 核心分析計算
    gemini_score, reasons = calculate_gemini_score(df, info, news)
    narrative = generate_narrative_summary(gemini_score)
    current_price = df['Close'].iloc[-1]
    
    # --- A. 總評分與報告 ---
    st.markdown('<div class="report-card">', unsafe_allow_html=True)
    st.subheader(f"💯 Gemini 智能洞察評分")
    
    col_score, col_narrative = st.columns([1, 4])
    with col_score:
        st.metric("總評分", f"{gemini_score}/100", delta_color="off")
        if gemini_score >= 75: st.success("🚀 強烈買入")
        elif gemini_score >= 60: st.warning("📈 謹慎樂觀")
        elif gemini_score >= 40: st.info("🟡 觀望中立")
        else: st.error("🛑 迴避風險")
    
    with col_narrative:
        st.write("#### 核心決策分析：")
        st.markdown(narrative)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

    # --- B. 關鍵技術信號圖 ---
    st.subheader("關鍵技術信號與點位")
    
    col_chart, col_key_metrics = st.columns([3, 1])

    with col_chart:
        # 只繪製 K 線和均線，極簡化圖表
        fig = go.Figure(data=[
            go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'),
            go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='SMA 20'),
            go.Scatter(x=df.index, y=df['SMA_60'], line=dict(color='blue', width=1), name='SMA 60'),
        ])
        fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, title='價格與趨勢線')
        st.plotly_chart(fig, use_container_width=True)

    with col_key_metrics:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.write("#### 🎯 建議進場點")
        st.metric("當前價格", f"${current_price:.2f}")
        
        # 計算支撐與壓力
        low_50 = df['Low'].tail(50).min()
        high_50 = df['High'].tail(50).max()

        if current_price < low_50 * 1.05: # 在接近支撐位時給出建議
            st.warning(f"**強支撐區：** ${low_50:.2f}")
        elif current_price > high_50 * 0.95:
            st.success(f"**目標壓力位：** ${high_50:.2f}")
            
        st.markdown('</div>', unsafe_allow_html=True)


    # --- C. 詳盡評分依據 ---
    st.divider()
    st.subheader("📊 評分依據：細項分析")
    
    for reason in reasons:
        st.markdown(f"- {reason}")
    
    st.caption("數據來源：Yahoo Finance 及 Pandas_TA 庫。分數為AI模型基於技術、財務、情緒三維度的綜合評估。")

else:
    st.info("請在左側輸入有效的股票代號，並開始進行 Gemini 智能分析。")

