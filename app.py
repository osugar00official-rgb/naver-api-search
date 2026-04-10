import streamlit as st  # 웹 기반 대시보드 제작을 위한 스트림릿 라이브러리 임포트
import pandas as pd  # 데이터 조작 및 분석을 위한 판다스 라이브러리 임포트
import plotly.express as px  # 쉽고 빠른 인터랙티브 시각화를 위한 플롯리 익스프레스 임포트
import plotly.graph_objects as go  # 보다 세밀한 시각화 제어를 위한 플롯리 그래프 오브젝트 임포트
import os  # 파일 경로 및 운영체제 자원 접근을 위한 모듈 임포트
from datetime import datetime, timedelta  # 날짜 계산 및 처리를 위한 클래스 임포트
from crawler import fetch_naver_search, fetch_datalab_trend  # 제작한 크롤러 모듈에서 데이터 수집 함수 임포트

# 대시보드 페이지의 전체적인 설정을 정의합니다 (웹 브라우저 탭 제목, 레이아웃 너비 등).
st.set_page_config(page_title="고도화된 실시간 네이버 분석 대시보드", layout="wide")

# 대시보드의 시각적인 미관을 위해 사용자 정의 CSS 스타일을 적용합니다.
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6  /* 배경색을 연한 회색으로 설정 */
    }
    .main .block-container {
        padding-top: 2rem;  /* 메인 콘텐츠 상단 여백 설정 */
    }
</style>
""", unsafe_allow_html=True)

# --- 유틸리티 함수 정의 섹션 ---

def get_data_profiling(df):
    """표시할 데이터프레임의 기본 정보와 품질 상태(결측치 등)를 진단하는 함수"""
    if df.empty: return pd.DataFrame()  # 데이터가 없으면 빈 데이터프레임 반환
    # 컬럼명, 타입, 결측치 수, 비율, 유니크 값 수 등을 포함하는 통계표를 생성합니다.
    stats = pd.DataFrame({
        '컬럼명': df.columns,
        '데이터 타입': df.dtypes.astype(str),
        '결측치 수': df.isnull().sum().values,
        '결측치 비율(%)': (df.isnull().sum().values / len(df) * 100).round(2),
        '유니크 값 수': [df[col].nunique() for col in df.columns]
    })
    return stats  # 진단 결과 반환

def analyze_text_freq(df, col_name, top_n=30):
    """지정한 컬럼의 텍스트에서 단어 빈도수를 계산하는 분석 함수 (형태소 분석기 미사용)"""
    if df.empty or col_name not in df.columns: return pd.DataFrame()  # 분석할 데이터가 없으면 종료
    
    # 해당 컬럼의 모든 텍스트를 하나로 결합합니다 (공백 기준).
    all_text = " ".join(df[col_name].dropna().astype(str).tolist())
    # 공백을 기준으로 단어를 분리하되, 의미 없는 1글자 단어는 제외합니다.
    words = [w for w in all_text.split() if len(w) > 1]
    
    # 단어별 빈도수를 구하고 상위 N개만 선택하여 데이터프레임으로 변환합니다.
    freq = pd.Series(words).value_counts().head(top_n).reset_index()
    freq.columns = ['단어', '빈도수']  # 컬럼명 재설정
    return freq  # 빈도 분석 결과 반환

# --- 대시보드 사이드바(Sidebar) 구성 섹션 ---

st.sidebar.title("📊 통합 분석 제어판")  # 사이드바 제목 표시
st.sidebar.info("네이버 오픈 API를 통한 실시간 데이터 수집 및 시각화")  # 안내 문구 표시

# 검색 조건 입력을 위한 폼을 사이드바에 생성합니다.
with st.sidebar.form("search_form"):
    # 쉼표로 구분하여 여러 개의 검색어를 입력받습니다 (기본값 설정됨).
    raw_keywords = st.text_input("검색어 입력 (쉼표로 구분)", value="핫팩, 선풍기")
    # 입력받은 문자열을 리스트로 변환하고 양끝 공백을 제거합니다.
    keywords = [k.strip() for k in raw_keywords.split(",") if k.strip()]
    
    # 날짜 범위 선택을 위한 위젯 구성
    today = datetime.now()  # 현재 날짜 가져오기
    default_start = today - timedelta(days=90)  # 기본 시작일 설정 (90일 전)
    date_range = st.date_input("데이터랩 분석 기간", [default_start, today])  # 날짜 입력 위젯 생성
    
    # 데이터 수집 및 분석을 트리거하는 버튼 생성
    submitted = st.form_submit_button("분석 실행")

# --- 메인 비즈니스 로직 및 실시간 데이터 수집 ---

# 버튼이 눌렸거나 처음 접속했을 때 데이터를 수집합니다.
if submitted or 'initialized' not in st.session_state:
    st.session_state.initialized = True  # 초기화 상태 저장
    
    # 서버측 대기 시간을 사용자에게 알리는 스피너 애니메이션 표시
    with st.spinner("네이버 API에서 실시간 데이터를 수집 중입니다..."):
        # 각 소스별 데이터를 담을 리스트 초기화
        all_shop = []
        all_news = []
        all_blog = []
        all_cafe = []
        
        # 입력된 모든 키워드에 대해 루프를 돌며 API를 호출합니다.
        for kw in keywords:
            all_shop.append(fetch_naver_search('shop', kw))      # 쇼핑 검색 호출
            all_news.append(fetch_naver_search('news', kw))      # 뉴스 검색 호출
            all_blog.append(fetch_naver_search('blog', kw))      # 블로그 검색 호출
            all_cafe.append(fetch_naver_search('cafearticle', kw)) # 카페 게시글 검색 호출
        
        # 수집된 리스트들을 하나의 데이터프레임으로 통합하여 세션 상태에 저장합니다.
        st.session_state.df_shop = pd.concat(all_shop, ignore_index=True) if all_shop else pd.DataFrame()
        st.session_state.df_news = pd.concat(all_news, ignore_index=True) if all_news else pd.DataFrame()
        st.session_state.df_blog = pd.concat(all_blog, ignore_index=True) if all_blog else pd.DataFrame()
        st.session_state.df_cafe = pd.concat(all_cafe, ignore_index=True) if all_cafe else pd.DataFrame()
        
        # 데이터랩 트렌드 데이터 수집 처리
        if len(date_range) == 2:
            st.session_state.df_trend = fetch_datalab_trend(
                keywords, 
                start_date=date_range[0].strftime('%Y-%m-%d'),  # 시작일 포맷팅
                end_date=date_range[1].strftime('%Y-%m-%d')     # 종료일 포맷팅
            )
        else:
            st.session_state.df_trend = pd.DataFrame()  # 날짜 범위가 부족하면 빈 데이터프레임

# 세션 상태에 저장된 데이터프레임을 변수에 할당합니다.
df_shop = st.session_state.get('df_shop', pd.DataFrame())
df_news = st.session_state.get('df_news', pd.DataFrame())
df_blog = st.session_state.get('df_blog', pd.DataFrame())
df_cafe = st.session_state.get('df_cafe', pd.DataFrame())
df_trend = st.session_state.get('df_trend', pd.DataFrame())

# --- 대시보드 메인 화면 레이아웃 구성 ---

st.title("🎛️ 실시간 네이버 통합 인사이트 대시보드")  # 메인 제목 표시

# 쇼핑 데이터가 없으면 사용자에게 처음에 안내 메시지를 보여줍니다.
if df_shop.empty:
    st.warning("데이터가 없습니다. 사이드바에서 검색을 실행해 주세요.")
else:
    # 기능별로 분석 내용을 나누기 위해 탭(Tab) 위젯을 사용합니다.
    tabs = st.tabs(["🏛️ 데이터 프로파일링", "🛒 쇼핑 분석", "📰 검색 결과(뉴스/블로그/카페)", "📈 트렌드 분석", "📑 원본 데이터"])
    
    # 1. 데이터 프로파일링 탭: 데이터 품질 진단 결과 표시
    with tabs[0]:
        st.header("📊 데이터 품질 및 프로파일링")
        
        # 진단할 데이터 소스를 선택하는 셀렉트박스 생성
        source_options = {
            "네이버 쇼핑": df_shop,
            "네이버 뉴스": df_news,
            "네이버 블로그": df_blog,
            "네이버 카페": df_cafe
        }
        sel_prof = st.selectbox("분석할 데이터 소스 선택", list(source_options.keys()))
        target_df = source_options[sel_prof]  # 선택된 데이터프레임 가져오기
        
        col_st1, col_st2 = st.columns(2)  # 화면을 2개의 컬럼으로 분할
        with col_st1:
            st.subheader("기본 정보")
            st.write(f"**전체 행 수:** {len(target_df):,} | **전체 열 수:** {len(target_df.columns)}")
            st.table(get_data_profiling(target_df))  # 진단 통계표 출력
            
        with col_st2:
            # 수치형 데이터(가격 등)가 포함된 경우 기술 통계량 추가 표시
            if 'lprice' in target_df.columns:
                st.subheader("수치형 데이터 통계 (쇼핑 최고가/최저가)")
                target_df['lprice'] = pd.to_numeric(target_df['lprice'], errors='coerce')  # 가격 데이터를 수치화
                st.write(target_df['lprice'].describe())  # 기술 통계 요약 표시
                
    # 2. 쇼핑 분석 탭: 시장 구조 분석
    with tabs[1]:
        st.header("🛒 쇼핑 시장 매트릭스")
        
        # 트리맵 시각화: 검색어와 브랜드, 판매처의 계층 구조를 면적으로 표시
        st.subheader("브랜드 및 판매처 계층 구조 (Treemap)")
        fig_tree = px.treemap(df_shop, path=[px.Constant("전체"), 'search_keyword', 'brand', 'mallName'], 
                              values='lprice', color='lprice',
                              color_continuous_scale='RdBu',
                              title="키워드별 브랜드 및 판매처 분포 (가격 기준 가중치)")
        st.plotly_chart(fig_tree, use_container_width=True)
        
        # 선버스트 차트: 카테고리별 분류 체계를 원형 계층 구조로 표시
        st.subheader("카테고리 계층 분석 (Sunburst)")
        cat_cols = [c for c in ['category1', 'category2', 'category3', 'category4'] if c in df_shop.columns]
        if cat_cols:
            fig_sun = px.sunburst(df_shop, path=['search_keyword'] + cat_cols, 
                                  title="키워드별 카테고리 매핑 구조")
            st.plotly_chart(fig_sun, use_container_width=True)
            
    # 3. 검색 결과 탭: 뉴스, 블로그, 카페의 소셜 인지도 분석
    with tabs[2]:
        st.header("📰 소셜 및 뉴스 버즈(Buzz) 분석")
        
        # 각 매체별로 상세 분석을 보기 위해 하위 탭 생성
        search_tabs = st.tabs(["뉴스", "블로그", "카페"])
        
        for i, (name, df_search) in enumerate([("뉴스", df_news), ("블로그", df_blog), ("카페", df_cafe)]):
            with search_tabs[i]:
                if not df_search.empty:
                    col_l, col_r = st.columns([2, 1])  # 2:1 비율로 컬럼 분할
                    
                    with col_l:
                        st.subheader(f"최근 {name} 주요 키워드 Top 30")
                        # 텍스트 분석 실행 (제목 컬럼 대상)
                        freq_df = analyze_text_freq(df_search, 'title')
                        # 단어 빈도수를 나타내는 수평 막대 차트 생성
                        fig_freq = px.bar(freq_df, x='빈도수', y='단어', orientation='h',
                                          color='빈도수', color_continuous_scale='Viridis',
                                          title=f"{name} 내 핵심 키워드 유입 현황")
                        st.plotly_chart(fig_freq, use_container_width=True)
                        
                    with col_r:
                        st.subheader(f"인기 {name} 데이터 섹션")
                        # 원본 제목 데이터 일부 출력
                        st.dataframe(df_search[['title', 'search_keyword']].head(20), use_container_width=True)
                else:
                    st.info(f"{name} 데이터가 없습니다.")

    # 4. 트렌드 분석 탭: 시간 경과에 따른 인기 검색어 추이 표시
    with tabs[3]:
        st.header("📈 네이버 데이터랩 검색 추이")
        if not df_trend.empty:
            # 기간별 검색 비중 변화를 선 그래프로 시각화
            fig_trend = px.line(df_trend, x='period', y='ratio', color='keyword',
                                markers=True, title="전체 검색어 트렌드 변화 (상대 수치)")
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.subheader("데이터랩 상세 수치")
            # 피벗 테이블 형태로 날짜별 수치 데이터 확인
            st.dataframe(df_trend.pivot(index='period', columns='keyword', values='ratio'), use_container_width=True)
        else:
            st.info("트렌드 데이터를 불러올 수 없습니다. 날짜 범위를 확인해 주세요.")
            
    # 5. 원본 데이터 조회 탭: 데이터프레임을 직접 조회하고 확인
    with tabs[4]:
        st.header("📑 수집 데이터 프레임 조회")
        
        # 조회할 대상 선택
        sel_data = st.selectbox("조회할 데이터 소스", ["쇼핑", "뉴스", "블로그", "카페"])
        data_map = {"쇼핑": df_shop, "뉴스": df_news, "블로그": df_blog, "카페": df_cafe}
        
        st.write(f"**현재 '{sel_data}' 데이터 소스 조회 중**")
        st.dataframe(data_map[sel_data], use_container_width=True)

# 페이지 하단 푸터 영역 구성
st.markdown("---")
st.markdown("Developed by **Data Analytics Expert AI** | Naver Open API Integration")  # 개발자 정보 표시
