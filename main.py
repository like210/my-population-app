import json
import numpy as np
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
st.write("원하시는 분석 메뉴를 선택하여 읍·면·동 심층 분석, 전국 고령화 지도, 울산 행정동 지도, 쌍둥이 동네 찾기를 하나의 화면에서 확인해보세요.")

# -----------------------------------------------------------------------------
# 2. 데이터 및 GeoJSON 캐싱 로딩
# -----------------------------------------------------------------------------
@st.cache_data
def load_all_years_data():
    # 저장소에서 압축된 CSV 전체 데이터를 판다스로 로드
    csv_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(csv_url)
    
    # 성별 및 전체 계 열 추출
    total_cols = [c for c in df.columns if c.startswith('계_')]
    male_cols = [c for c in df.columns if c.startswith('남_')]
    female_cols = [c for c in df.columns if c.startswith('여_')]
    
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

    # 총인구 및 고령인구 계산
    df['남인구'] = df[male_cols].sum(axis=1)
    df['여인구'] = df[female_cols].sum(axis=1)
    df['총인구'] = df['남인구'] + df['여인구']
    df['전체인구_계'] = df[total_cols].sum(axis=1)
    df['고령인구_계'] = df[elderly_cols].sum(axis=1)
    df['고령화율'] = (df['고령인구_계'] / df['전체인구_계']) * 100
    
    # 코드 정형화 (10자리 및 시군구 5자리)
    df['코드_str'] = df['코드'].astype(str).str.zfill(10)
    df['sigungu_code'] = df['코드_str'].str[:5]
    
    # 최신 연도(2026년) 데이터 기반 시군구 집계 (Tab 2용)
    max_year = df['연도'].max()
    df_latest_sigungu = df[df['연도'] == max_year].copy()
    
    sigungu_df = df_latest_sigungu.groupby('sigungu_code', as_index=False).agg({
        '시도': 'first',
        '시군구': 'first',
        '전체인구_계': 'sum',
        '고령인구_계': 'sum'
    })
    sigungu_df['고령화율'] = (sigungu_df['고령인구_계'] / sigungu_df['전체인구_계']) * 100
    sigungu_df['시군구풀네임'] = sigungu_df['시도'] + ' ' + sigungu_df['시군구']
    
    return df, sigungu_df, male_cols, female_cols, total_cols

@st.cache_data
def load_latest_data_for_twin(total_cols):
    # Tab 4(쌍둥이 동네 찾기)를 위한 최신 연도 데이터 및 비율 계산
    csv_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(csv_url)
    
    # 1) 가장 최신 연도만 추출
    max_year = df['연도'].max()
    df_twin = df[df['연도'] == max_year].copy()
    
    # 2) 행 번호를 0부터 다시 인덱싱 (어긋남 방지)
    df_twin.reset_index(drop=True, inplace=True)
    
    # 3) 동네 풀네임 식별 컬럼 생성
    df_twin['동네명_풀'] = df_twin['시도'] + ' ' + df_twin['시군구'] + ' ' + df_twin['동']
    
    # 4) 동네별 총인구 및 연령별 인구 비율 계산 ('계_' 열 사용)
    df_twin['총인구_합'] = df_twin[total_cols].sum(axis=1)
    
    # 각 '계_n세' 열을 총인구로 나누어 비율(0~1)로 변환
    ratio_df = df_twin[total_cols].div(df_twin['총인구_합'], axis=0).fillna(0)
    
    return df_twin, ratio_df

@st.cache_data
def load_geojson_sigungu():
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    return requests.get(url).json()

@st.cache_data
def load_geojson_ulsan():
    url = "https://raw.githubusercontent.com/raqoon886/Local_HangJeongDong/master/hangjeongdong_%EC%9A%B8%EC%82%B0%EA%B4%91%EC%97%AD%EC%8B%9C.geojson"
    return requests.get(url).json()

with st.spinner("전체 인구 데이터 및 지적 경계를 불러오는 중입니다..."):
    try:
        data_all, sigungu_df, male_cols, female_cols, total_cols = load_all_years_data()
        df_twin, ratio_df = load_latest_data_for_twin(total_cols)
        geojson_sigungu = load_geojson_sigungu()
        geojson_ulsan = load_geojson_ulsan()
        st.success("데이터 로드 완료!")
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        st.stop()


# -----------------------------------------------------------------------------
# 3. 탭(Tab) 메뉴를 통한 화면 전환
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 1. 읍·면·동 연도별 인구 피라미드 애니메이션", 
    "🗺️ 2. 전국 시·군·구 고령화 단계구분도", 
    "🏙️ 3. 울산 행정동 고령화 지도",
    "👯 4. 우리 동네 쌍둥이 동네 찾기"
])


# =============================================================================
# [TAB 1] 읍·면·동 인구 피라미드 애니메이션 및 연령 추이
# =============================================================================
with tab1:
    st.subheader("🎯 동네별 인구 피라미드 타임랩스 애니메이션 (2015~2026)")
    st.write("시·도 ➔ 시·군·구 ➔ 읍·면·동을 순서대로 선택하여, 지난 2015년부터 2026년까지 동네 인구 구조 변화를 확인해보세요.")

    col_sel1, col_sel2, col_sel3 = st.columns(3)
    
    with col_sel1:
        sido_list = sorted(data_all['시도'].dropna().unique())
        default_sido_idx = sido_list.index("서울특별시") if "서울특별시" in sido_list else 0
        selected_sido = st.selectbox("1. 시·도 선택", sido_list, index=default_sido_idx, key="t1_sido")
        
    df_filtered_sido = data_all[data_all['시도'] == selected_sido]
    
    with col_sel2:
        sigungu_list = sorted(df_filtered_sido['시군구'].dropna().unique())
        default_sigungu_idx = sigungu_list.index("강남구") if "강남구" in sigungu_list else 0
        selected_sigungu = st.selectbox("2. 시·군·구 선택", sigungu_list, index=default_sigungu_idx, key="t1_sigungu")
        
    df_filtered_sigungu = df_filtered_sido[df_filtered_sido['시군구'] == selected_sigungu]
    
    with col_sel3:
        dong_list = sorted(df_filtered_sigungu['동'].dropna().unique())
        default_dong_idx = dong_list.index("대치1동") if "대치1동" in dong_list else 0
        selected_dong = st.selectbox("3. 읍·면·동 선택", dong_list, index=default_dong_idx, key="t1_dong")

    target_dong_df = df_filtered_sigungu[df_filtered_sigungu['동'] == selected_dong].sort_values('연도')
    
    if target_dong_df.empty:
        st.warning("선택하신 동네의 데이터가 존재하지 않습니다.")
    else:
        pyramid_records = []
        age_summary_records = []
        years = sorted(target_dong_df['연도'].unique())

        for yr in years:
            row = target_dong_df[target_dong_df['연도'] == yr].iloc[0]
            total_pop_yr = row['총인구']
            weighted_age_sum = 0
            age_pop_pairs = []

            for col in male_cols:
                age_str = col.replace('남_', '')
                age_num = 100 if '이상' in age_str else int(age_str.replace('세', ''))
                
                m_val = row[f'남_{age_str}']
                f_val = row[f'여_{age_str}']
                tot_val = m_val + f_val
                
                pyramid_records.append({
                    '연도': yr,
                    '연령대': age_str,
                    '나이_숫자': age_num,
                    '남성': m_val,
                    '여성': f_val,
                    '남성_표시': -m_val
                })
                
                weighted_age_sum += age_num * tot_val
                age_pop_pairs.append((age_num, tot_val))

            avg_age_yr = weighted_age_sum / total_pop_yr if total_pop_yr > 0 else 0
            
            half_pop = total_pop_yr / 2.0
            cum_pop = 0
            median_age_yr = 0
            for age_num, count in sorted(age_pop_pairs, key=lambda x: x[0]):
                cum_pop += count
                if cum_pop >= half_pop:
                    median_age_yr = age_num
                    break

            age_summary_records.append({
                '연도': yr,
                '평균 연령': round(avg_age_yr, 1),
                '중앙값 연령': median_age_yr
            })

        pyr_long_df = pd.DataFrame(pyramid_records)
        age_sum_df = pd.DataFrame(age_summary_records)

        max_single_sex_pop = max(pyr_long_df['남성'].max(), pyr_long_df['여성'].max())
        max_limit = int(max_single_sex_pop * 1.1) if max_single_sex_pop > 0 else 1000

        fig_pyramid_anim = px.bar(
            pyr_long_df,
            x='남성_표시',
            y='연령대',
            animation_frame='연도',
            orientation='h',
            title=f"<b>{selected_sido} {selected_sigungu} {selected_dong} 연도별 인구 피라미드 (2015~2026)</b>",
            labels={'남성_표시': '인구수 (명)', '연령대': '나이 (세)'},
            hover_data={'남성_표시': False, '남성': ':,명', '여성': ':,명'}
        )

        fig_pyramid_anim.update_traces(
            marker_color='#4C8BF5',
            name='남성 (왼쪽)'
        )

        for frame in fig_pyramid_anim.frames:
            yr_val = int(frame.name)
            sub_df = pyr_long_df[pyr_long_df['연도'] == yr_val]
            frame.data = (
                go.Bar(
                    y=sub_df['연령대'],
                    x=sub_df['남성_표시'],
                    orientation='h',
                    name='남성',
                    marker_color='#4C8BF5',
                    hovertemplate='남성: %{customdata:,}명<extra></extra>',
                    customdata=sub_df['남성']
                ),
                go.Bar(
                    y=sub_df['연령대'],
                    x=sub_df['여성'],
                    orientation='h',
                    name='여성',
                    marker_color='#F4A261',
                    hovertemplate='여성: %{x:,}명<extra></extra>'
                )
            )

        init_df = pyr_long_df[pyr_long_df['연도'] == years[0]]
        fig_pyramid_anim.add_trace(go.Bar(
            y=init_df['연령대'],
            x=init_df['여성'],
            orientation='h',
            name='여성 (오른쪽)',
            marker_color='#F4A261',
            hovertemplate='여성: %{x:,}명<extra></extra>'
        ))

        ticks_pos = [-max_limit, -int(max_limit/2), 0, int(max_limit/2), max_limit]
        ticks_text = [f"{abs(t):,}" for t in ticks_pos]

        fig_pyramid_anim.update_layout(
            barmode='overlay',
            bargap=0.05,
            xaxis=dict(
                range=[-max_limit, max_limit],
                tickvals=ticks_pos,
                ticktext=ticks_text,
                title="<b>◀ 남성 (명) | 여성 (명) ▶</b>",
                showgrid=True,
                gridcolor="#F0EAE1"
            ),
            yaxis=dict(title="나이 (0세가 아래)", dtick=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#FFFDF9",
            font=dict(color="#4A3E3D"),
            height=550
        )

        st.plotly_chart(fig_pyramid_anim, use_container_width=True)

        st.markdown("---")
        st.subheader(f"📈 {selected_sido} {selected_sigungu} {selected_dong} 연령 지표 변화 추이 (2015~2026)")
        
        fig_line = px.line(
            age_sum_df,
            x='연도',
            y=['평균 연령', '중앙값 연령'],
            markers=True,
            title=f"<b>{selected_dong} 평균 연령 vs 중앙값 연령 변화</b>",
            labels={'value': '연령 (세)', 'variable': '지표 구분'},
            color_discrete_map={
                '평균 연령': '#E07A5F',
                '중앙값 연령': '#81B29A'
            }
        )

        fig_line.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#FFFDF9",
            font=dict(color="#4A3E3D"),
            xaxis=dict(dtick=1, showgrid=True, gridcolor="#F0EAE1"),
            yaxis=dict(showgrid=True, gridcolor="#F0EAE1", title="세 (Age)"),
            hovermode="x unified"
        )

        st.plotly_chart(fig_line, use_container_width=True)


# =============================================================================
# [TAB 2] 전국 시·군·구 고령화 단계구분도
# =============================================================================
with tab2:
    st.subheader("🗺️ 전국 시·군·구 고령화 지도 (기준선 기반 시각화)")

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

    threshold = st.slider(
        "🎚️ 고령화율 기준선(%)을 선택하세요 (선택 기준 이상인 지역만 강조 표시됩니다):",
        min_value=10.0,
        max_value=50.0,
        value=30.0,
        step=1.0,
        key="tab2_slider"
    )

    col_map, col_table = st.columns([3, 1])

    with col_map:
        sigungu_map_df = sigungu_df.copy()
        label_over = f"{threshold:.0f}% 이상"
        label_under = f"{threshold:.0f}% 미만"
        
        sigungu_map_df['구분'] = sigungu_map_df['고령화율'].apply(
            lambda x: label_over if x >= threshold else label_under
        )

        fig_map = px.choropleth(
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

        fig_map.update_geos(
            fitbounds="locations",
            visible=False
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
        st.markdown("### 🏆 고령화율 TOP 5")
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

    max_year = data_all['연도'].max()
    ulsan_df = data_all[(data_all['시도'] == '울산광역시') & (data_all['연도'] == max_year)].copy()
    
    ulsan_df['adm_cd2'] = ulsan_df['코드_str']
    ulsan_df['adm_nm'] = ulsan_df['시도'] + " " + ulsan_df['시군구'] + " " + ulsan_df['동']

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

    fig_ulsan = px.choropleth(
        ulsan_df,
        geojson=geojson_ulsan,
        locations="adm_cd2",
        featureidkey="properties.adm_cd2",
        color="고령화율",
        color_continuous_scale="YlOrRd",
        range_color=(10, 35),
        hover_name="adm_nm",
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

    fig_ulsan.update_geos(
        fitbounds="locations",
        visible=False
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


# =============================================================================
# [TAB 4] 우리 동네 쌍둥이 동네 찾기 (인구 구조 유사도 분석)
# =============================================================================
with tab4:
    st.subheader("👯 우리 동네와 인구 구조가 가장 비슷한 '쌍둥이 동네' 찾기")
    st.write("궁금한 동네를 선택하면, 전국 읍·면·동 중 연령별 인구 비율(0세~100세 이상)이 가장 닮은 동네를 계산하여 보여줍니다.")

    # 1) 시도 -> 시군구 -> 동 3단계 드롭다운
    c_sido, c_sigungu, c_dong = st.columns(3)
    
    with c_sido:
        twin_sido_list = sorted(df_twin['시도'].dropna().unique())
        default_tw_sido = twin_sido_list.index("서울특별시") if "서울특별시" in twin_sido_list else 0
        sel_tw_sido = st.selectbox("1. 시·도 선택", twin_sido_list, index=default_tw_sido, key="t4_sido")
        
    df_tw_sido = df_twin[df_twin['시도'] == sel_tw_sido]
    
    with c_sigungu:
        twin_sigungu_list = sorted(df_tw_sido['시군구'].dropna().unique())
        default_tw_sigungu = twin_sigungu_list.index("강남구") if "강남구" in twin_sigungu_list else 0
        sel_tw_sigungu = st.selectbox("2. 시·군·구 선택", twin_sigungu_list, index=default_tw_sigungu, key="t4_sigungu")
        
    df_tw_sigungu = df_tw_sido[df_tw_sido['시군구'] == sel_tw_sigungu]
    
    with c_dong:
        twin_dong_list = sorted(df_tw_sigungu['동'].dropna().unique())
        default_tw_dong = twin_dong_list.index("대치1동") if "대치1동" in twin_dong_list else 0
        sel_tw_dong = st.selectbox("3. 읍·면·동 선택", twin_dong_list, index=default_tw_dong, key="t4_dong")

    # 선택된 기준 동네의 인덱스 찾기
    selected_target_name = f"{sel_tw_sido} {sel_tw_sigungu} {sel_tw_dong}"
    target_idx = df_twin[df_twin['동네명_풀'] == selected_target_name].index

    if target_idx.empty:
        st.warning("선택한 동네의 데이터가 존재하지 않습니다.")
    else:
        target_idx = target_idx[0]
        
        # 2) 유클리드 거리(제곱합) 기반 유사도 계산
        # 기준 동네의 연령별 비율 벡터
        target_ratio_vector = ratio_df.iloc[target_idx].values
        
        # 모든 동네와의 나이별 비율 차이 제곱합 계산: sum((ratio_a - ratio_b)^2)
        diff_matrix = ratio_df.values - target_ratio_vector
        squared_diff_sum = np.sum(np.square(diff_matrix), axis=1)
        
        # 자기 자신(target_idx)의 차이는 무한대로 설정하여 추천 후보에서 제외
        squared_diff_sum[target_idx] = np.inf
        
        # 차이가 가장 작은(가장 닮은) 동네의 인덱스 찾기
        twin_idx = np.argmin(squared_diff_sum)
        twin_target_name = df_twin.loc[twin_idx, '동네명_풀']
        twin_diff_score = squared_diff_sum[twin_idx]

        st.markdown("---")
        
        # 3) 화면 출력 1: 찾은 '쌍둥이 동네' 이름 및 카드
        st.subheader("1️⃣ 계산된 쌍둥이 동네")
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.info(f"📍 **선택한 동네**: {selected_target_name} (총인구 {df_twin.loc[target_idx, '총인구_합']:,}명)")
        with col_res2:
            st.success(f"👯 **가장 닮은 쌍둥이 동네**: **{twin_target_name}** (총인구 {df_twin.loc[twin_idx, '총인구_합']:,}명)")

        # 4) 화면 출력 2: 두 동네의 연령별 인구 비율 겹쳐 그린 Plotly 꺾은선 그래프
        st.markdown("---")
        st.subheader("2️⃣ 연령별 인구 비율 비교 그래프 (Plotly)")
        st.write("총인구 차이의 영향을 없애기 위해 **연령별 인구 비율(%)**로 변환하여 겹쳐 그린 그래프입니다.")

        # X축 나이 라벨 가공 ('계_0세' -> '0세')
        age_labels = [c.replace('계_', '') for c in total_cols]
        
        # 비율 데이터 백분율(%) 변환
        target_percentages = ratio_df.iloc[target_idx].values * 100
        twin_percentages = ratio_df.iloc[twin_idx].values * 100

        # Plotly 기본 템플릿 사용 (template 지정 없음)
        fig_twin = go.Figure()

        # 기준 동네 꺾은선
        fig_twin.add_trace(go.Scatter(
            x=age_labels,
            y=target_percentages,
            mode='lines+markers',
            name=selected_target_name,
            line=dict(color='#E07A5F', width=2.5),
            hovertemplate='나이: %{x}<br>비율: %{y:.2f}%<extra></extra>'
        ))

        # 쌍둥이 동네 꺾은선
        fig_twin.add_trace(go.Scatter(
            x=age_labels,
            y=twin_percentages,
            mode='lines+markers',
            name=f"쌍둥이: {twin_target_name}",
            line=dict(color='#81B29A', width=2.5, dash='dash'),
            hovertemplate='나이: %{x}<br>비율: %{y:.2f}%<extra></extra>'
        ))

        # 차트 레이아웃 설정
        fig_twin.update_layout(
            title=dict(
                text=f"<b>{selected_target_name} vs {twin_target_name} 연령별 인구 비율 비교</b>",
                font=dict(size=16)
            ),
            xaxis_title="연령 (나이)",
            yaxis_title="해당 연령 인구 비율 (%)",
            xaxis=dict(dtick=5, showgrid=True),
            yaxis=dict(showgrid=True),
            hovermode="x unified",
            legend=dict(
                x=0.01,
                y=0.98,
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="#E6DFD5",
                borderwidth=1
            ),
            height=500
        )

        st.plotly_chart(fig_twin, use_container_width=True)
