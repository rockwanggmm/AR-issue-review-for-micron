import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# 1. 網頁基礎設定 (寬螢幕模式與科技感主題)
st.set_page_config(
    page_title="美光專案動態議題追蹤大盤",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 系統自訂樣式 CSS (用於網頁畫面上的排版美化)
st.markdown("""
    <style>
    .highlight-red {
        background-color: #ffe6e6;
        padding: 4px 8px;
        color: #cc0000;
        font-weight: bold;
        border-radius: 4px;
        font-size: 13px;
    }
    .highlight-yellow {
        background-color: #fff9db;
        padding: 4px 8px;
        color: #b28600;
        font-weight: bold;
        border-radius: 4px;
        font-size: 13px;
    }
    </style>
""", unsafe_allow_html=True)

# 2. 側邊欄：動態檔案上傳功能
st.sidebar.image("https://img.icons8.com/clouds/100/000000/data-configuration.png", width=80)
st.sidebar.title("數據管理中心")
st.sidebar.markdown("---")

st.sidebar.subheader("📂 步驟 1：上傳專案 CSV 檔案")
uploaded_file = st.sidebar.file_uploader(
    "請選擇或拖曳 Jira 匯出的 CSV 檔案", 
    type=["csv"], 
    help="支援包含 Summary, Status, Priority, 未解天數, Due date 等欄位的 CSV 報表"
)

# 3. 資料載入與動態清洗函數
def process_uploaded_data(file):
    df = pd.read_csv(file)
    
    # 【欄位防錯與標準化機制】
    rename_dict = {
        '主題': 'Summary', '問題摘要': 'Summary',
        '狀態': 'Status',
        '優先級': 'Priority', '優先程度': 'Priority',
        '經辦人': 'Assignee', '負責人': 'Assignee',
        '到期日': 'Due date', '預計完成日': 'Due date'
    }
    df = df.rename(columns=rename_dict)
    
    # 檢查核心欄位是否存在，若缺欄位則補空欄位避免程式崩潰
    required_cols = ['Summary', 'Status', 'Priority', 'Assignee', 'Created', 'Updated', 'Due date', '未解天數']
    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    # 轉換日期格式
    df['Created'] = pd.to_datetime(df['Created'], errors='coerce')
    df['Updated'] = pd.to_datetime(df['Updated'], errors='coerce')
    df['Due date'] = pd.to_datetime(df['Due date'], errors='coerce')
    
    # 【未解天數清洗】：將非數字欄位（如 'done', '無立案日期'）轉為數字 0
    df['未解天數'] = pd.to_numeric(df['未解天數'], errors='coerce').fillna(0).astype(int)
    
    # 建立客戶關注標籤 (動態掃描 Summary 關鍵字)
    def classify_tag(summary):
        s_str = str(summary)
        if any(keyword in s_str for keyword in ['Top 5', 'Top項目', '新 Top', '關鍵']):
            return "🔥 Top 核心議題"
        return "標準一般議題"
    
    df['議題分類'] = df['Summary'].apply(classify_tag)
    
    # 風險監控自動 Highlight 邏輯 (以資料最新 Updated 時間為基準)
    base_date = df['Updated'].max() if df['Updated'].notnull().any() else datetime.now()
    
    def detect_risk(row):
        risks = []
        if pd.notnull(row['Due date']) and row['Due date'] < base_date and row['Status'] not in ['Done', 'Closed']:
            risks.append("🚨 已逾期 (Overdue)")
        if pd.isna(row['Assignee']) or str(row['Assignee']).strip() == '' or str(row['Assignee']) == 'nan':
            risks.append("👤 未指派負責 R&D")
        if row['未解天數'] > 45:
            risks.append("⏳ 滯留超時 (>45天)")
        return " / ".join(risks) if risks else "✅ 正常追蹤中"

    df['風險監控'] = df.apply(detect_risk, axis=1)
    return df, base_date

# 4. 主畫面控制流：判斷是否有檔案上傳
if uploaded_file is not None:
    try:
        df, data_base_date = process_uploaded_data(uploaded_file)
        
        # 側邊欄：動態動態篩選器
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 步驟 2：篩選大盤資料")
        
        all_priorities = sorted(df['Priority'].dropna().unique().tolist())
        selected_priorities = st.sidebar.multiselect("議題優先級 (Priority)", all_priorities, default=all_priorities)

        all_statuses = df['Status'].dropna().unique().tolist()
        selected_statuses = st.sidebar.multiselect("目前處理狀態 (Status)", all_statuses, default=all_statuses)

        all_tags = df['議題分類'].unique().tolist()
        selected_tags = st.sidebar.multiselect("群組分類", all_tags, default=all_tags)

        # 執行篩選
        filtered_df = df[
            (df['Priority'].isin(selected_priorities)) & 
            (df['Status'].isin(selected_statuses)) &
            (df['議題分類'].isin(selected_tags))
        ]

        # 5. 主面板頁面呈現
        st.title("🏭 美光機台異常議題追蹤與質量分析 Dashboard")
        st.markdown(f"**📂 當前分析檔案：`{uploaded_file.name}`** ｜ 💡 數據分析基準日：{data_base_date.strftime('%Y/%m/%d')}")
        st.markdown("---")

        # 6. KPI 指標卡片
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="📊 當前篩選議題數", value=len(filtered_df))
        with col2:
            top_count = len(filtered_df[filtered_df['議題分類'] == "🔥 Top 核心議題"])
            st.metric(label="🔥 客戶關注 Top 項目", value=top_count)
        with col3:
            # 算平均天數時，只計算有未解天數（大於 0）的議題
            active_issues = filtered_df[filtered_df['未解天數'] > 0]
            avg_days = int(active_issues['未解天數'].mean()) if len(active_issues) > 0 else 0
            st.metric(label="⏳ 處理中議題平均未解天數", value=f"{avg_days} 天")
        with col4:
            risk_count = len(filtered_df[(filtered_df['風險監控'] != "✅ 正常追蹤中") & (filtered_df['Status'] != 'Done')])
            st.metric(label="⚠️ 紅燈異常警示項", value=risk_count)

        st.markdown("---")

        # 7. 雙圖表展示
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.subheader("📌 議題生命週期：未解天數排行")
            
            # 💡 網頁標註說明：讓客戶看懂顏色定義
            st.markdown("""
            **🎨 燈號顏色異常定義說明：**
            * 🔴 <span style='color:#ff4d4d; font-weight:bold;'>深紅燈 (>45天)</span>：高風險極具急迫性，嚴重卡關。
            * 🟡 <span style='color:#ffaa00; font-weight:bold;'>黃燈 (21-45天)</span>：需注意並加強收斂，已出現滯留現象。
            * 🔵 <span style='color:#4da6ff; font-weight:bold;'>藍燈 (≤20天)</span>：正常時效內，進度持續追蹤中。
            """, unsafe_allow_html=True)
            
            # 🔥【限定過濾】：只顯示有未解天數 ( > 0 ) 的項目
            chart_df = filtered_df[filtered_df['未解天數'] > 0]
            
            if not chart_df.empty:
                sort_df = chart_df.sort_values(by='未解天數', ascending=True)
                
                # 燈號顏色邏輯
                colors = ['#ff4d4d' if x > 45 else ('#ffaa00' if x > 20 else '#4da6ff') for x in sort_df['未解天數']]
                
                fig_days = go.Figure(go.Bar(
                    x=sort_df['未解天數'],
                    y=sort_df['Summary'].apply(lambda x: str(x)[:22] + "..."), 
                    orientation='h',
                    marker_color=colors,
                    text=sort_df['未解天數'].apply(lambda x: f" {x}天"),
                    textposition='outside',
                    hovertext=sort_df['Summary']
                ))
                
                # 💡 圖表內建附註 (Annotations)：確保圖片導出/截圖時也有圖例說明
                fig_days.update_layout(
                    height=max(400, len(sort_df) * 25), 
                    margin=dict(l=10, r=50, t=20, b=60), 
                    yaxis=dict(autorange="reversed"),
                    xaxis_title="未處理/未解天數 (Days)",
                    annotations=[dict(
                        text="圖表燈號說明: 🔴 >45天嚴重卡關 | 🟡 21-45天警告 | 🔵 ≤20天正常追蹤",
                        showarrow=False,
                        xref="paper", yref="paper",
                        x=0, y=-0.1,
                        font=dict(size=12, color="#555555")
                    )]
                )
                st.plotly_chart(fig_days, use_container_width=True)
            else:
                st.info("💡 目前篩選條件下，沒有正在卡關（有未解天數）的議題。")

        with chart_col2:
            st.subheader("📊 議題狀態與優先級交叉分析")
            if not filtered_df.empty:
                fig_status = px.histogram(
                    filtered_df, x='Status', color='Priority', barmode='group',
                    color_discrete_map={'P1': '#d9381e', 'P2': '#f28e2b', 'P3': '#4e79a7', 'P4': '#76b7b2'}
                )
                fig_status.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("暫無圖表數據。")

        st.markdown("---")

        # 8. 異常 Highlight 區塊
        st.subheader("🚨 客戶核心關注：異常與紅燈風險項目 (Risk Highlighting)")
        # 排除已完成項目
        risk_df = filtered_df[(filtered_df['風險監控'] != "✅ 正常追蹤中") & (filtered_df['Status'] != 'Done')]

        if not risk_df.empty:
            for idx, row in risk_df.iterrows():
                color_hex = "#ff4d4d" if "🚨" in row['風險監控'] else "#ffaa00"
                st.markdown(f"""
                <div style="border-left: 6px solid {color_hex}; background-color: #fff5f5; padding: 12px; margin-bottom: 10px; border-radius: 4px;">
                    <span style="background-color: {color_hex}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight:bold;">{row['Priority']}</span> 
                    <span style="color: #666; font-size: 13px;">[ {row['Status']} ]</span>
                    <strong style="font-size: 14px; color: #111; margin-left: 10px;">{row['Summary']}</strong>
                    <br/>
                    <div style="margin-top: 6px; font-size: 13px;">
                        <span class="highlight-red">風險原因：{row['風險監控']}</span> | 
                        <span>Owner：<b>{row['Assignee'] if pd.notnull(row['Assignee']) else '❌ 待指派'}</b></span> | 
                        <span>未解天數：<b>{row['未解天數']} 天</b></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("🎉 完美！目前所選條件下，無任何異常紅燈項目。")

        st.markdown("---")

        # 9. 明細資料表格
        st.subheader("📋 專案全議題全圖譜明細")
        display_df = filtered_df[['議題分類', 'Priority', 'Status', 'Summary', 'Assignee', '未解天數', 'Due date', '風險監控']].copy()
        display_df['Due date'] = display_df['Due date'].apply(lambda x: x.strftime('%Y/%m/%d') if pd.notnull(x) else '未定')
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"解析上傳的 CSV 檔案時出錯，請確認格式是否正確。錯誤訊息: {e}")

else:
    # 引導用戶上傳檔案的 Welcome Page 介面
    st.title("🏭 美光機台異常議題追蹤與質量分析 Dashboard")
    st.markdown("---")
    st.info("👋 歡迎使用專案動態追蹤大盤！目前系統處於等待數據狀態。")
    st.markdown("""
    ### 🚀 快速開始三步驟：
    1. **準備檔案**：自 Jira 匯出您最新的議題清單 CSV 檔。
    2. **拖曳上傳**：點擊左側邊欄的 **`Browse files`** 按鈕或直接將 CSV 檔案拖曳進去。
    3. **即時簡報**：系統將自動解析欄位，生成客製化的美光報告圖表與紅燈 Highlight 清單！
    """)
    st.image("https://img.icons8.com/clouds/400/000000/opened-folder.png", width=250)
