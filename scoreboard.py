#!/usr/bin/env python3
import sys, os, time, json, argparse
import pygame

# ===== 기본 설정 =====
PERIOD_MAX_DEFAULT = 4
GAME_SECONDS_DEFAULT = 10*60
SHOT_SECONDS_DEFAULT = 24

CONFIG_PATH = os.path.expanduser("~/.scoreboard_config.json")
FONT_CANDIDATES = [
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
        "windowed": False,
        "width": 1920,
        "height": 1080,
    }

def save_cfg(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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
    cfg = parse_args(load_cfg())
    save_cfg(cfg)  # 사용자가 준 옵션을 저장

    teamA_name = cfg["teamA"]
    teamB_name = cfg["teamB"]
    PERIOD_MAX = cfg["period_max"]
    GAME_SECONDS_INIT = cfg["game_seconds"]
    SHOT_SECONDS_INIT = cfg["shot_seconds"]

    pygame.init()
    flags = 0
    if not cfg["windowed"]:
        flags |= pygame.FULLSCREEN
    screen = pygame.display.set_mode((cfg["width"], cfg["height"]), flags)
    pygame.display.set_caption("Basketball Scoreboard (Offline)")

    W, H = screen.get_size()
    clock = pygame.time.Clock()
    FPS = 60

    # 폰트
    fontTeam = load_font(int(H*0.074))   # ~80 on 1080p
    fontScore = load_font(int(H*0.296))  # ~320
    fontBig = load_font(int(H*0.111))    # ~120
    fontSmall = load_font(int(H*0.033))  # ~36

    # 상태
    scoreA = 0
    scoreB = 0
    period = 1
    timeoutsA = 3
    timeoutsB = 3
    running_game = False
    running_shot = False
    game_seconds = GAME_SECONDS_INIT
    shot_seconds = SHOT_SECONDS_INIT

    last_t = time.perf_counter()
    mouse_visible = False
    pygame.mouse.set_visible(mouse_visible)

    # 사운드(선택)
    buzzer_path = os.path.expanduser("~/.scoreboard_buzzer.wav")
    has_sound = False
    if os.path.exists(buzzer_path):
        try:
            pygame.mixer.init()
            buzzer = pygame.mixer.Sound(buzzer_path)
            has_sound = True
        except Exception:
            has_sound = False

    def beep():
        if has_sound:
            try: buzzer.play()
            except Exception: pass

    def reset_all():
        nonlocal scoreA, scoreB, period, timeoutsA, timeoutsB
        nonlocal game_seconds, shot_seconds, running_game, running_shot
        scoreA = scoreB = 0
        period = 1
        timeoutsA = timeoutsB = 3
        game_seconds = GAME_SECONDS_INIT
        shot_seconds = SHOT_SECONDS_INIT
        running_game = False
        running_shot = False

    def render():
        screen.fill((17,17,17))
        cx = W//2

        # 좌측 팀
        teamA = fontTeam.render(teamA_name, True, (220,220,220))
        scoreA_surf = fontScore.render(str(scoreA), True, (255,255,255))
        screen.blit(teamA, (cx - int(W*0.365) - teamA.get_width()//2, int(H*0.139)))
        screen.blit(scoreA_surf, (cx - int(W*0.365) - scoreA_surf.get_width()//2, int(H*0.232)))

        # 우측 팀
        teamB = fontTeam.render(teamB_name, True, (220,220,220))
        scoreB_surf = fontScore.render(str(scoreB), True, (255,255,255))
        screen.blit(teamB, (cx + int(W*0.365) - teamB.get_width()//2, int(H*0.139)))
        screen.blit(scoreB_surf, (cx + int(W*0.365) - scoreB_surf.get_width()//2, int(H*0.232)))

        # 중앙 타이머/피리어드
        t_str = fmt_mmss(game_seconds)
        game_surf = fontBig.render(t_str, True, (255,255,255))
        prd_surf = fontBig.render(f"Q{period}", True, (200,200,200))
        screen.blit(game_surf, (cx - game_surf.get_width()//2, int(H*0.296)))
        screen.blit(prd_surf, (cx - prd_surf.get_width()//2, int(H*0.435)))

        # 샷클락
        shot_color = (255,80,80) if shot_seconds <= 5 else (255,215,0)
        shot_surf = fontBig.render(str(max(0,int(shot_seconds))), True, shot_color)
        screen.blit(shot_surf, (cx - shot_surf.get_width()//2, int(H*0.556)))

        # 타임아웃/힌트
        ta = fontSmall.render(f"Timeouts A: {timeoutsA}", True, (180,180,220))
        tb = fontSmall.render(f"Timeouts B: {timeoutsB}", True, (220,180,180))
        screen.blit(ta, (int(W*0.026), H - int(H*0.111)))
        screen.blit(tb, (W - int(W*0.026) - tb.get_width(), H - int(H*0.111)))

        hints = [
            "A/Z: A +1/-1 | K/M: B +1/-1 | 1/2/3: A +1/+2/+3 | 8/9/0: B +1/+2/+3",
            "Space: Game ▶/⏸ | S: Shot ▶/⏸ | R: Reset | [ / ]: Q- / Q+",
            "PgUp/PgDn: Game +60/-60s | ; / ': Shot +5/-5s | T/Y: A/B Timeout-1 | F/G: A/B Timeout+1",
            "Ctrl+T: Swap Teams | F11: Fullscreen toggle | H: Hide/Show Mouse | Esc: Quit",
        ]
        for i, line in enumerate(hints):
            surf = fontSmall.render(line, True, (150,150,150))
            screen.blit(surf, (int(W*0.026), H - int(H*0.083) + i*int(H*0.022)))

        pygame.display.flip()

    def swap_teams():
        nonlocal teamA_name, teamB_name, scoreA, scoreB, timeoutsA, timeoutsB
        teamA_name, teamB_name = teamB_name, teamA_name
        scoreA, scoreB = scoreB, scoreA
        timeoutsA, timeoutsB = timeoutsB, timeoutsA

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

                if k == pygame.K_ESCAPE:
                    save_cfg(cfg); pygame.quit(); sys.exit(0)
                elif k == pygame.K_F11:
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
                elif k == pygame.K_a:
                    scoreA += 1
                elif k == pygame.K_z:
                    scoreA = max(0, scoreA - 1)
                elif k == pygame.K_k:
                    scoreB += 1
                elif k == pygame.K_m:
                    scoreB = max(0, scoreB - 1)
                elif k == pygame.K_1:
                    scoreA += 1
                elif k == pygame.K_2:
                    scoreA += 2
                elif k == pygame.K_3:
                    scoreA += 3
                elif k == pygame.K_8:
                    scoreB += 1
                elif k == pygame.K_9:
                    scoreB += 2
                elif k == pygame.K_0:
                    scoreB += 3
                elif k == pygame.K_t:
                    timeoutsA = max(0, timeoutsA - 1)
                elif k == pygame.K_y:
                    timeoutsB = max(0, timeoutsB - 1)
                elif k == pygame.K_f:
                    timeoutsA += 1
                elif k == pygame.K_g:
                    timeoutsB += 1
                elif k == pygame.K_h:
                    mouse_visible = not pygame.mouse.get_visible()
                    pygame.mouse.set_visible(mouse_visible)
                elif k == pygame.K_PAGEUP:
                    game_seconds += 60
                elif k == pygame.K_PAGEDOWN:
                    game_seconds = max(0, game_seconds - 60)
                elif k == pygame.K_SEMICOLON:
                    shot_seconds += 5
                elif k == pygame.K_QUOTE:
                    shot_seconds = max(0, shot_seconds - 5)
                elif k == pygame.K_t and (mod & pygame.KMOD_CTRL):
                    swap_teams()

        if running_game and game_seconds > 0:
            game_seconds -= dt
            if game_seconds <= 0:
                game_seconds = 0
                running_game = False
                beep()
        if running_shot and shot_seconds > 0:
            shot_seconds -= dt
            if shot_seconds <= 0:
                shot_seconds = 0
                running_shot = False
                beep()

        render()
        clock.tick(FPS)

if __name__ == "__main__":
    main()
