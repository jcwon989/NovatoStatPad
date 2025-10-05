#!/usr/bin/env python3
import tkinter as tk
from tkinter import font, messagebox, ttk
import json
import os
import time
import threading
from datetime import datetime, timedelta
import argparse

# ===== 기본 설정 =====
PERIOD_MAX_DEFAULT = 4
GAME_SECONDS_DEFAULT = 10*60
SHOT_SECONDS_DEFAULT = 24

CONFIG_PATH = os.path.expanduser("~/.scoreboard_config.json")

def load_cfg():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
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
        "team_swapped": False,
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
    """1/100초까지 표시하는 시간 포맷"""
    s = max(0, s)
    m = int(s) // 60
    r = int(s) % 60
    centi = int((s - int(s)) * 100)
    return f"{m:02d}:{r:02d}.{centi:02d}"

class DualMonitorScoreboard:
    def __init__(self):
        self.cfg = load_cfg()
        
        # 게임 상태
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
        
        # 팀 이름
        self.teamA_name = self.cfg["teamA"]
        self.teamB_name = self.cfg["teamB"]
        
        # 타이머
        self.last_update = time.time()
        self.timer_running = True
        
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
        
        # 조작용 창 폰트 (작은 화면용)
        self.font_large = font.Font(family="Arial", size=int(48 * font_ratio), weight="bold")
        self.font_medium = font.Font(family="Arial", size=int(24 * font_ratio))
        self.font_small = font.Font(family="Arial", size=int(16 * font_ratio))
        self.font_score = font.Font(family="Arial", size=int(72 * font_ratio), weight="bold")
        self.font_time = font.Font(family="Arial", size=int(36 * font_ratio), weight="bold")
        
        # 프레젠테이션용 폰트 (큰 화면용)
        self.pres_font_team = font.Font(family="Arial", size=int(60 * font_ratio), weight="bold")
        self.pres_font_score = font.Font(family="Arial", size=int(200 * font_ratio), weight="bold")
        self.pres_font_time = font.Font(family="Arial", size=int(80 * font_ratio), weight="bold")
        self.pres_font_shot = font.Font(family="Arial", size=int(100 * font_ratio), weight="bold")
        self.pres_font_period = font.Font(family="Arial", size=int(60 * font_ratio), weight="bold")
    
    def create_control_window(self):
        """조작용 창 생성 (모니터 전환 기능 포함)"""
        self.control_window = tk.Toplevel(self.root)
        self.control_window.title("Basketball Scoreboard - Control")
        
        # 반응형 창 크기 계산
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 조작용 창 크기 (화면 크기에 비례)
        control_width = max(800, min(1200, int(screen_width * 0.6)))
        control_height = max(600, min(900, int(screen_height * 0.7)))
        
        # 모니터 전환에 따른 위치 설정
        if self.cfg.get("swap_monitors", False):
            # 전환 모드: 조작용 창을 두 번째 모니터에
            self.control_window.geometry(f"{control_width}x{control_height}+1920+0")  # 두 번째 모니터
        else:
            # 기본 모드: 조작용 창을 첫 번째 모니터에
            self.control_window.geometry(f"{control_width}x{control_height}+0+0")  # 첫 번째 모니터
            
        self.control_window.configure(bg='#1a1a1a')
        self.control_window.resizable(False, False)
        
        # 메인 프레임
        main_frame = tk.Frame(self.control_window, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 제목
        title_label = tk.Label(main_frame, text="NOVATO SCOREBOARD", 
                              font=self.font_large, fg='white', bg='#1a1a1a')
        title_label.pack(pady=(0, 20))
        
        # 스코어 표시 영역 (개선된 레이아웃)
        score_frame = tk.Frame(main_frame, bg='#1a1a1a')
        score_frame.pack(fill=tk.X, pady=(0, 20))
        
        # A팀 (왼쪽)
        team_a_frame = tk.Frame(score_frame, bg='#1a1a1a')
        team_a_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.team_a_label = tk.Label(team_a_frame, text=self.teamA_name, 
                                    font=self.font_medium, fg='lightblue', bg='#1a1a1a')
        self.team_a_label.pack()
        
        self.score_a_label = tk.Label(team_a_frame, text=str(self.scoreA), 
                                     font=self.font_score, fg='white', bg='#1a1a1a')
        self.score_a_label.pack()
        
        # 중앙 (시간, 쿼터, 샷클럭)
        center_frame = tk.Frame(score_frame, bg='#1a1a1a')
        center_frame.pack(side=tk.LEFT, fill=tk.Y, padx=20)
        
        # 게임 시간
        time_frame = tk.Frame(center_frame, bg='#1a1a1a')
        time_frame.pack(pady=10)
        
        self.time_label = tk.Label(time_frame, text=self.format_time(self.game_seconds), 
                                  font=self.font_time, fg='white', bg='#1a1a1a')
        self.time_label.pack()
        
        # 쿼터
        period_frame = tk.Frame(center_frame, bg='#1a1a1a')
        period_frame.pack(pady=5)
        
        self.period_label = tk.Label(period_frame, text=f"Q{self.period}", 
                                    font=self.font_medium, fg='yellow', bg='#1a1a1a')
        self.period_label.pack()
        
        # 샷클럭
        shot_frame = tk.Frame(center_frame, bg='#1a1a1a')
        shot_frame.pack(pady=5)
        
        self.shot_label = tk.Label(shot_frame, text=str(int(self.shot_seconds)), 
                                  font=self.font_time, fg='orange', bg='#1a1a1a')
        self.shot_label.pack()
        
        # B팀 (오른쪽)
        team_b_frame = tk.Frame(score_frame, bg='#1a1a1a')
        team_b_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.team_b_label = tk.Label(team_b_frame, text=self.teamB_name, 
                                    font=self.font_medium, fg='lightcoral', bg='#1a1a1a')
        self.team_b_label.pack()
        
        self.score_b_label = tk.Label(team_b_frame, text=str(self.scoreB), 
                                     font=self.font_score, fg='white', bg='#1a1a1a')
        self.score_b_label.pack()
        
        # 타임아웃 및 파울 표시
        timeout_foul_frame = tk.Frame(main_frame, bg='#1a1a1a')
        timeout_foul_frame.pack(fill=tk.X, pady=(0, 20))
        
        # A팀 타임아웃/파울
        a_stats_frame = tk.Frame(timeout_foul_frame, bg='#1a1a1a')
        a_stats_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(a_stats_frame, text="타임아웃", font=self.font_small, fg='lightblue', bg='#1a1a1a').pack()
        self.timeout_a_label = tk.Label(a_stats_frame, text=str(self.timeoutsA), 
                                       font=self.font_medium, fg='lightblue', bg='#1a1a1a')
        self.timeout_a_label.pack()
        
        tk.Label(a_stats_frame, text="파울", font=self.font_small, fg='lightblue', bg='#1a1a1a').pack()
        self.foul_a_label = tk.Label(a_stats_frame, text=str(self.foulsA), 
                                    font=self.font_medium, fg='lightblue', bg='#1a1a1a')
        self.foul_a_label.pack()
        
        # B팀 타임아웃/파울
        b_stats_frame = tk.Frame(timeout_foul_frame, bg='#1a1a1a')
        b_stats_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        tk.Label(b_stats_frame, text="타임아웃", font=self.font_small, fg='lightcoral', bg='#1a1a1a').pack()
        self.timeout_b_label = tk.Label(b_stats_frame, text=str(self.timeoutsB), 
                                       font=self.font_medium, fg='lightcoral', bg='#1a1a1a')
        self.timeout_b_label.pack()
        
        tk.Label(b_stats_frame, text="파울", font=self.font_small, fg='lightcoral', bg='#1a1a1a').pack()
        self.foul_b_label = tk.Label(b_stats_frame, text=str(self.foulsB), 
                                    font=self.font_medium, fg='lightcoral', bg='#1a1a1a')
        self.foul_b_label.pack()
        
        # 조작 버튼들
        self.create_control_buttons(main_frame)
        
        # 힌트
        self.create_hints(main_frame)
    
    def create_control_buttons(self, parent):
        """조작 버튼들 생성"""
        button_frame = tk.Frame(parent, bg='#1a1a1a')
        button_frame.pack(fill=tk.X, pady=(0, 20))
        
        # A팀 점수
        a_team_frame = tk.LabelFrame(button_frame, text="A팀 점수", 
                                    font=self.font_small, fg='lightblue', bg='#1a1a1a')
        a_team_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Button(a_team_frame, text="+1", command=lambda: self.update_score('A', 1),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(a_team_frame, text="+2", command=lambda: self.update_score('A', 2),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(a_team_frame, text="+3", command=lambda: self.update_score('A', 3),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(a_team_frame, text="-1", command=lambda: self.update_score('A', -1),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        
        # B팀 점수
        b_team_frame = tk.LabelFrame(button_frame, text="B팀 점수", 
                                    font=self.font_small, fg='lightcoral', bg='#1a1a1a')
        b_team_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        tk.Button(b_team_frame, text="+1", command=lambda: self.update_score('B', 1),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(b_team_frame, text="+2", command=lambda: self.update_score('B', 2),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(b_team_frame, text="+3", command=lambda: self.update_score('B', 3),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(b_team_frame, text="-1", command=lambda: self.update_score('B', -1),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        
        # 타임아웃 및 파울 조작
        timeout_foul_buttons = tk.Frame(button_frame, bg='#1a1a1a')
        timeout_foul_buttons.pack(fill=tk.X, pady=(10, 0))
        
        # A팀 타임아웃/파울
        a_control_frame = tk.LabelFrame(timeout_foul_buttons, text="A팀 제어", 
                                       font=self.font_small, fg='lightblue', bg='#1a1a1a')
        a_control_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        tk.Button(a_control_frame, text="타임아웃 +1", command=lambda: self.update_timeout('A', 1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(a_control_frame, text="타임아웃 -1", command=lambda: self.update_timeout('A', -1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(a_control_frame, text="파울 +1", command=lambda: self.update_foul('A', 1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(a_control_frame, text="파울 -1", command=lambda: self.update_foul('A', -1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        
        # B팀 타임아웃/파울
        b_control_frame = tk.LabelFrame(timeout_foul_buttons, text="B팀 제어", 
                                       font=self.font_small, fg='lightcoral', bg='#1a1a1a')
        b_control_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
        tk.Button(b_control_frame, text="타임아웃 +1", command=lambda: self.update_timeout('B', 1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(b_control_frame, text="타임아웃 -1", command=lambda: self.update_timeout('B', -1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(b_control_frame, text="파울 +1", command=lambda: self.update_foul('B', 1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(b_control_frame, text="파울 -1", command=lambda: self.update_foul('B', -1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        
        # 시간 조작
        time_control_frame = tk.Frame(parent, bg='#1a1a1a')
        time_control_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Button(time_control_frame, text="게임시간 시작/정지", 
                 command=self.toggle_game_time, font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(time_control_frame, text="샷클럭 시작/정지", 
                 command=self.toggle_shot_time, font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(time_control_frame, text="24초 리셋", 
                 command=self.reset_shot_clock, font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(time_control_frame, text="전체 리셋", 
                 command=self.reset_all, font=self.font_small).pack(side=tk.LEFT, padx=5)
        
        # 시간 조작 버튼들
        time_buttons_frame = tk.Frame(parent, bg='#1a1a1a')
        time_buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Button(time_buttons_frame, text="+1초", command=lambda: self.adjust_time(1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(time_buttons_frame, text="-1초", command=lambda: self.adjust_time(-1),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(time_buttons_frame, text="+10초", command=lambda: self.adjust_time(10),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(time_buttons_frame, text="-10초", command=lambda: self.adjust_time(-10),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(time_buttons_frame, text="+1분", command=lambda: self.adjust_time(60),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        tk.Button(time_buttons_frame, text="-1분", command=lambda: self.adjust_time(-60),
                 font=self.font_small).pack(side=tk.LEFT, padx=2)
        
        # 쿼터 조작
        quarter_frame = tk.Frame(parent, bg='#1a1a1a')
        quarter_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Button(quarter_frame, text="쿼터 -1", command=lambda: self.adjust_period(-1),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        tk.Button(quarter_frame, text="쿼터 +1", command=lambda: self.adjust_period(1),
                 font=self.font_small).pack(side=tk.LEFT, padx=5)
        
        # 종료 버튼
        exit_frame = tk.Frame(parent, bg='#1a1a1a')
        exit_frame.pack(fill=tk.X, pady=(20, 0))
        
        tk.Button(exit_frame, text="종료 (Esc)", command=self.on_closing,
                 font=self.font_small, bg='red', fg='white').pack(side=tk.RIGHT, padx=5)
    
    def create_hints(self, parent):
        """힌트 표시"""
        hints_frame = tk.LabelFrame(parent, text="키보드 단축키", 
                                   font=self.font_small, fg='gray', bg='#1a1a1a')
        hints_frame.pack(fill=tk.X, pady=(10, 0))
        
        hints_text = """점수: 1/2/3(A팀 +1/+2/+3) | 0/9/8(B팀 +1/+2/+3) | `/-(A/B팀 -1)
시간: 스페이스(게임시간) | s(샷클럭) | S(24초 리셋) | ←→(±1초) | ↑↓(±10초) | <>(±1분)
타임아웃: t/y(A/B팀 -1) | T/Y(A/B팀 +1) | 파울: f/j(A/B팀 +1) | F/J(A/B팀 -1)
게임: R(리셋) | [](쿼터 ±1) | F2(설정) | F3(모니터 전환) | Esc(종료)"""
        
        hints_label = tk.Label(hints_frame, text=hints_text, 
                              font=self.font_small, fg='gray', bg='#1a1a1a', justify=tk.LEFT)
        hints_label.pack(anchor=tk.W)
    
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
        
        # 중앙정렬을 위한 컨테이너 프레임
        center_container = tk.Frame(main_frame, bg='#111111')
        center_container.pack(expand=True, fill=tk.BOTH)
        
        # 팀 순서가 바뀌었는지 확인
        is_swapped = self.cfg.get("team_swapped", False)
        
        if is_swapped:
            # 팀 순서가 바뀐 경우: B팀이 왼쪽, A팀이 오른쪽
            self.create_team_display(center_container, self.teamB_name, self.teamA_name, 
                                   'lightcoral', 'lightblue', True)
        else:
            # 기본 순서: A팀이 왼쪽, B팀이 오른쪽
            self.create_team_display(center_container, self.teamA_name, self.teamB_name, 
                                   'lightblue', 'lightcoral', False)
        
        # 중앙 시간 표시
        self.create_time_display(center_container)
    
    def create_team_display(self, parent, left_team, right_team, left_color, right_color, swapped):
        """팀 표시 영역 생성"""
        # 왼쪽 팀 (A팀 또는 B팀)
        left_frame = tk.Frame(parent, bg='#111111')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        left_team_label = tk.Label(left_frame, text=left_team, 
                                  font=self.pres_font_team, 
                                  fg=left_color, bg='#111111')
        left_team_label.pack(pady=(50, 20))
        
        if swapped:
            self.pres_score_b_label = tk.Label(left_frame, text=str(self.scoreB), 
                                             font=self.pres_font_score, 
                                             fg='white', bg='#111111')
            self.pres_score_b_label.pack(pady=(0, 50))
        else:
            self.pres_score_a_label = tk.Label(left_frame, text=str(self.scoreA), 
                                             font=self.pres_font_score, 
                                             fg='white', bg='#111111')
            self.pres_score_a_label.pack(pady=(0, 50))
        
        # 오른쪽 팀 (B팀 또는 A팀)
        right_frame = tk.Frame(parent, bg='#111111')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        right_team_label = tk.Label(right_frame, text=right_team, 
                                   font=self.pres_font_team, 
                                   fg=right_color, bg='#111111')
        right_team_label.pack(pady=(50, 20))
        
        if swapped:
            self.pres_score_a_label = tk.Label(right_frame, text=str(self.scoreA), 
                                             font=self.pres_font_score, 
                                             fg='white', bg='#111111')
            self.pres_score_a_label.pack(pady=(0, 50))
        else:
            self.pres_score_b_label = tk.Label(right_frame, text=str(self.scoreB), 
                                             font=self.pres_font_score, 
                                             fg='white', bg='#111111')
            self.pres_score_b_label.pack(pady=(0, 50))
    
    def create_time_display(self, parent):
        """시간 표시 영역 생성"""
        time_frame = tk.Frame(parent, bg='#111111')
        time_frame.pack(fill=tk.BOTH, expand=True)
        
        # 게임 시간
        self.pres_time_label = tk.Label(time_frame, text=fmt_mmss_centi(self.game_seconds), 
                                       font=self.pres_font_time, 
                                       fg='yellow', bg='#111111')
        self.pres_time_label.pack(pady=(100, 20))
        
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
            self.toggle_shot_time()
        elif key == 'S':
            self.reset_shot_clock()  # 24초 리셋
        elif key == 'r':
            self.reset_all()
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
        # 타임아웃 조작
        elif key == 't':
            self.update_timeout('A', -1)  # A팀 타임아웃 -1
        elif key == 'y':
            self.update_timeout('B', -1)  # B팀 타임아웃 -1
        elif key == 'T':
            self.update_timeout('A', 1)   # A팀 타임아웃 +1
        elif key == 'Y':
            self.update_timeout('B', 1)   # B팀 타임아웃 +1
        # 파울 조작
        elif key == 'f':
            self.update_foul('A', 1)      # A팀 파울 +1
        elif key == 'j':
            self.update_foul('B', 1)      # B팀 파울 +1
        elif key == 'F':
            self.update_foul('A', -1)     # A팀 파울 -1
        elif key == 'J':
            self.update_foul('B', -1)     # B팀 파울 -1
        elif key == 'F2':
            self.show_settings()
        elif key == 'F3':
            # 모니터 전환 토글
            self.cfg["swap_monitors"] = not self.cfg.get("swap_monitors", False)
            save_cfg(self.cfg)
            if hasattr(self, 'presentation_window') and self.cfg.get("dual_monitor", False):
                self.presentation_window.destroy()
                self.create_presentation_window()
        elif key == 'Escape':
            self.on_closing()
    
    def update_score(self, team, points):
        """점수 업데이트"""
        if team == 'A':
            self.scoreA = max(0, self.scoreA + points)
        else:
            self.scoreB = max(0, self.scoreB + points)
        self.update_displays()
    
    def update_timeout(self, team, change):
        """타임아웃 업데이트"""
        if team == 'A':
            self.timeoutsA = max(0, self.timeoutsA + change)
        else:
            self.timeoutsB = max(0, self.timeoutsB + change)
        self.update_displays()
    
    def update_foul(self, team, change):
        """파울 업데이트"""
        if team == 'A':
            self.foulsA = max(0, self.foulsA + change)
        else:
            self.foulsB = max(0, self.foulsB + change)
        self.update_displays()
    
    def toggle_game_time(self):
        """게임 시간 시작/정지"""
        self.running_game = not self.running_game
        self.update_displays()
    
    def toggle_shot_time(self):
        """샷 클럭 시작/정지"""
        self.running_shot = not self.running_shot
        self.update_displays()
    
    def adjust_time(self, seconds):
        """시간 조정"""
        self.game_seconds = max(0, self.game_seconds + seconds)
        self.update_displays()
    
    def adjust_period(self, delta):
        """쿼터 조정"""
        self.period = max(1, min(self.cfg.get("period_max", 4), self.period + delta))
        self.update_displays()
    
    def reset_shot_clock(self):
        """샷클럭 24초 리셋"""
        self.shot_seconds = 24
        self.running_shot = False
        self.update_displays()
    
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
        self.update_displays()
    
    def start_timer(self):
        """타이머 시작"""
        def timer_thread():
            while self.timer_running:
                current_time = time.time()
                dt = current_time - self.last_update
                self.last_update = current_time
                
                # 게임 시간 업데이트
                if self.running_game and self.game_seconds > 0:
                    self.game_seconds = max(0, self.game_seconds - dt)
                
                # 샷 클럭 업데이트
                if self.running_shot and self.shot_seconds > 0:
                    self.shot_seconds = max(0, self.shot_seconds - dt)
                
                # UI 업데이트 (메인 스레드에서)
                self.root.after(0, self.update_displays)
                
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
        
        # 타임아웃과 파울 업데이트
        if hasattr(self, 'timeout_a_label'):
            self.timeout_a_label.config(text=str(self.timeoutsA))
            self.timeout_b_label.config(text=str(self.timeoutsB))
            self.foul_a_label.config(text=str(self.foulsA))
            self.foul_b_label.config(text=str(self.foulsB))
        
        # 프레젠테이션 창 업데이트
        if hasattr(self, 'presentation_window'):
            # 팀 순서에 따라 점수 표시
            is_swapped = self.cfg.get("team_swapped", False)
            if is_swapped:
                self.pres_score_b_label.config(text=str(self.scoreB))
                self.pres_score_a_label.config(text=str(self.scoreA))
            else:
                self.pres_score_a_label.config(text=str(self.scoreA))
                self.pres_score_b_label.config(text=str(self.scoreB))
            
            self.pres_time_label.config(text=fmt_mmss_centi(self.game_seconds))
            self.pres_period_label.config(text=f"Q{self.period}")
            self.pres_shot_label.config(text=str(int(self.shot_seconds)))
            
            # 마지막 10초부터 빨간색
            if self.game_seconds <= 10:
                self.pres_time_label.config(fg='red')
            else:
                self.pres_time_label.config(fg='yellow')
            
            # 마지막 5초부터 샷클럭 빨간색
            if self.shot_seconds <= 5:
                self.pres_shot_label.config(fg='red')
            else:
                self.pres_shot_label.config(fg='orange')
    
    def on_closing(self):
        """앱 종료 처리"""
        self.timer_running = False
        save_cfg(self.cfg)
        self.root.quit()
        self.root.destroy()
    
    def show_settings(self):
        """설정 창 표시"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("게임 설정")
        settings_window.geometry("400x500")
        settings_window.configure(bg='#2a2a2a')
        settings_window.resizable(False, False)
        
        # 설정 항목들
        tk.Label(settings_window, text="A팀 이름:", fg='white', bg='#2a2a2a').pack(pady=5)
        team_a_entry = tk.Entry(settings_window, font=self.font_small)
        team_a_entry.pack(pady=5)
        team_a_entry.insert(0, self.cfg["teamA"])
        
        tk.Label(settings_window, text="B팀 이름:", fg='white', bg='#2a2a2a').pack(pady=5)
        team_b_entry = tk.Entry(settings_window, font=self.font_small)
        team_b_entry.pack(pady=5)
        team_b_entry.insert(0, self.cfg["teamB"])
        
        tk.Label(settings_window, text="듀얼모니터:", fg='white', bg='#2a2a2a').pack(pady=5)
        dual_monitor_var = tk.BooleanVar(value=self.cfg.get("dual_monitor", False))
        tk.Checkbutton(settings_window, variable=dual_monitor_var, 
                      fg='white', bg='#2a2a2a', selectcolor='#444444').pack()
        
        tk.Label(settings_window, text="모니터 내용 전환 (1-2 ↔ 2-1):", fg='white', bg='#2a2a2a').pack(pady=5)
        swap_monitors_var = tk.BooleanVar(value=self.cfg.get("swap_monitors", False))
        tk.Checkbutton(settings_window, variable=swap_monitors_var, 
                      fg='white', bg='#2a2a2a', selectcolor='#444444').pack()
        
        tk.Label(settings_window, text="팀 순서 바꾸기:", fg='white', bg='#2a2a2a').pack(pady=5)
        team_swapped_var = tk.BooleanVar(value=self.cfg.get("team_swapped", False))
        tk.Checkbutton(settings_window, variable=team_swapped_var, 
                      fg='white', bg='#2a2a2a', selectcolor='#444444').pack()
        
        def save_settings():
            self.cfg["teamA"] = team_a_entry.get()
            self.cfg["teamB"] = team_b_entry.get()
            self.cfg["dual_monitor"] = dual_monitor_var.get()
            self.cfg["swap_monitors"] = swap_monitors_var.get()
            self.cfg["team_swapped"] = team_swapped_var.get()
            
            self.teamA_name = self.cfg["teamA"]
            self.teamB_name = self.cfg["teamB"]
            
            save_cfg(self.cfg)
            self.update_displays()
            
            # 모니터 전환 설정이 변경된 경우 창을 다시 생성
            if hasattr(self, 'presentation_window') and self.cfg.get("dual_monitor", False):
                self.presentation_window.destroy()
                self.create_presentation_window()
            
            settings_window.destroy()
        
        tk.Button(settings_window, text="저장", command=save_settings, 
                 font=self.font_small).pack(pady=20)
    
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
    args = parser.parse_args()
    
    # 설정 로드 및 명령행 인수 적용
    cfg = load_cfg()
    if args.teamA: cfg["teamA"] = args.teamA
    if args.teamB: cfg["teamB"] = args.teamB
    if args.game: cfg["game_seconds"] = max(1, int(args.game))
    if args.shot: cfg["shot_seconds"] = max(1, int(args.shot))
    if args.periods: cfg["period_max"] = max(1, int(args.periods))
    save_cfg(cfg)
    
    # 스코어보드 실행
    app = DualMonitorScoreboard()
    app.run()

if __name__ == "__main__":
    main()
