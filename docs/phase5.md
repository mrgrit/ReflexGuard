# Phase 5 — 보안 문서와 증거 관리 (0.5.0)

## 산출물

- [STRIDE 위협 모델](threat_model.md): 자산·주체·신뢰 경계, 구성요소별 위협, 검증과 잔여 위험.
- [KISA 매핑](kisa_mapping.md): 2023 개정본 27개 관련 항목을 현재 함수·동작 테스트와 연결. 부분 적용/후속 작업을 구분.
- [서비스 개요서 초안](service_overview.md): 목적·구성·보안 기능·시연 범위. 공식 대회 양식에 맞춘 최종 제출본은 아님.
- [Python 환경 SBOM](sbom.json), [생성 근거](sbom_provenance.json), [외부 고지](../THIRD_PARTY_NOTICES.md).

## 재생성

프로젝트 루트에서 다음을 실행한다.

```bash
.venv/bin/python scripts/render_security_docs.py
scripts/generate_sbom.sh
scripts/security_check.sh
```

SBOM은 pipx의 cyclonedx-bom 7.4.0 / `cyclonedx-py environment`로 생성한다. 현재 `.venv`의 서비스·테스트·설치 도구를 포함한 32개 패키지를 대상으로 한다. `pyproject.toml`은 애플리케이션 루트 구성요소 메타데이터를 제공하고 설치는 여전히 `requirements.txt --require-hashes`를 따른다. CycloneDX 1.6 JSON 스키마 검증과 재현 가능한 출력 옵션을 사용한다.

SBOM에 OS·Docker·Webots·별도 pipx 가상환경의 도구 전체·향후 MaleCNS 데이터가 포함된다고 주장하지 않는다. 해당 구성요소의 고지는 THIRD_PARTY_NOTICES와 환경 문서에서 별도로 관리한다. 설치 wheel 안의 네이티브 라이브러리를 Python 패키지 SBOM이 모두 분해해 나열하지 않으므로 NumPy/OpenCV 번들 고지도 확인한다.

`sbom_provenance.json`은 requirements 입력·잠금·프로젝트 메타데이터 및 SBOM 파일의 실제 SHA-256을 기록한다. 설치 파일 전체의 원격 증명이나 다운로드하지 않은 모든 플랫폼 wheel의 검증 결과가 아니다. requirements.txt에 고정된 후보 배포 파일 해시와 구분한다.

## 문서 품질 게이트

`test_security_docs.py`는 각 매핑 행에 연결된 함수·테스트가 존재하는지, Markdown 표가 JSON 원본과 일치하는지, SBOM·잠금·설치 버전 및 입력 해시가 같은지 확인한다. 실제 보안 동작은 해당 행이 가리키는 테스트와 별도 보안 게이트로 검증한다.
`test_security_evidence.py`는 bcrypt salt 독립성, UTF-8 비밀번호 경계, 세션 토큰과 DB digest 분리, debug/API 문서 비활성화 증거를 보강한다.

가이드 원문은 KISA 공식 배포 제목을 확인한 뒤, 공식 첨부 오류 때문에 대학 자료실의 KISA 원문 사본을 열람했다. 표지 2023, 176쪽 PDF와 목차를 확인했고 사본 출처·SHA-256을 `security_controls.json`에 기록했다. 공식 기관이 보증한 사본 해시라고 주장하지 않으며 PDF 원문·예제 코드를 저장소에 복제하지 않는다.

새 데이터나 GPU 패키지를 도입하면 SBOM·라이선스·위협 모델·매핑을 다시 생성/검토한다. 실제 모델 자산 서명 검증은 Phase 6 작업으로 남아 있다. 현재 실행 중인 로컬 mock·관제와 사용자 데이터는 이번 문서 작업에서 변경하지 않는다.


## 0.5.0 최종 결과

- 전체 pytest **252개 통과**, 기존 Starlette/httpx 관련 폐기 예정 경고 1개.
- Bandit·Semgrep·pip-audit 게이트 통과. Phase 4에 문서화한 고정 subprocess 국소 예외 5곳은 유지하며 전체 규칙을 비활성화하지 않았다.
- KISA 매핑 27개 행의 함수·테스트 참조와 Markdown 동기화 검사 통과. 부분 적용은 11개 행이며 제한을 각 행에 명시했다.
- Python 환경 32개 패키지의 SBOM·잠금·설치 버전·라이선스 고지 일치 검사 통과. 연속 두 번 재생성한 SBOM 및 provenance 파일 SHA-256이 각각 동일했다.
- [보안 검사 원문](logs/phase5-security.log), [문서·SBOM 검증 기록](logs/phase5-docs.json).

이번 단계는 문서와 증거 관리 작업이다. Phase 3/4 Webots 결과는 당시 기록을 인용하며 이번 단계에서 새로 실제 모델/하드웨어 시험을 했다고 표현하지 않는다.
