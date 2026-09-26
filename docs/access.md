# 사이트 접속과 초기 계정

0.8.1 기준. 관제·주행 설정·MaleCNS LIVE는 하나의 HTTPS 서비스이며 로그인 세션을 공유한다. 기본 장치 ID는 `seat-a`다.

## 주소와 기능

| 화면 | 주소 | 기능 |
|---|---|---|
| 로그인 | https://localhost:8444/login | 먼저 로그인한 뒤 다른 화면으로 이동 |
| 관제 | https://localhost:8444/ | 상태·원격 정지·속도 제한·판단 로그·사용자 관리 |
| 주행 설정 | https://localhost:8444/settings/control | 속도·루밍 민감도·정지/조향 임계값 저장·복원 |
| MaleCNS LIVE | https://localhost:8444/activity/seat-a | 뉴런 187개 발화·연결·루밍·판단 이력 |

로그 무결성 검증과 내보내기는 관제 화면의 링크를 사용한다. 다른 장치를 등록했다면 해당 장치의 LIVE 링크를 사용한다. 주행 설정은 같은 VM의 Webots 재시작 때 적용된다. 원격 정지·속도 제한은 실행 중인 장치로 전달된다. 방향키 운전은 Webots 3D 화면에서 한다.

## 최초 설치와 실행

먼저 [부트스트랩](bootstrap.md)과 [Phase 1](phase1.md)에 따라 가상환경·의존성·`.env`·TLS 인증서를 준비한다. 관제가 한 번도 초기화되지 않은 설치에서만 실행한다.

```bash
cd ~/work/reflexguard
scripts/init_control.sh
```

`.env.control`, `.env.admin`, `control.db`를 생성한다. 하나라도 이미 있으면 덮어쓰지 않고 중단한다. 기존 환경에서 로그인 문제를 해결하려고 DB를 삭제하거나 다시 초기화하지 않는다.

```bash
# 관제가 실행 중이지 않을 때: 이 터미널을 유지
scripts/run_control_server.sh
```

현재 개발 VM처럼 사용자 서비스가 설치된 환경에서는 `systemctl --user status reflexguard-control.service`로 확인하고 필요할 때 `systemctl --user start reflexguard-control.service`로 시작한다. 이 서비스 설치가 모든 신규 복제본에 자동 적용되는 것은 아니다. 이미 실행 중이면 서버를 중복 실행하지 않는다.

VM 브라우저에 개발 CA `certs/ca.crt`를 신뢰 등록한 뒤 로그인 주소를 연다. 실제 모델 준비는 [뇌 연결 안내](brain_connection.md)를 따른다. 관제만 실행하면 시뮬레이터가 보내는 상태는 아직 없다.

## 초기 계정과 역할

| 구분 | 초기 값 또는 확인 위치 |
|---|---|
| 관리자 아이디 | `admin` (`.env.admin`의 `REFLEXGUARD_ADMIN_USER`) |
| 관리자 비밀번호 | 설치 시 무작위 생성, `.env.admin`의 `REFLEXGUARD_ADMIN_PASSWORD` |
| 최초 생성 계정 | 관리자 1개 |
| 추가 계정 | 관리자 로그인 → 관제 하단 **사용자 관리**에서 생성 |

```bash
cd ~/work/reflexguard
cat .env.admin
```

본인 터미널에서만 읽고 비밀번호 값만 로그인 폼에 입력한다. 파일은 권한 0600 및 Git 제외 대상이다. 실제 비밀번호·API 토큰·인증서 개인키는 저장소에 넣지 않는다. `.env.admin`은 최초 생성/복구 기록이며 서비스가 로그인할 때 읽는 설정 파일이 아니다.

| 역할 | 권한 |
|---|---|
| guardian | 자신에게 지정된 휠체어 조회·LIVE·로그·원격 정지 |
| operator | 휠체어 관제·원격 정지/속도 제한·뉴런 침묵 요청·주행 설정 |
| admin | operator 기능과 사용자 생성·역할/활성 상태 관리·보호자 지정 |

보호자 생성 후 반환된 사용자 ID로 휠체어 `seat-a`를 지정한다. 비밀번호는 UTF-8 12~72바이트이며 로그인 5회 실패 시 계정은 15분 잠긴다.

비밀번호 분실·잠금 복구가 필요하면 서버에서 실행한다.

```bash
cd ~/work/reflexguard
scripts/reset_admin.sh
cat .env.admin
```

일반적으로 새 무작위 비밀번호를 생성해 DB와 파일을 함께 갱신한다. `REFLEXGUARD_ADMIN_PASSWORD` 환경변수가 지정되어 있으면 그 값을 사용한다. 관리자 잠금과 기존 로그인 세션도 해제/폐기한다. 서버 재시작은 필요 없으며 `/login`을 새로 열어 로그인한다. 파일만 편집해도 DB 비밀번호는 바뀌지 않는다.

## Windows PC에서 접속

관제는 VM의 `127.0.0.1:8444`에 바인딩된다. VM IP를 브라우저 주소로 쓰는 대신 SSH 터널을 통해 같은 `https://localhost:8444` 주소를 사용한다.

PowerShell에서 `VM_USER`와 `VM_IP`를 실제 Ubuntu 로그인 계정과 VM 주소로 바꿔 실행하고 창을 열어둔다. 현재 개발 VM의 OS 사용자는 `rg`이며 주소는 VM에서 `hostname -I`로 확인한다.

```powershell
ssh -o ExitOnForwardFailure=yes -N -L 127.0.0.1:8444:127.0.0.1:8444 VM_USER@VM_IP
```

SSH 비밀번호는 **Ubuntu 계정의 비밀번호**다. 웹사이트의 `admin` 계정이나 외부 GPU의 SSH 계정과 별개다. SSH 호스트 키는 VM에서 확인한 값과 대조한다.

브라우저용 개발 CA 공개 인증서만 Windows로 복사한다. 기본 설치 경로가 다르면 경로도 바꾼다.

```powershell
scp VM_USER@VM_IP:~/work/reflexguard/certs/ca.crt .\reflexguard-ca.crt
```

복사한 CA가 VM의 인증서와 같은지 확인하고 Windows/브라우저의 신뢰할 수 있는 루트 인증기관에 등록한다. Firefox가 별도 인증서 저장소를 쓰는 경우 Firefox에도 등록한다. `ca.key`, `server.key`, `client.key`는 복사하지 않는다. TLS 검증을 끄지 않는다. 이후 Windows 브라우저에서 `https://localhost:8444/login`을 연다.

## 접속 문제 확인

- 연결 거부: 관제 서비스와 SSH 터널을 확인한다. VM에서 `ss -lnt`로 127.0.0.1:8444를 확인한다.
- 터널 포트 사용 중: 기존 터널을 재사용하거나 충돌 프로세스를 확인한다. 쿠키·Origin 검증 때문에 임의로 주소/포트를 바꾸지 않는다.
- 인증서 오류: `https://localhost:8444` 주소, 신뢰 등록한 CA, 인증서 만료 여부를 확인한다.
- 로그인 실패: `.env.admin`만 편집했다면 DB에 반영되지 않는다. 위 재설정 절차를 사용한다.
- LIVE 수신 대기: Webots가 실행되고 관제에 연결되어 있는지 확인한다. GUI 기본 모델은 로컬 MaleCNS이며 외부 GPU는 `real` 프로필로 명시한다.

뇌 API 18444(local)·18443(GPU 터널)는 브라우저 관제 사이트가 아니며 mTLS와 API 토큰을 요구한다. Attack Lab은 현재 제출용 프로젝트에 구현되어 있지 않다.
