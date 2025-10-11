import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

class GameDatabase:
    def __init__(self):
        """Supabase 클라이언트 초기화"""
        self.url = os.getenv("APP_SUPABASE_URL")
        self.key = os.getenv("APP_SUPABASE_ANON_KEY")
        
        if not self.url or not self.key:
            raise ValueError("APP_SUPABASE_URL과 APP_SUPABASE_ANON_KEY 환경변수가 필요합니다.")
        
        self.supabase: Client = create_client(self.url, self.key)
    
    def get_games_by_month_range(self, current_date: datetime = None) -> List[Dict]:
        """
        현재 월 기준으로 이전월, 현재월, 다음월의 게임 데이터를 조회
        
        Args:
            current_date: 기준 날짜 (기본값: 현재 날짜)
        
        Returns:
            게임 데이터 리스트
        """
        if current_date is None:
            current_date = datetime.now()
        
        # 이전월 1일, 다음월 마지막일 계산
        prev_month = current_date.replace(day=1) - timedelta(days=1)
        prev_month_start = prev_month.replace(day=1)
        
        next_month = current_date.replace(day=28) + timedelta(days=4)
        next_month_end = next_month - timedelta(days=next_month.day)
        
        try:
            # game_league 테이블에서 게임 데이터 조회 (team_id 추가)
            response = self.supabase.table("game_league").select(
                "id, game_date, team1, team2, game_type, division, team1_score, team2_score, team1_color, team2_color, game_stage, team1_id, team2_id"
            ).gte(
                "game_date", prev_month_start.strftime("%Y-%m-%d")
            ).lte(
                "game_date", next_month_end.strftime("%Y-%m-%d")
            ).order(
                "game_date", desc=False
            ).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"게임 데이터 조회 중 오류 발생: {e}")
            return []
    
    def get_game_by_id(self, game_id: str) -> Optional[Dict]:
        """
        특정 게임 ID로 게임 상세 정보 조회
        
        Args:
            game_id: 게임 UUID
        
        Returns:
            게임 상세 정보 또는 None
        """
        try:
            response = self.supabase.table("game_league").select("*").eq("id", game_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            print(f"게임 상세 정보 조회 중 오류 발생: {e}")
            return None
    
    def format_game_list(self, games: List[Dict]) -> List[str]:
        """
        게임 리스트를 화면 표시용으로 포맷팅
        
        Args:
            games: 게임 데이터 리스트
        
        Returns:
            포맷팅된 게임 문자열 리스트
        """
        formatted_games = []
        
        for game in games:
            try:
                # 날짜 파싱 (YYYY-MM-DD 또는 YYYY-MM-DD HH:MM 형식 지원)
                game_date_str = game["game_date"]
                if " " in game_date_str:
                    # 시간이 포함된 경우 (YYYY-MM-DD HH:MM)
                    game_date = datetime.strptime(game_date_str, "%Y-%m-%d %H:%M")
                else:
                    # 날짜만 있는 경우 (YYYY-MM-DD)
                    game_date = datetime.strptime(game_date_str, "%Y-%m-%d")
                date_str = game_date.strftime("%m/%d")
                
                # 팀명과 게임 타입
                team1 = game.get("team1", "팀1")
                team2 = game.get("team2", "팀2")
                game_type = game.get("game_type", "result")
                division = game.get("division", "")
                
                # 게임 타입에 따른 상태 표시
                if game_type == "scheduled":
                    status = "(예정)"
                else:
                    status = ""
                
                # 디비전 정보 추가 (있는 경우)
                division_info = f" [{division}]" if division else ""
                
                # 포맷팅된 문자열 생성
                formatted = f"{date_str} {team1} vs {team2} {status}{division_info}"
                formatted_games.append(formatted)
                
            except Exception as e:
                print(f"게임 포맷팅 중 오류: {e}")
                continue
        
        return formatted_games

    def make_display_items(self, games: List[Dict]) -> List[Dict]:
        """
        표시 문자열과 원본 게임 객체를 함께 반환하여 인덱스 불일치를 방지
        정렬 순서:
        1. 최상단: "바로 시작"
        2. 오늘부터 미래의 경기 (오름차순)
        3. 어제부터 과거의 경기 (내림차순)
        Returns: [{ 'text': str, 'game': Dict }]
        """
        # 1. "바로 시작" 항목 추가
        items: List[Dict] = [{"text": "▶ 바로 시작", "game": None}]
        
        # 오늘 날짜 (자정 기준)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        future_games = []  # 오늘 이후 (오늘 포함)
        past_games = []    # 어제 이전
        
        # 2. 게임 데이터를 미래/과거로 분류
        for game in games:
            try:
                game_date_str = game["game_date"]
                if " " in game_date_str:
                    game_date = datetime.strptime(game_date_str, "%Y-%m-%d %H:%M")
                else:
                    game_date = datetime.strptime(game_date_str, "%Y-%m-%d")
                
                # 날짜만으로 비교 (자정 기준)
                game_date_only = game_date.replace(hour=0, minute=0, second=0, microsecond=0)
                
                date_str = game_date.strftime("%m/%d")
                team1 = game.get("team1", "팀1")
                team2 = game.get("team2", "팀2")
                game_type = game.get("game_type", "result")
                division = game.get("division", "")
                
                if game_type == "scheduled":
                    status = "(예정)"
                else:
                    status = ""
                
                division_info = f" [{division}]" if division else ""
                text = f"{date_str} {team1} vs {team2} {status}{division_info}"
                
                item = {"text": text, "game": game, "date": game_date}
                
                # 오늘 이후 vs 어제 이전 분류
                if game_date_only >= today:
                    future_games.append(item)
                else:
                    past_games.append(item)
                    
            except Exception as e:
                # 문제 있는 항목은 건너뜀
                print(f"게임 항목 처리 중 오류: {e}")
                continue
        
        # 3. 미래 경기 오름차순 정렬 (날짜 빠른 순)
        future_games.sort(key=lambda x: x["date"])
        
        # 4. 과거 경기 내림차순 정렬 (날짜 최근 순)
        past_games.sort(key=lambda x: x["date"], reverse=True)
        
        # 5. 최종 조합: 바로시작 → 미래 경기 → 과거 경기
        for item in future_games:
            items.append({"text": item["text"], "game": item["game"]})
        
        for item in past_games:
            items.append({"text": item["text"], "game": item["game"]})
        
        return items

# 전역 인스턴스
db = None

def get_database() -> GameDatabase:
    """데이터베이스 인스턴스 반환 (싱글톤 패턴)"""
    global db
    if db is None:
        try:
            db = GameDatabase()
        except Exception as e:
            print(f"데이터베이스 연결 실패: {e}")
            return None
    return db
