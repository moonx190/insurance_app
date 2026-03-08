import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="보험 시장 인사이트 리포트", layout="wide", page_icon="📈")

@st.cache_data
def load_master_data():
    try:
        df = pd.read_csv('insurance_integrated_data.csv')
        # 변수명 한글 매핑 (실무 용어 적용)
        df = df.rename(columns={
            'sttsAccmlTrgtYr': '기준년도', 'areaNm': '지역', 'rchnAggr': '연령대',
            'joinCnt': '가입건수', 'joinRto': '가입율(%)', 'data_source': '데이터구분',
            'offrTyNm': '모집채널', 'taxPrqlYn': '세제적격여부'
        })
        # 숫자 및 타입 정리
        df['가입건수'] = pd.to_numeric(df['가입건수'], errors='coerce').fillna(0)
        df['기준년도'] = pd.to_numeric(df['기준년도'], errors='coerce')
        return df
    except:
        return pd.DataFrame()

df = load_master_data()

# --- [핵심 로직] 2023년 데이터 평균치 보간 처리 ---
def get_trend_with_2023(source_df):
    trend = source_df.groupby(['기준년도', '데이터구분'])['가입건수'].sum().reset_index()
    combined = []
    for src in trend['데이터구분'].unique():
        temp = trend[trend['데이터구분'] == src].set_index('기준년도')
        # 2018-2024 전체 연도 틀 생성
        full_idx = pd.Index(range(2018, 2025), name='기준년도')
        temp = temp.reindex(full_idx)
        # 2023년 평균치 보간 (22년과 24년 사이를 직선으로 연결)
        temp['가입건수'] = temp['가입건수'].interpolate(method='linear')
        temp['데이터구분'] = src
        combined.append(temp.reset_index())
    return pd.concat(combined)

# --- 사이드바 필터 (규범님 요청사항 반영) ---
with st.sidebar:
    st.header("🔍 분석 설정")
    if not df.empty:
        # [수정] 연도 선택 리스트를 2018년부터 2024년까지 정방향 정렬
        all_years = sorted(df['기준년도'].unique())
        sel_year = st.selectbox("📅 상세 분석 연도 선택", all_years) 
        
        st.divider()
        sel_source = st.selectbox("📊 데이터 소스", ["전체보기"] + list(df['데이터구분'].unique()))
    else:
        st.error("데이터 파일이 없습니다.")

# 데이터 필터링
f_df = df if sel_source == "전체보기" else df[df['데이터구분'] == sel_source]
year_df = f_df[f_df['기준년도'] == sel_year]

# --- 메인 대시보드 ---
st.title("🛡️ 보험 가입 현황 입체 분석 리포트")
st.info(f"💡 현재 **{sel_year}년** 데이터를 상세 분석 중입니다. (상단 추이 그래프는 2023년 추정치 포함)")

if not f_df.empty:
    # 섹션 1: 시계열 추이 (2023년 평균치 보간 시각화)
    st.subheader("📊 연도별 가입 추이 및 시장 흐름 (2018-2024)")
    trend_data = get_trend_with_2023(f_df)
    
    fig_line = px.line(trend_data, x='기준년도', y='가입건수', color='데이터구분', 
                        markers=True, template='plotly_white')
    
    # 2023년 추정치 지점 강조 (빨간 점과 텍스트)
    val_2023 = trend_data[trend_data['기준년도']==2023]['가입건수'].mean()
    fig_line.add_annotation(x=2023, y=val_2023, text="2023년 추정치(평균)", 
                            showarrow=True, arrowhead=1, font=dict(color="red"))
    
    st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    # 섹션 2: 지역별 및 모집채널별 분석 (선택된 연도 기준)
    st.subheader(f"📍 {sel_year}년 지역 및 채널별 상세 현황")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**[{sel_year}년 지역별 가입 순위 (TOP 10)]**")
        area_sum = year_df.groupby('지역')['가입건수'].sum().sort_values(ascending=True).tail(10).reset_index()
        if not area_sum.empty:
            fig_area = px.bar(area_sum, x='가입건수', y='지역', orientation='h', 
                              color='가입건수', color_continuous_scale='Blues')
            st.plotly_chart(fig_area, use_container_width=True)
        else:
            st.write("해당 연도 지역 데이터가 없습니다.")

    with col2:
        st.markdown(f"**[{sel_year}년 모집 채널별 비중]**")
        # 채널 정보가 있는 경우만 출력 (주로 개인연금 데이터)
        channel_data = year_df.groupby('모집채널')['가입건수'].sum().reset_index()
        if not channel_data.empty and channel_data['가입건수'].sum() > 0:
            fig_pie = px.pie(channel_data, values='가입건수', names='모집채널', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("선택한 연도/데이터에는 상세 채널 정보가 포함되어 있지 않습니다.")

    # 섹션 3: 연령대별 가입 분포
    st.divider()
    st.subheader(f"👥 {sel_year}년 연령대별 가입 분포")
    age_data = year_df.groupby('연령대')['가입건수'].sum().reset_index()
    if not age_data.empty:
        fig_age = px.bar(age_data, x='연령대', y='가입건수', color='가입건수', 
                         color_continuous_scale='Purples', text_auto='.2s')
        st.plotly_chart(fig_age, use_container_width=True)

    # 섹션 4: 원본 데이터 확인 및 리포트 출력
    with st.expander("📄 상세 데이터 확인 및 보고서 다운로드"):
        st.dataframe(year_df.style.format({'가입건수': '{:,.0f}'}))
        csv = year_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(f"📥 {sel_year}년 분석 데이터 다운로드", data=csv, file_name=f"insurance_analysis_{sel_year}.csv")

else:
    st.warning("분석할 수 있는 데이터가 부족합니다.")