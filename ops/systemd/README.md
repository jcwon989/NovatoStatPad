## Novato StatPad systemd 운영 가이드

이 디렉터리는 라즈베리파이(리눅스)에서 Novato StatPad `scoreboard.py`를 부팅 시 자동 실행하기 위한 스크립트와 문서를 제공합니다.

### 구성 파일
- `run_scoreboard.sh`: 가상환경의 파이썬으로 `scoreboard.py`를 실행하는 런처 스크립트
- `install_service.sh`: 가상환경 생성/의존성 설치 및 `systemd` 서비스 등록/활성화 스크립트

### 요구 사항
- Python 3, `python3-venv`, `python3-pip`
- 시스템드(systemd) 기반 OS (라즈베리파이 OS 등)

### 설치 및 서비스 등록
```bash
cd /path/to/NovatoStatPad
sudo bash ops/systemd/install_service.sh
```

스크립트는 다음을 수행합니다.
- `.venv` 가상환경 생성 및 `requirements.txt` 설치
- 로그 디렉터리 `logs/` 준비
- 시스템드 유닛 `/etc/systemd/system/novato-statpad.service` 생성
- 서비스 활성화 및 즉시 시작

### 서비스 제어
- 상태 확인: `sudo systemctl status novato-statpad.service`
- 재시작: `sudo systemctl restart novato-statpad.service`
- 중지: `sudo systemctl stop novato-statpad.service`
- 부팅 비활성화: `sudo systemctl disable --now novato-statpad.service`

### 로그 확인
```bash
tail -f logs/stdout.log logs/stderr.log
```

### 환경 변수 사용
앱에서 `.env`가 필요한 경우 `install_service.sh`가 생성하는 유닛 파일의 `EnvironmentFile` 주석을 해제하고 경로를 설정하세요.

### 문제 해결
- 가상환경 누락: `ops/systemd/install_service.sh`를 다시 실행하세요.
- 권한 문제: 서비스가 실행될 사용자(`SUDO_USER` 또는 현재 사용자)가 프로젝트 디렉터리 접근 권한을 가지고 있어야 합니다.
- 오디오/디스플레이: 라즈베리파이에서는 필요 시 `run_scoreboard.sh`의 SDL 관련 환경 변수를 활성화해 보세요.


