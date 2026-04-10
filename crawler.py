import os  # 운영체제 인터페이스 기능을 사용하기 위한 모듈 임포트
import requests  # HTTP 요청을 보내기 위한 라이브러리 임포트
import pandas as pd  # 데이터 분석 및 조작을 위한 라이브러리 임포트
import time  # 시간 관련 기능을 사용하기 위한 모듈 임포트
import re  # 정규 표현식 연산을 위한 모듈 임포트
import json  # JSON 데이터 처리를 위한 모듈 임포트
import streamlit as st  # 스트림릿 시크릿 관리를 위한 라이브러리 임포트 (배포용)
from datetime import datetime, timedelta  # 날짜와 시간 조작을 위한 클래스 임포트
from dotenv import load_dotenv  # .env 파일에서 환경 변수를 로드하기 위한 라이브러리 임포트

# .env 파일에 정의된 환경 변수들을 시스템 환경 변수로 로드합니다 (로컬 개발 환경용).
load_dotenv()

def get_api_credentials():
    """Streamlit Secrets 또는 환경 변수에서 API 인증 정보를 가져오는 함수"""
    # 1. 먼저 Streamlit Secrets에서 정보를 시도합니다 (배포 환경 우선).
    try:
        if "naver" in st.secrets:
            client_id = st.secrets["naver"]["client_id"]
            client_secret = st.secrets["naver"]["client_secret"]
            return client_id, client_secret
    except:
        pass # Streamlit 환경이 아니거나 Secrets가 설정되지 않은 경우 무시

    # 2. 다음으로 시스템 환경 변수 또는 .env에서 가져옵니다 (로컬 환경).
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    return client_id, client_secret

# API 인증 정보를 가져옵니다.
CLIENT_ID, CLIENT_SECRET = get_api_credentials()

# 모든 API 요청에 공통으로 사용될 HTTP 헤더를 정의합니다.
HEADERS = {
    "X-Naver-Client-Id": CLIENT_ID,  # 클라이언트 아이디 설정
    "X-Naver-Client-Secret": CLIENT_SECRET,  # 클라이언트 시크릿 설정
    "Content-Type": "application/json"  # 데이터 형식을 JSON으로 설정
}

def clean_html(raw_html):
    """HTML 태그를 제거하여 순수 텍스트만 추출하는 함수"""
    if pd.isna(raw_html): return ""  # 데이터가 비어있으면 빈 문자열 반환
    cleanr = re.compile('<.*?>')  # HTML 태그를 찾는 정규식 패턴 컴파일
    return re.sub(cleanr, '', str(raw_html))  # 매칭되는 태그를 제거하고 반환

def fetch_naver_search(category, keyword, display=100, start=1, sort='sim'):
    """네이버 검색 API(쇼핑, 블로그, 뉴스, 카페 등)를 호출하는 공통 함수"""
    # 요청할 API의 카테고리에 따른 엔드포인트 URL을 구성합니다.
    url = f"https://openapi.naver.com/v1/search/{category}.json"
    # 검색어, 출력 개수, 시작 지점, 정렬 방식 등 파라미터를 설정합니다.
    params = {"query": keyword, "display": display, "start": start, "sort": sort}
    
    try:
        # 설정한 URL, 헤더, 파라미터로 GET 요청을 보냅니다.
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()  # 응답 코드에 에러가 있으면 예외를 발생시킵니다.
        items = response.json().get('items', [])  # 응답 데이터에서 실제 결과 아이템 리스트를 추출합니다.
        df = pd.DataFrame(items)  # 추출된 리스트를 판다스 데이터프레임으로 변환합니다.
        if not df.empty:  # 데이터가 존재하는 경우
            if 'title' in df.columns: df['title'] = df['title'].apply(clean_html)  # 제목에서 HTML 태그 제거
            if 'description' in df.columns: df['description'] = df['description'].apply(clean_html)  # 설명에서 HTML 태그 제거
            df['search_keyword'] = keyword  # 분석을 위해 검색에 사용된 키워드 저장
            df['source'] = category  # 데이터의 출처(카테고리) 저장
        return df  # 처리 완료된 데이터프레임 반환
    except Exception as e:
        # 에러 발생 시 에러 메시지를 출력하고 빈 데이터프레임을 반환합니다.
        print(f"Error fetching {category} for {keyword}: {e}")
        return pd.DataFrame()

def fetch_datalab_trend(keywords, start_date=None, end_date=None, time_unit='month'):
    """네이버 데이터랩 API를 통해 검색어 트렌드 추이를 조회하는 함수"""
    url = "https://openapi.naver.com/v1/datalab/search"  # 데이터랩 트렌드 API 엔드포인트
    
    # 종료일이 지정되지 않은 경우 오늘 날짜로 설정합니다.
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    # 시작일이 지정되지 않은 경우 1년 전 날짜로 설정합니다.
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
    keyword_groups = []  # 그룹화된 키워드들을 담을 리스트
    for kw in keywords:
        # 각 키워드를 각각의 그룹으로 만들어 개별 추이를 보낼 수 있게 구성합니다.
        keyword_groups.append({"groupName": kw, "keywords": [kw]})
        
    # API 요청 본문(Body)을 JSON 형식으로 작성합니다.
    body = {
        "startDate": start_date,  # 시작 날짜
        "endDate": end_date,  # 종료 날짜
        "timeUnit": time_unit,  # 분석 단위 (일/주/월)
        "keywordGroups": keyword_groups  # 주제어 군 리스트
    }
    
    try:
        # POST 방식을 사용하여 데이터랩 API에 요청을 보냅니다. 본문 데이터는 JSON 문자열로 변환합니다.
        response = requests.post(url, headers=HEADERS, data=json.dumps(body))
        response.raise_for_status()  # 응답 코드를 확인합니다.
        res_data = response.json()  # JSON 형태의 응답을 파싱합니다.
        
        results = []  # 최종 결과 데이터를 담을 리스트
        for group in res_data.get('results', []):
            title = group['title']  # 키워드 그룹 이름
            for entry in group.get('data', []):
                # 각 기간별 데이터 포인트와 제목(키워드)을 매핑하여 저장합니다.
                results.append({
                    "period": entry['period'],  # 날짜/기간
                    "ratio": entry['ratio'],  # 검색 비중 (0~100)
                    "keyword": title  # 해당 키워드명
                })
        return pd.DataFrame(results)  # 리스트를 데이터프레임으로 변환하여 반환합니다.
    except Exception as e:
        # 통신 에러 발생 시 메시지 출력 후 빈 데이터프레임 반환
        print(f"Error fetching datalab trend: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    # 이 스크립트가 직접 실행될 경우 진행할 테스트 로직입니다.
    test_kw = "선풍기"  # 테스트용 검색 키워드 설정
    print(fetch_naver_search('shop', test_kw).head())  # 쇼핑 검색 상위 5건 출력
    print(fetch_datalab_trend([test_kw, '핫팩']).head())  # 데이터랩 트렌드 상위 5건 출력
