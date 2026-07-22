"""
네이버 검색광고 API - 연관 키워드 발굴
시드 키워드: 음주운전, 명예훼손, 형사고소
필터: PC + 모바일 합산 월 검색량 >= 1,500
"""

import os
import time
import hmac
import hashlib
import base64
import csv
import requests
from dotenv import load_dotenv

# 🚨 [핵심 수정 1] 사장님 맥북 경로를 지우고, 현재 파일 위치를 스스로 찾도록 변경했습니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 찾아낸 위치를 기반으로 .env 파일을 불러옵니다.
load_dotenv(os.path.join(BASE_DIR, ".env"))

BASE_URL = "https://api.searchad.naver.com"
API_KEY = os.getenv("NAVER_AD_ACCESS_KEY")
SECRET_KEY = os.getenv("NAVER_AD_SECRET_KEY")
CUSTOMER_ID = os.getenv("NAVER_AD_CUSTOMER_ID")

SEED_KEYWORDS = ["음주운전", "명예훼손", "형사고소"]
MIN_VOLUME = 1500

# 🚨 [핵심 수정 2] CSV 파일 저장 경로도 서버의 현재 폴더로 자동 지정되게 변경했습니다.
OUTPUT_CSV = os.path.join(BASE_DIR, "keywords.csv")


def make_signature(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    message = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def get_headers(method: str, uri: str) -> dict:
    timestamp = str(int(time.time() * 1000))
    return {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Timestamp": timestamp,
        "X-API-KEY": API_KEY,
        "X-Customer": str(CUSTOMER_ID),
        "X-Signature": make_signature(timestamp, method, uri, SECRET_KEY),
    }


def parse_volume(value) -> int:
    """네이버 API는 검색량이 10 미만이면 '< 10' 문자열을 반환"""
    if isinstance(value, str):
        v = value.replace("<", "").replace(",", "").strip()
        try:
            return int(v)
        except ValueError:
            return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def fetch_related_keywords(seed: str, max_retries: int = 3) -> list[dict]:
    uri = "/keywordstool"
    params = {"hintKeywords": seed, "showDetail": "1"}

    last_err = None
    for attempt in range(1, max_retries + 1):
        # 재시도마다 새 서명/타임스탬프를 생성해야 인증 오류를 피할 수 있습니다.
        headers = get_headers("GET", uri)
        try:
            resp = requests.get(
                BASE_URL + uri,
                params=params,
                headers=headers,
                # (연결 타임아웃, 읽기 타임아웃) - 읽기를 넉넉히 확보
                timeout=(10, 60),
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("keywordList", [])
        except requests.exceptions.Timeout as e:
            last_err = e
            wait = attempt * 2
            print(f"  ~ 타임아웃(시도 {attempt}/{max_retries}) - {wait}초 후 재시도")
            time.sleep(wait)
        except requests.exceptions.ConnectionError as e:
            last_err = e
            wait = attempt * 2
            print(f"  ~ 연결 실패(시도 {attempt}/{max_retries}) - {wait}초 후 재시도")
            time.sleep(wait)

    # 모든 재시도 실패 시 마지막 예외를 올려 호출부에서 처리
    raise last_err


def main():
    # 🚨 [수정] 자격증명 누락 시 조용히 타임아웃/서명오류로 죽지 않도록 먼저 검증
    missing = [
        name
        for name, val in (
            ("NAVER_AD_ACCESS_KEY", API_KEY),
            ("NAVER_AD_SECRET_KEY", SECRET_KEY),
            ("NAVER_AD_CUSTOMER_ID", CUSTOMER_ID),
        )
        if not val
    ]
    if missing:
        print(f"  ! 환경변수 누락: {', '.join(missing)}")
        print("    Streamlit Secrets 또는 .env 에 네이버 검색광고 API 키를 등록하세요.")
        return 1

    all_rows = []
    seen = set()
    failed_seeds = []

    total_seeds = len(SEED_KEYWORDS)
    for idx, seed in enumerate(SEED_KEYWORDS, start=1):
        print(f"[{idx}/{total_seeds}] 시드 키워드 수집: {seed}")
        try:
            items = fetch_related_keywords(seed)
        except requests.HTTPError as e:
            body = ""
            if e.response is not None:
                body = e.response.text[:200]
            print(f"  ! API 응답 오류: {e} - {body}")
            failed_seeds.append(seed)
            continue
        except requests.exceptions.RequestException as e:
            # 타임아웃/연결오류 등 네트워크 계열 예외를 모두 흡수 (스크립트 크래시 방지)
            print(f"  ! 네트워크 오류로 '{seed}' 건너뜀: {type(e).__name__}")
            failed_seeds.append(seed)
            continue
        print(f"  - 응답 키워드 수: {len(items)}")

        kept = 0
        for it in items:
            kw = it.get("relKeyword", "").strip()
            if not kw or kw in seen:
                continue
            pc = parse_volume(it.get("monthlyPcQcCnt", 0))
            mo = parse_volume(it.get("monthlyMobileQcCnt", 0))
            total = pc + mo
            if total < MIN_VOLUME:
                continue
            seen.add(kw)
            all_rows.append(
                {
                    "seed": seed,
                    "keyword": kw,
                    "pc_volume": pc,
                    "mobile_volume": mo,
                    "total_volume": total,
                    "competition": it.get("compIdx", ""),
                    "pc_click_avg": it.get("monthlyAvePcClkCnt", 0),
                    "mobile_click_avg": it.get("monthlyAveMobileClkCnt", 0),
                }
            )
            kept += 1
        print(f"  - 1,500회 이상 통과: {kept}개")
        time.sleep(0.3)

    # 🚨 [수정] 수집 결과가 하나도 없으면 기존 keywords.csv 를 빈 값으로 덮어쓰지 않음
    if not all_rows:
        print("  ! 수집된 키워드가 없습니다. 기존 keywords.csv 를 유지합니다.")
        if failed_seeds:
            print(f"    (실패한 시드: {', '.join(failed_seeds)})")
        return 1

    all_rows.sort(key=lambda r: r["total_volume"], reverse=True)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "seed",
            "keyword",
            "pc_volume",
            "mobile_volume",
            "total_volume",
            "competition",
            "pc_click_avg",
            "mobile_click_avg",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n[완료] 저장: {OUTPUT_CSV}")
    print(f"[완료] 총 {len(all_rows)}개 키워드 수집")
    print("\n[상위 20개]")
    print(f"{'키워드':<25} {'PC':>8} {'모바일':>8} {'합계':>8} {'경쟁':>5}")
    for r in all_rows[:20]:
        print(
            f"{r['keyword']:<25} {r['pc_volume']:>8} {r['mobile_volume']:>8} "
            f"{r['total_volume']:>8} {str(r['competition']):>5}"
        )


if __name__ == "__main__":
    import sys

    sys.exit(main() or 0)