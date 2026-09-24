# Third-party notices

Phase 0·1에서는 아래 개발 도구와 Python 라이브러리를 설치해 사용합니다. 프로그램 바이너리나 데이터셋은 이 저장소에 복사하지 않습니다.
버전과 라이선스는 설치 패키지 메타데이터 및 아래 공식 프로젝트의 라이선스를 기준으로 기록했습니다.

| 구성요소 | 라이선스 | 출처 |
|---|---|---|
| Webots R2025a 및 console 샘플 코드 | Apache-2.0 | https://github.com/cyberbotics/webots |
| Webots 일부 모델·자산 | 자산별 고지 확인; CC-BY-4.0 등 | https://github.com/cyberbotics/webots |
| Docker Engine·CLI·Compose·Buildx | Apache-2.0 | https://github.com/moby/moby ; https://github.com/docker/compose |
| Python 3.10 | PSF-2.0 및 배포판 고지 | https://docs.python.org/3/license.html |
| pip / pipx / pytest / setuptools | MIT | https://github.com/pypa/pip ; https://github.com/pypa/pipx ; https://github.com/pytest-dev/pytest ; https://github.com/pypa/setuptools |
| Bandit 1.9.4 | Apache-2.0 | https://github.com/PyCQA/bandit |
| Semgrep 1.178.0 엔진 | LGPL-2.1-or-later | https://github.com/semgrep/semgrep |
| Semgrep 레지스트리 규칙 | 규칙 배포 라이선스 별도 적용 | https://semgrep.dev/p/python |
| pip-audit 2.10.1 | Apache-2.0 | https://github.com/pypa/pip-audit |
| pre-commit 4.6.2 | MIT | https://github.com/pre-commit/pre-commit |
| cyclonedx-bom 7.4.0 | Apache-2.0 | https://github.com/CycloneDX/cyclonedx-python |
| pip-tools 7.6.1 | BSD-3-Clause | https://github.com/jazzband/pip-tools |
| FastAPI 0.141.1 | MIT | https://github.com/fastapi/fastapi |
| Pydantic 2.13.5 | MIT | https://github.com/pydantic/pydantic |
| HTTPX 0.28.1 | BSD-3-Clause | https://github.com/encode/httpx |
| Uvicorn 0.53.0 | BSD-3-Clause | https://github.com/Kludex/uvicorn |
| Starlette 1.7.0 | BSD-3-Clause | https://github.com/Kludex/starlette |

Ubuntu 시스템 패키지(예: Git, GCC, Xvfb, IBus)의 세부 고지는 설치 장비의 `/usr/share/doc/<package>/copyright`에 있습니다.
전이 Python 의존성 목록은 `requirements.txt`, `tools/locks/*.txt`에 고정합니다.
Phase 5에서 서비스 의존성과 SBOM을 포함해 고지를 확장합니다. FlyWire 데이터나 뇌 모델은 아직 포함하지 않았습니다.
