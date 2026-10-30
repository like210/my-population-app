import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 디자인(따뜻한 톤) 적용
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="읍면동 인구 퍼짐(분포) 및 특징 확인하기",
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
    
    /* 카드/경계선 톤 조정 */
    .stAlert {
        background-color: #FFFDF9;
        border: 1px solid #E6DFD5;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 읍·면·동 인구 분포 및 성비·지역 차이 시각화")
st.write("전국 읍·면·동 인구 데이터의 분포(퍼짐)와 지역별 규모, 남녀 성비 편차를 한눈에 확인하는 앱입니다.")

# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 전처리 (캐싱 적용으로 속도 최적화)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 저장소 URL 정의 (gzip 압축된 CSV)
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # pandas로 URL에서 직접 CSV 데이터 읽어오기
    df = pd.read_csv(url)
    
    # 1) 가장 최신 연도 데이터만 추출
    max_year = df['연도'].max()
    df_latest = df[df['연도'] == max_year].copy()
    
    # 2) '남_'으로 시작하는 열과 '여_'로 시작하는 열 구하기 및 총인구 계산
    male_cols = [c for c in df_latest.columns if c.startswith('남_')]
    female_cols = [c for c in df_latest.columns if c.startswith('여_')]
    
    df_latest['남인구'] = df_latest[male_cols].sum(axis=1)
    df_latest['여인구'] = df_latest[female_cols].sum(axis=1)
    df_latest['총인구'] = df_latest['남인구'] + df_latest['여인구']
    
    return df_latest, max_year

# 데이터 로딩
with st.spinner("최신 인구 데이터를 불러오는 중입니다..."):
    try:
        data, latest_year = load_data()
        st.success(f"기준 연도: **{latest_year}년** (총 {len(data):,}개 읍·면·동 데이터)")
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        st.stop()


# -----------------------------------------------------------------------------
# 1) 총인구 describe() 결과 표
# -----------------------------------------------------------------------------
st.subheader("1️⃣ 총인구 요약 통계 (describe)")
st.write("총인구 데이터의 평균, 표준편차, 사분위수 등 수치적 '퍼짐'을 보여줍니다.")

desc = data[['총인구']].describe()
desc.index = ['개수(count)', '평균(mean)', '표준편차(std)', '최소값(min)', 
              '25%(1사분위수)', '중앙값(50%)', '75%(3사분위수)', '최대값(max)']

st.dataframe(desc.style.format("{:,.0f}"), use_container_width=True)


# -----------------------------------------------------------------------------
# 2) 총인구 히스토그램 (Plotly)
# -----------------------------------------------------------------------------
st.subheader("2️⃣ 총인구 히스토그램 (Histogram)")
st.write("인구 구간별로 읍·면·동이 몇 개씩 속해있는지 나타낸 빈도 그래프입니다.")

fig_hist = px.histogram(
    data,
    x="총인구",
    nbins=50,
    title="읍·면·동 총인구 분포 (히스토그램)",
    labels={"총인구": "총인구 (명)", "count": "동네(행) 개수"},
    color_discrete_sequence=["#E07A5F"]  # 따뜻한 코랄 주황
)

fig_hist.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#FFFDF9",
    xaxis_title="총인구 (명)",
    yaxis_title="동네 수 (개)",
    xaxis=dict(showgrid=True, gridcolor="#F0EAE1"),
    yaxis=dict(showgrid=True, gridcolor="#F0EAE1"),
    font=dict(color="#4A3E3D")
)

st.plotly_chart(fig_hist, use_container_width=True)


# -----------------------------------------------------------------------------
# 3) 총인구 상자그림 (Plotly)
# -----------------------------------------------------------------------------
st.subheader("3️⃣ 총인구 상자그림 (Box Plot)")
st.write("중앙값과 사분위수 범위를 상자로 표현하며, 인구가 유독 많은 동네(이상치)를 직관적으로 파악할 수 있습니다.")

fig_box = px.box(
    data,
    y="총인구",
    title="읍·면·동 총인구 분포 (상자그림)",
    labels={"총인구": "총인구 (명)"},
    color_discrete_sequence=["#D8B168"],  # 따뜻한 샌드 노랑
    points="outliers"
)

fig_box.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#FFFDF9",
    yaxis_title="총인구 (명)",
    yaxis=dict(showgrid=True, gridcolor="#F0EAE1"),
    font=dict(color="#4A3E3D")
)

st.plotly_chart(fig_box, use_container_width=True)


# -----------------------------------------------------------------------------
# 4) [신규] 시도별 총인구 막대그래프 (Bar Chart)
# -----------------------------------------------------------------------------
st.subheader("4️⃣ 시도별 총인구 비교 (막대그래프)")
st.write("개별 동네 단위를 넘어 **광역 지자체(시·도) 단위로 인구를 합산**하여 보기 위한 그래프입니다.")
st.write("수도권(경기·서울)과 비수도권 지역 간의 압도적인 인구 규모 격차를 한눈에 확인할 수 있습니다.")

# 시도별 인구 합산 후 내림차순 정렬
sido_pop = data.groupby('시도')['총인구'].sum().reset_index()
sido_pop = sido_pop.sort_values(by='총인구', ascending=False)

fig_sido = px.bar(
    sido_pop,
    x="시도",
    y="총인구",
    title="시·도별 총인구 규모 (내림차순)",
    labels={"시도": "시·도", "총인구": "합산 총인구 (명)"},
    color_discrete_sequence=["#81B29A"],  # 따뜻한 세이지 그린 톤
    text_auto=',.0f'  # 막대 위에 값 표시
)

fig_sido.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#FFFDF9",
    xaxis_title="시·도",
    yaxis_title="합산 인구수 (명)",
    xaxis=dict(showgrid=False, color="#4A3E3D"),
    yaxis=dict(showgrid=True, gridcolor="#F0EAE1", color="#4A3E3D"),
    font=dict(color="#4A3E3D")
)

# 막대 위 텍스트 위치 조절
fig_sido.update_traces(textposition='outside')

st.plotly_chart(fig_sido, use_container_width=True)


# -----------------------------------------------------------------------------
# 5) [신규] 동네별 남인구 vs 여인구 산점도 (Scatter Plot)
# -----------------------------------------------------------------------------
st.subheader("5️⃣ 동네별 남인구 vs 여인구 성비 (산점도)")
st.write("단순 총인구 표만 봐서는 놓치기 쉬운 **동네별 남녀 인구 비율(성비 편차)**을 확인하는 그래프입니다.")
st.write("대각선 기준선(1:1 균형선)에서 위나 아래로 멀어질수록 특정 성별의 비중이 쏠려있는 동네임을 알 수 있습니다.")

# 툴팁에 동네 이름(시군구+동)을 보여주기 위한 컬럼 생성
data['동네명'] = data['시군구'] + " " + data['동']

fig_scatter = px.scatter(
    data,
    x="남인구",
    y="여인구",
    hover_name="동네명",
    hover_data=["시도", "총인구"],
    title="동네(읍·면·동)별 남성/여성 인구 분포",
    labels={"남인구": "남성 인구 (명)", "여인구": "여성 인구 (명)"},
    opacity=0.6,
    color_discrete_sequence=["#E07A5F"]
)

# 남녀 1:1 완벽 균형선(참조 대각선) 추가
max_val = max(data['남인구'].max(), data['여인구'].max())
fig_scatter.add_trace(
    go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode="lines",
        name="1:1 남녀 균형선",
        line=dict(color="#3D405B", dash="dash", width=1.5)
    )
)

fig_scatter.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#FFFDF9",
    xaxis_title="남성 인구 (명)",
    yaxis_title="여성 인구 (명)",
    xaxis=dict(showgrid=True, gridcolor="#F0EAE1"),
    yaxis=dict(showgrid=True, gridcolor="#F0EAE1"),
    font=dict(color="#4A3E3D")
)

st.plotly_chart(fig_scatter, use_container_width=True)
