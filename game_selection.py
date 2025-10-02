import os
import pygame
import sys
from database import get_database

# 간단한 디버그 로깅
DEBUG = os.getenv("APP_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
def dlog(message: str):
    if DEBUG:
        print(f"[game_selection] {message}")

def show_game_selection(screen, font_large, font_medium, font_small):
    """게임 선택 화면 표시"""
    W, H = screen.get_size()
    
    # 데이터베이스 연결 시도
    db = get_database()
    if not db:
        # DB 연결 실패 시 오프라인 모드로 진행
        screen.fill((0, 0, 0))
        error_text = font_small.render("데이터베이스 연결 실패 - 오프라인 모드로 진행", True, (255, 100, 100))
        error_rect = error_text.get_rect(center=(W//2, H//2))
        screen.blit(error_text, error_rect)
        
        continue_text = font_small.render("아무 키나 누르면 계속...", True, (200, 200, 200))
        continue_rect = continue_text.get_rect(center=(W//2, H//2 + 50))
        screen.blit(continue_text, continue_rect)
        
        pygame.display.flip()
        
        # 키 입력 대기
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.KEYDOWN:
                    waiting = False
        return None
    
    # 게임 데이터 조회
    games = db.get_games_by_month_range()
    display_items = db.make_display_items(games)
    formatted_games = [it["text"] for it in display_items]
    
    # 게임 선택 화면 표시
    screen.fill((0, 0, 0))
    
    # 제목
    title = font_medium.render("경기 선택", True, (255, 255, 255))
    title_rect = title.get_rect(center=(W//2, int(H*0.1)))
    screen.blit(title, title_rect)
    
    if not formatted_games:
        # 게임이 없는 경우
        no_games_text = font_small.render("표시할 경기가 없습니다", True, (200, 200, 200))
        no_games_rect = no_games_text.get_rect(center=(W//2, H//2))
        screen.blit(no_games_text, no_games_rect)
        
        continue_text = font_small.render("아무 키나 누르면 오프라인 모드로 진행...", True, (150, 150, 150))
        continue_rect = continue_text.get_rect(center=(W//2, H//2 + 50))
        screen.blit(continue_text, continue_rect)
        
        pygame.display.flip()
        
        # 키 입력 대기
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.KEYDOWN:
                    waiting = False
        return None
    
    # 게임 목록 표시
    start_y = int(H*0.2)
    line_height = int(H*0.08)
    max_visible_games = 8  # 화면에 표시할 최대 게임 수
    total_games = len(formatted_games)
    
    selected_index = 0
    scroll_offset = 0  # 스크롤 오프셋
    prev_selected = selected_index
    prev_scroll = scroll_offset
    
    while True:
        screen.fill((0, 0, 0))
        
        # 제목 다시 그리기
        screen.blit(title, title_rect)
        
        # 게임 목록 그리기 (스크롤 적용)
        visible_start = scroll_offset
        visible_end = min(scroll_offset + max_visible_games, total_games)
        
        for i in range(visible_start, visible_end):
            display_index = i - scroll_offset
            y_pos = start_y + display_index * line_height
            game_text = formatted_games[i]
            
            # 선택된 게임 하이라이트
            if i == selected_index:
                color = (255, 255, 100)  # 노란색
            else:
                color = (200, 200, 200)  # 회색
            
            text_surface = font_small.render(game_text, True, color)
            text_rect = text_surface.get_rect(center=(W//2, y_pos))
            screen.blit(text_surface, text_rect)
            
            # 선택된 항목은 밑줄로 표시
            if i == selected_index:
                underline_y = text_rect.bottom + 2
                underline_start = text_rect.left
                underline_end = text_rect.right
                pygame.draw.line(screen, (255, 255, 100), (underline_start, underline_y), (underline_end, underline_y), 2)
        
        # 스크롤 인디케이터 (게임이 많을 때)
        if total_games > max_visible_games:
            # 스크롤 바 표시
            scroll_bar_height = int(H * 0.3)
            scroll_bar_y = start_y
            scroll_bar_width = 10
            scroll_bar_x = W - 50
            
            # 스크롤 바 배경
            pygame.draw.rect(screen, (50, 50, 50), (scroll_bar_x, scroll_bar_y, scroll_bar_width, scroll_bar_height))
            
            # 스크롤 바 위치 계산
            scroll_ratio = scroll_offset / (total_games - max_visible_games)
            thumb_height = max(20, int(scroll_bar_height * max_visible_games / total_games))
            thumb_y = scroll_bar_y + int((scroll_bar_height - thumb_height) * scroll_ratio)
            
            # 스크롤 바 썸
            pygame.draw.rect(screen, (150, 150, 150), (scroll_bar_x, thumb_y, scroll_bar_width, thumb_height))
        
        # 안내 텍스트
        if len(formatted_games) > 0:
            help_text = font_small.render("↑↓: 선택, Enter: 확인, ESC: 오프라인 모드", True, (150, 150, 150))
            help_text_rect = help_text.get_rect(center=(W//2, int(H*0.9)))
            screen.blit(help_text, help_text_rect)
        
        pygame.display.flip()
        
        # 키 입력 처리
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    if selected_index > 0:
                        selected_index -= 1
                        # 선택된 항목이 화면에 보이도록 스크롤 조정
                        if selected_index < scroll_offset:
                            scroll_offset = selected_index
                elif event.key == pygame.K_DOWN:
                    if selected_index < total_games - 1:
                        selected_index += 1
                        # 선택된 항목이 화면에 보이도록 스크롤 조정
                        if selected_index >= scroll_offset + max_visible_games:
                            scroll_offset = selected_index - max_visible_games + 1
                elif event.key == pygame.K_RETURN:
                    # 선택된 게임 반환 (표시 항목과 원본 매핑 사용)
                    if selected_index < len(display_items):
                        chosen = display_items[selected_index]["game"]
                        dlog(f"ENTER pressed. selected_index={selected_index}, id={chosen.get('id')}, text='{formatted_games[selected_index]}'")
                        return chosen
                elif event.key == pygame.K_ESCAPE:
                    return None

                # 변경 로그
                if selected_index != prev_selected or scroll_offset != prev_scroll:
                    vis_start = scroll_offset
                    vis_end = min(scroll_offset + max_visible_games, total_games)
                    dlog(
                        f"selected_index={selected_index}, scroll_offset={scroll_offset}, visible=[{vis_start}-{vis_end}) text='{formatted_games[selected_index]}'"
                    )
                    prev_selected = selected_index
                    prev_scroll = scroll_offset
    
    return None
