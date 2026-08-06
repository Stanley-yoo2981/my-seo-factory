import os
import re
import sys
import subprocess
import base64
import json
import random
import urllib.request
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# [!] 업데이트 확인용 태그
BUILD_TAG = "V5.0-2STAGE-KEYWORD-EDITION"

# ── 1. 인프라 및 경로 설정 ──────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_FOLDER = os.path.join(PROJECT_DIR, "images")
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.environ["IMG_DIR"] = IMAGE_FOLDER
CSV_PATH     = os.path.join(PROJECT_DIR, "keywords.csv")
SNIPPET_PATH = os.path.join(PROJECT_DIR, "snippet_data.json")

if os.path.exists(os.path.join(PROJECT_DIR, ".env")):
    load_dotenv(os.path.join(PROJECT_DIR, ".env"))

# ── session_state 초기값 ────────────────────────────────────────────────
if "factory_step"        not in st.session_state: st.session_state.factory_step        = 1
if "images_enabled"      not in st.session_state:
    env_val = os.getenv("IMAGES_ENABLED", "false").strip().lower()
    st.session_state.images_enabled = env_val in ("1", "true", "yes", "on")
if "show_data"           not in st.session_state: st.session_state.show_data           = False

# 2단계 키워드 UI 상태
if "active_type"         not in st.session_state: st.session_state.active_type         = None   # "hero"|"hub"|"help"|None
if "hero_candidates"     not in st.session_state: st.session_state.hero_candidates     = []
if "hub_candidates"      not in st.session_state: st.session_state.hub_candidates      = []
if "help_page"           not in st.session_state: st.session_state.help_page           = 0      # 0→1위~5위, 1→6~10위, 2→11~15위

# ── 2. 페이지 세팅 ─────────────────────────────────────────────────────
st.set_page_config(page_title="워드프레스 공장", layout="wide", initial_sidebar_state="collapsed")

# ── 사이드바: DALL-E 이미지 생성 토글 ──────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 이미지 생성 설정")
    images_enabled = st.toggle(
        "DALL-E 이미지 생성",
        value=st.session_state.images_enabled,
        help=(
            "켜면 DALL-E 3 이미지 3장을 생성하여 WordPress에 업로드합니다.\n"
            "끄면 HTML 주석 플레이스홀더만 삽입하고 OpenAI 크레딧을 소비하지 않습니다."
        ),
    )
    st.session_state.images_enabled = images_enabled
    os.environ["IMAGES_ENABLED"] = "true" if images_enabled else "false"
    if images_enabled:
        st.success("✅ 이미지 생성 ON — DALL-E 크레딧 소모 주의")
    else:
        st.info("🚫 이미지 생성 OFF — 플레이스홀더 삽입")

# ── 3. 🎨 Apple Glass UI ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

    /* ── 전역 리셋 & 배경 ── */
    html, body,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    section[data-testid="stSidebar"] {
        background: transparent !important;
        font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(ellipse 80% 60% at 20% 10%, rgba(200,185,255,0.18) 0%, transparent 60%),
            radial-gradient(ellipse 60% 50% at 80% 20%, rgba(255,190,170,0.15) 0%, transparent 55%),
            radial-gradient(ellipse 70% 60% at 50% 80%, rgba(160,210,255,0.13) 0%, transparent 60%),
            linear-gradient(160deg, #f0ecf8 0%, #fdf4ef 40%, #eef4fc 100%) !important;
        min-height: 100vh;
    }

    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 4rem !important;
        max-width: 1200px !important;
    }
    [data-testid="stHeader"] { background: transparent !important; }
    footer { visibility: hidden; }

    /* ── 타이틀 ── */
    .factory-title {
        text-align: center;
        font-size: clamp(40px, 6vw, 72px);
        font-weight: 900;
        letter-spacing: -0.03em;
        background: linear-gradient(135deg, #1d1d1f 0%, #4a3f6b 50%, #8b5e52 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.3rem;
        line-height: 1.1;
    }
    .factory-subtitle {
        text-align: center;
        font-size: 13px;
        font-weight: 500;
        color: rgba(60,50,80,0.42);
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin-bottom: 3.5rem;
    }

    /* ── 메인 액션 버튼 ── */
    div[data-testid="stButton"] > button {
        background: rgba(255,255,255,0.52) !important;
        backdrop-filter: blur(28px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(28px) saturate(180%) !important;
        border: 1px solid rgba(255,255,255,0.78) !important;
        border-radius: 28px !important;
        box-shadow:
            0 8px 32px rgba(80,60,120,0.08),
            0 2px 8px rgba(80,60,120,0.04),
            inset 0 1px 0 rgba(255,255,255,0.92) !important;
        width: 100% !important;
        min-height: 200px !important;
        aspect-ratio: 1 / 1 !important;
        color: #1d1d1f !important;
        font-family: 'Noto Sans KR', sans-serif !important;
        font-size: clamp(12px, 1.3vw, 17px) !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em !important;
        line-height: 1.6 !important;
        transition: all 0.38s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        white-space: pre-wrap !important;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-7px) scale(1.015) !important;
        box-shadow:
            0 28px 64px rgba(80,60,120,0.14),
            0 8px 20px rgba(80,60,120,0.07),
            inset 0 1px 0 rgba(255,255,255,0.96) !important;
        border-color: rgba(255,255,255,0.92) !important;
        color: #4a3f6b !important;
        background: rgba(255,255,255,0.72) !important;
    }
    div[data-testid="stButton"] > button:active {
        transform: translateY(-2px) scale(0.99) !important;
    }

    /* ── Active 단계 강조 ── */
    .active-engine div[data-testid="stButton"] > button {
        border: 1.5px solid rgba(130,100,200,0.45) !important;
        box-shadow:
            0 0 0 5px rgba(130,100,200,0.1),
            0 14px 44px rgba(130,100,200,0.16),
            inset 0 1px 0 rgba(255,255,255,0.95) !important;
        background: rgba(255,255,255,0.66) !important;
    }

    /* ── 진행 배지 ── */
    .step-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(255,255,255,0.58);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.82);
        border-radius: 99px;
        padding: 10px 22px;
        font-size: 14px;
        font-weight: 600;
        color: #3a3050;
        box-shadow: 0 4px 16px rgba(80,60,120,0.07);
        margin-bottom: 14px;
    }

    /* ── 프로그레스 바 ── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #7c6bb0, #c4837a) !important;
        border-radius: 99px !important;
        height: 5px !important;
    }
    .stProgress > div > div {
        background: rgba(200,190,230,0.2) !important;
        border-radius: 99px !important;
        height: 5px !important;
    }

    /* ── 스니펫 박스 ── */
    .snippet-box {
        background: rgba(255,255,255,0.54);
        backdrop-filter: blur(24px) saturate(160%);
        border: 1px solid rgba(255,255,255,0.8);
        border-radius: 24px;
        padding: 26px 30px;
        box-shadow: 0 8px 32px rgba(80,60,120,0.07), inset 0 1px 0 rgba(255,255,255,0.92);
        margin-top: 32px;
        margin-bottom: 18px;
    }
    .snippet-title {
        font-size: 17px;
        font-weight: 800;
        color: #3a3050;
        margin-bottom: 5px;
    }
    .snippet-sub {
        font-size: 13px;
        color: rgba(60,50,80,0.48);
        margin-bottom: 18px;
    }

    /* ── 타입 배지 ── */
    .type-badge {
        display: inline-block;
        font-size: 10.5px;
        font-weight: 700;
        letter-spacing: 0.06em;
        padding: 3px 10px;
        border-radius: 99px;
        margin-left: 8px;
        vertical-align: middle;
    }
    .badge-hero { background: rgba(255,100,80,0.1);  color: #b83232; border: 1px solid rgba(255,100,80,0.22); }
    .badge-hub  { background: rgba(70,120,240,0.1);  color: #1a4ec4; border: 1px solid rgba(70,120,240,0.22); }
    .badge-help { background: rgba(40,170,120,0.1);  color: #1a6a50; border: 1px solid rgba(40,170,120,0.22); }

    /* ── 워드프레스 이동 버튼 ── */
    .link-button {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: linear-gradient(135deg, #5c4f8a 0%, #8b5e52 100%);
        color: white !important;
        padding: 15px 34px;
        border-radius: 99px;
        text-decoration: none;
        font-weight: 700;
        font-size: 15px;
        margin-top: 8px;
        transition: all 0.3s ease;
        box-shadow: 0 8px 24px rgba(92,79,138,0.28);
        letter-spacing: -0.01em;
        font-family: 'Noto Sans KR', sans-serif;
    }
    .link-button:hover {
        transform: translateY(-3px);
        box-shadow: 0 16px 40px rgba(92,79,138,0.38);
        color: white !important;
    }

    /* ── 상태창 ── */
    [data-testid="stStatusWidget"] {
        background: rgba(255,255,255,0.58) !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255,255,255,0.78) !important;
        border-radius: 16px !important;
    }
    [data-testid="stStatusWidget"] * { color: #3a3050 !important; }

    /* ── 데이터프레임 ── */
    [data-testid="stDataFrame"] {
        background: rgba(255,255,255,0.5) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255,255,255,0.7) !important;
    }

    /* ── 인풋 필드 ── */
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {
        background: rgba(255,255,255,0.55) !important;
        border: 1px solid rgba(190,175,225,0.3) !important;
        border-radius: 12px !important;
        color: #1d1d1f !important;
        font-family: 'Noto Sans KR', sans-serif !important;
    }
            
    [data-testid="stWidgetLabel"] p,
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    [data-baseweb="radio"] div {
        color: #3a3050 !important;
        font-weight: 500 !important;
    }

    /* ── 라디오/체크박스 선택지 글자색 고정 ──
       옵션 텍스트는 <p> 안에 들어가는데, 부모 div에만 색을 주면
       Streamlit 기본 테마의 <p> 색상(다크모드 = 흰색)이 이겨서
       밝은 배경에 흰 글씨가 되어 보이지 않습니다. <p>를 직접 지정합니다. */
    [data-testid="stRadio"] label p,
    [data-testid="stRadio"] label div,
    [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p,
    [data-baseweb="radio"] p,
    [data-baseweb="radio"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stCheckbox"] label p,
    [data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {
        color: #3a3050 !important;
        font-weight: 500 !important;
        opacity: 1 !important;
    }

    /* 선택된 항목은 조금 더 진하게 */
    [data-testid="stRadio"] label[aria-checked="true"] p,
    [data-baseweb="radio"][aria-checked="true"] p {
        color: #241c3a !important;
        font-weight: 700 !important;
    }

    /* ── 셀렉트박스 ── */
    [data-testid="stSelectbox"] > div {
        background: rgba(255,255,255,0.55) !important;
        border: 1px solid rgba(190,175,225,0.3) !important;
        border-radius: 12px !important;
        font-family: 'Noto Sans KR', sans-serif !important;
    }

    /* ── 키워드 선택 박스 (2단계 UI) ── */
    .kw-panel {
        background: rgba(255,255,255,0.60);
        backdrop-filter: blur(28px) saturate(170%);
        border: 1px solid rgba(130,100,200,0.22);
        border-radius: 24px;
        padding: 28px 34px 24px;
        box-shadow: 0 10px 40px rgba(80,60,120,0.09), inset 0 1px 0 rgba(255,255,255,0.94);
        margin-top: 28px;
        margin-bottom: 8px;
    }
    .kw-panel-title {
        font-size: 16px;
        font-weight: 800;
        color: #3a3050;
        margin-bottom: 4px;
    }
    .kw-panel-sub {
        font-size: 12.5px;
        color: rgba(60,50,80,0.48);
        margin-bottom: 18px;
        line-height: 1.7;
    }
    .kw-divider {
        border: none;
        border-top: 1px solid rgba(150,130,200,0.14);
        margin: 18px 0;
    }

    /* ── 구분선 ── */
    hr { border-color: rgba(150,130,200,0.12) !important; }

    /* ── 가이드 래퍼 ── */
    .guide-wrap {
        background: rgba(255,255,255,0.46);
        backdrop-filter: blur(24px) saturate(150%);
        border: 1px solid rgba(255,255,255,0.72);
        border-radius: 32px;
        padding: 60px 68px;
        margin-top: 52px;
        box-shadow: 0 16px 48px rgba(80,60,120,0.07), inset 0 1px 0 rgba(255,255,255,0.9);
        color: #1d1d1f;
    }
    .guide-h2 {
        font-size: 1.25rem;
        font-weight: 800;
        color: #1d1d1f;
        border-bottom: 1px solid rgba(150,130,200,0.18);
        padding-bottom: 12px;
        margin-top: 48px;
        margin-bottom: 22px;
    }
    .guide-h3 {
        font-size: 1.05rem;
        font-weight: 700;
        color: #5c4f8a;
        margin-top: 26px;
        margin-bottom: 10px;
    }
    .guide-p { font-size: 16px; line-height: 1.85; color: #3a3050; }
</style>
""", unsafe_allow_html=True)


# ── 스크립트 실행 헬퍼 ──────────────────────────────────────────────────
def run_factory_script(filename, *args):
    script_path = os.path.join(PROJECT_DIR, filename)
    if not os.path.exists(script_path):
        st.error(f"🚨 '{filename}' 파일이 없습니다!")
        return -1
    try:
        cmd = [sys.executable, "-u", script_path, *args]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=PROJECT_DIR,
            bufsize=1,
        )

        progress_bar = st.progress(0)
        status_text  = st.empty()
        LOG_PATTERN  = re.compile(r"\[(\d+(?:\.\d+)?)/(\d+)\]\s*(.+)")

        for line in proc.stdout:
            stripped = line.strip()
            if any(kw in stripped for kw in ("Traceback", "Error", "Exception")):
                st.error(stripped)
                continue
            m = LOG_PATTERN.search(stripped)
            if m:
                current   = float(m.group(1))
                total     = int(m.group(2))
                task_name = m.group(3).strip()
                pct = min(current / total, 1.0)
                progress_bar.progress(pct)
                status_text.markdown(
                    f"<div style='"
                    f"background:rgba(255,255,255,0.58);"
                    f"backdrop-filter:blur(16px);"
                    f"border:1px solid rgba(255,255,255,0.82);"
                    f"border-radius:99px;"
                    f"padding:8px 20px;"
                    f"font-size:13px;"
                    f"font-weight:600;"
                    f"color:#3a3050;"
                    f"display:inline-block;"
                    f"box-shadow:0 4px 16px rgba(80,60,120,0.07);'>"
                    f"⚙️ &nbsp;진행 중: {task_name} &nbsp;"
                    f"<span style='color:rgba(92,79,138,0.55);font-weight:500;'>"
                    f"({current:g}/{total})</span></div>",
                    unsafe_allow_html=True,
                )

        proc.wait()

        if proc.returncode == 0:
            progress_bar.progress(1.0)
            status_text.markdown(
                "<div style='"
                "background:rgba(40,170,120,0.1);"
                "border:1px solid rgba(40,170,120,0.25);"
                "border-radius:99px;"
                "padding:8px 20px;"
                "font-size:13px;"
                "font-weight:700;"
                "color:#1a6a50;"
                "display:inline-block;'>"
                "✅ &nbsp;완료!</div>",
                unsafe_allow_html=True,
            )
        else:
            status_text.markdown(
                "<div style='"
                "background:rgba(255,80,60,0.08);"
                "border:1px solid rgba(255,80,60,0.22);"
                "border-radius:99px;"
                "padding:8px 20px;"
                "font-size:13px;"
                "font-weight:700;"
                "color:#b83232;"
                "display:inline-block;'>"
                "❌ &nbsp;오류가 발생했습니다. 위 에러 메시지를 확인하세요.</div>",
                unsafe_allow_html=True,
            )
        return proc.returncode

    except Exception as e:
        st.error(f"❌ 오류: {str(e)}")
        return -1


# ── Hero 키워드 필터링용 키워드 사전 ───────────────────────────────────
# 정치 기사(정당·선거·외교·정부 인사 등)는 법률 콘텐츠로 풀기 어렵고
# 민감하므로 크롤링 후보에서 제외합니다.
POLITICAL_KEYWORDS = [
    "대통령", "대통령실", "청와대", "대선", "총선", "지방선거", "보궐선거", "선거",
    "여당", "야당", "정당", "민주당", "국민의힘", "조국혁신당", "개혁신당",
    "국회", "의원", "원내대표", "당대표", "공천", "탄핵", "개헌", "지지율",
    "장관", "차관", "개각", "인사청문", "정부", "외교", "정상회담", "북한", "미사일",
    "여야", "친윤", "친명", "정치", "표결", "국정감사", "국정조사", "예산안",
]

# 법률적으로 풀어낼 수 있는 사건·분쟁 관련 키워드 (하나라도 포함되면 우선 채택)
LEGAL_KEYWORDS = [
    "고소", "고발", "소송", "재판", "판결", "선고", "기소", "구속", "체포", "압수수색",
    "검찰", "경찰", "법원", "변호사", "혐의", "피의자", "피해자", "가해자", "용의자",
    "처벌", "징역", "벌금", "실형", "집행유예", "항소", "상고", "유죄", "무죄",
    "사기", "횡령", "배임", "폭행", "상해", "절도", "강도", "협박", "감금", "살인",
    "성범죄", "성폭력", "성추행", "불법촬영", "스토킹", "음주운전", "뺑소니",
    "명예훼손", "모욕", "무고", "위증", "손해배상", "배상", "합의", "위자료",
    "상속", "이혼", "친권", "양육", "계약", "임대차", "전세사기", "보이스피싱",
    "학교폭력", "직장내괴롭힘", "산업재해", "위반", "불법", "적발", "송치", "입건",
]


def _is_political(text: str) -> bool:
    return any(kw in text for kw in POLITICAL_KEYWORDS)


def _is_legal(text: str) -> bool:
    return any(kw in text for kw in LEGAL_KEYWORDS)


# ── Hero 키워드 후보 크롤링/생성 ────────────────────────────────────────
def fetch_hero_candidates():
    """
    네이버 뉴스 사회 섹션을 가볍게 크롤링하여 헤드라인 기반 키워드 3개를 반환.
    - 정치 기사(정당·선거·외교 등)는 제외
    - 법률적으로 풀어낼 수 있는 사건·분쟁 헤드라인만 우선 채택
    크롤링 실패 시 기본 후보를 반환.
    """
    fallback = [
        "오늘의 사건사고 법률 이슈",
        "최신 판결 이슈 분석",
        "이번 주 화제의 법률 뉴스",
    ]
    try:
        url = "https://news.naver.com/section/102"  # 사회 섹션
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 헤드라인 텍스트 간단 추출 (og:title 또는 <a> 내 짧은 텍스트)
        titles = re.findall(r'<a[^>]+class="[^"]*headlines[^"]*"[^>]*>([^<]{8,40})</a>', html)
        if not titles:
            titles = re.findall(r'<strong[^>]*>([가-힣][^<]{5,35})</strong>', html)

        # 중복 제거 + 길이 필터
        headlines = list(dict.fromkeys([t.strip() for t in titles if len(t.strip()) >= 6]))

        # 1) 정치 기사 제외
        non_political = [h for h in headlines if not _is_political(h)]

        # 2) 법률 사건 관련 헤드라인 우선 채택
        legal_first = [h for h in non_political if _is_legal(h)]
        # 3) 법률 후보가 3개 미만이면 비정치 헤드라인으로 보충
        pool = list(dict.fromkeys(legal_first + non_political))[:8]

        if len(pool) >= 3:
            # 법률 관련 후보가 3개 이상이면 그 안에서, 아니면 pool에서 샘플
            base = legal_first if len(legal_first) >= 3 else pool
            return random.sample(base, 3)
        elif len(pool) > 0:
            return (pool + fallback)[:3]
        else:
            return fallback
    except Exception:
        return fallback


# ── Hub 키워드 후보 생성 ─────────────────────────────────────────────────
def fetch_hub_candidates():
    """
    네이버 자동완성/연관검색어 느낌의 정보성 키워드 풀에서 3~5개를 반환.
    실제 API 연동 없이 고품질 법률 정보성 키워드 풀을 구성하여 무작위 제공.
    """
    pool = [
        "민사소송 절차 총정리",
        "형사고소 방법과 주의사항",
        "계약서 작성 필수 체크리스트",
        "부동산 전세 사기 예방법",
        "상속 포기 한정승인 차이",
        "이혼 재산분할 기준 총정리",
        "근로계약서 없이 일했을 때 대처법",
        "명예훼손 고소 성립 요건",
        "개인파산 신청 조건과 절차",
        "교통사고 합의 요령과 주의점",
        "임대차 분쟁 해결 완벽 가이드",
        "소액심판 청구 방법과 비용",
        "성희롱 직장 내 대처 절차",
        "공정거래법 위반 신고 방법",
        "저작권 침해 대응 완벽 정리",
    ]
    return random.sample(pool, min(5, len(pool)))


# ── 이미지 헬퍼 ────────────────────────────────────────────────────────
def get_img_html(filename):
    img_path = os.path.join(PROJECT_DIR, filename)
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return (
            f'<img src="data:image/png;base64,{encoded}" '
            'style="width:100%; max-width:800px; border-radius:16px; '
            'margin:20px 0; box-shadow:0 8px 32px rgba(80,60,120,0.1);">'
        )
    return ""


# ════════════════════════════════════════════════════════════════════════
#  RENDER START
# ════════════════════════════════════════════════════════════════════════

# ── 타이틀 ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="factory-title">워드프레스 공장</div>
<div class="factory-subtitle">Automated WordPress Publishing · 3H Content Strategy</div>
""", unsafe_allow_html=True)


# ── 메인 5열 레이아웃: [키워드분석] [Hero] [Hub] [Help] [데이터분석] ─────
col1, col_hero, col_hub, col_help, col3 = st.columns([1, 1, 1, 1, 1], gap="medium")

# ── col1: 키워드 분석 ───────────────────────────────────────────────────
with col1:
    if st.session_state.factory_step == 1:
        st.markdown('<div class="active-engine">', unsafe_allow_html=True)
    if st.button("🔍\n\n키워드 분석", key="btn1"):
        with st.status("분석 중...", expanded=True):
            if run_factory_script("keyword_research.py") == 0:
                st.session_state.factory_step = 2
                st.session_state.active_type  = None  # 키워드 패널 닫기
                st.rerun()
    if st.session_state.factory_step == 1:
        st.markdown("</div>", unsafe_allow_html=True)

# ── col_hero: 🔥 Hero 버튼 ─────────────────────────────────────────────
with col_hero:
    if st.session_state.factory_step == 2:
        st.markdown('<div class="active-engine">', unsafe_allow_html=True)
    if st.button("🔥\n\nHero\n가십·이슈", key="btn_hero"):
        if st.session_state.active_type == "hero":
            # 이미 열려있으면 닫기
            st.session_state.active_type = None
        else:
            st.session_state.active_type = "hero"
            # 후보 새로 생성
            with st.spinner("뉴스 헤드라인 로딩 중..."):
                st.session_state.hero_candidates = fetch_hero_candidates()
        st.rerun()
    if st.session_state.factory_step == 2:
        st.markdown("</div>", unsafe_allow_html=True)

# ── col_hub: 📚 Hub 버튼 ───────────────────────────────────────────────
with col_hub:
    if st.session_state.factory_step == 2:
        st.markdown('<div class="active-engine">', unsafe_allow_html=True)
    if st.button("📚\n\nHub\n전문성·공유", key="btn_hub"):
        if st.session_state.active_type == "hub":
            st.session_state.active_type = None
        else:
            st.session_state.active_type = "hub"
            st.session_state.hub_candidates = fetch_hub_candidates()
        st.rerun()
    if st.session_state.factory_step == 2:
        st.markdown("</div>", unsafe_allow_html=True)

# ── col_help: 💡 Help 버튼 ─────────────────────────────────────────────
with col_help:
    if st.session_state.factory_step == 2:
        st.markdown('<div class="active-engine">', unsafe_allow_html=True)
    if st.button("💡\n\nHelp\n실전 해결", key="btn_help"):
        if st.session_state.active_type == "help":
            st.session_state.active_type = None
        else:
            st.session_state.active_type = "help"
            st.session_state.help_page   = 0
        st.rerun()
    if st.session_state.factory_step == 2:
        st.markdown("</div>", unsafe_allow_html=True)

# ── col3: 데이터 분석 ───────────────────────────────────────────────────
with col3:
    if st.button("📊\n\n데이터 분석", key="btn3"):
        st.session_state.show_data = not st.session_state.get("show_data", False)
        st.rerun()

if st.session_state.get("show_data", False):
    st.divider()
    if os.path.exists(CSV_PATH):
        st.dataframe(pd.read_csv(CSV_PATH, encoding="utf-8-sig"), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════
#  2단계 키워드 선택 패널 (Hero / Hub / Help 각각)
# ════════════════════════════════════════════════════════════════════════

active = st.session_state.get("active_type")

# ─────────────────────────────────────────────────────────────────────
#  🔥 HERO 키워드 패널
# ─────────────────────────────────────────────────────────────────────
if active == "hero" and st.session_state.factory_step == 2:
    st.markdown("""
    <div class="kw-panel">
        <div class="kw-panel-title">🔥 Hero — 이슈/가십 키워드 선택</div>
        <div class="kw-panel-sub">
            네이버 뉴스 사건사고 헤드라인 기반 추천 키워드입니다.<br>
            라디오 버튼으로 선택하거나, 직접 입력하세요.<br>
            <b>직접 입력값이 있으면 라디오 선택은 무시됩니다.</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    candidates = st.session_state.hero_candidates or fetch_hero_candidates()

    col_r1, col_r2 = st.columns([3, 1])
    with col_r1:
        hero_radio = st.radio(
            "현재 이슈 기반 추천 키워드",
            options=candidates,
            key="hero_radio",
            label_visibility="visible",
        )
    with col_r2:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 다른 키워드 후보 추출", key="hero_refresh"):
            with st.spinner("헤드라인 재크롤링 중..."):
                st.session_state.hero_candidates = fetch_hero_candidates()
            st.rerun()

    hero_manual = st.text_input(
        "✏️ 직접 입력 (입력 시 라디오 무시)",
        placeholder="예: 강남 살인사건 법률 해석",
        key="hero_manual",
    )

    st.markdown("<hr class='kw-divider'>", unsafe_allow_html=True)

    if st.button("✍️ 포스팅 최종 생성하기", key="hero_submit", type="primary"):
        final_keyword = hero_manual.strip() if hero_manual.strip() else hero_radio
        with st.status(f"🔥 Hero 포스팅 생성 중 — 키워드: {final_keyword}", expanded=True):
            ret = run_factory_script(
                "wp_content_generator.py",
                "--type", "hero",
                "--keyword", final_keyword,
            )
            if ret == 0:
                st.session_state.factory_step = 3
                st.session_state.active_type  = None
                st.rerun()

# ─────────────────────────────────────────────────────────────────────
#  📚 HUB 키워드 패널
# ─────────────────────────────────────────────────────────────────────
elif active == "hub" and st.session_state.factory_step == 2:
    st.markdown("""
    <div class="kw-panel">
        <div class="kw-panel-title">📚 Hub — 정보성/검색어 키워드 선택</div>
        <div class="kw-panel-sub">
            네이버 연관검색어·자동완성 스타일의 정보성 키워드 후보입니다.<br>
            라디오 버튼으로 선택하거나, 직접 입력하세요.<br>
            <b>직접 입력값이 있으면 라디오 선택은 무시됩니다.</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    candidates = st.session_state.hub_candidates or fetch_hub_candidates()

    col_r1, col_r2 = st.columns([3, 1])
    with col_r1:
        hub_radio = st.radio(
            "정보성 추천 키워드",
            options=candidates,
            key="hub_radio",
            label_visibility="visible",
        )
    with col_r2:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 다른 키워드 불러오기", key="hub_refresh"):
            st.session_state.hub_candidates = fetch_hub_candidates()
            st.rerun()

    hub_manual = st.text_input(
        "✏️ 직접 입력 (입력 시 라디오 무시)",
        placeholder="예: 전세 사기 피해 대처법",
        key="hub_manual",
    )

    st.markdown("<hr class='kw-divider'>", unsafe_allow_html=True)

    if st.button("✍️ 포스팅 최종 생성하기", key="hub_submit", type="primary"):
        final_keyword = hub_manual.strip() if hub_manual.strip() else hub_radio
        with st.status(f"📚 Hub 포스팅 생성 중 — 키워드: {final_keyword}", expanded=True):
            ret = run_factory_script(
                "wp_content_generator.py",
                "--type", "hub",
                "--keyword", final_keyword,
            )
            if ret == 0:
                st.session_state.factory_step = 3
                st.session_state.active_type  = None
                st.rerun()

# ─────────────────────────────────────────────────────────────────────
#  💡 HELP 키워드 패널
# ─────────────────────────────────────────────────────────────────────
elif active == "help" and st.session_state.factory_step == 2:
    st.markdown("""
    <div class="kw-panel">
        <div class="kw-panel-title">💡 Help — 수익성/CSV 키워드 선택</div>
        <div class="kw-panel-sub">
            keywords.csv 점수 상위 키워드입니다. 페이지를 넘겨 원하는 키워드를 선택하세요.<br>
            라디오 버튼으로 선택하거나, 직접 입력하세요.<br>
            <b>직접 입력값이 있으면 라디오 선택은 무시됩니다.</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if os.path.exists(CSV_PATH):
        df_kw = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

        # 점수 컬럼 자동 감지 (score, 점수, Score 등)
        score_cols = [c for c in df_kw.columns if "score" in c.lower() or "점수" in c]
        if score_cols:
            df_kw = df_kw.sort_values(score_cols[0], ascending=False).reset_index(drop=True)

        keyword_col = "keyword" if "keyword" in df_kw.columns else df_kw.columns[0]
        all_keywords = df_kw[keyword_col].dropna().tolist()

        page      = st.session_state.help_page          # 0, 1, 2
        start_idx = page * 5
        end_idx   = start_idx + 5
        page_kws  = all_keywords[start_idx:end_idx]

        # 페이지 라벨
        page_label = f"{start_idx+1}위 ~ {min(end_idx, len(all_keywords))}위"
        st.caption(f"📄 현재 표시: **{page_label}** (총 {len(all_keywords)}개)")

        col_r1, col_r2 = st.columns([3, 1])
        with col_r1:
            if page_kws:
                help_radio = st.radio(
                    "CSV 상위 키워드",
                    options=page_kws,
                    key=f"help_radio_{page}",
                    label_visibility="visible",
                )
            else:
                st.warning("이 페이지에 키워드가 없습니다.")
                help_radio = None
        with col_r2:
            st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
            # 다음 페이지 버튼 (순환)
            total_pages = max(1, (len(all_keywords) + 4) // 5)
            next_label  = f"🔄 다음 키워드 목록 보기\n({((page+1)%total_pages)*5+1}위~)"
            if st.button(next_label, key="help_next_page"):
                st.session_state.help_page = (page + 1) % total_pages
                st.rerun()
    else:
        st.warning("⚠️ keywords.csv 파일이 없습니다. 먼저 키워드 분석을 실행하세요.")
        help_radio = None

    help_manual = st.text_input(
        "✏️ 직접 입력 (입력 시 라디오 무시)",
        placeholder="예: 교통사고 합의 요령",
        key="help_manual",
    )

    st.markdown("<hr class='kw-divider'>", unsafe_allow_html=True)

    if st.button("✍️ 포스팅 최종 생성하기", key="help_submit", type="primary"):
        if help_manual.strip():
            final_keyword = help_manual.strip()
        elif help_radio:
            final_keyword = help_radio
        else:
            st.error("키워드를 선택하거나 직접 입력해 주세요.")
            st.stop()

        with st.status(f"💡 Help 포스팅 생성 중 — 키워드: {final_keyword}", expanded=True):
            ret = run_factory_script(
                "wp_content_generator.py",
                "--type", "help",
                "--keyword", final_keyword,
            )
            if ret == 0:
                st.session_state.factory_step = 3
                st.session_state.active_type  = None
                st.rerun()


# ── 진행 단계 표시 ──────────────────────────────────────────────────────
st.markdown("<div style='margin-top:52px;'></div>", unsafe_allow_html=True)

step_info = {
    1: ("○ ○ ○", "1단계 대기 중",   0.0),
    2: ("● ○ ○", "2단계 준비 완료", 0.5),
    3: ("● ● ●", "모든 공정 완료",  1.0),
}
icon, label, prog = step_info.get(st.session_state.factory_step, ("○ ○ ○", "대기 중", 0.0))

st.markdown(f'<div class="step-badge">{icon}&nbsp;&nbsp;{label}</div>', unsafe_allow_html=True)
st.progress(prog)


# ── 완료 시: 스니펫 복사 박스 ──────────────────────────────────────────
if st.session_state.factory_step == 3:
    if os.path.exists(SNIPPET_PATH):
        with open(SNIPPET_PATH, "r", encoding="utf-8") as f:
            snippet_data = json.load(f)

        _type = snippet_data.get("content_type", "")
        badge_map = {
            "hero": ("badge-hero", "🔥 Hero"),
            "hub":  ("badge-hub",  "📚 Hub"),
            "help": ("badge-help", "💡 Help"),
        }
        badge_cls, badge_label = badge_map.get(_type, ("badge-help", _type.upper()))

        st.markdown(f"""
        <div class="snippet-box">
            <div class="snippet-title">
                RankMath 스니펫 복사 박스
                <span class="type-badge {badge_cls}">{badge_label}</span>
            </div>
            <div class="snippet-sub">아래 내용을 워드프레스 RankMath 스니펫 편집기에 그대로 붙여넣으세요.</div>
        </div>
        """, unsafe_allow_html=True)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.text_input("📌 제목 (Title)", value=snippet_data.get("title", ""))
        with col_s2:
            st.text_input("🔗 퍼머링크 (Permalink)", value=snippet_data.get("permalink", ""))
        st.text_area("📝 설명 (Description)", value=snippet_data.get("description", ""), height=100)

    st.markdown("""
    <div style="text-align:center; margin-top:32px;">
        <a href="https://law-brief.kr/wp-admin/" target="_blank" class="link-button">
            🚀&nbsp; 글 확인하기 — 워드프레스 이동
        </a>
    </div>
    """, unsafe_allow_html=True)


# ── 이미지 헬퍼 ────────────────────────────────────────────────────────
def get_img_html(filename):
    img_path = os.path.join(PROJECT_DIR, filename)
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return (
            f'<img src="data:image/png;base64,{encoded}" '
            'style="width:100%; max-width:800px; border-radius:16px; '
            'margin:20px 0; box-shadow:0 8px 32px rgba(80,60,120,0.1);">'
        )
    return ""


# ── 가이드 섹션 ────────────────────────────────────────────────────────
guide_html = f"""
<div class="guide-wrap">

<h1 style="text-align:center; font-size:2rem; font-weight:900; letter-spacing:-0.03em;
    background:linear-gradient(135deg,#3a2f6b 0%,#8b5e52 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text; margin-bottom:52px;">워드프레스 검수 가이드</h1>

<!-- 0. 3H 전략 -->
<h2 class="guide-h2" style="margin-top:0;">0. 성공적인 블로그 운영을 위한 3H 발행 비율</h2>
<p class="guide-p" style="margin-bottom:26px;">
구글이 사랑하는 콘텐츠 믹스 전략입니다. 세 유형을 적절히 섞어 발행하면 검색 유입 · 브랜딩 · 재방문이 동시에 완성됩니다.
</p>

<div style="display:flex; gap:14px; margin-bottom:16px; flex-wrap:wrap;">
    <div style="flex:1; min-width:190px; background:rgba(40,170,120,0.07);
        border:1px solid rgba(40,170,120,0.18); border-radius:20px; padding:24px 22px;">
        <div style="font-size:28px; margin-bottom:8px;">💡</div>
        <h3 style="color:#1a6a50; margin:0 0 8px; font-size:1rem; font-weight:800;">Help — 60%</h3>
        <p style="font-size:13.5px; line-height:1.75; color:#1a5040; margin:0;">
        매일 꾸준히 발행. 검색 유입의 핵심.<br>
        실제 고민·문제 해결 중심의 실용 정보.<br>
        롱테일 키워드로 자연 검색 트래픽 축적.
        </p>
    </div>
    <div style="flex:1; min-width:190px; background:rgba(70,120,240,0.07);
        border:1px solid rgba(70,120,240,0.18); border-radius:20px; padding:24px 22px;">
        <div style="font-size:28px; margin-bottom:8px;">📚</div>
        <h3 style="color:#1a4ec4; margin:0 0 8px; font-size:1rem; font-weight:800;">Hub — 30%</h3>
        <p style="font-size:13.5px; line-height:1.75; color:#0d3580; margin:0;">
        주 1~2회 발행. 전문성 강조 콘텐츠.<br>
        공유하고 싶은 법률 상식·가이드 심화 글.<br>
        구독자 재방문과 브랜드 신뢰도 향상.
        </p>
    </div>
    <div style="flex:1; min-width:190px; background:rgba(255,90,70,0.06);
        border:1px solid rgba(255,90,70,0.18); border-radius:20px; padding:24px 22px;">
        <div style="font-size:28px; margin-bottom:8px;">🔥</div>
        <h3 style="color:#b83232; margin:0 0 8px; font-size:1rem; font-weight:800;">Hero — 10%</h3>
        <p style="font-size:13.5px; line-height:1.75; color:#7f1010; margin:0;">
        월 1~2회 발행. 가십·이슈형 폭발 트래픽.<br>
        시의성 높은 사건·판결과 법률 연결.<br>
        SNS 확산 + 단기 대규모 유입.
        </p>
    </div>
</div>

<div style="background:rgba(92,79,138,0.06); border-radius:14px; padding:16px 22px;
    border-left:4px solid rgba(92,79,138,0.35); margin-bottom:8px;">
    <span style="font-weight:700; color:#5c4f8a; font-size:14px;">💡 전략 핵심 </span>
    <span style="font-size:14px; color:#3a3050;">Help로 기반을 쌓고, Hub로 권위를 키우고, Hero로 폭발시킨다.</span>
</div>

<!-- 1 -->
<h2 class="guide-h2">1. 워드프레스 임시글 확인 및 진입</h2>
<p class="guide-p">
포스팅 생성이 완료되면 워드프레스 관리자 페이지의 <b>[글] &gt; [모든 글]</b> 메뉴로 접속하세요. 목록에서 작성된 제목을 클릭하여 편집 화면으로 들어갑니다.
</p>
{get_img_html("step1.png")}

<!-- 2 -->
<h2 class="guide-h2">2. 검수 / RankMath SEO 설정 (중요)</h2>
<p class="guide-p">AI가 작성한 글을 사람이 최종적으로 다듬어 문맥상 이상한 부분이 없는지 체크하는 단계입니다.</p>

<h3 class="guide-h3">1) 스니펫 편집</h3>
<div style="background:rgba(92,79,138,0.06); border-radius:14px; padding:18px 22px;
    border-left:4px solid rgba(92,79,138,0.3); font-size:14.5px; line-height:1.8; margin-bottom:18px;">
    <b>🎉 제미나이 복사/붙여넣기 작업이 생략되었습니다!</b><br><br>
    포스팅 생성 완료 후 화면에 표시되는 <b>RankMath 스니펫 복사 박스</b>에서 제목·퍼머링크·설명을
    복사해 워드프레스 우측 RankMath 스니펫 편집기에 붙여넣으시면 끝입니다.
</div>
{get_img_html("step2.png")}
{get_img_html("step2-1.png")}

<h3 class="guide-h3">2) 포커스 키워드</h3>
<p class="guide-p">제목 맨 첫번째 키워드를 삽입합니다.</p>
{get_img_html("step2-2.png")}

<h3 class="guide-h3">3) Rank Math 초록불 만들기</h3>
<p class="guide-p">기본 SEO, 추가, 제목 가독성, 콘텐츠 가독성이 모두 초록색 ✓ 표시가 되도록 보완합니다.</p>
{get_img_html("step2-3.png")}
{get_img_html("step2-4.png")}

<div style="background:rgba(245,245,250,0.65); border-radius:18px; padding:26px 28px; margin-top:32px;">
<h3 style="font-size:1rem; font-weight:700; color:#5c4f8a; margin-top:0;">💡 4) 기타 경고 안내 (무시 가능)</h3>
<p style="font-size:14.5px; line-height:1.8; margin-bottom:10px;">
    <b>"Table of Contents plugin를 사용하지 않는 것 같습니다."</b><br>
    <span style="color:#666;">공장에서 구글이 선호하는 수제 HTML 목차를 자동 생성합니다. 특정 플러그인을 찾지 못한 경고이며 노출에 전혀 지장 없습니다.</span>
</p>
<p style="font-size:14.5px; line-height:1.8; margin:0;">
    <b>"Content AI를 사용하여 Post를 최적화하십시오."</b><br>
    <span style="color:#666;">RankMath 유료 서비스 광고입니다. 무시하세요.</span>
</p>
</div>

<!-- 3 -->
<h2 class="guide-h2">3. 공개일정 예약</h2>
<p class="guide-p">
구글 애드센스 승인을 위해 20개 중 <b>하루에 10개는 즉시 업로드</b>하고, 나머지 10개는 <b>매일 오전 9시 발행</b>되도록 예약 걸어두세요.
</p>
{get_img_html("step3.png")}
{get_img_html("step3-1.png")}
{get_img_html("step3-2.png")}
{get_img_html("step4.png")}

</div>
"""

st.markdown(guide_html, unsafe_allow_html=True)

st.markdown(
    f"<div style='text-align:center; color:rgba(80,60,120,0.3); margin-top:28px; "
    f"font-size:11.5px; letter-spacing:0.1em;'>{BUILD_TAG}</div>",
    unsafe_allow_html=True,
)
