import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 頁面全域設定 ---
st.set_page_config(page_title="🚀 超級智能決策系統", layout="wide", page_icon="🚀")

# 自定義 CSS 讓介面更專業簡潔
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    h1, h2, h3 {margin-bottom: 0.5rem; color: #69F0AE;}
    .report-card {background-color: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00E676;}
    .metric-container {background-color: #2F2F2F; padding: 10px; border-radius: 5px; margin-bottom: 10px;}
    p {font-size: 16px;}
</style>
""", unsafe_allow_html=True)

# --- 2. 數據獲取與指標計算 (新增所有指標) ---

@st.cache_data(ttl=300)
def get_data(symbol, period, interval):
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period, interval=interval)
        info = stock.info
        
        # --- 新增所有均線 ---
        df['SMA_5'] = ta.sma(df['Close'], length=5)
        df['SMA_10'] = ta.sma(df['Close'], length=10)
        df['SMA_20'] = ta.sma(df['Close'], length=20)
        df['SMA_50'] = ta.sma(df['Close'], length=50) # 長線趨勢

        # --- 新增高階指標 ---
        df['RSI'] = ta.rsi(df['Close'], length=14)
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        stoch = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3) # KD 指數
        df = pd.concat([df, stoch], axis=1)

        # --- 主力追蹤指標 ---
        df['MFI'] = ta.mfi(df['High'], df['Low'], df['Close'], df['Volume'], length=14)
        df['OBV'] = ta.obv(df['Close'], df['Volume'])
        
        return df, info
    except Exception:
        return None, None

# --- 3. 核心：超級智能五維度評分函數 ---

def calculate_super_score(df, info):
    if df is None or df.empty or info is None: return 50, []
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    score = 50
    reasons = []

    # --- 權重設定 ---
    WEIGHTS = {
        'TREND': 30,       # 長線趨勢 (SMA 50)
        'MOMENTUM': 30,    # 短線動能 (MA 5/10, MACD, RSI)
        'INSTITUTION': 20, # 主力追蹤 (MFI, OBV)
        'SHORT_RISK': 20   # 空頭風險 (Short Float)
    }
    
    # ----------------------------------------------------
    # 1. 趨勢分析 (Trend - 長線方向 30%)
    # ----------------------------------------------------
    if last['SMA_5'] > last['SMA_50']:
        score += 15
        reasons.append("🟢 **長線趨勢確認**：短線均線 (MA5) 在長線均線 (MA50) 之上，大方向看多。")
    elif last['SMA_5'] < last['SMA_50']:
        score -= 15
        reasons.append("🔻 **長線趨勢轉弱**：股價位於長線均線之下，操作應以防守為主。")

    # ----------------------------------------------------
    # 2. 動能分析 (Momentum - 短線進場點 30%)
    # ----------------------------------------------------
    
    # MA 5/10 交叉 (最強短線訊號)
    if last['SMA_5'] > last['SMA_10'] and prev['SMA_5'] <= prev['SMA_10']:
        score += 10
        reasons.append("🚀 **MA金叉訊號**：5日線向上突破10日線，短線強勢進場點。")
    
    # KD 指標金叉/死叉 (STOCHk/STOCHd)
    k_line = f'STOCHk_14_3_3'
    d_line = f'STOCHd_14_3_3'
    if k_line in df.columns and d_line in df.columns:
        if last[k_line] > last[d_line] and last[k_line] < 50:
            score += 10
            reasons.append("💎 **KD低檔金叉**：K線向上突破D線，低檔買入機會。")
        elif last[k_line] < last[d_line] and last[k_line] > 80:
            score -= 10
            reasons.append("🛑 **KD高檔死叉**：K線向下突破D線，高檔賣出警示。")
    
    # ----------------------------------------------------
    # 3. 主力追蹤 (Institution - 資金流向 20%)
    # ----------------------------------------------------
    if last['MFI'] > 80 and last['OBV'] > df['OBV'].iloc[-10]:
        score += 10
        reasons.append("💰 **主力資金湧入**：MFI 過熱且 OBV 上升，主力資金積極佈局中。")
    elif last['MFI'] < 20:
        score += 5
        reasons.append("🌊 **MFI資金超賣**：資金流出已達極限，容易反彈。")

    # ----------------------------------------------------
    # 4. 空頭風險分析 (Short Risk - 20%)
    # ----------------------------------------------------
    short_pct = info.get('shortPercentOfFloat', 0)
    if short_pct > 0.2: # 做空比例超過 20%
        score += 15 # 視為潛在軋空動能
        reasons.append(f"🔥 **超高軋空風險**：做空比例高達 {short_pct*100:.1f}%，若上漲易引發劇烈軋空行情。")

    # 綜合調整至 0-100 範圍
    return max(0, min(100, int(score))), reasons

def generate_narrative_summary(score):
    """根據分數生成 AI 報告的簡述"""
    if score >= 80:
        return "✨ **超級買入訊號：** 五大維度指標全面共振，趨勢強勁，短線動能啟動，且存在軋空潛力。建議立即執行買入策略。"
    elif score >= 65:
        return "🚀 **強勢樂觀信號：** 長線趨勢確立，短線雖有波動，但主力資金穩定流入。是中長線佈局的良好時機。"
    elif score >= 45:
        return "🟡 **中立觀望階段：** 指標訊號分歧，多空拉鋸。建議等待 MA5/10 或 KD 指標給出明確的金叉/死叉訊號。"
    else:
        return "🛑 **極度迴避風險：** 長線趨勢轉空，技術指標多數警示，建議立即停止買入，並考慮減倉或出場。"

# --- 4. 主介面：超級智能分析儀表板 ---

# UI 輸入控制
with st.sidebar:
    st.title("🎛️ 智能分析控制台")
    ticker_symbol = st.text_input("輸入美股代號", "NVDA").upper()
    
df, info = get_data(ticker_symbol, "1y", "1d")

st.title(f"💡 超級智能決策報告：{info.get('longName', ticker_symbol)} ({ticker_symbol})")

if df is not None and not df.empty and info is not None:
    
    # 核心分析計算
    super_score, reasons = calculate_super_score(df, info)
    narrative = generate_narrative_summary(super_score)
    current_price = df['Close'].iloc[-1]
    
    # --- A. 總評分與報告 ---
    st.markdown('<div class="report-card">', unsafe_allow_html=True)
    st.subheader(f"✅ 超級智能綜合評分")
    
    col_score, col_narrative = st.columns([1, 4])
    with col_score:
        st.metric("核心評分", f"{super_score}/100", delta_color="off")
        if super_score >= 80: st.success("🎯 買入！")
        elif super_score >= 65: st.warning("📈 謹慎樂觀")
        elif super_score >= 45: st.info("🟡 觀望中立")
        else: st.error("🛑 迴避風險")
    
    with col_narrative:
        st.markdown(f"**當前價格:** ${current_price:.2f}")
        st.write("#### 📝 智能總結報告")
        st.markdown(narrative)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

    # --- B. 關鍵技術信號圖 (極簡化) ---
    st.subheader("趨勢與短線動能視覺化")
    
    # 只繪製 K 線和 MA 5, 10, 50
    fig = go.Figure(data=[
        go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'),
        go.Scatter(x=df.index, y=df['SMA_5'], line=dict(color='#00E676', width=1), name='MA 5 (短線)'),
        go.Scatter(x=df.index, y=df['SMA_10'], line=dict(color='orange', width=1), name='MA 10 (動能)'),
        go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=2), name='MA 50 (趨勢)'),
    ])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, title=f'{ticker_symbol} 價格與均線走勢')
    st.plotly_chart(fig, use_container_width=True)


    # --- C. 詳盡評分依據與追蹤 ---
    st.divider()
    
    col_reasons, col_fundamentals = st.columns(2)
    
    with col_reasons:
        st.subheader("📚 五維度分析報告 (評分依據)")
        for reason in reasons:
            st.markdown(f"- {reason}")
            
    with col_fundamentals:
        st.subheader("🏦 空頭追蹤與基本面")
        
        # 1. 空頭追蹤
        short_pct = info.get('shortPercentOfFloat', 0)
        short_risk_level = "低"
        if short_pct > 0.2: short_risk_level = "極高 (潛在軋空)"
        elif short_pct > 0.1: short_risk_level = "高"
        
        st.markdown(f"**做空比例 (Short Float)**：**{short_pct*100:.1f}%** (風險級別：{short_risk_level})")
        st.markdown(f"**空頭回補天數 (Days to Cover)**：{info.get('daysToCover', 'N/A')}")
        
        st.markdown("---")
        
        # 2. 財務簡評
        st.markdown(f"**本益比 (PE)**：{info.get('trailingPE', 'N/A')}")
        st.markdown(f"**營收成長率 (YoY)**：{info.get('revenueGrowth', 0)*100:.1f}%")
        st.markdown(f"**分析師共識**：{info.get('recommendationKey', 'N/A').upper()}")
        
    st.caption("數據來源：Yahoo Finance 及 Pandas_TA 庫。分數是基於多重高階技術指標、主力指標及空頭風險的綜合權重計算。")

