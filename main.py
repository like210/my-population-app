import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 디자인(따뜻한 톤) 적용
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 읍면동 인구 분포 및 동네별 피라미드 분석",
    page_icon="📊",
    layout="centered"
)

# 커스텀 CSS: 배경색과 카드 형태를 따뜻한 크림/베이지 톤으로 꾸밈
st.markdown("""
    <style>
    /* 전체 앱 배경색 (크림 톤) */
    .stApp {
        background-color: #FAF8F5;
    }
    
    /* 헤더 및 본문 글자 색상 지정 */
    h1, h2, h3 {
        color: #4A3E3D !important;
    }
    p, span, div {
        color: #5C524C;
    }
    
    /* 지표 카드(Metric) 커스텀 스타일 */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #F0EAE1;
    }
    
    /* 경고/안내 박스 스타일 */
    .stAlert {
        background-color: #FFFDF9;
        border: 1px solid #E6DFD5;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 읍·면·동 인구 분포 및 세부 심층 분석")
st.write("전국 읍·면·동의 인구 퍼짐(분포)을 파악하고, 특정 동네의 인구 피라미드와 고령화 지표를 분석합니다.")

# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 전처리 (캐싱 적용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(url)
    
    # 가장 최신 연도 추출
    max_year = df['연도'].max()
    df_latest = df[df['연도'] == max_year].copy()
    
    # 연령별 열 추출
    male_cols = [c for c in df_latest.columns if c.startswith('남_')]
    female_cols = [c for c in df_latest.columns if c.startswith('여_')]
    
    # 1) 동네별 남/여/총인구 계산
    df_latest['남인구'] = df_latest[male_cols].sum(axis=1)
    df_latest['여인구'] = df_latest[female_cols].sum(axis=1)
    df_latest['총인구'] = df_latest['남인구'] + df_latest['여인구']
    
    # 검색/식별용 전체 동네 이름 생성
    df_latest['동네명_풀'] = df_latest['시도'] + " " + df_latest['시군구'] + " " + df_latest['동']
    
    return df_latest, max_year, male_cols, female_cols

with st.spinner("최신 인구 데이터를 불러오는 중입니다..."):
    try:
        data, latest_year, male_cols, female_cols = load_data()
        st.success(f"기준 연도: **{latest_year}년** (총 {len(data):,}개 읍·면·동 데이터)")
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        st.stop()


# -----------------------------------------------------------------------------
# 3. [신규] 특정 동네 선택 및 지표 카드 / 인구 피라미드 섹션
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🎯 관심 동네 세부 분석 (지표 카드 & 인구 피라미드)")

# 동네 선택 셀렉트박스 (기본값: 첫 번째 동네)
selected_dong = st.selectbox(
    "분석할 동네(시도 + 시군구 + 읍면동)를 선택하세요:",
    options=data['동네명_풀'].unique(),
    index=0
)

# 선택된 동네 데이터 추출
target_row = data[data['동네명_풀'] == selected_dong].iloc[0]

# --- 지표 계산 logic ---
# A. 총인구
target_total_pop = target_row['총인구']

# B. 연령별 인구수 및 계산용 데이터 정리
# '남_0세', '여_0세' 등의 컬럼에서 연령(숫자) 추출
ages = []
pop_by_age = []
elderly_pop = 0   # 65세 이상 인구합
child_pop = 0     # 0~14세 아동 인구합

for col in male_cols:
    age_str = col.replace('남_', '')
    if '이상' in age_str:
        age_num = 100
    else:
        age_num = int(age_str.replace('세', ''))
    
    m_val = target_row[f'남_{age_str}']
    f_val = target_row[f'여_{age_str}']
    sum_val = m_val + f_val
    
    ages.append(age_num)
    pop_by_age.append((age_num, sum_val, m_val, f_val, age_str))
    
    # 65세 이상 및 14세 이하 집계
    if age_num >= 65:
        elderly_pop += sum_val
    if age_num <= 14:
        child_pop += sum_val

# C. 평균연령 계산: (각 나이 * 해당 나이 인구수)의 합 / 총인구
total_age_sum = sum([age * count for age, count, _, _, _ in pop_by_age])
avg_age = total_age_sum / target_total_pop if target_total_pop > 0 else 0

# D. 고령화율(%) 계산: (65세 이상 인구 / 총인구) * 100
aging_rate = (elderly_pop / target_total_pop) * 100 if target_total_pop > 0 else 0


# --- 상단 지표 카드 3개 나란히 표시 ---
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="총인구",
        value=f"{target_total_pop:,.0f} 명"
    )

with col2:
    st.metric(
        label="평균연령",
        value=f"{avg_age:.1f} 세"
    )

with col3:
    # 고령화율이 20% 이상(초고령사회 기준)이면 주의 표시(⚠️) 붙이기
    if aging_rate >= 20.0:
        label_text = "고령화율 ⚠️ (초고령)"
    else:
        label_text = "고령화율"
        
    st.metric(
        label=label_text,
        value=f"{aging_rate:.1f} %"
    )

# 고령화율 20% 초과 시 안내 메시지 카드 출력
if aging_rate >= 20.0:
    st.warning(f"⚠️ **{selected_dong}**은(는) 고령화율이 **{aging_rate:.1f}%**로 20%를 넘어 **초고령사회**에 해당합니다.")


# --- 인구 피라미드 그래프 생성 (Plotly) ---
pyramid_df = pd.DataFrame(pop_by_age, columns=['나이_숫자', '합계', '남성', '여성', '연령대'])

fig_pyramid = go.Figure()

# 남성 인구 (왼쪽 방향으로 표현하기 위해 음수로 변환)
fig_pyramid.add_trace(go.Bar(
    y=pyramid_df['연령대'],
    x=-pyramid_df['남성'],
    name='남성',
    orientation='h',
    marker=dict(color='#81B29A'),
    hoverinfo='text',
    hovertext=[f"남성 ({row['연령대']}): {row['남성']:,}명" for _, row in pyramid_df.iterrows()]
))

# 여성 인구 (오른쪽 방향)
fig_pyramid.add_trace(go.Bar(
    y=pyramid_df['연령대'],
    x=pyramid_df['여성'],
    name='여성',
    orientation='h',
    marker=dict(color='#E07A5F'),
    hoverinfo='text',
    hovertext=[f"여성 ({row['연령대']}): {row['여성']:,}명" for _, row in pyramid_df.iterrows()]
))

# X축 눈금을 양수로만 보이도록 가공
max_val = max(pyramid_df['남성'].max(), pyramid_df['여성'].max())
ticks = [int(-max_val), int(-max_val/2), 0, int(max_val/2), int(max_val)]
tick_texts = [f"{abs(t):,}" for t in ticks]

fig_pyramid.update_layout(
    title=f"<b>{selected_dong} 연령별 인구 피라미드</b>",
    barmode='relative',
    bargap=0.1,
    xaxis=dict(
        tickvals=ticks,
        ticktext=tick_texts,
        title="인구수 (명)",
        showgrid=True,
        gridcolor="#F0EAE1"
    ),
    yaxis=dict(title="연령대", dtick=10),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#FFFDF9",
    font=dict(color="#4A3E3D"),
    legend=dict(x=0.8, y=1.1, orientation="h")
)

st.plotly_chart(fig_pyramid, use_container_width=True)


# --- 피라미드 아래 자동 한 줄 설명 (아동 vs 어르신 비중 판별) ---
if child_pop > elderly_pop:
    status_text = f"💡 **{selected_dong}**은(는) 유소년(0~14세, {child_pop:,}명)이 어르신(65세 이상, {elderly_pop:,}명)보다 많아 **아이가 상대적으로 많은 젊은 동네**입니다."
elif elderly_pop > child_pop:
    status_text = f"💡 **{selected_dong}**은(는) 어르신(65세 이상, {elderly_pop:,}명)이 유소년(0~14세, {child_pop:,}명)보다 많아 **어르신 비중이 높은 동네**입니다."
else:
    status_text = f"💡 **{selected_dong}**은(는) 유소년 인구와 어르신 인구 비율이 비슷한 균형을 이루고 있습니다."

st.info(status_text)


# -----------------------------------------------------------------------------
# 4. 전체 데이터 분포 시각화 (기존 5개 그래프)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🌐 전국 읍·면·동 인구 분포 (전체 비교)")

# 1) 요약 통계 표
with st.expander("1️⃣ 전국 총인구 요약 통계 (describe) 보기"):
    desc = data[['총인구']].describe()
    desc.index = ['개수(count)', '평균(mean)', '표준편차(std)', '최소값(min)', 
                  '25%(1사분위수)', '중앙값(50%)', '75%(3사분위수)', '최대값(max)']
    st.dataframe(desc.style.format("{:,.0f}"), use_container_width=True)

# 2) 히스토그램
fig_hist = px.histogram(
    data, x="총인구", nbins=50,
    title="전국 읍·면·동 총인구 분포 (히스토그램)",
    labels={"총인구": "총인구 (명)", "count": "동네 수"},
    color_discrete_sequence=["#E07A5F"]
)
fig_hist.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFDF9", font=dict(color="#4A3E3D"))
st.plotly_chart(fig_hist, use_container_width=True)

# 3) 상자그림
fig_box = px.box(
    data, y="총인구",
    title="전국 읍·면·동 총인구 분포 (상자그림)",
    labels={"총인구": "총인구 (명)"},
    color_discrete_sequence=["#D8B168"],
    points="outliers"
)
fig_box.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFDF9", font=dict(color="#4A3E3D"))
st.plotly_chart(fig_box, use_container_width=True)

# 4) 시도별 합산 막대그래프
sido_pop = data.groupby('시도')['총인구'].sum().reset_index().sort_values(by='총인구', ascending=False)
fig_sido = px.bar(
    sido_pop, x="시도", y="총인구",
    title="시·도별 합산 총인구 (수도권 vs 지방 격차 확인)",
    labels={"시도": "시·도", "총인구": "합산 인구수 (명)"},
    color_discrete_sequence=["#81B29A"],
    text_auto=',.0f'
)
fig_sido.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFDF9", font=dict(color="#4A3E3D"))
fig_sido.update_traces(textposition='outside')
st.plotly_chart(fig_sido, use_container_width=True)

# 5) 남녀 산점도
fig_scatter = px.scatter(
    data, x="남인구", y="여인구",
    hover_name="동네명_풀",
    hover_data=["총인구"],
    title="동네별 남성/여성 인구 성비 산점도",
    labels={"남인구": "남성 인구 (명)", "여인구": "여성 인구 (명)"},
    opacity=0.6,
    color_discrete_sequence=["#E07A5F"]
)
max_val_sc = max(data['남인구'].max(), data['여인구'].max())
fig_scatter.add_trace(go.Scatter(x=[0, max_val_sc], y=[0, max_val_sc], mode="lines", name="1:1 균형선", line=dict(color="#3D405B", dash="dash")))
fig_scatter.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFDF9", font=dict(color="#4A3E3D"))
st.plotly_chart(fig_scatter, use_container_width=True)
