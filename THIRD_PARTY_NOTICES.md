# Third-party notices

현재 개발 환경에서는 아래 개발 도구와 Python 라이브러리를 설치해 사용합니다. 프로그램 바이너리나 데이터셋은 이 저장소에 복사하지 않습니다.
버전과 라이선스는 설치 패키지 메타데이터 및 아래 공식 프로젝트의 라이선스를 기준으로 기록했습니다.

| 구성요소 | 라이선스 | 출처 |
|---|---|---|
| Webots R2025a 및 console 샘플 코드 | Apache-2.0 | https://github.com/cyberbotics/webots |
| Webots Pedestrian 및 종속 모델 | Cyberbotics Webots assets license: Webots 사용에 한정. Apache-2.0으로 간주하지 않음 | https://cyberbotics.com/webots_assets_license ; https://github.com/cyberbotics/webots/blob/R2025a/projects/humans/pedestrian/protos/Pedestrian.proto |
| 기본 pedestrian.py 컨트롤러(설치본 참조) | Apache-2.0 | https://github.com/cyberbotics/webots/blob/R2025a/projects/humans/pedestrian/controllers/pedestrian/pedestrian.py |
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
아래 Python 환경 전체 목록과 docs/sbom.json에 전이 의존성까지 기록합니다. MaleCNS 원본/가중치 파일은 별도로 배포하며 저장소에는 모델 코드·출처·manifest를 기록합니다.

| Phase 3 추가 구성요소 | 라이선스 | 출처 |
|---|---|---|
| NumPy 2.2.6 | BSD-3-Clause, wheel 내 OpenBLAS 등 별도 고지 포함 | https://numpy.org/doc/stable/license.html |
| OpenCV 5.0.0 / opencv-python-headless 5.0.0.93 | OpenCV Apache-2.0, Python 패키징 MIT; FFmpeg 등 번들 라이선스 별도 | https://github.com/opencv/opencv/blob/5.0.0/LICENSE ; https://github.com/opencv/opencv-python/blob/master/LICENSE.txt |

설치 wheel의 `opencv_python_headless-5.0.0.93.dist-info/LICENSE.txt`, `LICENSE-3RD-PARTY.txt` 및 NumPy의 라이선스 파일을 함께 확인한다. 설치 바이너리를 이 저장소에 재배포하지 않는다.

## MaleCNS 데이터(0.7.0 실제 모델에서 사용)

MaleCNS v1.0의 공식 배포자는 FlyEM(HHMI Janelia), University of Cambridge, MRC Laboratory of Molecular Biology 및 Google Research 공동 프로젝트입니다. [공식 다운로드](https://male-cns.janelia.org/download/)에서 연결하는 데이터 라이선스는 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)입니다. v1.0에서 LPLC2→DNp01 187뉴런·185간선을 선택하고 연결 수를 출력별 정규화한 LIF로 변환했습니다. 세부 변경은 docs/neurons.md, 원본/파생 SHA-256은 brain_server/assets.lock에 기록합니다. 데이터 라이선스는 시뮬레이터 코드의 라이선스와 구분합니다.

## Phase 4 관제 의존성

- SQLAlchemy 2.0.54: MIT — https://github.com/sqlalchemy/sqlalchemy
- Jinja2 3.1.6: BSD-3-Clause — https://github.com/pallets/jinja
- MarkupSafe 3.0.3: BSD-3-Clause (Jinja2의 이스케이프 의존성; 애플리케이션에서 Markup 사용 금지) — https://github.com/pallets/markupsafe
- bcrypt 5.0.0: Apache-2.0 — https://github.com/pyca/bcrypt
- greenlet 3.5.6: MIT AND PSF-2.0 — https://github.com/python-greenlet/greenlet

## 개발 VM Python 환경 전체 목록

현재 `.venv`의 35개 패키지다. 버전·라이선스 메타데이터와 설치 LICENSE/NOTICE 파일을 근거로 작성했다. 분류자만 모호하게 제공된 Jinja2·NumPy·OpenCV는 실제 설치 고지로 보완했다. 아래 경로는 `.venv/lib/python3.10/site-packages/` 기준이다. 저장소에는 의존성 바이너리를 복제하지 않는다. 배포물에 wheel/바이너리를 포함할 때는 해당 전체 고지와 번들 라이브러리 조건도 함께 확인한다.

| 패키지 | 버전 | 라이선스 | 출처 | 설치 고지 파일 |
|---|---|---|---|---|
| Jinja2 | 3.1.6 | BSD-3-Clause (설치 LICENSE.txt 확인) | [프로젝트](https://jinja.palletsprojects.com/changes/) | `jinja2-3.1.6.dist-info/licenses/LICENSE.txt` |
| MarkupSafe | 3.0.3 | BSD-3-Clause | [프로젝트](https://palletsprojects.com/donate) | `markupsafe-3.0.3.dist-info/licenses/LICENSE.txt` |
| Pygments | 2.21.0 | BSD-2-Clause | [프로젝트](https://pygments.org) | `pygments-2.21.0.dist-info/licenses/AUTHORS`; `pygments-2.21.0.dist-info/licenses/LICENSE` |
| SQLAlchemy | 2.0.54 | MIT | [프로젝트](https://www.sqlalchemy.org) | `sqlalchemy-2.0.54.dist-info/licenses/AUTHORS`; `sqlalchemy-2.0.54.dist-info/licenses/LICENSE` |
| annotated-doc | 0.0.5 | MIT | [프로젝트](https://github.com/fastapi/annotated-doc) | `annotated_doc-0.0.5.dist-info/licenses/LICENSE` |
| annotated-types | 0.8.0 | MIT | [프로젝트](https://github.com/annotated-types/annotated-types) | `annotated_types-0.8.0.dist-info/licenses/LICENSE` |
| anyio | 4.15.1 | MIT | [프로젝트](https://anyio.readthedocs.io/en/latest/) | `anyio-4.15.1.dist-info/licenses/LICENSE` |
| bcrypt | 5.0.0 | Apache-2.0 | [프로젝트](https://github.com/pyca/bcrypt/) | `bcrypt-5.0.0.dist-info/licenses/LICENSE` |
| certifi | 2026.7.22 | MPL-2.0 | [프로젝트](https://github.com/certifi/python-certifi) | `certifi-2026.7.22.dist-info/licenses/LICENSE` |
| click | 8.5.0 | BSD-3-Clause | [프로젝트](https://click.palletsprojects.com/page/changes/) | `click-8.5.0.dist-info/licenses/LICENSE.txt` |
| exceptiongroup | 1.3.1 | MIT | [프로젝트](https://github.com/agronholm/exceptiongroup/blob/main/CHANGES.rst) | `exceptiongroup-1.3.1.dist-info/licenses/LICENSE` |
| fastapi | 0.141.1 | MIT | [프로젝트](https://github.com/fastapi/fastapi) | `fastapi-0.141.1.dist-info/licenses/LICENSE` |
| greenlet | 3.5.6 | MIT AND PSF-2.0 | [프로젝트](https://greenlet.readthedocs.io) | `greenlet-3.5.6.dist-info/licenses/LICENSE`; `greenlet-3.5.6.dist-info/licenses/LICENSE.PSF` |
| h11 | 0.16.0 | MIT | [프로젝트](https://github.com/python-hyper/h11) | `h11-0.16.0.dist-info/licenses/LICENSE.txt` |
| httpcore | 1.0.9 | BSD-3-Clause | [프로젝트](https://www.encode.io/httpcore) | `httpcore-1.0.9.dist-info/licenses/LICENSE.md` |
| httpx | 0.28.1 | BSD-3-Clause | [프로젝트](https://github.com/encode/httpx/blob/master/CHANGELOG.md) | `httpx-0.28.1.dist-info/licenses/LICENSE.md` |
| idna | 3.20 | BSD-3-Clause | [프로젝트](https://github.com/kjd/idna/blob/master/HISTORY.md) | `idna-3.20.dist-info/licenses/LICENSE.md` |
| iniconfig | 2.3.0 | MIT | [프로젝트](https://github.com/pytest-dev/iniconfig) | `iniconfig-2.3.0.dist-info/licenses/LICENSE` |
| numpy | 2.2.6 | BSD-3-Clause; wheel 번들 별도 고지 | [프로젝트](https://numpy.org) | `numpy-2.2.6.dist-info/LICENSE.txt` |
| opencv-python-headless | 5.0.0.93 | 패키징 MIT; OpenCV Apache-2.0; wheel 번들 별도 고지 | [프로젝트](https://github.com/opencv/opencv-python) | `opencv_python_headless-5.0.0.93.dist-info/LICENSE-3RD-PARTY.txt`; `opencv_python_headless-5.0.0.93.dist-info/LICENSE.txt` |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | [프로젝트](https://packaging.pypa.io/) | `packaging-26.3.dist-info/licenses/LICENSE`; `packaging-26.3.dist-info/licenses/LICENSE.APACHE`; `packaging-26.3.dist-info/licenses/LICENSE.BSD` |
| pip | 26.2.1 | MIT | [프로젝트](https://pip.pypa.io/en/stable/news/) | `pip-26.2.1.dist-info/licenses/AUTHORS.txt`; `pip-26.2.1.dist-info/licenses/LICENSE.txt`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/cachecontrol/LICENSE.txt`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/certifi/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/distlib/LICENSE.txt`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/distro/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/idna/LICENSE.md`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/msgpack/COPYING`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/packaging/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/packaging/LICENSE.APACHE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/packaging/LICENSE.BSD`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/pkg_resources/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/platformdirs/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/pygments/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/pyproject_hooks/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/requests/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/resolvelib/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/rich/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/tomli/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/tomli_w/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/truststore/LICENSE`; `pip-26.2.1.dist-info/licenses/src/pip/_vendor/urllib3/LICENSE.txt` |
| pluggy | 1.6.0 | MIT | 설치 메타데이터 | `pluggy-1.6.0.dist-info/licenses/LICENSE` |
| pydantic | 2.13.5 | MIT | [프로젝트](https://github.com/pydantic/pydantic) | `pydantic-2.13.5.dist-info/licenses/LICENSE` |
| pydantic_core | 2.46.5 | MIT | [프로젝트](https://github.com/pydantic/pydantic) | `pydantic_core-2.46.5.dist-info/licenses/LICENSE` |
| pytest | 9.1.1 | MIT | [프로젝트](https://docs.pytest.org/en/stable/changelog.html) | `pytest-9.1.1.dist-info/licenses/LICENSE` |
| setuptools | 84.0.0 | MIT | [프로젝트](https://github.com/pypa/setuptools) | `setuptools-84.0.0.dist-info/licenses/LICENSE`; `setuptools/_vendor/autocommand-2.2.2.dist-info/LICENSE`; `setuptools/_vendor/backports.tarfile-1.2.0.dist-info/LICENSE`; `setuptools/_vendor/importlib_metadata-8.7.1.dist-info/licenses/LICENSE`; `setuptools/_vendor/jaraco.text-4.0.0.dist-info/LICENSE`; `setuptools/_vendor/jaraco_context-6.1.0.dist-info/licenses/LICENSE`; `setuptools/_vendor/jaraco_functools-4.4.0.dist-info/licenses/LICENSE`; `setuptools/_vendor/more_itertools-10.8.0.dist-info/licenses/LICENSE`; `setuptools/_vendor/packaging-26.0.dist-info/licenses/LICENSE`; `setuptools/_vendor/packaging-26.0.dist-info/licenses/LICENSE.APACHE`; `setuptools/_vendor/packaging-26.0.dist-info/licenses/LICENSE.BSD`; `setuptools/_vendor/platformdirs-4.4.0.dist-info/licenses/LICENSE`; `setuptools/_vendor/tomli-2.4.0.dist-info/licenses/LICENSE`; `setuptools/_vendor/wheel-0.46.3.dist-info/licenses/LICENSE.txt`; `setuptools/_vendor/zipp-3.23.0.dist-info/licenses/LICENSE` |
| starlette | 1.7.0 | BSD-3-Clause | [프로젝트](https://github.com/Kludex/starlette) | `starlette-1.7.0.dist-info/licenses/LICENSE.md` |
| tomli | 2.4.1 | MIT | [프로젝트](https://github.com/hukkin/tomli/blob/master/CHANGELOG.md) | `tomli-2.4.1.dist-info/licenses/LICENSE` |
| typing-inspection | 0.4.4 | MIT | [프로젝트](https://github.com/pydantic/typing-inspection) | `typing_inspection-0.4.4.dist-info/licenses/LICENSE` |
| typing_extensions | 4.16.0 | PSF-2.0 | [프로젝트](https://github.com/python/typing_extensions/issues) | `typing_extensions-4.16.0.dist-info/licenses/LICENSE` |
| uvicorn | 0.53.0 | BSD-3-Clause | [프로젝트](https://uvicorn.dev/release-notes) | `uvicorn-0.53.0.dist-info/licenses/LICENSE.md` |

## 가이드 참고 자료

KISA Python 시큐어코딩 가이드(2023년 개정본)는 보안 항목의 참고 문서이며 프로그램 의존성이나 SBOM 구성요소가 아니다. 원문 PDF·예제 코드는 저장소에 포함하지 않는다. 공식 게시물은 인용 시 출처 표시와 비영리 사용 조건을 고지한다. [공식 사용 고지](https://www.krcert.or.kr/kr/bbs/view.do?bbsId=B0000127&menuNo=205021&nttId=71002&pageIndex=1), 열람 사본 출처·해시는 docs/security_controls.json에 기록한다.

이 목록은 외부 구성요소의 고지다. ReflexGuard 자체 코드에 새 오픈소스 라이선스를 부여하지 않는다.

## 외부 GPU 준비 환경

- NVIDIA PyTorch NGC 25.08 ARM64 컨테이너: [NVIDIA Deep Learning Container License](https://developer.download.nvidia.com/licenses/NVIDIA_Deep_Learning_Container_License.pdf) 및 각 포함 구성요소의 라이선스. 이미지 다이제스트·실행 범위는 [GPU 환경](docs/gpu_environment.md)에 기록한다. 컨테이너 자체를 이 저장소에 재배포하지 않는다. CUDA/JetPack 등 NVIDIA 구성요소를 MIT/Apache 라이선스로 간주하지 않는다.
- 외부 GPU에서 받은 MaleCNS v1.0 원본: [공식 다운로드](https://male-cns.janelia.org/download/), CC-BY-4.0. 파일은 저장소 밖에 보관하고, 연구자/프로젝트 출처를 유지한다. 데이터 확인은 모델의 생리학적 타당성 검증을 의미하지 않는다.
- 로컬 VPN 호환 접속 도구 OpenConnect 8.20-1은 Ubuntu 패키지로 설치한 운영 도구이며 애플리케이션에 번들하지 않는다. 라이선스는 호스트 `/usr/share/doc/openconnect/copyright`를 따른다.

## 0.7.0 서명 검증 의존성 (VM/GPU 공통)

| 패키지 | 버전 | 라이선스 | 출처 |
|---|---|---|---|
| cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause | https://github.com/pyca/cryptography |
| cffi | 2.1.1 | MIT-0 | https://github.com/python-cffi/cffi |
| pycparser | 3.0 | BSD-3-Clause | https://github.com/eliben/pycparser |

설치 dist-info/licenses의 LICENSE 파일과 License-Expression을 확인했다. cryptography wheel의 OpenSSL/Rust 번들 고지도 배포물에 별도 유지해야 한다.

## GPU 추가/상이한 구성요소

| 패키지 | 버전 | 라이선스 | 근거 |
|---|---|---|---|
| torch | 2.8.0a0+34c6371d24.nv25.8 | BSD-3-Clause 및 NVIDIA 컨테이너/번들 별도 고지 | 설치 torch dist-info/LICENSE, NGC 고정 이미지 |
| numpy | 1.26.4 | BSD-3-Clause 및 wheel 번들 고지 | 설치 numpy dist-info/LICENSE.txt |
| pyarrow | 25.0.1 | Apache-2.0 | 설치 메타데이터, https://github.com/apache/arrow |
| filelock | 4.0.3 | MIT | 설치 메타데이터, https://github.com/tox-dev/filelock |
| fsspec | 2026.9.0 | BSD-3-Clause | 설치 메타데이터, https://github.com/fsspec/filesystem_spec |
| networkx | 3.4.2 | BSD-3-Clause | 설치 LICENSE.txt, https://github.com/networkx/networkx |
| sympy | 1.14.0 | BSD-3-Clause | 설치 LICENSE, https://github.com/sympy/sympy |
| mpmath | 1.3.0 | BSD-3-Clause | 설치 LICENSE, https://github.com/mpmath/mpmath |

전체 실제 설치 파일 경로는 docs/logs/gpu-python-inventory.json, 해시 잠금 목록은 docs/sbom-gpu.json에 분리했다. NVIDIA vendor torch는 PyPI 해시 잠금 대신 컨테이너 manifest 다이제스트로 출처를 고정한다. 모델 구현은 이 저장소에서 작성했고 원안에 있던 타 데이터셋 모델 코드를 복사하지 않았다. 문헌은 docs/neurons.md에서 인용한다.

0.8.1 로컬 시연은 이미 고지한 NumPy 백엔드와 동일한 MaleCNS v1.0 서명 파생 가중치를 사용한다. 새 외부 데이터셋이나 라이선스 의존성을 추가하지 않았다.
