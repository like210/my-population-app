import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 디자인(따뜻한 톤) 적용
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 인구 및 울산 고령화 심층 분석 데이터 앱",
    page_icon="📊",
    layout="wide"
)

# 커스텀 CSS: 배경색, 카드, 탭 디자인을 따뜻한 크림/베이지 톤으로 통합
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
    
    /* 안내 메세지 박스 톤 조정 */
    .stAlert {
        background-color: #FFFDF9;
        border: 1px solid #E6DFD5;
        border-radius: 10px;
    }
    
    /* 탭 스타일 강조 */
    button[data-baseweb="tab"] {
        font-size: 16px !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 대한민국 인구 분포 및 고령화 지도 종합 분석")
st.write("원하시는 분석 메뉴를 선택하여 읍·면·동 단위 심층 분석, 전국 고령화 단계구분도, 울산 행정동 지도 분석을 하나의 화면에서 확인해보세요.")

# -----------------------------------------------------------------------------
# 2. 데이터 및 GeoJSON 캐싱 로딩
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    csv_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(csv_url)
    
    # 가장 최신 연도 추출 (2026년)
    max_year = df['연도'].max()
    df_latest = df[df['연도'] == max_year].copy()
    
    # 컬럼 분류
    total_cols = [c for c in df_latest.columns if c.startswith('계_')]
    male_cols = [c for c in df_latest.columns if c.startswith('남_')]
    female_cols = [c for c in df_latest.columns if c.startswith('여_')]
    
    # 65세 이상 컬럼 분류
    elderly_cols = []
    for c in total_cols:
        age_str = c.replace('계_', '')
        if '이상' in age_str:
            elderly_cols.append(c)
        else:
            try:
                if int(age_str.replace('세', '')) >= 65:
                    elderly_cols.append(c)
            except ValueError:
                pass

    # 동네별 기본 집계
    df_latest['남인구'] = df_latest[male_cols].sum(axis=1)
    df_latest['여인구'] = df_latest[female_cols].sum(axis=1)
    df_latest['총인구'] = df_latest['남인구'] + df_latest['여인구']
    df_latest['전체인구_계'] = df_latest[total_cols].sum(axis=1)
    df_latest['고령인구_계'] = df_latest[elderly_cols].sum(axis=1)
    df_latest['고령화율'] = (df_latest['고령인구_계'] / df_latest['전체인구_계']) * 100
    
    df_latest['동네명_풀'] = df_latest['시도'] + " " + df_latest['시군구'] + " " + df_latest['동']
    
    # 행정동 코드(10자리 문자열) 정형화
    df_latest['코드_str'] = df_latest['코드'].astype(str).str.zfill(10)
    df_latest['sigungu_code'] = df_latest['코드_str'].str[:5]
    
    # 시군구 단위 합산 데이터
    sigungu_df = df_latest.groupby('sigungu_code', as_index=False).agg({
        '시도': 'first',
        '시군구': 'first',
        '전체인구_계': 'sum',
        '고령인구_계': 'sum'
    })
    sigungu_df['고령화율'] = (sigungu_df['고령인구_계'] / sigungu_df['전체인구_계']) * 100
    sigungu_df['시군구풀네임'] = sigungu_df['시도'] + ' ' + sigungu_df['시군구']
    
    return df_latest, sigungu_df, max_year, male_cols, female_cols

@st.cache_data
def load_geojson_sigungu():
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    return requests.get(url).json()

@st.cache_data
def load_geojson_ulsan():
    url = "https://raw.githubusercontent.com/raqoon886/Local_HangJeongDong/master/hangjeongdong_%EC%9A%B8%EC%82%B0%EA%B4%91%EC%97%AD%EC%8B%9C.geojson"
    return requests.get(url).json()

with st.spinner("최신 인구 데이터 및 전국/울산 지적 경계를 불러오는 중입니다..."):
    try:
        data, sigungu_df, latest_year, male_cols, female_cols = load_data()
        geojson_sigungu = load_geojson_sigungu()
        geojson_ulsan = load_geojson_ulsan()
        st.success(f"데이터 로드 완료! (기준 연도: **{latest_year}년**)")
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        st.stop()


# -----------------------------------------------------------------------------
# 3. 탭(Tab) 메뉴를 통한 화면 전환
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "🎯 1. 읍·면·동 인구 피라미드 & 세부 분석", 
    "🗺️ 2. 전국 시·군·구 고령화 단계구분도",
    "🏙️ 3. 울산 행정동 고령화 지도"
])


# =============================================================================
# [TAB 1] 읍·면·동 인구 분포 및 세부 심층 분석
# =============================================================================
with tab1:
    st.subheader("🎯 동네별 인구 피라미드 및 특성 진단")
    
    # 1) 동네 선택 박스
    selected_dong = st.selectbox(
        "분석할 동네(시도 + 시군구 + 읍면동)를 선택하세요:",
        options=data['동네명_풀'].unique(),
        index=0
    )
    
    target_row = data[data['동네명_풀'] == selected_dong].iloc[0]
    target_total_pop = target_row['총인구']
    
    # 나이별 인구 수집
    ages, pop_by_age = [], []
    elderly_pop, child_pop = 0, 0
    
    for col in male_cols:
        age_str = col.replace('남_', '')
        age_num = 100 if '이상' in age_str else int(age_str.replace('세', ''))
        
        m_val = target_row[f'남_{age_str}']
        f_val = target_row[f'여_{age_str}']
        sum_val = m_val + f_val
        
        ages.append(age_num)
        pop_by_age.append((age_num, sum_val, m_val, f_val, age_str))
        
        if age_num >= 65:
            elderly_pop += sum_val
        if age_num <= 14:
            child_pop += sum_val

    # 지표 계산
    total_age_sum = sum([age * count for age, count, _, _, _ in pop_by_age])
    avg_age = total_age_sum / target_total_pop if target_total_pop > 0 else 0
    aging_rate = (elderly_pop / target_total_pop) * 100 if target_total_pop > 0 else 0

    # 2) 지표 카드 3개
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("총인구", f"{target_total_pop:,.0f} 명")
    with c2:
        st.metric("평균연령", f"{avg_age:.1f} 세")
    with c3:
        label_text = "고령화율 ⚠️ (초고령)" if aging_rate >= 20.0 else "고령화율"
        st.metric(label_text, f"{aging_rate:.1f} %")
        
    if aging_rate >= 20.0:
        st.warning(f"⚠️ **{selected_dong}**은(는) 고령화율이 **{aging_rate:.1f}%**로 20%를 넘어 **초고령사회**에 해당합니다.")

    # 3) 인구 피라미드 차트
    pyramid_df = pd.DataFrame(pop_by_age, columns=['나이_숫자', '합계', '남성', '여성', '연령대'])
    fig_pyramid = go.Figure()
    
    fig_pyramid.add_trace(go.Bar(
        y=pyramid_df['연령대'], x=-pyramid_df['남성'], name='남성',
        orientation='h', marker=dict(color='#81B29A'),
        hoverinfo='text', hovertext=[f"남성 ({row['연령대']}): {row['남성']:,}명" for _, row in pyramid_df.iterrows()]
    ))
    fig_pyramid.add_trace(go.Bar(
        y=pyramid_df['연령대'], x=pyramid_df['여성'], name='여성',
        orientation='h', marker=dict(color='#E07A5F'),
        hoverinfo='text', hovertext=[f"여성 ({row['연령대']}): {row['여성']:,}명" for _, row in pyramid_df.iterrows()]
    ))
    
    max_val = max(pyramid_df['남성'].max(), pyramid_df['여성'].max())
    ticks = [int(-max_val), int(-max_val/2), 0, int(max_val/2), int(max_val)]
    tick_texts = [f"{abs(t):,}" for t in ticks]

    fig_pyramid.update_layout(
        title=f"<b>{selected_dong} 연령별 인구 피라미드</b>",
        barmode='relative', bargap=0.1,
        xaxis=dict(tickvals=ticks, ticktext=tick_texts, title="인구수 (명)", showgrid=True, gridcolor="#F0EAE1"),
        yaxis=dict(title="연령대", dtick=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFDF9", font=dict(color="#4A3E3D")
    )
    st.plotly_chart(fig_pyramid, use_container_width=True)

    # 4) 자동 진단 설명
    if child_pop > elderly_pop:
        status_text = f"💡 **{selected_dong}**은(는) 유소년(0~14세, {child_pop:,}명)이 어르신(65세 이상, {elderly_pop:,}명)보다 많아 **아이가 상대적으로 많은 젊은 동네**입니다."
    elif elderly_pop > child_pop:
        status_text = f"💡 **{selected_dong}**은(는) 어르신(65세 이상, {elderly_pop:,}명)이 유소년(0~14세, {child_pop:,}명)보다 많아 **어르신 비중이 높은 동네**입니다."
    else:
        status_text = f"💡 **{selected_dong}**은(는) 유소년 인구와 어르신 인구 비율이 비슷한 균형을 이루고 있습니다."
    st.info(status_text)

    # 5) 접이식으로 배치한 전체 인구 분포 그래프들
    with st.expander("🌐 전국 읍·면·동 인구 분포 시각화 (히스토그램, 상자그림, 성비 산점도 등) 펼치기"):
        # 히스토그램
        fig_hist = px.histogram(data, x="총인구", nbins=50, title="전국 읍·면·동 총인구 분포 (히스토그램)", color_discrete_sequence=["#E07A5F"])
        fig_hist.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFDF9")
        st.plotly_chart(fig_hist, use_container_width=True)
        
        # 상자그림
        fig_box = px.box(data, y="총인구", title="전국 읍·면·동 총인구 분포 (상자그림)", color_discrete_sequence=["#D8B168"], points="outliers")
        fig_box.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFDF9")
        st.plotly_chart(fig_box, use_container_width=True)
        
        # 성비 산점도
        fig_scatter = px.scatter(data, x="남인구", y="여인구", hover_name="동네명_풀", title="동네별 남성/여성 인구 성비 산점도", color_discrete_sequence=["#E07A5F"], opacity=0.6)
        max_val_sc = max(data['남인구'].max(), data['여인구'].max())
        fig_scatter.add_trace(go.Scatter(x=[0, max_val_sc], y=[0, max_val_sc], mode="lines", name="1:1 균형선", line=dict(color="#3D405B", dash="dash")))
        fig_scatter.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFDF9")
        st.plotly_chart(fig_scatter, use_container_width=True)


# =============================================================================
# [TAB 2] 전국 시·군·구 고령화 단계구분도
# =============================================================================
with tab2:
    st.subheader("🗺️ 전국 시·군·구 고령화 지도 (기준선 기반 시각화)")

    # 1) 고령화 요약 지표 카드
    mc1, mc2, mc3 = st.columns(3)
    avg_rate = sigungu_df['고령화율'].mean()
    max_row = sigungu_df.loc[sigungu_df['고령화율'].idxmax()]
    min_row = sigungu_df.loc[sigungu_df['고령화율'].idxmin()]

    with mc1:
        st.metric("전국 시군구 평균 고령화율", f"{avg_rate:.1f}%")
    with mc2:
        st.metric("최고 고령화 지역", f"{max_row['시군구풀네임']}", delta=f"{max_row['고령화율']:.1f}%")
    with mc3:
        st.metric("최저 고령화 지역", f"{min_row['시군구풀네임']}", delta=f"{min_row['고령화율']:.1f}%")

    st.markdown("---")

    # 2) 기준선 설정 슬라이더
    threshold = st.slider(
        "🎚️ 고령화율 기준선(%)을 선택하세요 (선택 기준 이상인 지역만 강조 표시됩니다):",
        min_value=10.0,
        max_value=50.0,
        value=30.0,
        step=1.0,
        key="tab2_slider"
    )

    # 3) 화면 구성: 지도(75%) vs 고령화율 상위 5곳 표(25%)
    col_map, col_table = st.columns([3, 1])

    with col_map:
        sigungu_map_df = sigungu_df.copy()
        label_over = f"{threshold:.0f}% 이상"
        label_under = f"{threshold:.0f}% 미만"
        
        sigungu_map_df['구분'] = sigungu_map_df['고령화율'].apply(
            lambda x: label_over if x >= threshold else label_under
        )

        fig_map = px.choropleth_mapbox(
            sigungu_map_df,
            geojson=geojson_sigungu,
            locations="sigungu_code",
            featureidkey="properties.코드",
            color="구분",
            color_discrete_map={
                label_over: "#E07A5F",
                label_under: "#D3D3D3"
            },
            category_orders={"구분": [label_over, label_under]},
            mapbox_style="white-bg",
            center={"lat": 35.8, "lon": 127.8},
            zoom=6.0,
            hover_name="시군구풀네임",
            hover_data={
                "sigungu_code": False,
                "구분": False,
                "고령화율": ":.1f}%",
                "전체인구_계": ":,명",
                "고령인구_계": ":,명"
            },
            labels={
                "고령화율": "고령화율 (%)",
                "전체인구_계": "전체 인구",
                "고령인구_계": "65세 이상 인구",
                "구분": "고령화율 범주"
            }
        )

        fig_map.update_layout(
            margin={"r": 0, "t": 20, "l": 0, "b": 0},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#4A3E3D"),
            legend=dict(
                title=dict(text=f"<b>고령화율 기준 ({threshold:.0f}%)</b>"),
                x=0.02,
                y=0.98,
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="#E6DFD5",
                borderwidth=1
            )
        )
        fig_map.update_traces(marker_line_width=0.5, marker_line_color="#888888")

        st.plotly_chart(fig_map, use_container_width=True)

    with col_table:
        st.markdown(f"### 🏆 고령화율 TOP 5")
        st.write("전국에서 고령화 비율이 가장 높은 시·군·구 5곳입니다.")
        
        top5_df = sigungu_df.sort_values(by='고령화율', ascending=False).head(5)[
            ['시군구풀네임', '고령화율', '전체인구_계']
        ].copy()
        
        top5_df.columns = ['지역', '고령화율(%)', '전체인구(명)']
        top5_df.reset_index(drop=True, inplace=True)
        top5_df.index = top5_df.index + 1
        
        st.dataframe(
            top5_df.style.format({
                '고령화율(%)': '{:.1f}%',
                '전체인구(명)': '{:,.0f}'
            }),
            use_container_width=True
        )


# =============================================================================
# [TAB 3] 울산광역시 행정동 고령화 지도
# =============================================================================
with tab3:
    st.subheader("🏙️ 울산광역시 행정동별 고령화 단계구분도 (2026년 기준)")
    st.write("울산광역시 내 읍·면·동(10자리 adm_cd2 코드) 기준 고령화율(%)을 시각화한 지도입니다.")

    # 1) 울산 광역시 데이터 필터링 (시도 == '울산광역시')
    ulsan_df = data[data['시도'] == '울산광역시'].copy()
    
    # GeoJSON에 맞춰 adm_nm 생성 및 코드 세팅
    ulsan_df['adm_cd2'] = ulsan_df['코드_str']
    ulsan_df['adm_nm'] = ulsan_df['시도'] + " " + ulsan_df['시군구'] + " " + ulsan_df['동']

    # 2) 요약 지표 카드 3개
    uc1, uc2, uc3 = st.columns(3)
    ulsan_avg_rate = (ulsan_df['고령인구_계'].sum() / ulsan_df['전체인구_계'].sum()) * 100
    ulsan_max_row = ulsan_df.loc[ulsan_df['고령화율'].idxmax()]
    ulsan_min_row = ulsan_df.loc[ulsan_df['고령화율'].idxmin()]

    with uc1:
        st.metric("울산광역시 평균 고령화율", f"{ulsan_avg_rate:.1f}%")
    with uc2:
        st.metric("울산 최고 고령화 동네", f"{ulsan_max_row['시군구']} {ulsan_max_row['동']}", delta=f"{ulsan_max_row['고령화율']:.1f}%")
    with uc3:
        st.metric("울산 최저 고령화 동네", f"{ulsan_min_row['시군구']} {ulsan_min_row['동']}", delta=f"{ulsan_min_row['고령화율']:.1f}%")

    st.markdown("---")

    # 3) 울산 지도 (Plotly Choropleth Mapbox)
    fig_ulsan = px.choropleth_mapbox(
        ulsan_df,
        geojson=geojson_ulsan,
        locations="adm_cd2",              # 10자리 코드
        featureidkey="properties.adm_cd2", # GeoJSON의 'adm_cd2' 속성과 매핑
        color="고령화율",
        color_continuous_scale="YlOrRd",   # 고령화율이 높을수록 진한 색상
        range_color=(10, 35),
        mapbox_style="white-bg",
        center={"lat": 35.5384, "lon": 129.3114}, # 울산 중심 좌표
        zoom=9.5,
        hover_name="adm_nm",              # 마우스 올렸을 때 행정동 풀네임 표시
        hover_data={
            "adm_cd2": False,
            "고령화율": ":.1f}%",
            "전체인구_계": ":,명",
            "고령인구_계": ":,명"
        },
        labels={
            "고령화율": "고령화율 (%)",
            "전체인구_계": "전체 인구",
            "고령인구_계": "65세 이상 인구"
        }
    )

    fig_ulsan.update_layout(
        margin={"r": 0, "t": 20, "l": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#4A3E3D"),
        coloraxis_colorbar=dict(
            title="고령화율 (%)",
            ticksuffix="%",
            thickness=15,
            len=0.8
        )
    )
    fig_ulsan.update_traces(marker_line_width=0.6, marker_line_color="#666666")

    st.plotly_chart(fig_ulsan, use_container_width=True)
