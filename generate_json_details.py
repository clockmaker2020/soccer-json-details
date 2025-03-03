import os
import json
import requests
from datetime import datetime, timedelta

# ✅ API 설정
API_KEY = "0776a35eb1067086efe59bb7f93c6498"
LEAGUE_ID = 39  # 프리미어리그 ID
SEASON = 2024
HEADERS = {"x-apisports-key": API_KEY}

# ✅ 저장할 폴더 설정
DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ✅ 기존 JSON 파일 삭제 (새로운 데이터로 대체)
for file in os.listdir(DATA_DIR):
    if file.endswith(".json"):
        os.remove(os.path.join(DATA_DIR, file))

print(f"🗑️ 기존 JSON 파일 삭제 완료.")

# ✅ API 요청 함수
def fetch_data(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json().get("response", [])
    except requests.exceptions.RequestException as e:
        print(f"⚠️ [ERROR] API 요청 실패: {e}")
        return []

# ✅ 오늘부터 한 달간의 경기 ID 가져오기
today = datetime.utcnow().strftime("%Y-%m-%d")
one_month_later = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")

fixture_url = f"https://v3.football.api-sports.io/fixtures?league={LEAGUE_ID}&season={SEASON}&from={today}&to={one_month_later}"
fixtures = fetch_data(fixture_url)

# ✅ 개별 경기 상세 정보 저장
for fixture in fixtures:
    match_id = fixture["fixture"]["id"]
    detail_url = f"https://v3.football.api-sports.io/fixtures?id={match_id}"
    match_details = fetch_data(detail_url)

    if not match_details:
        continue

    match_data = match_details[0]  # 첫 번째 응답 데이터 사용
    fixture = match_data["fixture"]
    teams = match_data["teams"]
    odds = match_data.get("odds", {})
    stats = match_data.get("statistics", [])
    events = match_data.get("events", [])

    # 🕒 UTC → KST 변환
    utc_time = datetime.strptime(fixture["date"], "%Y-%m-%dT%H:%M:%S%z")
    kst_time = utc_time + timedelta(hours=9)

    # ✅ 경기 개요 + 경기 예상 정보 (변하지 않는 데이터)
    match_static_json = {
        "1. 경기 개요": {
            "경기 ID": match_id,
            "경기 날짜": kst_time.strftime("%Y-%m-%d %H:%M"),
            "경기장": fixture["venue"]["name"],
            "도시": fixture["venue"]["city"],
            "경기 상태": fixture["status"]["long"]
        },
        "2. 경기 예상 정보": {
            "배당률": {
                "홈 승리 확률": odds.get("home", "N/A"),
                "무승부 확률": odds.get("draw", "N/A"),
                "원정 승리 확률": odds.get("away", "N/A")
            },
            "최근 맞대결": [
                {
                    "경기 날짜": h2h["fixture"]["date"],
                    "홈팀": h2h["teams"]["home"]["name"],
                    "원정팀": h2h["teams"]["away"]["name"],
                    "스코어": h2h["score"]["fulltime"]
                }
                for h2h in fetch_data(f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={teams['home']['id']}-{teams['away']['id']}")
            ],
            "부상 선수": fetch_data(f"https://v3.football.api-sports.io/injuries?league={LEAGUE_ID}&season={SEASON}"),
            "예상 선발": fetch_data(f"https://v3.football.api-sports.io/fixtures/lineups?fixture={match_id}")
        },
        "블로그 URL": ""
    }

    # ✅ 실시간 경기 정보 (업데이트 시만 갱신)
    match_live_json = {
        "3. 실시간 경기 정보": {
            "현재 점수": f"{match_data['goals']['home']} - {match_data['goals']['away']}",
            "득점 기록": match_data["score"]["fulltime"],
            "주요 경기 이벤트": [
                {
                    "이벤트 종류": event["type"],
                    "선수": event["player"]["name"],
                    "팀": event["team"]["name"],
                    "시간": event["time"]["elapsed"]
                }
                for event in events
            ],
            "경기 통계": {
                stat["type"]: {
                    "홈팀": stat["statistics"][0]["value"],
                    "원정팀": stat["statistics"][1]["value"]
                }
                for stat in stats
            }
        }
    }

    # ✅ JSON 파일 저장 (파일명을 경기 ID 기반으로 변경)
    static_path = os.path.join(DATA_DIR, f"match_{match_id}.json")
    live_path = os.path.join(DATA_DIR, f"match_{match_id}_live.json")
    
    with open(static_path, "w", encoding="utf-8") as file:
        json.dump(match_static_json, file, indent=4, ensure_ascii=False)
    
    with open(live_path, "w", encoding="utf-8") as file:
        json.dump(match_live_json, file, indent=4, ensure_ascii=False)
    
    print(f"✅ 경기 개요 저장 완료: {static_path}")
    print(f"✅ 실시간 데이터 저장 완료: {live_path}")

