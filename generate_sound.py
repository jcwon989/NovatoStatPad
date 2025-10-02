#!/usr/bin/env python3
"""
농구 스코어보드용 사운드 파일 생성기
샷클럭이나 게임타임 종료 시 나오는 사운드를 생성합니다.
"""

import numpy as np
import wave
import os

def generate_buzzer_sound(filename="buzzer.wav", duration=2.5, sample_rate=44100):
    """
    긴 부저 사운드를 생성합니다 (게임 종료용).
    
    Args:
        filename: 저장할 파일명
        duration: 사운드 지속 시간 (초)
        sample_rate: 샘플링 레이트
    """
    # 사인파 주파수들 (부저 소리 효과)
    frequencies = [600, 800, 1000]  # Hz
    
    # 시간 배열 생성
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 여러 주파수의 사인파를 합성
    audio = np.zeros_like(t)
    for freq in frequencies:
        # 각 주파수에 대해 감쇠하는 사인파 생성
        envelope = np.exp(-t * 1.5)  # 더 천천히 감쇠
        audio += np.sin(2 * np.pi * freq * t) * envelope
    
    # 정규화 (0.4으로 볼륨 조절)
    audio = audio * 0.4 / len(frequencies)
    
    # 16비트 정수로 변환
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # WAV 파일로 저장
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # 모노
        wav_file.setsampwidth(2)  # 16비트
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    print(f"긴 부저 사운드가 '{filename}'로 저장되었습니다.")

def generate_shot_buzzer_sound(filename="shot_buzzer.wav", duration=1.5, sample_rate=44100):
    """
    샷클럭 종료용 부저 사운드를 생성합니다.
    
    Args:
        filename: 저장할 파일명
        duration: 사운드 지속 시간 (초)
        sample_rate: 샘플링 레이트
    """
    # 사인파 주파수들 (샷클럭 부저 소리)
    frequencies = [1000, 1200, 1400]  # Hz
    
    # 시간 배열 생성
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 여러 주파수의 사인파를 합성
    audio = np.zeros_like(t)
    for freq in frequencies:
        # 각 주파수에 대해 감쇠하는 사인파 생성
        envelope = np.exp(-t * 2)  # 지수적 감쇠
        audio += np.sin(2 * np.pi * freq * t) * envelope
    
    # 정규화 (0.35으로 볼륨 조절)
    audio = audio * 0.35 / len(frequencies)
    
    # 16비트 정수로 변환
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # WAV 파일로 저장
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # 모노
        wav_file.setsampwidth(2)  # 16비트
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    print(f"샷클럭 부저 사운드가 '{filename}'로 저장되었습니다.")

def generate_beep_sound(filename="beep.wav", duration=0.3, frequency=1000, sample_rate=44100):
    """
    간단한 비프 사운드를 생성합니다 (경고음용).
    
    Args:
        filename: 저장할 파일명
        duration: 사운드 지속 시간 (초)
        frequency: 주파수 (Hz)
        sample_rate: 샘플링 레이트
    """
    # 시간 배열 생성
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 사인파 생성 (페이드 인/아웃 효과)
    envelope = np.exp(-t * 3)  # 지수적 감쇠
    audio = np.sin(2 * np.pi * frequency * t) * envelope * 0.25
    
    # 16비트 정수로 변환
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # WAV 파일로 저장
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # 모노
        wav_file.setsampwidth(2)  # 16비트
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    print(f"비프 사운드가 '{filename}'로 저장되었습니다.")

def generate_alert_sound(filename="alert.wav", duration=0.8, sample_rate=44100):
    """
    경고 알림 사운드를 생성합니다.
    
    Args:
        filename: 저장할 파일명
        duration: 사운드 지속 시간 (초)
        sample_rate: 샘플링 레이트
    """
    # 시간 배열 생성
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 두 개의 주파수가 번갈아 나타나는 효과
    freq1, freq2 = 600, 800
    audio = np.zeros_like(t)
    
    # 첫 번째 반 (높은 주파수)
    first_half = t < duration / 2
    audio[first_half] = np.sin(2 * np.pi * freq1 * t[first_half])
    
    # 두 번째 반 (낮은 주파수)
    second_half = t >= duration / 2
    audio[second_half] = np.sin(2 * np.pi * freq2 * t[second_half])
    
    # 페이드 인/아웃 효과
    envelope = np.exp(-t * 1.5)
    audio *= envelope * 0.4
    
    # 16비트 정수로 변환
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # WAV 파일로 저장
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # 모노
        wav_file.setsampwidth(2)  # 16비트
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    print(f"알림 사운드가 '{filename}'로 저장되었습니다.")

def main():
    """메인 함수 - 여러 종류의 사운드 파일을 생성합니다."""
    print("농구 스코어보드용 사운드 파일을 생성합니다...")
    
    # sound 폴더에 사운드 파일 생성
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sound_dir = os.path.join(script_dir, "sound")
    
    # sound 폴더가 없으면 생성
    os.makedirs(sound_dir, exist_ok=True)
    
    # 긴 부저 사운드 (게임 종료용)
    buzzer_path = os.path.join(sound_dir, "buzzer.wav")
    generate_buzzer_sound(buzzer_path, duration=2.5)
    
    # 샷클럭 부저 사운드 (샷클럭 종료용)
    shot_buzzer_path = os.path.join(sound_dir, "shot_buzzer.wav")
    generate_shot_buzzer_sound(shot_buzzer_path, duration=1.5)
    
    # 비프 사운드 (경고음용)
    beep_path = os.path.join(sound_dir, "beep.wav")
    generate_beep_sound(beep_path, duration=0.3, frequency=1000)
    
    # 알림 사운드 (타임아웃용)
    alert_path = os.path.join(sound_dir, "alert.wav")
    generate_alert_sound(alert_path, duration=1.0)
    
    print("\n생성된 사운드 파일:")
    print(f"- 게임 종료 부저: {buzzer_path} (2.5초)")
    print(f"- 샷클럭 부저: {shot_buzzer_path} (1.5초)")
    print(f"- 경고 비프: {beep_path} (0.3초)")
    print(f"- 알림 사운드: {alert_path} (1.0초)")
    print("\n이제 스코어보드에서 다양한 사운드가 재생됩니다!")

if __name__ == "__main__":
    main()
