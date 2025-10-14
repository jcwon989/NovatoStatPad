#!/usr/bin/env python3
import tkinter as tk
from tkinter import font, messagebox, ttk
import json
import os
import time
import threading
from datetime import datetime, timedelta
import argparse
from dotenv import load_dotenv
from supabase import create_client, Client
from database import get_database
import pygame  # 사운드 재생용
from PIL import Image, ImageTk  # 이미지 처리용
import requests  # 이미지 다운로드용
from io import BytesIO  # 이미지 메모리 처리용

# ===== 기본 설정 =====
PERIOD_MAX_DEFAULT = 4
GAME_SECONDS_DEFAULT = 10*60
SHOT_SECONDS_DEFAULT = 24

CONFIG_PATH = os.path.expanduser("~/.scoreboard_config.json")

# Supabase 설정
load_dotenv()
SUPABASE_URL = os.getenv("APP_SUPABASE_URL")
SUPABASE_KEY = os.getenv("APP_SUPABASE_ANON_KEY")
WEB_VIEWER_URL = os.getenv("APP_WEB_VIEWER_URL", "")  # 웹 뷰어 URL (방송 채널 표시용)

def init_supabase_client():
    """Supabase 클라이언트 초기화"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("경고: Supabase 설정이 없습니다. .env 파일을 확인하세요.")
        return None
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return supabase
    except Exception as e:
        print(f"Supabase 클라이언트 초기화 실패: {e}, {SUPABASE_URL}, {SUPABASE_KEY}")
        return None

# generate_game_id 함수는 더 이상 사용하지 않음 (고정된 "pyscore" 사용)

def update_live_score_to_supabase(supabase_client, game_id, score_data):
    """Supabase에 라이브 스코어 업데이트"""
    if not supabase_client:
        return False
    
    try:
        # upsert 사용하여 게임 데이터 업데이트/삽입
        update_data = {
            'game_id': game_id,
            'team1_name': score_data['team1_name'],
            'team2_name': score_data['team2_name'],
            'team1_score': score_data['team1_score'],
            'team2_score': score_data['team2_score'],
            'team1_fouls': score_data['team1_fouls'],
            'team2_fouls': score_data['team2_fouls'],
            'team1_timeouts': score_data['team1_timeouts'],
            'team2_timeouts': score_data['team2_timeouts'],
            'current_quarter': score_data['current_quarter'],
            'quarter_time': score_data['quarter_time'],
            'game_status': score_data['game_status'],
            'shot_clock': int(score_data['shot_clock']),  # 24초 필드 추가
            'team1_color': score_data['team1_color'],  # 팀 컬러 전송 (live_score 테이블용)
            'team2_color': score_data['team2_color'],  # 팀 컬러 전송 (live_score 테이블용)
            # 로고 정보 항상 추가 (None이어도 전송하여 이전 값 제거)
            'team1_logo': score_data.get('team1_logo'),
            'team2_logo': score_data.get('team2_logo'),
            'last_updated': datetime.now().isoformat()
        }
        
        result = supabase_client.table('live_scores').upsert(update_data, on_conflict='game_id').execute()
        
        return True
    except Exception as e:
        print(f"Supabase 업데이트 실패: {e}")
        return False

def load_cfg():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                
                # 구버전 호환성: team_swapped를 두 개로 분리
                if "team_swapped" in cfg and "control_team_swapped" not in cfg:
                    cfg["control_team_swapped"] = cfg["team_swapped"]
                    cfg["presentation_team_swapped"] = cfg["team_swapped"]
                
                return cfg
        except Exception:
            pass
    return {
        "teamA": "TEAM A",
        "teamB": "TEAM B",
        "game_seconds": GAME_SECONDS_DEFAULT,
        "shot_seconds": SHOT_SECONDS_DEFAULT,
        "period_max": PERIOD_MAX_DEFAULT,
        "overtime_seconds": 5*60,
        "timeouts_per_team": 3,
        "dual_monitor": False,
        "swap_monitors": False,  # 모니터 내용 전환 (조작용 ↔ 프레젠테이션)
        "monitor_index": 0,
        "control_team_swapped": False,  # 컨트롤 창 팀 순서 바꾸기
        "presentation_team_swapped": False,  # 프레젠테이션 창 팀 순서 바꾸기
        "game_minutes": 9,  # 게임 시간 (분)
        "timeout_count": 3,  # 타임아웃 갯수
        "overtime_minutes": 5,  # 연장전 시간 (분)
        "team_a_color": "#F4F4F4",  # A팀 컬러 (흰색)
        "team_b_color": "#2563EB",  # B팀 컬러 (파랑)
        "game_id": "novato-scoreboard",  # 게임 ID
    }

def save_cfg(cfg):
    try:
        config_dir = os.path.dirname(CONFIG_PATH)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def fmt_mmss(s):
    s = max(0, int(s))
    m = s // 60
    r = s % 60
    return f"{m:02d}:{r:02d}"

def fmt_mmss_centi(s):
    """1/5초까지 표시하는 시간 포맷 (0.0, 0.2, 0.4, 0.6, 0.8)"""
    s = max(0, s)
    m = int(s) // 60
    r = int(s) % 60
    # 1/5초 단위로 변환 (5분의 1 = 0.2초)
    fifth = int((s - int(s)) * 5) * 2  # 0, 2, 4, 6, 8
    return f"{m:02d}:{r:02d}.{fifth:01d}"

def show_logo_selection_dialog(parent_window=None):
    """팀 로고 선택 다이얼로그"""
    # 기본 로고 URL 목록 (.env의 SUPABASE_URL 사용)
    if SUPABASE_URL:
        base_url = f"{SUPABASE_URL}/storage/v1/object/public/team-logo/default"
    else:
        base_url = "https://rnccawguqclhuzntkghd.supabase.co/storage/v1/object/public/team-logo/default"
    
    logo_options = [
        {"name": "로고 없음", "url": None},
        {"name": "기본 로고 1", "url": f"{base_url}/default_logo01.png"},
        {"name": "기본 로고 2", "url": f"{base_url}/default_logo02.png"},
        {"name": "기본 로고 3", "url": f"{base_url}/default_logo03.png"},
        {"name": "기본 로고 4", "url": f"{base_url}/default_logo04.png"},
    ]
    
    # 다이얼로그 생성
    dialog = tk.Toplevel(parent_window) if parent_window else tk.Tk()
    dialog.title("팀 로고 선택")
    dialog.geometry("600x500")
    dialog.configure(bg='#2a2a2a')
    
    if parent_window:
        dialog.transient(parent_window)
        dialog.grab_set()
    
    selected_logo = {'url': None, 'cancelled': False}
    
    tk.Label(dialog, text="팀 로고를 선택하세요", 
            font=('Arial', 14, 'bold'), fg='white', bg='#2a2a2a').pack(pady=20)
    
    # 스크롤 가능한 프레임
    canvas = tk.Canvas(dialog, bg='#2a2a2a', highlightthickness=0)
    scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg='#2a2a2a')
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    canvas.pack(side="left", fill="both", expand=True, padx=20, pady=(0, 20))
    scrollbar.pack(side="right", fill="y", pady=(0, 20))
    
    def on_select(logo_url):
        selected_logo['url'] = logo_url
        selected_logo['cancelled'] = False
        dialog.destroy()
    
    def on_cancel():
        selected_logo['cancelled'] = True
        dialog.destroy()
    
    # 로고 옵션 표시
    for option in logo_options:
        frame = tk.Frame(scrollable_frame, bg='#3a3a3a', relief=tk.RAISED, borderwidth=2)
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 이미지 로드 및 표시
        if option['url']:
            try:
                response = requests.get(option['url'], timeout=3)
                img_data = Image.open(BytesIO(response.content))
                # 썸네일 크기로 조정 (150x150)
                img_data.thumbnail((150, 150), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img_data)
                
                img_label = tk.Label(frame, image=photo, bg='#3a3a3a')
                img_label.image = photo  # 참조 유지
                img_label.pack(pady=10)
            except Exception as e:
                print(f"로고 로드 실패: {option['url']}, 오류: {e}")
                tk.Label(frame, text="이미지 로드 실패", fg='red', bg='#3a3a3a').pack(pady=10)
        else:
            tk.Label(frame, text="(로고 없음)", fg='gray', bg='#3a3a3a', 
                    font=('Arial', 12)).pack(pady=30)
        
        # 선택 버튼
        tk.Button(frame, text=option['name'], 
                 command=lambda url=option['url']: on_select(url),
                 font=('Arial', 11), bg='#4CAF50', fg='black', width=15).pack(pady=10)
    
    # 취소 버튼
    tk.Button(dialog, text="취소", command=on_cancel,
             font=('Arial', 11), bg='#f44336', fg='black', width=15).pack(pady=10)
    
    # Toplevel 윈도우는 wait_window() 사용 (mainloop() 대신)
    if parent_window:
        dialog.wait_window()
    else:
        dialog.mainloop()
    
    # 취소한 경우 None 반환 (변경하지 않음을 의미)
    if selected_logo['cancelled']:
        return None
    
    # 선택한 URL 반환 ("로고 없음" 선택 시 빈 문자열, 로고 선택 시 URL 반환)
    result_url = selected_logo['url']
    return result_url if result_url else ""

def show_game_selection_dialog(small_screen=False):
    """게임 선택 다이얼로그 표시"""
    db = get_database()
    if not db:
        return None
    
    # 게임 목록 가져오기
    games = db.get_games_by_month_range()
    display_items = db.make_display_items(games)
    
    # 현재 설정 로드 (모니터 위치 확인)
    cfg = load_cfg()
    swap_monitors = cfg.get("swap_monitors", False)
    
    # 다이얼로그 생성
    dialog = tk.Tk()
    dialog.title("게임 선택")
    
    # 화면 크기 설정 (small_screen 모드 대응)
    if small_screen:
        dialog_w, dialog_h = 600, 400  # 높이를 400으로 제한
    else:
        dialog_w, dialog_h = 600, 500
    
    # 컨트롤 패널과 같은 위치에 표시
    if swap_monitors:
        # 전환 모드: 두 번째 모니터
        dialog.geometry(f"{dialog_w}x{dialog_h}+1920+100")
    else:
        # 기본 모드: 첫 번째 모니터
        dialog.geometry(f"{dialog_w}x{dialog_h}+100+100")
    
    dialog.configure(bg='#1a1a1a')
    
    selected_game = {'game': None}
    
    tk.Label(dialog, text="게임을 선택하세요", 
            font=('Arial', 16, 'bold'), fg='white', bg='#1a1a1a').pack(pady=20)
    
    # 리스트박스와 스크롤바
    frame = tk.Frame(dialog, bg='#1a1a1a')
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
    
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, 
                        font=('Arial', 12), bg='#2a2a2a', fg='white',
                        selectmode=tk.SINGLE, height=15)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)
    
    # 게임 목록 추가 (database.py에서 이미 "바로 시작"을 첫 번째로 추가함)
    for item in display_items:
        listbox.insert(tk.END, item['text'])
    
    # 첫 번째 항목 선택
    listbox.selection_set(0)
    
    def on_select():
        selection = listbox.curselection()
        if selection:
            idx = selection[0]
            # display_items에서 직접 가져오기 (인덱스 조정 불필요)
            selected_game['game'] = display_items[idx]['game']
        dialog.destroy()
    
    def on_cancel():
        dialog.destroy()
        exit()
    
    # 버튼 프레임
    button_frame = tk.Frame(dialog, bg='#1a1a1a')
    button_frame.pack(pady=(0, 20))
    
    tk.Button(button_frame, text="선택", command=on_select, 
             font=('Arial', 12), width=10, bg='#4CAF50', fg='black').pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="취소", command=on_cancel, 
             font=('Arial', 12), width=10, bg='#f44336', fg='black').pack(side=tk.LEFT, padx=10)
    
    # 더블클릭으로 선택
    listbox.bind('<Double-Button-1>', lambda e: on_select())
    
    # 엔터 키로 선택
    listbox.bind('<Return>', lambda e: on_select())
    
    # 마우스 휠로 선택 이동
    def on_mousewheel(event):
        # 먼저 스크롤 처리
        if event.delta:
            # macOS/Windows
            delta = event.delta
            if abs(delta) >= 120:
                # Windows
                scroll_amount = -1 if delta > 0 else 1
            else:
                # macOS
                scroll_amount = -1 if delta > 0 else 1
        else:
            # Linux
            scroll_amount = -1 if event.num == 4 else 1
        
        # 현재 선택 항목 가져오기
        current = listbox.curselection()
        if current:
            current_idx = current[0]
        else:
            current_idx = 0
        
        # 새로운 인덱스 계산
        new_idx = current_idx + scroll_amount
        
        # 범위 체크
        if 0 <= new_idx < listbox.size():
            # 선택 해제 후 새로 선택
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(new_idx)
            listbox.activate(new_idx)
            # 보이도록 스크롤
            listbox.see(new_idx)
        
        return "break"  # 기본 스크롤 동작 방지
    
    listbox.bind("<MouseWheel>", on_mousewheel)  # Windows/macOS
    listbox.bind("<Button-4>", on_mousewheel)    # Linux 스크롤 업
    listbox.bind("<Button-5>", on_mousewheel)    # Linux 스크롤 다운
    
    # 키보드 화살표 키로 선택 이동
    def on_arrow_key(event):
        # 현재 선택 항목 가져오기
        current = listbox.curselection()
        if current:
            current_idx = current[0]
        else:
            current_idx = 0
        
        # 화살표 키에 따라 이동
        if event.keysym == 'Up':
            new_idx = current_idx - 1
        elif event.keysym == 'Down':
            new_idx = current_idx + 1
        else:
            return
        
        # 범위 체크
        if 0 <= new_idx < listbox.size():
            # 선택 해제 후 새로 선택
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(new_idx)
            listbox.activate(new_idx)
            # 보이도록 스크롤
            listbox.see(new_idx)
        
        return "break"  # 기본 동작 방지 (중복 스크롤 방지)
    
    listbox.bind("<Up>", on_arrow_key)
    listbox.bind("<Down>", on_arrow_key)
    
    # 포커스 설정
    listbox.focus_set()
    
    dialog.mainloop()
    
    return selected_game['game']

class DualMonitorScoreboard:
    def __init__(self, selected_game=None, small_screen=False):
        self.cfg = load_cfg()
        
        # 화면 크기 모드 설정
        self.small_screen = small_screen
        
        # Supabase 클라이언트 초기화
        self.supabase_client = init_supabase_client()
        self.game_id = self.cfg.get("game_id", "novato-scoreboard")  # 설정에서 게임 ID 가져오기
        print(f"게임 방송 채널: {self.get_broadcast_channel()}")
        print(f"화면 모드: {'작은 화면 (726x416)' if small_screen else '일반 화면'}")
        
        # 게임 유형 저장 (서버 게임 vs 바로 시작)
        self.is_quick_start = (selected_game is None)
        
        # 선택된 게임 데이터로 초기화
        if selected_game:
            self.init_from_game_data(selected_game)
        else:
            # 기본값으로 초기화
            self.init_with_defaults()
        
        # 공통 초기화
        self.running_game = False
        self.running_shot = False
        self.game_seconds = self.cfg["game_seconds"]
        self.shot_seconds = self.cfg["shot_seconds"]
        self.game_status = "scheduled"
        
        # 타이머
        self.last_update = time.time()
        self.timer_running = True
        
        # Supabase 업데이트용 타이머
        self.supabase_update_timer = time.time()
        self.supabase_update_interval = 1.0  # 1초마다 업데이트
        self.last_score_data = None  # 이전 데이터 저장용
        
        # 사운드 재생 플래그 (중복 재생 방지)
        self.game_buzzer_played = False
        self.shot_buzzer_played = False
        
        # pygame 사운드 초기화
        try:
            pygame.mixer.init()
            buzzer_path = os.path.join(os.path.dirname(__file__), "sound", "buzzer_main.wav")
            self.buzzer_sound = pygame.mixer.Sound(buzzer_path)
            print(f"버저 사운드 로드 성공: {buzzer_path}")
        except Exception as e:
            print(f"사운드 초기화 실패: {e}")
            self.buzzer_sound = None
        
        # Tkinter 루트
        self.root = tk.Tk()
        self.root.withdraw()  # 메인 창 숨기기
        
        # 폰트 설정
        self.setup_fonts()
        
        # 창 생성
        self.create_control_window()
        
        if self.cfg.get("dual_monitor", False):
            self.create_presentation_window()
        
        # 타이머 시작
        self.start_timer()
        
        # 키보드 바인딩
        self.setup_keyboard_bindings()
        
        # 초기 데이터를 Supabase에 전송
        self.update_supabase_data()
    
    def init_with_defaults(self):
        """기본값으로 초기화 (바로시작)"""
        self.scoreA = 0
        self.scoreB = 0
        self.period = 1
        self.timeoutsA = self.cfg.get("timeouts_per_team", 3)
        self.timeoutsB = self.cfg.get("timeouts_per_team", 3)
        self.foulsA = 0
        self.foulsB = 0
        self.teamA_name = self.cfg["teamA"]
        self.teamB_name = self.cfg["teamB"]
        self.team1_logo = None
        self.team2_logo = None
        self.team1_color = None
        self.team2_color = None
    
    def init_from_game_data(self, game_data):
        """게임 데이터로 초기화"""
        # 팀 이름
        self.teamA_name = game_data.get("team1") if game_data.get("team1") else "홈팀"
        self.teamB_name = game_data.get("team2") if game_data.get("team2") else "어웨이팀"
        
        # 점수
        self.scoreA = game_data.get("team1_score") if game_data.get("team1_score") is not None else 0
        self.scoreB = game_data.get("team2_score") if game_data.get("team2_score") is not None else 0
        
        # 파울, 타임아웃은 기본값
        self.period = 1
        self.timeoutsA = self.cfg.get("timeouts_per_team", 3)
        self.timeoutsB = self.cfg.get("timeouts_per_team", 3)
        self.foulsA = 0
        self.foulsB = 0
        
        # 팀 컬러 저장 (game_league에서 가져온 값)
        self.team1_color = game_data.get("team1_color")
        self.team2_color = game_data.get("team2_color")
        
        # 팀 로고 가져오기
        team1_id = game_data.get("team1_id")
        team2_id = game_data.get("team2_id")
        print(f"game_league에서 가져온 team1_id: {team1_id}, team2_id: {team2_id}")
        
        self.team1_logo = self.get_team_logo(team1_id)
        self.team2_logo = self.get_team_logo(team2_id)
        
        print(f"게임 로드: {self.teamA_name} vs {self.teamB_name}")
        print(f"점수: {self.scoreA} - {self.scoreB}")
        print(f"팀 컬러: {self.team1_color} / {self.team2_color}")
        print(f"팀 로고: {self.team1_logo} / {self.team2_logo}")
    
    def get_broadcast_channel(self):
        """방송 채널 전체 주소 반환 (웹 뷰어 URL + 채널 ID)"""
        if WEB_VIEWER_URL:
            # URL 끝의 슬래시 제거
            base_url = WEB_VIEWER_URL.rstrip('/')
            return f"{base_url}/{self.game_id}"
        else:
            # 웹 뷰어 URL이 없으면 채널 ID만 반환
            return self.game_id
    
    def get_team_logo(self, team_id):
        """팀 ID로 로고 URL 가져오기"""
        if not team_id:
            print(f"팀 ID가 없음: {team_id}")
            return None
        
        if not self.supabase_client:
            print("Supabase 클라이언트가 없음")
            return None
        
        try:
            print(f"팀 로고 조회 시작: team_id={team_id}, type={type(team_id)}")
            response = self.supabase_client.table('teams').select('team_logo').eq('id', team_id).execute()
            print(f"조회 결과: {response.data}")
            
            if response.data and len(response.data) > 0:
                logo_url = response.data[0].get('team_logo')
                print(f"팀 로고 찾음: {logo_url}")
                return logo_url
            else:
                print(f"팀 로고를 찾을 수 없음: team_id={team_id}")
        except Exception as e:
            print(f"팀 로고 조회 실패: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def get_color_hex(self, color_value):
        """색상 값을 hex 코드로 변환"""
        if not color_value:
            return "#F4F4F4"  # 기본값: 흰색
        
        # 이미 hex 코드인 경우 (#로 시작)
        if isinstance(color_value, str) and color_value.startswith('#'):
            return color_value
        
        # 색상 이름인 경우 hex로 변환 (하위 호환성)
        color_map = {
            "white": "#F4F4F4",
            "red": "#EF4444", 
            "blue": "#2563EB",
            "yellow": "#FACC15",
            "green": "#22C55E",
            "lightgreen": "#22C55E",
            "black": "#222222"
        }
        return color_map.get(color_value, "#F4F4F4")
    
    def get_score_data(self):
        """현재 게임 상태를 딕셔너리로 반환"""
        # game_league에서 가져온 팀 컬러 사용 (없으면 기본값)
        team1_color_value = getattr(self, 'team1_color', None) or self.cfg.get("team_a_color", "#F4F4F4")
        team2_color_value = getattr(self, 'team2_color', None) or self.cfg.get("team_b_color", "#2563EB")
        
        data = {
            'game_id': self.game_id,
            'team1_name': self.teamA_name,
            'team2_name': self.teamB_name,
            'team1_score': self.scoreA,
            'team2_score': self.scoreB,
            'team1_fouls': self.foulsA,
            'team2_fouls': self.foulsB,
            'team1_timeouts': self.timeoutsA,
            'team2_timeouts': self.timeoutsB,
            'current_quarter': self.period,
            'quarter_time': fmt_mmss(self.game_seconds),
            'game_status': self.game_status,
            'shot_clock': int(self.shot_seconds),  # 24초 필드 추가
            'team1_color': self.get_color_hex(team1_color_value),
            'team2_color': self.get_color_hex(team2_color_value),
            # 로고 정보 항상 추가 (없으면 None으로 명시적으로 전송하여 이전 값 제거)
            'team1_logo': getattr(self, 'team1_logo', None),
            'team2_logo': getattr(self, 'team2_logo', None)
        }
        
        return data
    
    def update_supabase_data(self):
        """Supabase에 현재 게임 데이터 업데이트 (변경사항이 있을 때만)"""
        if not self.supabase_client:
            return
        
        try:
            score_data = self.get_score_data()
            
            # 이전 데이터와 비교 (변경사항이 있을 때만 업데이트)
            if self.last_score_data != score_data:
                success = update_live_score_to_supabase(self.supabase_client, self.game_id, score_data)
                if success:
                    # print(f"Supabase 업데이트 성공: {self.game_id}")  # 로그 최소화
                    self.last_score_data = score_data.copy()
                else:
                    print(f"Supabase 업데이트 실패: {self.game_id}")
        except Exception as e:
            print(f"Supabase 업데이트 중 오류: {e}")
    
    def setup_fonts(self):
        """폰트 설정"""
        # 반응형 폰트 크기 계산
        self.setup_responsive_fonts()
    
    def setup_responsive_fonts(self):
        """반응형 폰트 크기 설정"""
        # 화면 크기 감지
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 기준 해상도 (1920x1080)
        base_width = 1920
        base_height = 1080
        
        # 비율 계산 (최소 0.5, 최대 2.0으로 제한)
        width_ratio = max(0.5, min(2.0, screen_width / base_width))
        height_ratio = max(0.5, min(2.0, screen_height / base_height))
        
        # 폰트 크기 비율 (가로 세로 중 작은 값 사용)
        font_ratio = min(width_ratio, height_ratio)
        
        if self.small_screen:
            # 작은 화면 모드 (726x416): 창 크기는 그대로, 폰트만 1.2배 증가
            self.font_large = font.Font(family="Arial", size=19, weight="bold")  # 16 * 1.2
            self.font_medium = font.Font(family="Arial", size=12)  # 10 * 1.2
            self.font_small = font.Font(family="Arial", size=10)  # 8 * 1.2 (반올림)
            self.font_score = font.Font(family="Arial", size=38, weight="bold")  # 32 * 1.2
            self.font_time = font.Font(family="Arial", size=24, weight="bold")  # 20 * 1.2
        else:
            # 일반 화면 모드: 반응형 컨트롤 창 폰트
            self.font_large = font.Font(family="Arial", size=int(48 * font_ratio), weight="bold")
            self.font_medium = font.Font(family="Arial", size=int(24 * font_ratio))
            self.font_small = font.Font(family="Arial", size=int(16 * font_ratio))
            self.font_score = font.Font(family="Arial", size=int(72 * font_ratio), weight="bold")
            self.font_time = font.Font(family="Arial", size=int(36 * font_ratio), weight="bold")
        
        # 프레젠테이션용 폰트 (항상 큰 화면용, small_screen과 무관)
        self.pres_font_team = font.Font(family="Arial", size=int(90 * font_ratio), weight="bold")  # 120 → 90
        self.pres_font_score = font.Font(family="Arial", size=int(300 * font_ratio), weight="bold")  # 400 → 300
        self.pres_font_time = font.Font(family="Arial", size=int(120 * font_ratio), weight="bold")  # 160 → 120 (분:초용)
        self.pres_font_time_small = font.Font(family="Arial", size=int(90 * font_ratio), weight="bold")  # 120 * 0.75 = 90 (1/5초용)
        self.pres_font_shot = font.Font(family="Arial", size=int(150 * font_ratio), weight="bold")  # 200 → 150
        self.pres_font_period = font.Font(family="Arial", size=int(90 * font_ratio), weight="bold")  # 120 → 90
        self.pres_font_stats = font.Font(family="Arial", size=int(60 * font_ratio), weight="bold")  # 80 → 60
    
    def create_control_window(self):
        """조작용 창 생성 (모니터 전환 기능 포함)"""
        self.control_window = tk.Toplevel(self.root)
        self.control_window.title(f"Novato Scoreboard - {self.get_broadcast_channel()}")
        
        if self.small_screen:
            # 작은 화면 모드: 726x416 고정 (내용물만 1.2배)
            control_width = 726
            control_height = 416
            self.control_window.resizable(False, False)  # 크기 고정
            # 작은 화면은 해당 모니터의 좌측 상단에 고정
            if self.cfg.get("swap_monitors", False):
                self.control_window.geometry(f"{control_width}x{control_height}+1920+0")
            else:
                self.control_window.geometry(f"{control_width}x{control_height}+0+0")
        else:
            # 일반 화면 모드: 반응형 창 크기
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # 조작용 창 크기 (화면 크기에 비례)
            control_width = max(800, min(1200, int(screen_width * 0.6)))
            control_height = max(600, min(900, int(screen_height * 0.7)))
            
            self.control_window.resizable(True, True)
            
            # 일반 화면은 모니터 전환 기능 적용
            if self.cfg.get("swap_monitors", False):
                # 전환 모드: 조작용 창을 두 번째 모니터에
                self.control_window.geometry(f"{control_width}x{control_height}+1920+0")  # 두 번째 모니터
            else:
                # 기본 모드: 조작용 창을 첫 번째 모니터에
                self.control_window.geometry(f"{control_width}x{control_height}+0+0")  # 첫 번째 모니터
            
        self.control_window.configure(bg='#1a1a1a')
        
        # 메인 프레임 (작은 화면은 패딩 최소화)
        padding = 6 if self.small_screen else 20  # 작은 화면 패딩 1.2배 증가 (5->6)
        main_frame = tk.Frame(self.control_window, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=padding, pady=padding)
        
        # 제목 (작은 화면에서는 숨김)
        if not self.small_screen:
            title_label = tk.Label(main_frame, text="NOVATO SCOREBOARD", 
                                  font=self.font_small, fg='gray', bg='#1a1a1a')
            title_label.pack(anchor=tk.CENTER, pady=(0, 10))
        
        # 스코어 표시 영역 (개선된 레이아웃)
        score_frame = tk.Frame(main_frame, bg='#1a1a1a')
        score_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 컨트롤 창 팀 순서 확인
        is_swapped = self.cfg.get("control_team_swapped", False)
        
        # 왼쪽 팀 프레임
        left_team_frame = tk.Frame(score_frame, bg='#1a1a1a')
        left_team_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        if is_swapped:
            # B팀이 왼쪽
            self.team_b_label = tk.Label(left_team_frame, text=self.teamB_name, 
                                        font=self.font_medium, fg='white', bg='#1a1a1a')
            self.team_b_label.pack()
            
            self.score_b_label = tk.Label(left_team_frame, text=str(self.scoreB), 
                                         font=self.font_score, fg='white', bg='#1a1a1a')
            self.score_b_label.pack()
            
            # B팀 타임아웃/파울
            b_stats_row = tk.Frame(left_team_frame, bg='#1a1a1a')
            b_stats_row.pack(pady=(10, 0))
            
            tk.Label(b_stats_row, text="TO", font=self.font_small, fg='white', bg='#1a1a1a').pack(side=tk.LEFT, padx=(0, 5))
            self.timeout_b_label = tk.Label(b_stats_row, text=str(self.timeoutsB), 
                                           font=self.font_medium, fg='white', bg='#1a1a1a')
            self.timeout_b_label.pack(side=tk.LEFT, padx=(0, 15))
            
            tk.Label(b_stats_row, text="F", font=self.font_small, fg='white', bg='#1a1a1a').pack(side=tk.LEFT, padx=(0, 5))
            self.foul_b_label = tk.Label(b_stats_row, text=str(self.foulsB), 
                                        font=self.font_medium, fg='white', bg='#1a1a1a')
            self.foul_b_label.pack(side=tk.LEFT)
        else:
            # A팀이 왼쪽 (기본)
            self.team_a_label = tk.Label(left_team_frame, text=self.teamA_name, 
                                        font=self.font_medium, fg='white', bg='#1a1a1a')
            self.team_a_label.pack()
            
            self.score_a_label = tk.Label(left_team_frame, text=str(self.scoreA), 
                                         font=self.font_score, fg='white', bg='#1a1a1a')
            self.score_a_label.pack()
            
            # A팀 타임아웃/파울
            a_stats_row = tk.Frame(left_team_frame, bg='#1a1a1a')
            a_stats_row.pack(pady=(10, 0))
            
            tk.Label(a_stats_row, text="TO", font=self.font_small, fg='white', bg='#1a1a1a').pack(side=tk.LEFT, padx=(0, 5))
            self.timeout_a_label = tk.Label(a_stats_row, text=str(self.timeoutsA), 
                                           font=self.font_medium, fg='white', bg='#1a1a1a')
            self.timeout_a_label.pack(side=tk.LEFT, padx=(0, 15))
            
            tk.Label(a_stats_row, text="F", font=self.font_small, fg='white', bg='#1a1a1a').pack(side=tk.LEFT, padx=(0, 5))
            self.foul_a_label = tk.Label(a_stats_row, text=str(self.foulsA), 
                                        font=self.font_medium, fg='white', bg='#1a1a1a')
            self.foul_a_label.pack(side=tk.LEFT)
        
        # 중앙 (시간, 쿼터, 샷클럭)
        center_frame = tk.Frame(score_frame, bg='#1a1a1a')
        center_frame.pack(side=tk.LEFT, fill=tk.Y, padx=20)
        
        # 게임 시간
        time_frame = tk.Frame(center_frame, bg='#1a1a1a')
        time_frame.pack(pady=2)
        
        self.time_label = tk.Label(time_frame, text=fmt_mmss_centi(self.game_seconds), 
                                  font=self.font_time, fg='white', bg='#1a1a1a')
        self.time_label.pack()
        
        # 쿼터
        period_frame = tk.Frame(center_frame, bg='#1a1a1a')
        period_frame.pack(pady=1)
        
        self.period_label = tk.Label(period_frame, text=f"Q{self.period}", 
                                    font=self.font_medium, fg='yellow', bg='#1a1a1a')
        self.period_label.pack()
        
        # 샷클럭
        shot_frame = tk.Frame(center_frame, bg='#1a1a1a')
        shot_frame.pack(pady=1)
        
        self.shot_label = tk.Label(shot_frame, text=str(int(self.shot_seconds)), 
                                  font=self.font_time, fg='orange', bg='#1a1a1a')
        self.shot_label.pack()
        
        # 오른쪽 팀 프레임
        right_team_frame = tk.Frame(score_frame, bg='#1a1a1a')
        right_team_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        if is_swapped:
            # A팀이 오른쪽
            self.team_a_label = tk.Label(right_team_frame, text=self.teamA_name, 
                                        font=self.font_medium, fg='white', bg='#1a1a1a')
            self.team_a_label.pack()
            
            self.score_a_label = tk.Label(right_team_frame, text=str(self.scoreA), 
                                         font=self.font_score, fg='white', bg='#1a1a1a')
            self.score_a_label.pack()
            
            # A팀 타임아웃/파울
            a_stats_row = tk.Frame(right_team_frame, bg='#1a1a1a')
            a_stats_row.pack(pady=(10, 0))
            
            tk.Label(a_stats_row, text="TO", font=self.font_small, fg='white', bg='#1a1a1a').pack(side=tk.LEFT, padx=(0, 5))
            self.timeout_a_label = tk.Label(a_stats_row, text=str(self.timeoutsA), 
                                           font=self.font_medium, fg='white', bg='#1a1a1a')
            self.timeout_a_label.pack(side=tk.LEFT, padx=(0, 15))
            
            tk.Label(a_stats_row, text="F", font=self.font_small, fg='white', bg='#1a1a1a').pack(side=tk.LEFT, padx=(0, 5))
            self.foul_a_label = tk.Label(a_stats_row, text=str(self.foulsA), 
                                        font=self.font_medium, fg='white', bg='#1a1a1a')
            self.foul_a_label.pack(side=tk.LEFT)
        else:
            # B팀이 오른쪽 (기본)
            self.team_b_label = tk.Label(right_team_frame, text=self.teamB_name, 
                                        font=self.font_medium, fg='white', bg='#1a1a1a')
            self.team_b_label.pack()
            
            self.score_b_label = tk.Label(right_team_frame, text=str(self.scoreB), 
                                         font=self.font_score, fg='white', bg='#1a1a1a')
            self.score_b_label.pack()
            
            # B팀 타임아웃/파울
            b_stats_row = tk.Frame(right_team_frame, bg='#1a1a1a')
            b_stats_row.pack(pady=(10, 0))
            
            tk.Label(b_stats_row, text="TO", font=self.font_small, fg='white', bg='#1a1a1a').pack(side=tk.LEFT, padx=(0, 5))
            self.timeout_b_label = tk.Label(b_stats_row, text=str(self.timeoutsB), 
                                           font=self.font_medium, fg='white', bg='#1a1a1a')
            self.timeout_b_label.pack(side=tk.LEFT, padx=(0, 15))
            
            tk.Label(b_stats_row, text="F", font=self.font_small, fg='white', bg='#1a1a1a').pack(side=tk.LEFT, padx=(0, 5))
            self.foul_b_label = tk.Label(b_stats_row, text=str(self.foulsB), 
                                        font=self.font_medium, fg='white', bg='#1a1a1a')
            self.foul_b_label.pack(side=tk.LEFT)
        
        # 조작 버튼들
        self.create_control_buttons(main_frame)
        
        # 힌트 (작은 화면에서는 간소화)
        if not self.small_screen:
            self.create_hints(main_frame)
            # 창이 완전히 렌더링된 후 크기 업데이트
            self.control_window.after(100, self.update_hints_text)
            # 창 크기 변경 시 힌트 텍스트 업데이트
            self.control_window.bind('<Configure>', lambda e: self.update_hints_text())
        else:
            # 작은 화면용 간단한 힌트
            self.create_simple_hints(main_frame)
    
    def create_control_buttons(self, parent):
        """조작 버튼들 생성"""
        pady_spacing = (0, 6) if self.small_screen else (0, 20)  # 작은 화면 간격 1.2배 증가 (5->6)
        button_frame = tk.Frame(parent, bg='#1a1a1a')
        button_frame.pack(fill=tk.X, pady=pady_spacing)
        
        # A팀 점수
        a_team_frame = tk.LabelFrame(button_frame, text="A팀 점수", 
                                    font=self.font_small, fg='lightblue', bg='#1a1a1a')
        a_team_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 버튼 중앙 정렬을 위한 컨테이너
        a_score_container = tk.Frame(a_team_frame, bg='#1a1a1a')
        a_score_container.pack(expand=True)
        
        tk.Button(a_score_container, text="+1 (1)", command=lambda: self.update_score('A', 1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(a_score_container, text="+2 (2)", command=lambda: self.update_score('A', 2),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(a_score_container, text="+3 (3)", command=lambda: self.update_score('A', 3),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(a_score_container, text="-1 (`)", command=lambda: self.update_score('A', -1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        
        # B팀 점수
        b_team_frame = tk.LabelFrame(button_frame, text="B팀 점수", 
                                    font=self.font_small, fg='lightcoral', bg='#1a1a1a')
        b_team_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # 버튼 중앙 정렬을 위한 컨테이너
        b_score_container = tk.Frame(b_team_frame, bg='#1a1a1a')
        b_score_container.pack(expand=True)
        
        tk.Button(b_score_container, text="+1 (0)", command=lambda: self.update_score('B', 1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(b_score_container, text="+2 (9)", command=lambda: self.update_score('B', 2),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(b_score_container, text="+3 (8)", command=lambda: self.update_score('B', 3),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(b_score_container, text="-1 (-)", command=lambda: self.update_score('B', -1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        
        
        # 팀 제어 (점수 제어 다음 줄)
        team_control_frame = tk.Frame(parent, bg='#1a1a1a')
        team_control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # A팀 제어
        a_control_frame = tk.LabelFrame(team_control_frame, text="A팀 제어", 
                                       font=self.font_small, fg='lightblue', bg='#1a1a1a')
        a_control_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 첫 번째 줄: 타임아웃 +1, 파울 -1 (빨간색)
        a_control_row1 = tk.Frame(a_control_frame, bg='#1a1a1a')
        a_control_row1.pack(expand=True, pady=2)
        tk.Button(a_control_row1, text="타임아웃 +1 (Q)", command=lambda: self.update_timeout('A', 1),
                 font=self.font_small, fg='red', width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(a_control_row1, text="파울 -1 (W)", command=lambda: self.update_foul('A', -1),
                 font=self.font_small, fg='red', width=15).pack(side=tk.LEFT, padx=2)
        
        # 두 번째 줄: 타임아웃 -1, 파울 +1 (파란색)
        a_control_row2 = tk.Frame(a_control_frame, bg='#1a1a1a')
        a_control_row2.pack(expand=True, pady=2)
        tk.Button(a_control_row2, text="타임아웃 -1 (q)", command=lambda: self.update_timeout('A', -1),
                 font=self.font_small, fg='blue', width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(a_control_row2, text="파울 +1 (w)", command=lambda: self.update_foul('A', 1),
                 font=self.font_small, fg='blue', width=15).pack(side=tk.LEFT, padx=2)
        
        # B팀 제어
        b_control_frame = tk.LabelFrame(team_control_frame, text="B팀 제어", 
                                       font=self.font_small, fg='lightcoral', bg='#1a1a1a')
        b_control_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # 첫 번째 줄: 타임아웃 +1, 파울 -1 (빨간색)
        b_control_row1 = tk.Frame(b_control_frame, bg='#1a1a1a')
        b_control_row1.pack(expand=True, pady=2)
        tk.Button(b_control_row1, text="타임아웃 +1 (P)", command=lambda: self.update_timeout('B', 1),
                 font=self.font_small, fg='red', width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(b_control_row1, text="파울 -1 (O)", command=lambda: self.update_foul('B', -1),
                 font=self.font_small, fg='red', width=15).pack(side=tk.LEFT, padx=2)
        
        # 두 번째 줄: 타임아웃 -1, 파울 +1 (파란색)
        b_control_row2 = tk.Frame(b_control_frame, bg='#1a1a1a')
        b_control_row2.pack(expand=True, pady=2)
        tk.Button(b_control_row2, text="타임아웃 -1 (p)", command=lambda: self.update_timeout('B', -1),
                 font=self.font_small, fg='blue', width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(b_control_row2, text="파울 +1 (o)", command=lambda: self.update_foul('B', 1),
                 font=self.font_small, fg='blue', width=15).pack(side=tk.LEFT, padx=2)
        
        # 시간/샷클럭 조작 (좌우 배치)
        time_shot_frame = tk.Frame(parent, bg='#1a1a1a')
        time_shot_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 게임 시간 제어 (왼쪽) - A팀과 동일한 패딩
        game_time_frame = tk.LabelFrame(time_shot_frame, text="게임 시간", 
                                       font=self.font_small, fg='yellow', bg='#1a1a1a')
        game_time_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 게임시간 버튼 컨테이너
        game_time_buttons = tk.Frame(game_time_frame, bg='#1a1a1a')
        game_time_buttons.pack(side=tk.LEFT, expand=True)
        
        # 첫 번째 줄: -1초, -10초, -1분
        game_time_row1 = tk.Frame(game_time_buttons, bg='#1a1a1a')
        game_time_row1.pack(pady=2)
        tk.Button(game_time_row1, text="-1초 (←)", command=lambda: self.adjust_time(-1),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        tk.Button(game_time_row1, text="-10초 (↓)", command=lambda: self.adjust_time(-10),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        tk.Button(game_time_row1, text="-1분 (<)", command=lambda: self.adjust_time(-60),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        
        # 두 번째 줄: +1초, +10초, +1분
        game_time_row2 = tk.Frame(game_time_buttons, bg='#1a1a1a')
        game_time_row2.pack(pady=2)
        tk.Button(game_time_row2, text="+1초 (→)", command=lambda: self.adjust_time(1),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        tk.Button(game_time_row2, text="+10초 (↑)", command=lambda: self.adjust_time(10),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        tk.Button(game_time_row2, text="+1분 (>)", command=lambda: self.adjust_time(60),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        
        # 게임시간 play/pause 버튼 (2줄 높이, 오른쪽)
        self.game_time_button = tk.Button(game_time_frame, text="시간\n▶\n(Space)", 
                                         command=self.toggle_game_time, 
                                         font=self.font_small, fg='red', width=8, height=3)
        self.game_time_button.pack(side=tk.RIGHT, padx=5, fill=tk.Y)
        
        # 샷클럭 제어 (오른쪽) - side를 RIGHT로 명시적으로 설정
        shot_clock_frame = tk.LabelFrame(time_shot_frame, text="샷클럭 (24초)", 
                                        font=self.font_small, fg='orange', bg='#1a1a1a')
        shot_clock_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # 샷클럭 버튼 컨테이너
        shot_clock_buttons = tk.Frame(shot_clock_frame, bg='#1a1a1a')
        shot_clock_buttons.pack(side=tk.LEFT, expand=True)
        
        # 첫 번째 줄: -1초, -5초, 14초
        shot_clock_row1 = tk.Frame(shot_clock_buttons, bg='#1a1a1a')
        shot_clock_row1.pack(pady=2)
        tk.Button(shot_clock_row1, text="-1초 (z)", command=lambda: self.adjust_shot_time(-1),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        tk.Button(shot_clock_row1, text="-5초", command=lambda: self.adjust_shot_time(-5),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        tk.Button(shot_clock_row1, text="14초 (f)", command=self.reset_shot_clock_14,
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        
        # 두 번째 줄: +1초, +5초, 24초
        shot_clock_row2 = tk.Frame(shot_clock_buttons, bg='#1a1a1a')
        shot_clock_row2.pack(pady=2)
        tk.Button(shot_clock_row2, text="+1초 (a)", command=lambda: self.adjust_shot_time(1),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        tk.Button(shot_clock_row2, text="+5초", command=lambda: self.adjust_shot_time(5),
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        tk.Button(shot_clock_row2, text="24초 (d)", command=self.reset_shot_clock,
                 font=self.font_small, width=7).pack(side=tk.LEFT, padx=2)
        
        # 샷클럭 play/pause 버튼 (2줄 높이, 오른쪽)
        self.shot_clock_button = tk.Button(shot_clock_frame, text="샷클럭\n▶\n(s)", 
                                          command=self.toggle_shot_time, 
                                          font=self.font_small, fg='orange', width=8, height=3)
        self.shot_clock_button.pack(side=tk.RIGHT, padx=5, fill=tk.Y)
        
        # 기타 조작 버튼들 (중앙 배치)
        other_buttons_frame = tk.Frame(parent, bg='#1a1a1a')
        pady_btn = (10, 5) if self.small_screen else (20, 10)
        other_buttons_frame.pack(pady=pady_btn)
        
        # 버튼 컨테이너 (중앙 정렬용)
        buttons_container = tk.Frame(other_buttons_frame, bg='#1a1a1a')
        buttons_container.pack()
        
        if self.small_screen:
            # 작은 화면: 필수 버튼만 표시 (2줄로 압축)
            # 첫 번째 줄
            row1 = tk.Frame(buttons_container, bg='#1a1a1a')
            row1.pack(pady=1)
            
            tk.Button(row1, text="리셋(r)", command=self.reset_all, 
                     font=self.font_small, width=8).pack(side=tk.LEFT, padx=1)
            tk.Button(row1, text="시간(t)", command=self.reset_game_time, 
                     font=self.font_small, fg='blue', width=8).pack(side=tk.LEFT, padx=1)
            tk.Button(row1, text="Q-([)", command=lambda: self.adjust_period(-1),
                     font=self.font_small, width=8).pack(side=tk.LEFT, padx=1)
            tk.Button(row1, text="Q+(])", command=lambda: self.adjust_period(1),
                     font=self.font_small, width=8).pack(side=tk.LEFT, padx=1)
            
            # 두 번째 줄
            row2 = tk.Frame(buttons_container, bg='#1a1a1a')
            row2.pack(pady=1)
            
            tk.Button(row2, text="설정(F2)", command=self.show_settings, 
                     font=self.font_small, width=8).pack(side=tk.LEFT, padx=1)
            tk.Button(row2, text="게임(F3)", command=self.change_game, 
                     font=self.font_small, fg='orange', width=8).pack(side=tk.LEFT, padx=1)
            tk.Button(row2, text="모니터(F4)", command=self.toggle_monitor_swap, 
                     font=self.font_small, fg='purple', width=8).pack(side=tk.LEFT, padx=1)
            tk.Button(row2, text="종료(Esc)", command=self.on_closing, 
                     font=self.font_small, fg='red', width=8).pack(side=tk.LEFT, padx=1)
        else:
            # 일반 화면: 모든 버튼 한 줄로 표시
            tk.Button(buttons_container, text="전체 리셋 (r)", 
                     command=self.reset_all, font=self.font_small).pack(side=tk.LEFT, padx=2)
            
            # 게임 시간 리셋 (전체 리셋 옆에 배치)
            tk.Button(buttons_container, text="시간 리셋 (t)", 
                     command=self.reset_game_time, font=self.font_small, fg='blue').pack(side=tk.LEFT, padx=5)
            
            # 쿼터 조작 (시간 리셋 옆에 배치)
            tk.Button(buttons_container, text="쿼터 -1 ([)", command=lambda: self.adjust_period(-1),
                     font=self.font_small).pack(side=tk.LEFT, padx=5)
            tk.Button(buttons_container, text="쿼터 +1 (])", command=lambda: self.adjust_period(1),
                     font=self.font_small).pack(side=tk.LEFT, padx=5)
            
            # 설정 버튼 (쿼터 버튼 옆)
            tk.Button(buttons_container, text="설정 (F2)", 
                     command=self.show_settings, font=self.font_small).pack(side=tk.LEFT, padx=5)
            
            # 게임 변경 버튼 (설정 버튼 옆)
            tk.Button(buttons_container, text="게임 변경 (F3)", 
                     command=self.change_game, font=self.font_small, fg='orange').pack(side=tk.LEFT, padx=5)
            
            # 모니터 전환 버튼 (게임 변경 버튼 옆)
            tk.Button(buttons_container, text="모니터 전환 (F4)", 
                     command=self.toggle_monitor_swap, font=self.font_small, fg='purple').pack(side=tk.LEFT, padx=5)
            
            # 종료 버튼 (모니터 전환 버튼 옆)
            tk.Button(buttons_container, text="종료 (Esc)", 
                     command=self.on_closing, font=self.font_small, fg='red').pack(side=tk.LEFT, padx=5)
        
    
    def create_simple_hints(self, parent):
        """작은 화면용 간단한 힌트 표시"""
        hints_frame = tk.Frame(parent, bg='#1a1a1a')
        hints_frame.pack(fill=tk.X, pady=(6, 0))  # 1.2배 증가 (5->6)
        
        hints_text = "Space(시작) | t(시간리셋) | s(샷클럭) | d/f(24/14초) | F2(설정)"
        
        tk.Label(hints_frame, text=hints_text, 
                font=('Arial', 8), fg='gray', bg='#1a1a1a').pack(anchor=tk.CENTER)  # 1.2배 증가 (7->8)
    
    def create_hints(self, parent):
        """힌트 표시"""
        hints_frame = tk.LabelFrame(parent, text="키보드 단축키", 
                                   font=self.font_small, fg='gray', bg='#1a1a1a')
        hints_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 초기 크기 (아직 정확하지 않을 수 있음)
        self.hints_label = tk.Label(hints_frame, text="", 
                              font=self.font_small, fg='gray', bg='#1a1a1a', justify=tk.LEFT)
        self.hints_label.pack(anchor=tk.W)
        
        # 힌트 텍스트 업데이트 (크기 포함)
        self.update_hints_text()
    
    def update_hints_text(self):
        """힌트 텍스트 업데이트 (창 크기 포함)"""
        if not hasattr(self, 'hints_label'):
            return
        
        # 컨트롤 창 크기 가져오기
        try:
            width = self.control_window.winfo_width()
            height = self.control_window.winfo_height()
            size_text = f"화면 크기: {width} × {height}"
            
            # 윈도우 타이틀도 업데이트
            broadcast_channel = self.get_broadcast_channel()
            self.control_window.title(f"Novato Scoreboard - {broadcast_channel} | {width} × {height}")
        except:
            size_text = "화면 크기: 계산 중..."
        
        hints_text = f"""{size_text}
점수: 1/2/3(A팀 +1/+2/+3) | 0/9/8(B팀 +1/+2/+3) | `/-(A/B팀 -1)
게임시간: 스페이스(play/pause) | t(시간 리셋) | ←→(±1초) | ↑↓(±10초) | <>(±1분)
샷클럭: s(play/pause) | a/z(±1초) | d(24초 리셋) | f(14초 리셋)
홈팀(A): q/Q(타임아웃 -/+) | w/W(파울 +/-) | 원정팀(B): p/P(타임아웃 -/+) | o/O(파울 +/-)
게임: R(전체 리셋) | [](쿼터 ±1) | F2(설정) | F3(게임 변경) | F4(모니터 전환) | Esc(종료 확인)"""
        
        self.hints_label.config(text=hints_text)
    
    def create_presentation_window(self):
        """프레젠테이션용 전체화면 창 생성 (모니터 전환 기능 포함)"""
        self.presentation_window = tk.Toplevel(self.root)
        self.presentation_window.title("Basketball Scoreboard - Presentation")
        
        # 모니터 전환에 따른 위치 설정
        if self.cfg.get("swap_monitors", False):
            # 전환 모드: 프레젠테이션 창을 첫 번째 모니터에
            self.presentation_window.geometry("1920x1080+0+0")  # 첫 번째 모니터
        else:
            # 기본 모드: 프레젠테이션 창을 두 번째 모니터에
            screen_width = self.root.winfo_screenwidth()
            self.presentation_window.geometry(f"1920x1080+{screen_width}+0")  # 두 번째 모니터
        
        self.presentation_window.configure(bg='#111111')
        self.presentation_window.attributes('-fullscreen', True)
        self.presentation_window.resizable(False, False)
        
        # 메인 프레임 (세로 중앙정렬)
        main_frame = tk.Frame(self.presentation_window, bg='#111111')
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 세로 중앙정렬을 위한 상하 여백 프레임
        top_spacer = tk.Frame(main_frame, bg='#111111')
        top_spacer.pack(fill=tk.BOTH, expand=True)
        
        # 메인 콘텐츠 프레임 (중앙에 배치)
        content_frame = tk.Frame(main_frame, bg='#111111')
        content_frame.pack(fill=tk.X, pady=50)
        
        bottom_spacer = tk.Frame(main_frame, bg='#111111')
        bottom_spacer.pack(fill=tk.BOTH, expand=True)
        
        # 프레젠테이션 창 팀 순서 설정
        is_swapped = self.cfg.get("presentation_team_swapped", False)
        
        if is_swapped:
            # 팀 순서가 바뀐 경우: B팀이 왼쪽, A팀이 오른쪽
            self.create_team_display(content_frame, self.teamB_name, self.teamA_name, True)
        else:
            # 기본 순서: A팀이 왼쪽, B팀이 오른쪽
            self.create_team_display(content_frame, self.teamA_name, self.teamB_name, False)
        
        # 중앙 시간 표시
        self.create_time_display(content_frame)
    
    def create_team_display(self, parent, left_team, right_team, swapped):
        """팀 표시 영역 생성 (모두 흰색으로 표시)"""
        # 왼쪽 팀 (A팀 또는 B팀)
        left_frame = tk.Frame(parent, bg='#111111')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        left_team_label = tk.Label(left_frame, text=left_team, 
                                  font=self.pres_font_team, 
                                  fg='white', bg='#111111')
        left_team_label.pack(pady=(50, 20))
        
        if swapped:
            self.pres_score_b_label = tk.Label(left_frame, text=str(self.scoreB), 
                                             font=self.pres_font_score, 
                                             fg='white', bg='#111111')
            self.pres_score_b_label.pack(pady=(0, 20))
            
            # B팀 타임아웃/파울 표시
            stats_b_frame = tk.Frame(left_frame, bg='#111111')
            stats_b_frame.pack(pady=10)
            
            tk.Label(stats_b_frame, text="TO", font=self.pres_font_stats, 
                    fg='white', bg='#111111').pack(side=tk.LEFT, padx=5)
            self.pres_timeout_b_label = tk.Label(stats_b_frame, text=str(self.timeoutsB), 
                                               font=self.pres_font_stats, 
                                               fg='white', bg='#111111')
            self.pres_timeout_b_label.pack(side=tk.LEFT, padx=10)
            
            tk.Label(stats_b_frame, text="F", font=self.pres_font_stats, 
                    fg='white', bg='#111111').pack(side=tk.LEFT, padx=5)
            self.pres_foul_b_label = tk.Label(stats_b_frame, text=str(self.foulsB), 
                                            font=self.pres_font_stats, 
                                            fg='white', bg='#111111')
            self.pres_foul_b_label.pack(side=tk.LEFT)
        else:
            self.pres_score_a_label = tk.Label(left_frame, text=str(self.scoreA), 
                                             font=self.pres_font_score, 
                                             fg='white', bg='#111111')
            self.pres_score_a_label.pack(pady=(0, 20))
            
            # A팀 타임아웃/파울 표시
            stats_a_frame = tk.Frame(left_frame, bg='#111111')
            stats_a_frame.pack(pady=10)
            
            tk.Label(stats_a_frame, text="TO", font=self.pres_font_stats, 
                    fg='white', bg='#111111').pack(side=tk.LEFT, padx=5)
            self.pres_timeout_a_label = tk.Label(stats_a_frame, text=str(self.timeoutsA), 
                                               font=self.pres_font_stats, 
                                               fg='white', bg='#111111')
            self.pres_timeout_a_label.pack(side=tk.LEFT, padx=10)
            
            tk.Label(stats_a_frame, text="F", font=self.pres_font_stats, 
                    fg='white', bg='#111111').pack(side=tk.LEFT, padx=5)
            self.pres_foul_a_label = tk.Label(stats_a_frame, text=str(self.foulsA), 
                                            font=self.pres_font_stats, 
                                            fg='white', bg='#111111')
            self.pres_foul_a_label.pack(side=tk.LEFT)
        
        # 오른쪽 팀 (B팀 또는 A팀)
        right_frame = tk.Frame(parent, bg='#111111')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        right_team_label = tk.Label(right_frame, text=right_team, 
                                   font=self.pres_font_team, 
                                   fg='white', bg='#111111')
        right_team_label.pack(pady=(50, 20))
        
        if swapped:
            self.pres_score_a_label = tk.Label(right_frame, text=str(self.scoreA), 
                                             font=self.pres_font_score, 
                                             fg='white', bg='#111111')
            self.pres_score_a_label.pack(pady=(0, 20))
            
            # A팀 타임아웃/파울 표시
            stats_a_frame = tk.Frame(right_frame, bg='#111111')
            stats_a_frame.pack(pady=10)
            
            tk.Label(stats_a_frame, text="TO", font=self.pres_font_stats, 
                    fg='white', bg='#111111').pack(side=tk.LEFT, padx=5)
            self.pres_timeout_a_label = tk.Label(stats_a_frame, text=str(self.timeoutsA), 
                                               font=self.pres_font_stats, 
                                               fg='white', bg='#111111')
            self.pres_timeout_a_label.pack(side=tk.LEFT, padx=10)
            
            tk.Label(stats_a_frame, text="F", font=self.pres_font_stats, 
                    fg='white', bg='#111111').pack(side=tk.LEFT, padx=5)
            self.pres_foul_a_label = tk.Label(stats_a_frame, text=str(self.foulsA), 
                                            font=self.pres_font_stats, 
                                            fg='white', bg='#111111')
            self.pres_foul_a_label.pack(side=tk.LEFT)
        else:
            self.pres_score_b_label = tk.Label(right_frame, text=str(self.scoreB), 
                                             font=self.pres_font_score, 
                                             fg='white', bg='#111111')
            self.pres_score_b_label.pack(pady=(0, 20))
            
            # B팀 타임아웃/파울 표시
            stats_b_frame = tk.Frame(right_frame, bg='#111111')
            stats_b_frame.pack(pady=10)
            
            tk.Label(stats_b_frame, text="TO", font=self.pres_font_stats, 
                    fg='white', bg='#111111').pack(side=tk.LEFT, padx=5)
            self.pres_timeout_b_label = tk.Label(stats_b_frame, text=str(self.timeoutsB), 
                                               font=self.pres_font_stats, 
                                               fg='white', bg='#111111')
            self.pres_timeout_b_label.pack(side=tk.LEFT, padx=10)
            
            tk.Label(stats_b_frame, text="F", font=self.pres_font_stats, 
                    fg='white', bg='#111111').pack(side=tk.LEFT, padx=5)
            self.pres_foul_b_label = tk.Label(stats_b_frame, text=str(self.foulsB), 
                                            font=self.pres_font_stats, 
                                            fg='white', bg='#111111')
            self.pres_foul_b_label.pack(side=tk.LEFT)
    
    def create_time_display(self, parent):
        """시간 표시 영역 생성"""
        time_frame = tk.Frame(parent, bg='#111111')
        time_frame.pack(fill=tk.BOTH, expand=True)
        
        # 게임 시간 (분:초와 1/5초를 분리하여 표시)
        time_container = tk.Frame(time_frame, bg='#111111')
        time_container.pack(pady=(100, 20))
        
        # 분:초 부분 (큰 글자)
        s = max(0, self.game_seconds)
        m = int(s) // 60
        r = int(s) % 60
        self.pres_time_mmss = tk.Label(time_container, text=f"{m:02d}:{r:02d}", 
                                       font=self.pres_font_time, 
                                       fg='yellow', bg='#111111')
        self.pres_time_mmss.pack(side=tk.LEFT, anchor='s')
        
        # 1/5초 부분 (75% 크기, 아래 라인 맞춤)
        fifth = int((s - int(s)) * 5) * 2
        self.pres_time_fifth = tk.Label(time_container, text=f".{fifth:01d}", 
                                        font=self.pres_font_time_small, 
                                        fg='yellow', bg='#111111')
        self.pres_time_fifth.pack(side=tk.LEFT, anchor='s')
        
        # 쿼터
        self.pres_period_label = tk.Label(time_frame, text=f'Q{self.period}', 
                                         font=self.pres_font_period, 
                                         fg='white', bg='#111111')
        self.pres_period_label.pack(pady=(0, 20))
        
        # 샷 클럭
        self.pres_shot_label = tk.Label(time_frame, text=str(int(self.shot_seconds)), 
                                       font=self.pres_font_shot, 
                                       fg='orange', bg='#111111')
        self.pres_shot_label.pack(pady=(0, 50))
    
    def setup_keyboard_bindings(self):
        """키보드 바인딩 설정"""
        self.root.bind('<Key>', self.on_key_press)
        self.control_window.bind('<Key>', self.on_key_press)
        self.control_window.focus_set()
        
        # 창 닫기 이벤트 바인딩
        self.control_window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        if hasattr(self, 'presentation_window'):
            self.presentation_window.bind('<Key>', self.on_key_press)
            self.presentation_window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_key_press(self, event):
        """키보드 입력 처리"""
        key = event.keysym
        
        if key == '1':
            self.update_score('A', 1)
        elif key == '2':
            self.update_score('A', 2)
        elif key == '3':
            self.update_score('A', 3)
        elif key == '0':
            self.update_score('B', 1)
        elif key == '9':
            self.update_score('B', 2)
        elif key == '8':
            self.update_score('B', 3)
        elif key == 'grave':  # ` 키
            self.update_score('A', -1)
        elif key == 'minus':
            self.update_score('B', -1)
        elif key == 'space':
            self.toggle_game_time()
        elif key == 's':
            self.toggle_shot_time()  # 샷클럭 play/pause
        elif key == 'a':
            self.adjust_shot_time(1)  # 샷클럭 +1초
        elif key == 'z':
            self.adjust_shot_time(-1)  # 샷클럭 -1초
        elif key == 'd':
            self.reset_shot_clock()  # 24초 리셋
        elif key == 'f':
            self.reset_shot_clock_14()  # 14초 리셋
        elif key == 'r':
            self.reset_all()
        elif key == 't':
            self.reset_game_time()
        elif key == 'Left':
            self.adjust_time(-1)
        elif key == 'Right':
            self.adjust_time(1)
        elif key == 'Up':
            self.adjust_time(10)
        elif key == 'Down':
            self.adjust_time(-10)
        elif key == 'comma':  # < 키
            self.adjust_time(-60)
        elif key == 'period':  # > 키
            self.adjust_time(60)
        elif key == 'bracketleft':  # [ 키
            self.adjust_period(-1)
        elif key == 'bracketright':  # ] 키
            self.adjust_period(1)
        # 타임아웃/파울 조작 (홈팀 A, 원정팀 B)
        elif key == 'q':
            self.update_timeout('A', -1)  # 홈팀 타임아웃 -1
        elif key == 'Q':
            self.update_timeout('A', 1)   # 홈팀 타임아웃 +1
        elif key == 'w':
            self.update_foul('A', 1)      # 홈팀 파울 +1
        elif key == 'W':
            self.update_foul('A', -1)     # 홈팀 파울 -1
        elif key == 'p':
            self.update_timeout('B', -1)  # 원정팀 타임아웃 -1
        elif key == 'P':
            self.update_timeout('B', 1)   # 원정팀 타임아웃 +1
        elif key == 'o':
            self.update_foul('B', 1)      # 원정팀 파울 +1
        elif key == 'O':
            self.update_foul('B', -1)     # 원정팀 파울 -1
        elif key == 'F2':
            self.show_settings()
        elif key == 'F3':
            self.change_game()
        elif key == 'F4':
            self.toggle_monitor_swap()
        elif key == 'Escape':
            self.on_closing()
    
    def update_score(self, team, points):
        """점수 업데이트"""
        if team == 'A':
            self.scoreA = max(0, self.scoreA + points)
        else:
            self.scoreB = max(0, self.scoreB + points)
        self.update_displays()
        self.update_supabase_data()
    
    def update_timeout(self, team, change):
        """타임아웃 업데이트"""
        if team == 'A':
            self.timeoutsA = max(0, self.timeoutsA + change)
        else:
            self.timeoutsB = max(0, self.timeoutsB + change)
        self.update_displays()
        self.update_supabase_data()
    
    def update_foul(self, team, change):
        """파울 업데이트"""
        if team == 'A':
            self.foulsA = max(0, self.foulsA + change)
        else:
            self.foulsB = max(0, self.foulsB + change)
        self.update_displays()
        self.update_supabase_data()
    
    def toggle_game_time(self):
        """게임 시간 시작/정지 (시간이 0이면 리셋)"""
        # 게임 시간이 0이면 리셋
        if self.game_seconds == 0:
            self.reset_game_time()
        else:
            self.running_game = not self.running_game
            # 게임 상태 업데이트
            if self.running_game:
                self.game_status = "live"
            else:
                self.game_status = "paused"
            self.update_displays()
            self.update_supabase_data()
    
    def reset_game_time(self):
        """게임 시간 리셋"""
        self.game_seconds = self.cfg["game_seconds"]
        self.running_game = False
        self.game_buzzer_played = False
        self.game_status = "paused"
        self.update_displays()
        self.update_supabase_data()
    
    def toggle_shot_time(self):
        """샷 클럭 시작/정지"""
        self.running_shot = not self.running_shot
        self.update_displays()
        self.update_supabase_data()
    
    def adjust_time(self, seconds):
        """시간 조정"""
        self.game_seconds = max(0, self.game_seconds + seconds)
        # 시간이 0보다 크면 버저 플래그 리셋
        if self.game_seconds > 0:
            self.game_buzzer_played = False
        self.update_displays()
        self.update_supabase_data()
    
    def adjust_period(self, delta):
        """쿼터 조정"""
        self.period = max(1, min(self.cfg.get("period_max", 4), self.period + delta))
        self.update_displays()
        self.update_supabase_data()
    
    def adjust_shot_time(self, delta):
        """샷클럭 시간 조정"""
        self.shot_seconds = max(0, min(99, self.shot_seconds + delta))
        # 샷 클럭이 0보다 크면 버저 플래그 리셋
        if self.shot_seconds > 0:
            self.shot_buzzer_played = False
        self.update_displays()
        self.update_supabase_data()
    
    def reset_shot_clock_14(self):
        """샷클럭 14초 리셋"""
        self.shot_seconds = 14
        self.running_shot = False
        self.shot_buzzer_played = False  # 버저 플래그 리셋
        self.update_displays()
        self.update_supabase_data()
    
    def reset_shot_clock(self):
        """샷클럭 24초 리셋"""
        self.shot_seconds = 24
        self.running_shot = False
        self.shot_buzzer_played = False  # 버저 플래그 리셋
        self.update_displays()
        self.update_supabase_data()
    
    def reset_all(self):
        """전체 리셋"""
        self.scoreA = 0
        self.scoreB = 0
        self.period = 1
        self.timeoutsA = self.cfg.get("timeouts_per_team", 3)
        self.timeoutsB = self.cfg.get("timeouts_per_team", 3)
        self.foulsA = 0
        self.foulsB = 0
        self.running_game = False
        self.running_shot = False
        self.game_seconds = self.cfg["game_seconds"]
        self.shot_seconds = self.cfg["shot_seconds"]
        self.game_status = "scheduled"
        # 버저 플래그 리셋
        self.game_buzzer_played = False
        self.shot_buzzer_played = False
        self.update_displays()
        self.update_supabase_data()
    
    def start_timer(self):
        """타이머 시작"""
        def timer_thread():
            while self.timer_running:
                current_time = time.time()
                dt = current_time - self.last_update
                self.last_update = current_time
                
                # 게임 시간 업데이트
                if self.running_game and self.game_seconds > 0:
                    prev_game_seconds = self.game_seconds
                    self.game_seconds = max(0, self.game_seconds - dt)
                    
                    # 게임 시간이 0이 되는 순간 버저 재생
                    if prev_game_seconds > 0 and self.game_seconds == 0:
                        if self.buzzer_sound and not self.game_buzzer_played:
                            try:
                                self.buzzer_sound.play()
                                self.game_buzzer_played = True
                                print("게임 시간 종료 - 버저 재생")
                            except Exception as e:
                                print(f"버저 재생 실패: {e}")
                
                # 샷 클럭 업데이트
                if self.running_shot and self.shot_seconds > 0:
                    prev_shot_seconds = self.shot_seconds
                    self.shot_seconds = max(0, self.shot_seconds - dt)
                    
                    # 샷 클럭이 0이 되는 순간 버저 재생
                    if prev_shot_seconds > 0 and self.shot_seconds == 0:
                        if self.buzzer_sound and not self.shot_buzzer_played:
                            try:
                                self.buzzer_sound.play()
                                self.shot_buzzer_played = True
                                print("샷 클럭 종료 - 버저 재생")
                            except Exception as e:
                                print(f"버저 재생 실패: {e}")
                
                # UI 업데이트 (메인 스레드에서)
                self.root.after(0, self.update_displays)
                
                # 1초마다 Supabase 업데이트
                if current_time - self.supabase_update_timer >= self.supabase_update_interval:
                    self.supabase_update_timer = current_time
                    self.root.after(0, self.update_supabase_data)
                
                time.sleep(1/60)  # 60 FPS
        
        timer = threading.Thread(target=timer_thread, daemon=True)
        timer.start()
    
    def update_displays(self):
        """화면 업데이트"""
        # 조작용 창 업데이트
        self.score_a_label.config(text=str(self.scoreA))
        self.score_b_label.config(text=str(self.scoreB))
        self.time_label.config(text=fmt_mmss_centi(self.game_seconds))
        self.period_label.config(text=f"Q{self.period}")
        self.shot_label.config(text=str(int(self.shot_seconds)))
        
        # 팀 이름 업데이트
        if hasattr(self, 'team_a_label'):
            self.team_a_label.config(text=self.teamA_name)
        if hasattr(self, 'team_b_label'):
            self.team_b_label.config(text=self.teamB_name)
        
        # 타임아웃과 파울 업데이트
        if hasattr(self, 'timeout_a_label'):
            self.timeout_a_label.config(text=str(self.timeoutsA))
            self.timeout_b_label.config(text=str(self.timeoutsB))
            self.foul_a_label.config(text=str(self.foulsA))
            self.foul_b_label.config(text=str(self.foulsB))
        
        # 게임시간 버튼 상태 업데이트
        if hasattr(self, 'game_time_button'):
            if self.game_seconds == 0:
                # 게임 시간이 0이면 리셋 버튼으로 변경
                self.game_time_button.config(text="시간\n리셋\n(Space)", fg='blue')
            elif self.running_game:
                self.game_time_button.config(text="시간\n⏸\n(Space)", fg='darkred')
            else:
                self.game_time_button.config(text="시간\n▶\n(Space)", fg='red')
        
        # 샷클럭 버튼 상태 업데이트
        if hasattr(self, 'shot_clock_button'):
            if self.running_shot:
                self.shot_clock_button.config(text="샷클럭\n⏸\n(s)", fg='darkorange')
            else:
                self.shot_clock_button.config(text="샷클럭\n▶\n(s)", fg='orange')
        
        # 프레젠테이션 창 업데이트
        if hasattr(self, 'presentation_window'):
            # 프레젠테이션 창 팀 순서에 따라 점수 표시
            is_swapped = self.cfg.get("presentation_team_swapped", False)
            if is_swapped:
                self.pres_score_b_label.config(text=str(self.scoreB))
                self.pres_score_a_label.config(text=str(self.scoreA))
            else:
                self.pres_score_a_label.config(text=str(self.scoreA))
                self.pres_score_b_label.config(text=str(self.scoreB))
            
            # 프레젠테이션 창 타임아웃/파울 업데이트
            if hasattr(self, 'pres_timeout_a_label'):
                self.pres_timeout_a_label.config(text=str(self.timeoutsA))
                self.pres_timeout_b_label.config(text=str(self.timeoutsB))
                self.pres_foul_a_label.config(text=str(self.foulsA))
                self.pres_foul_b_label.config(text=str(self.foulsB))
            
            # 시간 업데이트 (분:초와 1/5초 분리)
            s = max(0, self.game_seconds)
            m = int(s) // 60
            r = int(s) % 60
            fifth = int((s - int(s)) * 5) * 2
            self.pres_time_mmss.config(text=f"{m:02d}:{r:02d}")
            self.pres_time_fifth.config(text=f".{fifth:01d}")
            
            self.pres_period_label.config(text=f"Q{self.period}")
            self.pres_shot_label.config(text=str(int(self.shot_seconds)))
            
            # 마지막 10초부터 빨간색
            if self.game_seconds <= 10:
                self.pres_time_mmss.config(fg='red')
                self.pres_time_fifth.config(fg='red')
            else:
                self.pres_time_mmss.config(fg='yellow')
                self.pres_time_fifth.config(fg='yellow')
            
            # 마지막 5초부터 샷클럭 빨간색
            if self.shot_seconds <= 5:
                self.pres_shot_label.config(fg='red')
            else:
                self.pres_shot_label.config(fg='orange')
    
    def toggle_monitor_swap(self):
        """모니터 전환 토글"""
        self.cfg["swap_monitors"] = not self.cfg.get("swap_monitors", False)
        save_cfg(self.cfg)
        
        # 프레젠테이션 창 재생성
        if hasattr(self, 'presentation_window') and self.cfg.get("dual_monitor", False):
            self.presentation_window.destroy()
            self.create_presentation_window()
        
        # 컨트롤 창도 재생성 (위치 변경)
        self.control_window.destroy()
        self.create_control_window()
        self.setup_keyboard_bindings()
    
    def change_game(self):
        """게임 변경 (게임 선택 화면으로 이동)"""
        result = tk.messagebox.askquestion("게임 변경", 
                                         "게임을 변경하시겠습니까?\n현재 진행 중인 게임 데이터는 저장되지 않습니다.",
                                         icon='question')
        
        if result == 'yes':
            # 현재 앱 종료
            self.timer_running = False
            save_cfg(self.cfg)
            
            # 모든 창 닫기
            if hasattr(self, 'presentation_window'):
                self.presentation_window.destroy()
            self.control_window.destroy()
            self.root.destroy()
            
            # 새로운 게임 선택 다이얼로그 표시 및 앱 재시작
            selected_game = show_game_selection_dialog()
            new_app = DualMonitorScoreboard(selected_game)
            new_app.run()
    
    def on_closing(self):
        """앱 종료 처리 (확인 팝업 포함)"""
        # 종료 확인 팝업
        result = tk.messagebox.askquestion("종료 확인", 
                                         "스코어보드를 종료하시겠습니까?",
                                         icon='question')
        
        if result == 'yes':
            self.timer_running = False
            save_cfg(self.cfg)
            self.root.quit()
            self.root.destroy()
    
    def show_settings(self):
        """설정 창 표시 (개선된 레이아웃)"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("게임 설정")
        
        # small_screen 모드일 때 높이 조정
        if self.small_screen:
            settings_window.geometry("700x400")
        else:
            settings_window.geometry("700x650")
        
        settings_window.configure(bg='#2a2a2a')
        settings_window.resizable(True, True)
        
        # 설정 창을 조작용 창 위에 표시
        settings_window.transient(self.control_window)
        settings_window.grab_set()
        
        # 스크롤 가능한 프레임 생성
        canvas = tk.Canvas(settings_window, bg='#2a2a2a', highlightthickness=0)
        scrollbar = tk.Scrollbar(settings_window, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#2a2a2a')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 캔버스와 스크롤바 배치
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # ===== 방송 채널 설정 =====
        game_id_frame = tk.LabelFrame(scrollable_frame, text="방송 채널 (Supabase 전송용)", 
                                      font=self.font_small, fg='orange', bg='#2a2a2a')
        game_id_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # 현재 방송 채널 전체 주소 표시
        broadcast_channel = self.get_broadcast_channel()
        tk.Label(game_id_frame, text=f"방송 채널: {broadcast_channel}", 
                fg='lightgreen', bg='#2a2a2a', font=self.font_small).pack(pady=(10, 5), padx=10, anchor=tk.W)
        
        tk.Label(game_id_frame, text="채널 ID:", fg='white', bg='#2a2a2a').pack(pady=(10, 5), padx=10, anchor=tk.W)
        game_id_entry = tk.Entry(game_id_frame, font=self.font_small, width=40)
        game_id_entry.pack(pady=5, padx=10, anchor=tk.W)
        game_id_entry.insert(0, self.game_id)
        
        tk.Label(game_id_frame, text="※ 여러 기기에서 같은 게임을 공유하려면 동일한 채널 ID를 사용하세요.", 
                fg='gray', bg='#2a2a2a', font=('Arial', 9)).pack(pady=(0, 10), padx=10, anchor=tk.W)
        
        # 구분선
        tk.Label(scrollable_frame, text="─────────────────────────────────────", fg='gray', bg='#2a2a2a').pack(pady=10)
        
        # ===== 팀 설정 (좌우 배치) =====
        teams_frame = tk.Frame(scrollable_frame, bg='#2a2a2a')
        teams_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # A팀 설정 (왼쪽)
        team_a_frame = tk.LabelFrame(teams_frame, text="A팀 설정", 
                                     font=self.font_small, fg='lightblue', bg='#2a2a2a')
        team_a_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(team_a_frame, text="팀 이름:", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
        
        team_a_entry = None
        if self.is_quick_start:
            # 바로 시작: 수정 가능한 Entry
            team_a_entry = tk.Entry(team_a_frame, font=self.font_small)
            team_a_entry.pack(pady=5, padx=10)
            team_a_entry.insert(0, self.teamA_name)
        else:
            # 서버 게임: 읽기 전용 Label
            tk.Label(team_a_frame, text=self.teamA_name, fg='lightblue', bg='#2a2a2a',
                    font=self.font_small).pack(pady=5)
        
        # A팀 컬러 및 로고
        team_a_color_var = None
        team_a_logo_var = None
        colors = ["#F4F4F4", "#2563EB", "#EF4444", "#FACC15", "#222222", "#22C55E"]
        color_names = ["흰색", "파랑", "빨강", "노랑", "검정", "녹색"]
        color_map = dict(zip(colors, color_names))
        
        if self.is_quick_start:
            # 바로 시작: 라디오 버튼으로 선택 가능
            tk.Label(team_a_frame, text="팀 컬러:", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
            team_a_color_var = tk.StringVar(value=self.cfg.get("team_a_color", "#F4F4F4"))
            
            # 3개씩 2줄로 표시
            color_row1 = tk.Frame(team_a_frame, bg='#2a2a2a')
            color_row1.pack(padx=10, pady=2)
            for i in range(3):
                tk.Radiobutton(color_row1, text=color_names[i], variable=team_a_color_var, 
                              value=colors[i], fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT, padx=5)
            
            color_row2 = tk.Frame(team_a_frame, bg='#2a2a2a')
            color_row2.pack(padx=10, pady=2)
            for i in range(3, 6):
                tk.Radiobutton(color_row2, text=color_names[i], variable=team_a_color_var, 
                              value=colors[i], fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT, padx=5)
            
            # A팀 로고 설정
            tk.Label(team_a_frame, text="팀 로고:", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
            team_a_logo_var = tk.StringVar(value=getattr(self, 'team1_logo', None) or "")
            
            logo_display_frame = tk.Frame(team_a_frame, bg='#2a2a2a')
            logo_display_frame.pack(pady=5)
            
            team_a_logo_label = tk.Label(logo_display_frame, 
                                         text="로고 없음" if not team_a_logo_var.get() else "로고 설정됨",
                                         fg='yellow', bg='#2a2a2a')
            team_a_logo_label.pack(side=tk.LEFT, padx=5)
            
            def select_team_a_logo():
                result = show_logo_selection_dialog(settings_window)
                
                # None이면 취소 (아무 것도 하지 않음)
                if result is None:
                    return
                
                # 선택됨 (빈 문자열 = 로고 없음, URL = 로고 있음)
                team_a_logo_var.set(result)
                
                # UI 업데이트만 (실제 저장은 save_settings에서)
                team_a_logo_label.config(text="로고 없음" if not result else "로고 설정됨")
                print(f"A팀 로고 선택: {result if result else '(로고 없음)'}")
            
            tk.Button(logo_display_frame, text="로고 선택", command=select_team_a_logo,
                     font=('Arial', 9), bg='#2196F3', fg='black').pack(side=tk.LEFT, padx=5)
        else:
            # 서버 게임: 읽기 전용으로 컬러 표시
            tk.Label(team_a_frame, text="팀 컬러:", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
            team_a_color = getattr(self, 'team1_color', None) or self.cfg.get("team_a_color", "#F4F4F4")
            # 팔레트에 있으면 이름, 없으면 hex 코드 표시
            color_display = color_map.get(team_a_color, team_a_color)
            tk.Label(team_a_frame, text=color_display, fg='lightblue', bg='#2a2a2a',
                    font=self.font_small).pack(pady=5)
        
        # B팀 설정 (오른쪽)
        team_b_frame = tk.LabelFrame(teams_frame, text="B팀 설정", 
                                     font=self.font_small, fg='lightcoral', bg='#2a2a2a')
        team_b_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        tk.Label(team_b_frame, text="팀 이름:", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
        
        team_b_entry = None
        if self.is_quick_start:
            # 바로 시작: 수정 가능한 Entry
            team_b_entry = tk.Entry(team_b_frame, font=self.font_small)
            team_b_entry.pack(pady=5, padx=10)
            team_b_entry.insert(0, self.teamB_name)
        else:
            # 서버 게임: 읽기 전용 Label
            tk.Label(team_b_frame, text=self.teamB_name, fg='lightcoral', bg='#2a2a2a',
                    font=self.font_small).pack(pady=5)
        
        # B팀 컬러 및 로고
        team_b_color_var = None
        team_b_logo_var = None
        if self.is_quick_start:
            # 바로 시작: 라디오 버튼으로 선택 가능
            tk.Label(team_b_frame, text="팀 컬러:", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
            team_b_color_var = tk.StringVar(value=self.cfg.get("team_b_color", "#2563EB"))
            
            # 3개씩 2줄로 표시
            color_row1 = tk.Frame(team_b_frame, bg='#2a2a2a')
            color_row1.pack(padx=10, pady=2)
            for i in range(3):
                tk.Radiobutton(color_row1, text=color_names[i], variable=team_b_color_var, 
                              value=colors[i], fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT, padx=5)
            
            color_row2 = tk.Frame(team_b_frame, bg='#2a2a2a')
            color_row2.pack(padx=10, pady=2)
            for i in range(3, 6):
                tk.Radiobutton(color_row2, text=color_names[i], variable=team_b_color_var, 
                              value=colors[i], fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT, padx=5)
            
            # B팀 로고 설정
            tk.Label(team_b_frame, text="팀 로고:", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
            team_b_logo_var = tk.StringVar(value=getattr(self, 'team2_logo', None) or "")
            
            logo_display_frame = tk.Frame(team_b_frame, bg='#2a2a2a')
            logo_display_frame.pack(pady=5)
            
            team_b_logo_label = tk.Label(logo_display_frame, 
                                         text="로고 없음" if not team_b_logo_var.get() else "로고 설정됨",
                                         fg='yellow', bg='#2a2a2a')
            team_b_logo_label.pack(side=tk.LEFT, padx=5)
            
            def select_team_b_logo():
                result = show_logo_selection_dialog(settings_window)
                
                # None이면 취소 (아무 것도 하지 않음)
                if result is None:
                    return
                
                # 선택됨 (빈 문자열 = 로고 없음, URL = 로고 있음)
                team_b_logo_var.set(result)
                
                # UI 업데이트만 (실제 저장은 save_settings에서)
                team_b_logo_label.config(text="로고 없음" if not result else "로고 설정됨")
                print(f"B팀 로고 선택: {result if result else '(로고 없음)'}")
            
            tk.Button(logo_display_frame, text="로고 선택", command=select_team_b_logo,
                     font=('Arial', 9), bg='#2196F3', fg='black').pack(side=tk.LEFT, padx=5)
        else:
            # 서버 게임: 읽기 전용으로 컬러 표시
            tk.Label(team_b_frame, text="팀 컬러:", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
            team_b_color = getattr(self, 'team2_color', None) or self.cfg.get("team_b_color", "#2563EB")
            # 팔레트에 있으면 이름, 없으면 hex 코드 표시
            color_display = color_map.get(team_b_color, team_b_color)
            tk.Label(team_b_frame, text=color_display, fg='lightcoral', bg='#2a2a2a',
                    font=self.font_small).pack(pady=5)
        
        # 구분선
        tk.Label(scrollable_frame, text="─────────────────────────────────────", fg='gray', bg='#2a2a2a').pack(pady=10)
        
        # ===== 모니터 설정 =====
        monitor_frame = tk.LabelFrame(scrollable_frame, text="모니터 및 팀 순서 설정", 
                                     font=self.font_small, fg='white', bg='#2a2a2a')
        monitor_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # 듀얼모니터 설정
        dual_frame = tk.Frame(monitor_frame, bg='#2a2a2a')
        dual_frame.pack(pady=5, padx=10, anchor=tk.W)
        
        dual_monitor_var = tk.BooleanVar(value=self.cfg.get("dual_monitor", False))
        tk.Checkbutton(dual_frame, text="듀얼모니터 사용 (프레젠테이션 창 표시)", 
                      variable=dual_monitor_var, 
                      fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT)
        
        # 팀 순서 바꾸기 (독립적으로 제어)
        tk.Label(monitor_frame, text="팀 순서 전환:", fg='lightgreen', bg='#2a2a2a',
                font=self.font_small).pack(pady=(15, 5), padx=10, anchor=tk.W)
        
        # 컨트롤 창 팀 순서
        control_swap_frame = tk.Frame(monitor_frame, bg='#2a2a2a')
        control_swap_frame.pack(pady=5, padx=20, anchor=tk.W)
        
        control_team_swapped_var = tk.BooleanVar(value=self.cfg.get("control_team_swapped", False))
        tk.Checkbutton(control_swap_frame, text="컨트롤 창:", 
                      variable=control_team_swapped_var, 
                      fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT)
        
        # 현재 팀 순서 표시
        control_order_text = "팀 B | 팀 A" if control_team_swapped_var.get() else "팀 A | 팀 B"
        control_order_label = tk.Label(control_swap_frame, text=control_order_text, 
                                      fg='lightblue', bg='#2a2a2a', font=self.font_small)
        control_order_label.pack(side=tk.LEFT, padx=10)
        
        # 체크박스 변경 시 라벨 업데이트
        def update_control_order():
            new_text = "팀 B | 팀 A" if control_team_swapped_var.get() else "팀 A | 팀 B"
            control_order_label.config(text=new_text)
        
        control_team_swapped_var.trace_add('write', lambda *args: update_control_order())
        
        # 전체화면 팀 순서
        presentation_swap_frame = tk.Frame(monitor_frame, bg='#2a2a2a')
        presentation_swap_frame.pack(pady=5, padx=20, anchor=tk.W)
        
        presentation_team_swapped_var = tk.BooleanVar(value=self.cfg.get("presentation_team_swapped", False))
        tk.Checkbutton(presentation_swap_frame, text="전체화면:", 
                      variable=presentation_team_swapped_var, 
                      fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT)
        
        # 현재 팀 순서 표시
        pres_order_text = "팀 B | 팀 A" if presentation_team_swapped_var.get() else "팀 A | 팀 B"
        pres_order_label = tk.Label(presentation_swap_frame, text=pres_order_text, 
                                   fg='lightcoral', bg='#2a2a2a', font=self.font_small)
        pres_order_label.pack(side=tk.LEFT, padx=10)
        
        # 체크박스 변경 시 라벨 업데이트
        def update_pres_order():
            new_text = "팀 B | 팀 A" if presentation_team_swapped_var.get() else "팀 A | 팀 B"
            pres_order_label.config(text=new_text)
        
        presentation_team_swapped_var.trace_add('write', lambda *args: update_pres_order())
        
        # 구분선
        tk.Label(scrollable_frame, text="─────────────────────────────────────", fg='gray', bg='#2a2a2a').pack(pady=10)
        
        # ===== 게임 규칙 설정 =====
        rules_frame = tk.LabelFrame(scrollable_frame, text="게임 규칙", 
                                    font=self.font_small, fg='yellow', bg='#2a2a2a')
        rules_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # 게임 시간 설정
        tk.Label(rules_frame, text="게임 시간 (분):", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
        game_minutes_frame = tk.Frame(rules_frame, bg='#2a2a2a')
        game_minutes_frame.pack()
        
        game_minutes_var = tk.IntVar(value=self.cfg.get("game_minutes", 9))
        for minutes in range(5, 13):
            tk.Radiobutton(game_minutes_frame, text=f"{minutes}분", variable=game_minutes_var, 
                          value=minutes, fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT, padx=3)
        
        # 타임아웃 갯수 설정
        tk.Label(rules_frame, text="타임아웃 갯수:", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
        timeout_count_frame = tk.Frame(rules_frame, bg='#2a2a2a')
        timeout_count_frame.pack()
        
        timeout_count_var = tk.IntVar(value=self.cfg.get("timeout_count", 3))
        for count in range(1, 6):
            tk.Radiobutton(timeout_count_frame, text=f"{count}개", variable=timeout_count_var, 
                          value=count, fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT, padx=5)
        
        # 연장전 시간 설정
        tk.Label(rules_frame, text="연장전 시간 (분):", fg='white', bg='#2a2a2a').pack(pady=(10, 5))
        overtime_frame = tk.Frame(rules_frame, bg='#2a2a2a')
        overtime_frame.pack(pady=(0, 10))
        
        overtime_minutes_var = tk.IntVar(value=self.cfg.get("overtime_minutes", 5))
        for minutes in range(1, 11):
            tk.Radiobutton(overtime_frame, text=f"{minutes}분", variable=overtime_minutes_var, 
                          value=minutes, fg='white', bg='#2a2a2a', selectcolor='#444444').pack(side=tk.LEFT, padx=3)
        
        def save_settings():
            # 게임 ID 저장
            new_game_id = game_id_entry.get().strip()
            if new_game_id:
                self.cfg["game_id"] = new_game_id
                self.game_id = new_game_id
            
            # 팀 이름은 바로 시작일 때만 저장 (서버 게임은 수정 불가)
            if self.is_quick_start and team_a_entry and team_b_entry:
                self.cfg["teamA"] = team_a_entry.get()
                self.cfg["teamB"] = team_b_entry.get()
                self.teamA_name = team_a_entry.get()
                self.teamB_name = team_b_entry.get()
            
            self.cfg["dual_monitor"] = dual_monitor_var.get()
            self.cfg["control_team_swapped"] = control_team_swapped_var.get()
            self.cfg["presentation_team_swapped"] = presentation_team_swapped_var.get()
            
            # 새로운 설정들 저장
            self.cfg["game_minutes"] = game_minutes_var.get()
            self.cfg["timeout_count"] = timeout_count_var.get()
            self.cfg["overtime_minutes"] = overtime_minutes_var.get()
            
            # 팀 컬러와 로고는 바로 시작일 때만 저장
            if self.is_quick_start:
                if team_a_color_var and team_b_color_var:
                    self.cfg["team_a_color"] = team_a_color_var.get()
                    self.cfg["team_b_color"] = team_b_color_var.get()
                
                # 팀 로고 저장
                if team_a_logo_var:
                    logo_value = team_a_logo_var.get()
                    self.team1_logo = None if logo_value == "" else logo_value
                    print(f"저장: A팀 로고 = {self.team1_logo}")
                
                if team_b_logo_var:
                    logo_value = team_b_logo_var.get()
                    self.team2_logo = None if logo_value == "" else logo_value
                    print(f"저장: B팀 로고 = {self.team2_logo}")
            
            # 설정에 따른 값 업데이트
            self.cfg["game_seconds"] = self.cfg["game_minutes"] * 60
            self.cfg["timeouts_per_team"] = self.cfg["timeout_count"]
            self.cfg["overtime_seconds"] = self.cfg["overtime_minutes"] * 60
            
            # 현재 게임 시간과 타임아웃 수 업데이트
            self.game_seconds = self.cfg["game_seconds"]
            self.timeoutsA = self.cfg["timeout_count"]
            self.timeoutsB = self.cfg["timeout_count"]
            
            save_cfg(self.cfg)
            self.update_displays()
            
            # 설정 저장 시 Supabase 업데이트
            print(f"설정 저장 완료 - 서버 업데이트 시작")
            self.update_supabase_data()
            print(f"설정 저장 후 로고 상태: team1_logo={self.team1_logo}, team2_logo={self.team2_logo}")
            
            # 듀얼모니터 설정 변경시 창 재생성
            if self.cfg.get("dual_monitor", False):
                if hasattr(self, 'presentation_window'):
                    self.presentation_window.destroy()
                self.create_presentation_window()
            else:
                if hasattr(self, 'presentation_window'):
                    self.presentation_window.destroy()
                    del self.presentation_window
            
            # 컨트롤 창 재생성
            self.control_window.destroy()
            self.create_control_window()
            
            # 키보드 바인딩 다시 설정
            self.setup_keyboard_bindings()
            
            settings_window.destroy()
        
        # 저장/취소 버튼 프레임
        button_frame = tk.Frame(scrollable_frame, bg='#2a2a2a')
        button_frame.pack(pady=20)
        
        tk.Button(button_frame, text="저장", command=save_settings, 
                 font=self.font_small, fg='green', width=10).pack(side=tk.LEFT, padx=10)
        
        tk.Button(button_frame, text="취소", command=settings_window.destroy, 
                 font=self.font_small, fg='red', width=10).pack(side=tk.LEFT, padx=10)
        
        # 마우스 휠 스크롤 지원 (macOS 및 Windows/Linux 모두 지원)
        def _on_mousewheel(event):
            # macOS와 Windows에서 delta 값이 다름
            if event.delta:
                # macOS는 delta가 작은 값, Windows는 120 단위
                delta = event.delta
                if abs(delta) >= 120:
                    # Windows
                    canvas.yview_scroll(int(-1 * (delta / 120)), "units")
                else:
                    # macOS
                    canvas.yview_scroll(int(-1 * delta), "units")
            else:
                # Linux (Button-4, Button-5)
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
        
        def _bind_mousewheel(widget):
            """위젯과 그 자식들에 마우스 휠 이벤트 바인딩"""
            widget.bind("<MouseWheel>", _on_mousewheel)  # Windows/macOS
            widget.bind("<Button-4>", _on_mousewheel)    # Linux 스크롤 업
            widget.bind("<Button-5>", _on_mousewheel)    # Linux 스크롤 다운
            
            # 모든 자식 위젯에도 바인딩
            for child in widget.winfo_children():
                _bind_mousewheel(child)
        
        # canvas와 scrollable_frame에 마우스 휠 바인딩
        _bind_mousewheel(canvas)
        _bind_mousewheel(scrollable_frame)
    
    def run(self):
        """메인 루프 실행"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.timer_running = False
            self.root.quit()

def main():
    parser = argparse.ArgumentParser(description="Tkinter Basketball Scoreboard")
    parser.add_argument("--teamA", type=str, help="A팀 이름")
    parser.add_argument("--teamB", type=str, help="B팀 이름")
    parser.add_argument("--game", type=int, help="게임 시간 (초)")
    parser.add_argument("--shot", type=int, help="샷 클럭 시간 (초)")
    parser.add_argument("--periods", type=int, help="최대 쿼터 수")
    parser.add_argument("--small-screen", action="store_true", help="작은 화면 모드 (726x416)")
    args = parser.parse_args()
    
    # 설정 로드 및 명령행 인수 적용
    cfg = load_cfg()
    if args.teamA: cfg["teamA"] = args.teamA
    if args.teamB: cfg["teamB"] = args.teamB
    if args.game: cfg["game_seconds"] = max(1, int(args.game))
    if args.shot: cfg["shot_seconds"] = max(1, int(args.shot))
    if args.periods: cfg["period_max"] = max(1, int(args.periods))
    save_cfg(cfg)
    
    # 게임 선택 다이얼로그 표시 (작은 화면 모드 전달)
    selected_game = show_game_selection_dialog(small_screen=args.small_screen)
    
    # 스코어보드 실행 (작은 화면 모드 전달)
    app = DualMonitorScoreboard(selected_game, small_screen=args.small_screen)
    app.run()

if __name__ == "__main__":
    main()
