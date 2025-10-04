#!/usr/bin/env python3
import sys, os, time, json, argparse
import pygame
from game_selection import show_game_selection
from dotenv import load_dotenv

# ===== 기본 설정 =====
PERIOD_MAX_DEFAULT = 4
GAME_SECONDS_DEFAULT = 10*60
SHOT_SECONDS_DEFAULT = 24

CONFIG_PATH = os.path.expanduser("~/.scoreboard_config.json")
FONT_CANDIDATES = [
    "font/Pretendard-Bold.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

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
        "overtime_seconds": 5*60,  # 5분 연장전
        "timeouts_per_team": 3,
        "windowed": False,
        "width": 1920,
        "height": 1080,
        "hints_visible": True,
    }

def save_cfg(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def show_exit_confirm_fullscreen(screen, font_large, font_medium):
    """종료 확인 전체화면 표시 (hint 스타일)"""
    W, H = screen.get_size()
    
    # 전체화면 배경
    screen.fill((0, 0, 0))
    
    # 제목
    title = font_large.render("프로그램을 종료하시겠습니까?", True, (255, 255, 255))
    title_rect = title.get_rect(center=(W//2, H//2 - int(H*0.1)))
    screen.blit(title, title_rect)
    
    # 선택 옵션들
    options = [
        "Y - 예, 프로그램 종료",
        "N - 아니오, 계속하기",
        "M - 목록으로 돌아가기",
        "ESC - 취소"
    ]
    
    # 옵션들 표시
    for i, option in enumerate(options):
        option_text = font_medium.render(option, True, (200, 200, 200))
        option_rect = option_text.get_rect(center=(W//2, H//2 + int(H*0.05) + i * int(H*0.08)))
        screen.blit(option_text, option_rect)
    
    pygame.display.flip()


def show_settings_window(cfg):
    """게임 설정 창을 표시하고 설정을 수정할 수 있게 함"""
    pygame.init()
    settings_screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("게임 설정")
    
    # 폰트 설정
    font_large = load_font(32)
    font_medium = load_font(24)
    font_small = load_font(18)
    
    # 설정 항목들 (기존 설정 파일과 호환)
    settings = {
        "teamA": cfg["teamA"],
        "teamB": cfg["teamB"],
        "game_seconds": str(cfg["game_seconds"] // 60),  # 분 단위로 표시
        "overtime_seconds": str(cfg.get("overtime_seconds", 5*60) // 60),
        "shot_seconds": str(cfg["shot_seconds"]),
        "period_max": str(cfg["period_max"]),
        "timeouts_per_team": str(cfg.get("timeouts_per_team", 3))
    }
    
    # 입력 필드 정보
    fields = [
        {"key": "teamA", "label": "A팀 이름", "x": 50, "y": 80, "width": 300},
        {"key": "teamB", "label": "B팀 이름", "x": 450, "y": 80, "width": 300},
        {"key": "game_seconds", "label": "쿼터 시간 (분)", "x": 50, "y": 150, "width": 150},
        {"key": "overtime_seconds", "label": "연장전 시간 (분)", "x": 250, "y": 150, "width": 150},
        {"key": "shot_seconds", "label": "샷 클럭 (초)", "x": 450, "y": 150, "width": 150},
        {"key": "period_max", "label": "최대 쿼터 수", "x": 50, "y": 220, "width": 150},
        {"key": "timeouts_per_team", "label": "팀당 타임아웃 수", "x": 250, "y": 220, "width": 150},
    ]
    
    active_field = None
    clock = pygame.time.Clock()
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return cfg
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return cfg
                elif event.key == pygame.K_RETURN:
                    # 설정 저장
                    try:
                        cfg["teamA"] = settings["teamA"]
                        cfg["teamB"] = settings["teamB"]
                        cfg["game_seconds"] = int(settings["game_seconds"]) * 60
                        cfg["overtime_seconds"] = int(settings["overtime_seconds"]) * 60
                        cfg["shot_seconds"] = int(settings["shot_seconds"])
                        cfg["period_max"] = int(settings["period_max"])
                        cfg["timeouts_per_team"] = int(settings["timeouts_per_team"])
                        save_cfg(cfg)
                        pygame.quit()
                        return cfg
                    except ValueError:
                        pass  # 잘못된 입력 무시
                elif event.key == pygame.K_TAB:
                    # 다음 필드로 이동
                    if active_field is None:
                        active_field = 0
                    else:
                        active_field = (active_field + 1) % len(fields)
                elif active_field is not None:
                    field = fields[active_field]
                    if event.key == pygame.K_BACKSPACE:
                        settings[field["key"]] = settings[field["key"]][:-1]
                    else:
                        if field["key"] in ["teamA", "teamB"]:
                            # 팀명은 모든 문자 허용
                            settings[field["key"]] += event.unicode
                        else:
                            # 숫자만 허용
                            if event.unicode.isdigit():
                                settings[field["key"]] += event.unicode
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # 마우스 클릭으로 필드 선택
                mouse_x, mouse_y = pygame.mouse.get_pos()
                for i, field in enumerate(fields):
                    if (field["x"] <= mouse_x <= field["x"] + field["width"] and
                        field["y"] <= mouse_y <= field["y"] + 30):
                        active_field = i
                        break
        
        # 화면 그리기
        settings_screen.fill((30, 30, 30))
        
        # 제목
        title = font_large.render("게임 설정", True, (255, 255, 255))
        settings_screen.blit(title, (400 - title.get_width()//2, 20))
        
        # 필드들 그리기
        for i, field in enumerate(fields):
            # 라벨
            label = font_medium.render(field["label"], True, (200, 200, 200))
            settings_screen.blit(label, (field["x"], field["y"] - 30))
            
            # 입력 필드
            color = (100, 100, 100) if active_field == i else (60, 60, 60)
            pygame.draw.rect(settings_screen, color, (field["x"], field["y"], field["width"], 30))
            pygame.draw.rect(settings_screen, (255, 255, 255), (field["x"], field["y"], field["width"], 30), 2)
            
            # 텍스트
            text = font_small.render(settings[field["key"]], True, (255, 255, 255))
            settings_screen.blit(text, (field["x"] + 5, field["y"] + 5))
        
        # 안내 텍스트
        help_text = [
            "Tab: 다음 필드 | Enter: 저장 | Esc: 취소",
            "마우스로 필드 클릭하여 선택 가능"
        ]
        for i, text in enumerate(help_text):
            help_surf = font_small.render(text, True, (150, 150, 150))
            settings_screen.blit(help_surf, (50, 500 + i * 25))
        
        pygame.display.flip()
        clock.tick(60)

def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return pygame.font.Font(p, size)
    return pygame.font.SysFont(None, size)

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
    return f"{m:02d}:{r:02d} {centi:02d}"

def parse_args(cfg):
    ap = argparse.ArgumentParser(description="Offline Basketball Scoreboard")
    ap.add_argument("--teamA", type=str, help="Left team name")
    ap.add_argument("--teamB", type=str, help="Right team name")
    ap.add_argument("--game", type=int, help="Game clock seconds (e.g., 600 for 10:00)")
    ap.add_argument("--shot", type=int, help="Shot clock seconds (e.g., 24)")
    ap.add_argument("--periods", type=int, help="Max periods (default 4)")
    ap.add_argument("--windowed", action="store_true", help="Run windowed (for development)")
    ap.add_argument("--size", type=str, help="Window size WxH (e.g., 1280x720)")
    args = ap.parse_args()

    if args.teamA: cfg["teamA"] = args.teamA
    if args.teamB: cfg["teamB"] = args.teamB
    if args.game: cfg["game_seconds"] = max(1, int(args.game))
    if args.shot: cfg["shot_seconds"] = max(1, int(args.shot))
    if args.periods: cfg["period_max"] = max(1, int(args.periods))
    if args.windowed: cfg["windowed"] = True
    if args.size:
        try:
            w, h = args.size.lower().split("x")
            cfg["width"], cfg["height"] = int(w), int(h)
            cfg["windowed"] = True
        except Exception:
            pass
    return cfg

def main():
    # .env 로드 (APP_DEBUG 등)
    try:
        load_dotenv()
    except Exception:
        pass
    cfg = parse_args(load_cfg())
    save_cfg(cfg)  # 사용자가 준 옵션을 저장

    teamA_name = cfg["teamA"]
    teamB_name = cfg["teamB"]
    PERIOD_MAX = cfg["period_max"]
    GAME_SECONDS_INIT = cfg["game_seconds"]
    SHOT_SECONDS_INIT = cfg["shot_seconds"]
    TIMEOUTS_INIT = cfg.get("timeouts_per_team", 3)

    pygame.init()
    flags = 0
    if not cfg["windowed"]:
        flags |= pygame.FULLSCREEN
    screen = pygame.display.set_mode((cfg["width"], cfg["height"]), flags)
    pygame.display.set_caption("Basketball Scoreboard")

    W, H = screen.get_size()
    clock = pygame.time.Clock()
    FPS = 60

    # 폰트
    fontTeam = load_font(int(H*0.074))   # ~80 on 1080p
    fontScore = load_font(int(H*0.296))  # ~320
    fontBig = load_font(int(H*0.167))    # ~180 (1.5배)
    fontMedium = load_font(int(H*0.084))    # ~180 (1.5배)
    fontSmall = load_font(int(H*0.033))  # ~36
    fontTimeout = load_font(int(H*0.060))  # ~65 (타임아웃 표시용)
    fontCenti = load_font(int(H*0.084))  # ~90 (1/100초 표시용, 시간의 절반 크기)

    # 게임 선택 화면 표시
    selected_game = show_game_selection(screen, fontBig, fontMedium, fontSmall)
    if os.getenv("APP_DEBUG", "0").lower() in {"1", "true", "yes", "on"}:
        if selected_game:
            print(f"[scoreboard] selected_game id={selected_game.get('id')} team1='{selected_game.get('team1')}' team2='{selected_game.get('team2')}'")
        else:
            print("[scoreboard] no game selected (offline mode)")
    
    # 선택된 게임이 있으면 설정 업데이트
    if selected_game:
        cfg["teamA"] = selected_game.get("team1", cfg["teamA"])
        cfg["teamB"] = selected_game.get("team2", cfg["teamB"])
        # 게임 날짜 정보도 저장 (필요시 사용)
        cfg["selected_game_id"] = selected_game.get("id")
        save_cfg(cfg)
        if os.getenv("APP_DEBUG", "0").lower() in {"1", "true", "yes", "on"}:
            print(f"[scoreboard] applied teamA='{cfg['teamA']}', teamB='{cfg['teamB']}', game_id={cfg.get('selected_game_id')}")
        # 화면 표시용 런타임 변수도 즉시 갱신
        teamA_name = cfg["teamA"]
        teamB_name = cfg["teamB"]

    # 상태
    scoreA = 0
    scoreB = 0
    period = 1
    timeoutsA = TIMEOUTS_INIT
    timeoutsB = TIMEOUTS_INIT
    foulsA = 0  # A팀 파울 수
    foulsB = 0  # B팀 파울 수
    running_game = False
    running_shot = False
    game_seconds = GAME_SECONDS_INIT
    shot_seconds = SHOT_SECONDS_INIT

    last_t = time.perf_counter()
    mouse_visible = False
    hints_visible = cfg.get("hints_visible", True)
    pygame.mouse.set_visible(mouse_visible)
    # 한글 입력 경고 타임스탬프 초기화
    last_korean_warning_at = None

    # 사운드(선택)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    buzzer_main_path = os.path.join(script_dir, "sound", "buzzer_main.wav")
    beep_path = os.path.join(script_dir, "sound", "beep.wav")
    
    has_sound = False
    buzzer_main = None
    beep_sound = None
    
    if os.path.exists(buzzer_main_path):
        try:
            pygame.mixer.init()
            buzzer_main = pygame.mixer.Sound(buzzer_main_path)
            has_sound = True
        except Exception:
            pass
    
    if os.path.exists(beep_path):
        try:
            if not has_sound:
                pygame.mixer.init()
                has_sound = True
            beep_sound = pygame.mixer.Sound(beep_path)
        except Exception:
            pass

    def beep():
        if has_sound and beep_sound:
            try: beep_sound.play()
            except Exception: pass
    
    def main_buzzer():
        if has_sound and buzzer_main:
            try: buzzer_main.play()
            except Exception: pass

    def is_korean_char(ch):
        code = ord(ch)
        return (
            0xAC00 <= code <= 0xD7A3  # Hangul Syllables
            or 0x1100 <= code <= 0x11FF  # Hangul Jamo
            or 0x3130 <= code <= 0x318F  # Hangul Compatibility Jamo
        )

    def reset_all():
        nonlocal scoreA, scoreB, period, timeoutsA, timeoutsB, foulsA, foulsB
        nonlocal game_seconds, shot_seconds, running_game, running_shot
        scoreA = scoreB = 0
        period = 1
        timeoutsA = timeoutsB = TIMEOUTS_INIT
        foulsA = foulsB = 0
        game_seconds = GAME_SECONDS_INIT
        shot_seconds = SHOT_SECONDS_INIT
        running_game = False
        running_shot = False

    def render():
        screen.fill((17,17,17))
        
        if hints_visible:
            # 힌트만 표시
            hints = [
                "점수 조작: 1/2/3(A팀 +1/+2/+3점) | `(A팀 -1점) | 0/9/8(B팀 +1/+2/+3점) | -(B팀 -1점)",
                "",
                "시간 조작: 스페이스(게임시간 시작/정지) | ←→(±1초) | ↑↓(±10초) | < >(±1분)",
                "",
                "샷클럭 조작: S(샷클럭 시작/정지) | D(24초 리셋) | F(14초 리셋) | C/V(±1초)",
                "",
                "게임 :  R(전체 리셋) | [ / ](쿼터 감소/증가)", 
                "",
                "기타: Q/W(A팀 타임아웃 ±1) | Z/X(A A팀 파울 ±1) | O/P(B팀 타임아웃 ±1) | N/M(A/B팀 파울 ±1)",
                "",
                "환경: G(전체화면) | J(마우스) | H(힌트) | F2(설정) | Esc(종료)",
            ]
            # 힌트를 화면 중앙에 표시 (줄간격 개선)
            line_height = int(H*0.05)  # 줄간격을 더 넓게 (5%)
            start_y = H // 2 - len(hints) * line_height // 2
            for i, line in enumerate(hints):
                surf = fontSmall.render(line, True, (200,200,200))
                screen.blit(surf, (W//2 - surf.get_width()//2, start_y + i*line_height))
        else:
            # 좌단: A팀 정보
            left_x = W // 6
            teamA = fontTeam.render(teamA_name, True, (220,220,220))
            scoreA_surf = fontScore.render(str(scoreA), True, (255,255,255))
            timeoutA_surf = fontTimeout.render(f"Timeouts: {timeoutsA}", True, (180,180,220))
            foulA_surf = fontTimeout.render(f"Fouls: {foulsA}", True, (220,180,180))
            
            screen.blit(teamA, (left_x - teamA.get_width()//2, int(H*0.2)))
            screen.blit(scoreA_surf, (left_x - scoreA_surf.get_width()//2, int(H*0.35)))
            screen.blit(timeoutA_surf, (left_x - timeoutA_surf.get_width()//2, int(H*0.75)))
            screen.blit(foulA_surf, (left_x - foulA_surf.get_width()//2, int(H*0.85)))

            # 우단: B팀 정보
            right_x = W * 5 // 6
            teamB = fontTeam.render(teamB_name, True, (220,220,220))
            scoreB_surf = fontScore.render(str(scoreB), True, (255,255,255))
            timeoutB_surf = fontTimeout.render(f"Timeouts: {timeoutsB}", True, (220,180,180))
            foulB_surf = fontTimeout.render(f"Fouls: {foulsB}", True, (180,180,220))
            
            screen.blit(teamB, (right_x - teamB.get_width()//2, int(H*0.2)))
            screen.blit(scoreB_surf, (right_x - scoreB_surf.get_width()//2, int(H*0.35)))
            screen.blit(timeoutB_surf, (right_x - timeoutB_surf.get_width()//2, int(H*0.75)))
            screen.blit(foulB_surf, (right_x - foulB_surf.get_width()//2, int(H*0.85)))

            # 중단: 시간/쿼터/샷클락
            center_x = W // 2
            t_str = fmt_mmss_centi(game_seconds)
            # 시간과 1/100초를 분리해서 렌더링
            time_part = t_str.split(' ')[0]  # "09:00"
            centi_part = t_str.split(' ')[1]  # "22"
            # 마지막 10초부터 빨간색으로 변경
            time_color = (255,80,80) if game_seconds <= 10 else (255,255,255)
            game_surf = fontBig.render(time_part, True, time_color)
            centi_surf = fontCenti.render(centi_part, True, time_color)
            prd_surf = fontBig.render(f"Q{period}", True, (200,200,200))
            shot_color = (255,80,80) if shot_seconds <= 5 else (255,215,0)
            shot_surf = fontBig.render(str(max(0,int(shot_seconds))), True, shot_color)
            
            # 중앙 배치: 쿼터가 화면 중앙, 시간은 상단과 쿼터 중간, 샷클락은 쿼터와 하단 중간
            center_y = H // 2  # 쿼터 위치 (화면 중앙)
            time_y = (0 + center_y) // 2  # 시간 위치 (상단과 쿼터 중간)
            shot_y = (center_y + H) // 2  # 샷클락 위치 (쿼터와 하단 중간)
            
            # 시간과 1/100초를 고정 위치에 표시 (해상도에 비례)
            # 시간은 중앙에서 왼쪽으로, 1/100초는 중앙에서 오른쪽으로 고정
            time_x = center_x - int(W * 0.015)  # 시간 고정 위치 (화면 너비의 15% 왼쪽)
            centi_x = center_x + int(W * 0.16)  # 1/100초 고정 위치 (화면 너비의 8% 오른쪽)
            screen.blit(game_surf, (time_x - game_surf.get_width()//2, int(time_y - game_surf.get_height()//2)))
            screen.blit(centi_surf, (centi_x - centi_surf.get_width()//2, int(time_y - centi_surf.get_height()//3)))
            screen.blit(prd_surf, (center_x - prd_surf.get_width()//2, int(center_y - prd_surf.get_height()//2)))
            screen.blit(shot_surf, (center_x - shot_surf.get_width()//2, int(shot_y - shot_surf.get_height()//2)))

        # 한글 입력 경고 오버레이 (상단 중앙, 노란색)
        if last_korean_warning_at is not None and (time.perf_counter() - last_korean_warning_at) < 3.0:
            warn_text = "입력 언어가 한글입니다. 영어(EN)로 전환하세요."
            warn_surf = fontSmall.render(warn_text, True, (255, 215, 0))
            screen.blit(warn_surf, (W//2 - warn_surf.get_width()//2, int(H*0.03)))

        pygame.display.flip()

    def swap_teams():
        nonlocal teamA_name, teamB_name, scoreA, scoreB, timeoutsA, timeoutsB, foulsA, foulsB
        teamA_name, teamB_name = teamB_name, teamA_name
        scoreA, scoreB = scoreB, scoreA
        timeoutsA, timeoutsB = timeoutsB, timeoutsA
        foulsA, foulsB = foulsB, foulsA

    reset_all()
    render()

    while True:
        now = time.perf_counter()
        dt = now - last_t
        last_t = now

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                save_cfg(cfg); pygame.quit(); sys.exit(0)
            if e.type == pygame.KEYDOWN:
                k = e.key
                mod = pygame.key.get_mods()

                # 한글 입력 감지 → 경고 표시 타임스탬프 갱신
                try:
                    ch = e.unicode
                except Exception:
                    ch = ""
                if ch:
                    for _c in ch:
                        if is_korean_char(_c):
                            last_korean_warning_at = time.perf_counter()
                            break

                if k == pygame.K_ESCAPE:
                    # 종료 확인 전체화면 표시
                    show_exit_confirm_fullscreen(screen, fontMedium, fontSmall)
                    
                    # 사용자 입력 대기
                    waiting_for_confirm = True
                    while waiting_for_confirm:
                        for confirm_event in pygame.event.get():
                            if confirm_event.type == pygame.QUIT:
                                save_cfg(cfg)
                                pygame.quit()
                                sys.exit(0)
                            elif confirm_event.type == pygame.KEYDOWN:
                                if confirm_event.key == pygame.K_y or confirm_event.key == pygame.K_RETURN:
                                    save_cfg(cfg)
                                    pygame.quit()
                                    sys.exit(0)
                                elif confirm_event.key == pygame.K_m:
                                    # 목록으로 돌아가기: 모든 상태 초기화 후 게임 선택 화면으로 이동
                                    # 런타임 상태 초기화
                                    scoreA = 0; scoreB = 0
                                    period = 1
                                    game_seconds = GAME_SECONDS_INIT
                                    shot_seconds = SHOT_SECONDS_INIT
                                    running_game = False
                                    running_shot = False
                                    last_beep_sec_game = None
                                    last_beep_sec_shot = None
                                    timeoutsA = TIMEOUTS_INIT
                                    timeoutsB = TIMEOUTS_INIT
                                    foulsA = 0
                                    foulsB = 0
                                    teamA_name = cfg["teamA"]
                                    teamB_name = cfg["teamB"]
                                    hints_visible = cfg.get("hints_visible", True)

                                    waiting_for_confirm = False

                                    # 게임 선택 화면 표시
                                    selected_game2 = show_game_selection(screen, fontBig, fontMedium, fontSmall)
                                    if selected_game2:
                                        cfg["teamA"] = selected_game2.get("team1", cfg["teamA"])
                                        cfg["teamB"] = selected_game2.get("team2", cfg["teamB"])
                                        cfg["selected_game_id"] = selected_game2.get("id")
                                        save_cfg(cfg)
                                        teamA_name = cfg["teamA"]
                                        teamB_name = cfg["teamB"]
                                elif confirm_event.key == pygame.K_n or confirm_event.key == pygame.K_ESCAPE:
                                    waiting_for_confirm = False
                        
                        # 깜빡임 방지를 위해 화면을 다시 그리지 않음
                        clock.tick(60)  # CPU 사용량 조절만
                elif k == pygame.K_g:
                    cfg["windowed"] = not cfg["windowed"]
                    save_cfg(cfg)
                    if cfg["windowed"]:
                        pygame.display.set_mode((cfg["width"], cfg["height"]))
                    else:
                        pygame.display.set_mode((cfg["width"], cfg["height"]), pygame.FULLSCREEN)
                elif k == pygame.K_SPACE:
                    running_game = not running_game
                elif k == pygame.K_s:
                    running_shot = not running_shot
                elif k == pygame.K_r:
                    reset_all()
                elif k == pygame.K_LEFTBRACKET:
                    period = max(1, period - 1)
                elif k == pygame.K_RIGHTBRACKET:
                    period = min(PERIOD_MAX, period + 1)
                elif k == pygame.K_BACKQUOTE:
                    scoreA = max(0, scoreA - 1)
                elif k == pygame.K_MINUS:
                    scoreB = max(0, scoreB - 1)
                elif k == pygame.K_1:
                    scoreA += 1
                elif k == pygame.K_2:
                    scoreA += 2
                elif k == pygame.K_3:
                    scoreA += 3
                elif k == pygame.K_0:
                    scoreB += 1
                elif k == pygame.K_9:
                    scoreB += 2
                elif k == pygame.K_8:
                    scoreB += 3
                elif k == pygame.K_q:
                    timeoutsA = max(0, timeoutsA - 1)
                elif k == pygame.K_w:
                    timeoutsA += 1
                elif k == pygame.K_z:
                    foulsA = max(0, foulsA - 1)
                elif k == pygame.K_x:
                    foulsA += 1
                elif k == pygame.K_o:
                    timeoutsB = max(0, timeoutsB - 1)
                elif k == pygame.K_p:
                    timeoutsB += 1
                elif k == pygame.K_n:
                    foulsB = max(0, foulsB - 1)
                elif k == pygame.K_m:
                    foulsB += 1
                elif k == pygame.K_j:
                    mouse_visible = not pygame.mouse.get_visible()
                    pygame.mouse.set_visible(mouse_visible)
                elif k == pygame.K_h:
                    hints_visible = not hints_visible
                    cfg["hints_visible"] = hints_visible
                    save_cfg(cfg)
                elif k == pygame.K_d:
                    shot_seconds = 24
                    running_shot = False
                elif k == pygame.K_f:
                    shot_seconds = 14
                    running_shot = False
                elif k == pygame.K_c:
                    shot_seconds += 1
                elif k == pygame.K_v:
                    shot_seconds = max(0, shot_seconds - 1)
                elif k == pygame.K_PAGEUP:
                    game_seconds += 60
                elif k == pygame.K_PAGEDOWN:
                    game_seconds = max(0, game_seconds - 60)
                elif k == pygame.K_t and (mod & pygame.KMOD_CTRL):
                    swap_teams()
                elif k == pygame.K_LEFT:
                    game_seconds = max(0, game_seconds - 1)
                elif k == pygame.K_RIGHT:
                    game_seconds += 1
                elif k == pygame.K_UP:
                    game_seconds += 10
                elif k == pygame.K_DOWN:
                    game_seconds = max(0, game_seconds - 10)
                elif k == pygame.K_COMMA:  # < 키
                    game_seconds = max(0, game_seconds - 60)
                elif k == pygame.K_PERIOD:  # > 키
                    game_seconds += 60
                elif k == pygame.K_F2:
                    # 설정 창 열기
                    pygame.quit()
                    cfg = show_settings_window(cfg)
                    # 설정이 변경되었을 수 있으므로 변수들 업데이트
                    teamA_name = cfg["teamA"]
                    teamB_name = cfg["teamB"]
                    PERIOD_MAX = cfg["period_max"]
                    GAME_SECONDS_INIT = cfg["game_seconds"]
                    SHOT_SECONDS_INIT = cfg["shot_seconds"]
                    TIMEOUTS_INIT = cfg.get("timeouts_per_team", 3)
                    # 현재 타임아웃 수도 새로운 설정값으로 업데이트
                    timeoutsA = TIMEOUTS_INIT
                    timeoutsB = TIMEOUTS_INIT
                    # 현재 게임 시간도 새로운 설정값으로 업데이트
                    game_seconds = GAME_SECONDS_INIT
                    # pygame 재초기화
                    pygame.init()
                    flags = 0
                    if not cfg["windowed"]:
                        flags |= pygame.FULLSCREEN
                    screen = pygame.display.set_mode((cfg["width"], cfg["height"]), flags)
                    pygame.display.set_caption("Basketball Scoreboard (Offline)")
                    # 폰트 재로드
                    fontTeam = load_font(int(H*0.074))
                    fontScore = load_font(int(H*0.296))
                    fontBig = load_font(int(H*0.167))
                    fontMedium = load_font(int(H*0.084))
                    fontSmall = load_font(int(H*0.033))
                    fontTimeout = load_font(int(H*0.060))
                    fontCenti = load_font(int(H*0.084))

        if running_game:
            game_seconds -= dt
            # 마지막 10초부터 경고음 (정수 초일 때만, 0초 포함)
            if game_seconds <= 10 and int(game_seconds) != int(game_seconds + dt):
                beep()
            # 1/100초가 0이 되는 순간(0.01초 → 0.00초)에 부저 울림
            if game_seconds <= 0:
                game_seconds = 0
                running_game = False  # 타이머 멈춤
                main_buzzer()  # 게임 종료 시 buzzer_main.wav 재생
        if running_shot and shot_seconds > 0:
            shot_seconds -= dt
            # 마지막 5초부터 경고음 (정수 초일 때만, 0초는 제외)
            if shot_seconds <= 5 and int(shot_seconds) > 0 and int(shot_seconds) != int(shot_seconds + dt):
                beep()
            # 화면에 0이 표시되는 순간(0.99에서 0.00으로 바뀌는 순간)에 부저 울림
            if int(shot_seconds) == 0 and int(shot_seconds + dt) == 1:
                shot_seconds = 0
                running_shot = False  # 타이머 멈춤
                main_buzzer()  # 샷클럭 종료 시 buzzer_main.wav 재생
            elif shot_seconds <= 0:
                shot_seconds = 0
                running_shot = False  # 타이머 멈춤

        render()
        clock.tick(FPS)

if __name__ == "__main__":
    main()
