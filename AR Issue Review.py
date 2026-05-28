import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

# 1. 網頁基礎設定 (寬螢幕模式與科技感主題)
st.set_page_config(
    page_title="美光專案動態議題追蹤大盤",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 系統自訂樣式 CSS
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
    .overdue-box {
        border-left: 6px solid #cc0000;
        background-color: #fff0f0;
        padding: 15px;
        margin-bottom: 12px;
        border-radius: 6px;
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
    
    # 【未解天數清洗】
    df['未解天數'] = pd.to_numeric(df['未解天數'], errors='coerce').fillna(0).astype(int)
    
    # 建立客戶關注標籤
    def classify_tag(summary):
        s_str = str(summary)
        if any(keyword in s_str for keyword in ['Top 5', 'Top項目', '新 Top', '關鍵']):
            return "🔥 Top 核心議題"
        return "標準一般議題"
    
    df['議題分類'] = df['Summary'].apply(classify_tag)
    
    # 風險監控自動 Highlight 邏輯
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
        
        # 側邊欄：動態篩選器
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 步驟 2：篩選大盤資料")
        
        # 原有基本篩選
        all_priorities = sorted(df['Priority'].dropna().unique().tolist())
        selected_priorities = st.sidebar.multiselect("議題優先級 (Priority)", all_priorities, default=all_priorities)

        all_statuses = df['Status'].dropna().unique().tolist()
        selected_statuses = st.sidebar.multiselect("目前處理狀態 (Status)", all_statuses, default=all_statuses)

        all_tags = df['議題分類'].unique().tolist()
        selected_tags = st.sidebar.multiselect("群組分類", all_tags, default=all_tags)

        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 步驟 3：進階條件篩選")

        # 🌟 功能 1：有無超過 Due date 篩選
        overdue_filter = st.sidebar.radio(
            "1. 有無超過 Due date",
            options=["全部", "🚨 已逾期 (Overdue)", "📅 未逾期/未定時效"],
            index=0,
            help="已逾期定義：到期日小於基準日且尚未結案"
        )

        # 🌟 功能 2：時間區間 (依據 Created 建立日期)
        st.sidebar.markdown("**2. 立案時間區間 (Created Date)**")
        min_date = df['Created'].min().date() if df['Created'].notnull().any() else date(2025, 1, 1)
        max_date = df['Created'].max().date() if df['Created'].notnull().any() else date.today()
        
        start_date = st.sidebar.date_input("開始日期", min_date, min_value=min_date, max_value=max_date)
        end_date = st.sidebar.date_input("結束日期", max_date, min_value=min_date, max_value=max_date)

        # 🌟 功能 3：有無異常篩選
        risk_filter = st.sidebar.radio(
            "3. 異常風險狀態",
            options=["全部", "⚠️ 僅看異常警示項", "✅ 僅看正常追蹤項"],
            index=0,
            help="異常包含：已逾期、未指派人員、未解天數>45天之項目"
        )

        # 【執行多重動態篩選邏輯】
        # A. 基本篩選
        filtered_df = df[
            (df['Priority'].isin(selected_priorities)) & 
            (df['Status'].isin(selected_statuses)) &
            (df['議題分類'].isin(selected_tags))
        ].copy()

        # B. 執行時間區間篩選 (Created Date)
        if filtered_df['Created'].notnull().any():
            filtered_df = filtered_df[
                (filtered_df['Created'].dt.date >= start_date) & 
                (filtered_df['Created'].dt.date <= end_date)
            ]

        # C. 執行有無超過 Due date 篩選
        if overdue_filter == "🚨 已逾期 (Overdue)":
            filtered_df = filtered_df[
                (filtered_df['Due date'].notnull()) & 
                (filtered_df['Due date'] < data_base_date) & 
                (~filtered_df['Status'].isin(['Done', 'Closed']))
            ]
        elif overdue_filter == "📅 未逾期/未定時效":
            # 未過期狀況：沒有填 Due date，或者是 Due date 還沒到，或者已經 Done/Closed 了
            filtered_df = filtered_df[
                (filtered_df['Due date'].isna()) | 
                (filtered_df['Due date'] >= data_base_date) | 
                (filtered_df['Status'].isin(['Done', 'Closed']))
            ]

        # D. 執行有無異常篩選
        if risk_filter == "⚠️ 僅看異常警示項":
            filtered_df = filtered_df[filtered_df['風險監控'] != "✅ 正常追蹤中"]
        elif risk_filter == "✅ 僅看正常追蹤項":
            filtered_df = filtered_df[filtered_df['風險監控'] == "✅ 正常追蹤中"]


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
            active_issues = filtered_df[filtered_df['未解天數'] > 0]
            avg_days = int(active_issues['未解天數'].mean()) if len(active_issues) > 0 else 0
            st.metric(label="⏳ 處理中議題平均未解天數", value=f"{avg_days} 天")
        with col4:
            total_overdue = len(filtered_df[
                (filtered_df['Due date'].notnull()) & 
                (filtered_df['Due date'] < data_base_date) & 
                (~filtered_df['Status'].isin(['Done', 'Closed']))
            ])
            st.metric(label="🚨 篩選範圍內逾期項", value=f"{total_overdue} 項")

        st.markdown("---")

        # 7. 雙圖表展示
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.subheader("📌 議題生命週期：未解天數排行")
            
            st.markdown("""
            **🎨 燈號顏色異常定義說明：**
            * 🔴 <span style='color:#ff4d4d; font-weight:bold;'>深紅燈 (>45天)</span>：高風險極具急迫性，嚴重卡關。
            * 🟡 <span style='color:#ffaa00; font-weight:bold;'>黃燈 (21-45天)</span>：需注意並加強收斂，已出現滯留現象。
            * 🔵 <span style='color:#4da6ff; font-weight:bold;'>藍燈 (≤20天)</span>：正常時效內，進度持續追蹤中。
            """, unsafe_allow_html=True)
            
            chart_df = filtered_df[filtered_df['未解天數'] > 0].copy()
            
            if not chart_df.empty:
                sort_df = chart_df.sort_values(by='未解天數', ascending=True)
                
                if 'Issue key' in sort_df.columns:
                    sort_df['Unique_ID'] = sort_df.apply(lambda r: f"{str(r['Issue key'])}##{str(r['Summary'])}", axis=1)
                else:
                    sort_df['Unique_ID'] = [f"Idx_{i}##{str(text)}" for i, text in enumerate(sort_df['Summary'])]
                
                sort_df['Display_Label'] = sort_df['Summary'].apply(lambda x: str(x)[:22] + "...")
                colors = ['#ff4d4d' if x > 45 else ('#ffaa00' if x > 20 else '#4da6ff') for x in sort_df['未解天數']]
                
                fig_days = go.Figure(go.Bar(
                    x=sort_df['未解天數'],
                    y=sort_df['Unique_ID'], 
                    orientation='h',
                    marker_color=colors,
                    text=sort_df['未解天數'].apply(lambda x: f" {x}天"),
                    textposition='outside',
                    hovertext=sort_df['Summary']
                ))
                
                fig_days.update_yaxes(
                    type='category',
                    tickvals=sort_df['Unique_ID'],
                    ticktext=sort_df['Display_Label']
                )
                
                fig_days.update_layout(
                    height=max(400, len(sort_df) * 25), 
                    margin=dict(l=10, r=50, t=20, b=30), 
                    yaxis=dict(autorange="reversed"),
                    xaxis_title="未處理/未解天數 (Days)"
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

        # 8. 專案特快報表：Jira 承諾日期已逾期項目
        st.subheader("🚨 專案核心追蹤：承諾到期日 (Due date) 已逾期報表")
        
        overdue_df = filtered_df[
            (filtered_df['Due date'].notnull()) & 
            (filtered_df['Due date'] < data_base_date) & 
            (~filtered_df['Status'].isin(['Done', 'Closed']))
        ].copy()

        if not overdue_df.empty:
            overdue_df['逾期天數'] = (data_base_date - overdue_df['Due date']).dt.days
            overdue_df = overdue_df.sort_values(by='逾期天數', ascending=False)
            
            st.markdown(f"⚠️ 以下共列出 **{len(overdue_df)}** 項已超過預定交付日卻未完結的異常：")
            
            for idx, row in overdue_df.iterrows():
                issue_key_str = f"【{row['Issue key']}】" if 'Issue key' in row and pd.notnull(row['Issue key']) else ""
                st.markdown(f"""
                <div class="overdue-box">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 15px; color: #cc0000; font-weight: bold;">
                            ⏳ 已延誤 {row['逾期天數']} 天
                        </span>
                        <span style="background-color: #cc0000; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">
                            {row['Priority']}
                        </span>
                    </div>
                    <div style="margin-top: 8px; font-size: 15px; color: #111;">
                        <strong>{issue_key_str}{row['Summary']}</strong>
                    </div>
                    <div style="margin-top: 8px; font-size: 13px; color: #555;">
                        👤 負責人：<b style="color:#111;">{row['Assignee'] if pd.notnull(row['Assignee']) else '❌ 尚未分派負責 R&D'}</b> ｜ 
                        ⚙️ 目前狀態：<b>{row['Status']}</b> ｜ 
                        📅 原定承諾日：<span style="color:#cc0000; font-weight:bold;">{row['Due date'].strftime('%Y/%m/%d')}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("🎉 太棒了！當前篩選範圍內沒有任何已逾期卻未完結的專案項目。")

        st.markdown("---")

        # 9. 異常 Highlight 區塊 (原有的紅燈風險監控)
        st.subheader("⚠️ 系統自動掃描：其他異常與紅燈風險項目 (Risk Highlighting)")
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

        # 10. 明細資料表格
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
