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

# ... (이전 설정 및 fetch_data 함수 정의는 그대로 유지) ...

# ✅ 오늘부터 한 달간의 경기 일정 가져오기 (변경 없음)
today = datetime.utcnow().strftime("%Y-%m-%d")
one_month_later = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
fixture_url = f"https://v3.football.api-sports.io/fixtures?league={LEAGUE_ID}&season={SEASON}&from={today}&to={one_month_later}"
fixtures = fetch_data(fixture_url)

# ✅ 개별 경기 상세 정보 처리
for fixture in fixtures:
    match_id = fixture["fixture"]["id"]
    detail_url = f"https://v3.football.api-sports.io/fixtures?id={match_id}"
    match_details = fetch_data(detail_url)
    if not match_details:
        continue

    match_data = match_details[0]
    fixture_info = match_data["fixture"]
    teams = match_data["teams"]
    odds = match_data.get("odds", {})          # 승률/배당률 정보
    events = match_data.get("events", [])      # 경기 이벤트 리스트
    stats = match_data.get("statistics", [])   # 경기 통계 (필요 시 사용)
    league_info = match_data.get("league", {}) # 리그 정보 (이름, 라운드 등)

    # 🕒 UTC 시간 -> KST 시간 변환
    utc_time = datetime.strptime(fixture_info["date"], "%Y-%m-%dT%H:%M:%S%z")
    kst_time = utc_time + timedelta(hours=9)

    # 1. 🏟 경기 개요 데이터
    overview_data = {
        "경기 ID": match_id,
        "경기 날짜": kst_time.strftime("%Y-%m-%d %H:%M"),      # 한국시간 날짜 및 시간
        "경기장": fixture_info["venue"]["name"],
        "도시": fixture_info["venue"]["city"],
        "경기 상태": fixture_info["status"]["long"],
        "리그": league_info.get("name", "N/A"),
        "라운드": league_info.get("round", "N/A"),
        "심판": fixture_info.get("referee", "N/A") or "N/A",
        "관중 수": fixture_info.get("attendance", "N/A") or "N/A"
    }

    # 2. 💰 승률 및 배당률 데이터
    odds_data = {
        "홈 승리 확률": odds.get("home", "N/A"),
        "무승부 확률": odds.get("draw", "N/A"),
        "원정 승리 확률": odds.get("away", "N/A")
    }

    # 3. ⚽ 팀 정보 데이터 (팀 이름 및 로고)
    teams_data = {
        "홈팀": {
            "이름": teams["home"]["name"],
            "로고": teams["home"]["logo"]
        },
        "원정팀": {
            "이름": teams["away"]["name"],
            "로고": teams["away"]["logo"]
        }
    }

    # 4. 🔥 최근 맞대결(H2H) 데이터 (두 팀간 최근 경기 기록 몇 경기만)
    h2h_url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={teams['home']['id']}-{teams['away']['id']}"
    h2h_matches = fetch_data(h2h_url)
    h2h_data = []
    if h2h_matches:
        # 최신 경기순으로 정렬 후 상위 5경기만 선택
        h2h_matches.sort(key=lambda x: x["fixture"]["date"], reverse=True)
        recent_h2h = h2h_matches[:5]
        for h2h in recent_h2h:
            # 날짜를 한국시간 기준 날짜로 변환 (시간은 생략)
            try:
                h2h_date = datetime.strptime(h2h["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
                h2h_date_kst = h2h_date + timedelta(hours=9)
                date_str = h2h_date_kst.strftime("%Y-%m-%d")
            except Exception:
                date_str = h2h["fixture"]["date"][:10]  # 변환 실패 시 날짜 부분만 사용
            # 득점 결과 문자열 생성 (예: "2 - 1")
            score = h2h.get("score", {}).get("fulltime", {})
            if score:
                home_goals = score.get("home")
                away_goals = score.get("away")
                score_str = f"{home_goals} - {away_goals}" if home_goals is not None and away_goals is not None else " - "
            else:
                score_str = " - "
            h2h_data.append({
                "경기 날짜": date_str,
                "홈팀": h2h["teams"]["home"]["name"],
                "원정팀": h2h["teams"]["away"]["name"],
                "스코어": score_str
            })

    # 5. 🚑 부상 선수 데이터 (해당 경기 두 팀 관련 부상 목록만)
    injuries_url = f"https://v3.football.api-sports.io/injuries?league={LEAGUE_ID}&season={SEASON}"
    injuries_response = fetch_data(injuries_url)
    injuries_data = []
    if injuries_response:
        # 응답 구조에 따라 분기 (팀별 그룹 vs 개별 부상 리스트)
        if "players" in injuries_response[0]:
            # 팀별로 묶인 경우
            for team_entry in injuries_response:
                team_info = team_entry.get("team", {})
                if team_info.get("id") in [teams["home"]["id"], teams["away"]["id"]]:
                    team_name = team_info.get("name", "N/A")
                    for player in team_entry.get("players", []):
                        # 선수 이름과 부상/결장 사유, 부상 발생 날짜 추출
                        if "name" in player:
                            player_name = player.get("name", "N/A")
                            reason = player.get("reason") or player.get("type") or "N/A"
                            inj_date = player.get("date") or player.get("since")
                        elif "player" in player:
                            player_name = player["player"].get("name", "N/A")
                            reason = player.get("reason") or player["player"].get("type") or "N/A"
                            inj_date = player.get("date") or player.get("since") or player.get("fixture", {}).get("date")
                        else:
                            continue
                        # 날짜 형식 정리 (YYYY-MM-DD)
                        if inj_date:
                            try:
                                inj_date_obj = datetime.fromisoformat(inj_date)
                                inj_date_str = inj_date_obj.strftime("%Y-%m-%d")
                            except Exception:
                                inj_date_str = str(inj_date)
                        else:
                            inj_date_str = "N/A"
                        injuries_data.append({
                            "선수": player_name,
                            "부상 부위": reason,
                            "부상 날짜": inj_date_str,
                            "소속팀": team_name
                        })
        else:
            # 개별 부상 리스트인 경우
            for entry in injuries_response:
                team_info = entry.get("team", {})
                if team_info.get("id") not in [teams["home"]["id"], teams["away"]["id"]]:
                    continue  # 해당 경기 팀이 아니면 건너뜀
                team_name = team_info.get("name", "N/A")
                player_info = entry.get("player", {})
                player_name = player_info.get("name", "N/A")
                # 부상 종류 및 날짜 추출
                reason = entry.get("reason") or entry.get("type") or player_info.get("type") or "N/A"
                inj_date = entry.get("fixture", {}).get("date") or player_info.get("since") or player_info.get("date")
                if inj_date:
                    try:
                        inj_date_obj = datetime.fromisoformat(inj_date)
                        inj_date_str = inj_date_obj.strftime("%Y-%m-%d")
                    except Exception:
                        inj_date_str = str(inj_date)
                else:
                    inj_date_str = "N/A"
                injuries_data.append({
                    "선수": player_name,
                    "부상 부위": reason,
                    "부상 날짜": inj_date_str,
                    "소속팀": team_name
                })

    # 6. ⏳ 실시간 경기 정보 데이터 (득점 현황, 이벤트 등)
    current_score = f"{match_data['goals']['home']} - {match_data['goals']['away']}"
    # 풀타임 득점 기록 (경기 종료 시 업데이트됨)
    fulltime_score = match_data.get("score", {}).get("fulltime", {})
    if fulltime_score:
        if fulltime_score.get("home") is not None and fulltime_score.get("away") is not None:
            goal_record = f"{fulltime_score['home']} - {fulltime_score['away']}"
        else:
            goal_record = " - "
    else:
        goal_record = " - "
    live_data = {
        "현재 점수": current_score,
        "득점 기록": goal_record,
        "주요 경기 이벤트": [
            {
                "이벤트 종류": event.get("type", "N/A"),
                "선수": event.get("player", {}).get("name", "N/A"),
                "팀": event.get("team", {}).get("name", "N/A"),
                "시간": event.get("time", {}).get("elapsed", "N/A")
            }
            for event in events
        ]
    }

    # ✅ JSON 파일로 저장 (경기ID와 항목별로 파일명 지정)
    base_path = os.path.join(DATA_DIR, f"match_{match_id}")
    with open(f"{base_path}_overview.json", "w", encoding="utf-8") as f:
        json.dump(overview_data, f, ensure_ascii=False, indent=4)
    with open(f"{base_path}_odds.json", "w", encoding="utf-8") as f:
        json.dump(odds_data, f, ensure_ascii=False, indent=4)
    with open(f"{base_path}_teams.json", "w", encoding="utf-8") as f:
        json.dump(teams_data, f, ensure_ascii=False, indent=4)
    with open(f"{base_path}_h2h.json", "w", encoding="utf-8") as f:
        json.dump(h2h_data, f, ensure_ascii=False, indent=4)
    with open(f"{base_path}_injuries.json", "w", encoding="utf-8") as f:
        json.dump(injuries_data, f, ensure_ascii=False, indent=4)
    with open(f"{base_path}_live.json", "w", encoding="utf-8") as f:
        json.dump(live_data, f, ensure_ascii=False, indent=4)

    print(f"✅ 경기 {match_id} 개요 저장 완료: match_{match_id}_overview.json")
    print(f"✅ 경기 {match_id} 승률/배당 저장 완료: match_{match_id}_odds.json")
    print(f"✅ 경기 {match_id} 팀정보 저장 완료: match_{match_id}_teams.json")
    print(f"✅ 경기 {match_id} 맞대결 저장 완료: match_{match_id}_h2h.json")
    print(f"✅ 경기 {match_id} 부상정보 저장 완료: match_{match_id}_injuries.json")
    print(f"✅ 경기 {match_id} 실시간 저장 완료: match_{match_id}_live.json")
