# 사이트 접속과 초기 계정

0.8.2 기준. 관제·주행 설정·MaleCNS LIVE는 하나의 HTTPS 서비스이며 로그인 세션을 공유한다. 기본 장치 ID는 `seat-a`다.

## 주소와 기능

| 화면 | 주소 | 기능 |
|---|---|---|
| 로그인 | https://192.168.0.149:8444/login | 먼저 로그인한 뒤 다른 화면으로 이동 |
| 관제 | https://192.168.0.149:8444/ | 상태·원격 정지·속도 제한·판단 로그·사용자 관리 |
| 주행 설정 | https://192.168.0.149:8444/settings/control | 속도·루밍 민감도·정지/조향 임계값 저장·복원 |
| MaleCNS LIVE | https://192.168.0.149:8444/activity/seat-a | 뉴런 187개 발화·연결·루밍·판단 이력 |

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

## 다른 PC에서 직접 접속

현재 VM의 관제는 `REFLEXGUARD_CONTROL_HOST=0.0.0.0` 설정으로 모든 인터페이스의 8444 포트에서 수신한다. 새 설치의 미설정 기본값은 127.0.0.1이며 외부 접속을 원할 때 아래 값을 명시한다. 현재 개발 VM 주소는 **https://192.168.0.149:8444**이며 Windows에서도 이 주소로 접속한다. `0.0.0.0`은 수신 설정값이며 브라우저에 입력하는 주소가 아니다. SSH 터널은 필요 없다.

주소는 DHCP로 바뀔 수 있다. VM에서 `hostname -I`로 주소를 확인한다. 같은 네트워크 또는 VM까지 라우팅 가능한 네트워크에서 사용할 수 있다. 인터넷 공유기의 포트 전달이나 공인 도메인 설정까지 구성한 것은 아니다.

관제의 `.env.control` 예시(토큰 등 기존 항목은 보존):

```dotenv
REFLEXGUARD_CONTROL_HOST=0.0.0.0
REFLEXGUARD_CONTROL_URL=https://192.168.0.149:8444
REFLEXGUARD_CONTROL_TLS_CERT=certs/control-lan-20260926/server.crt
REFLEXGUARD_CONTROL_TLS_KEY=certs/control-lan-20260926/server.key
```

현재 VM에는 해당 IP의 SAN이 포함된 관제 전용 인증서를 발급했다. 위 인증서 경로는 현재 VM의 Git 제외 파일이므로 새 복제본에는 없다. 새 설치에서는 실제 접속 IP/DNS를 SAN에 넣어 신뢰하는 CA로 발급하고 해당 경로로 바꾼다. 기존 개발 CA로 IP 인증서를 발급하는 예시는 다음과 같다. 새 디렉터리를 사용하고 IP는 실제 주소로 바꾼다.

```bash
cd ~/work/reflexguard
umask 077
CONTROL_IP=192.168.0.149
CONTROL_CERT_DIR=certs/control-lan-new
mkdir "$CONTROL_CERT_DIR"
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -subj /CN=reflexguard-control -keyout "$CONTROL_CERT_DIR/server.key" \
  -out "$CONTROL_CERT_DIR/server.csr"
printf 'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:%s\n' "$CONTROL_IP" > "$CONTROL_CERT_DIR/server.ext"
openssl x509 -req -sha256 -days 7 -in "$CONTROL_CERT_DIR/server.csr" \
  -CA certs/ca.crt -CAkey certs/ca.key -set_serial "0x$(openssl rand -hex 16)" \
  -extfile "$CONTROL_CERT_DIR/server.ext" -out "$CONTROL_CERT_DIR/server.crt"
openssl verify -CAfile certs/ca.crt -verify_ip "$CONTROL_IP" "$CONTROL_CERT_DIR/server.crt"
```

CA 자체도 유효해야 한다. `.env.control`의 관제 전용 인증서 경로를 발급 경로로 맞추고 관제 서비스를 재시작한다. 장치도 같은 `REFLEXGUARD_CONTROL_URL`을 사용하므로 실행 중인 Webots는 다시 시작한다. 기존 뇌 API의 mTLS 인증서는 교체하지 않는다.

Host/Origin 검증은 `REFLEXGUARD_CONTROL_URL` 한 개를 기준으로 유지한다. LAN 주소로 설정한 환경에서는 기존 `https://localhost:8444` 북마크를 새 주소로 바꾼다. 로컬 전용으로 되돌리려면 HOST를 `127.0.0.1`, URL을 `https://localhost:8444`로 맞추고 localhost SAN이 있는 인증서를 사용한다.

Windows 브라우저에는 개발 CA 공개 인증서만 신뢰 등록한다. `VM_USER`/`VM_IP`는 실제 Ubuntu 계정/주소로 바꾼다(현재 OS 사용자 `rg`).

```powershell
scp VM_USER@VM_IP:~/work/reflexguard/certs/ca.crt .\reflexguard-ca.crt
```

SSH 비밀번호는 Ubuntu 계정의 비밀번호이며 웹사이트 `admin` 비밀번호와 별개다. 공개 인증서를 VM의 원본과 대조한 뒤 Windows/브라우저의 신뢰할 수 있는 루트 인증기관에 등록한다. Firefox가 별도 인증서 저장소를 쓰는 경우 Firefox에도 등록한다. 개인키는 복사하지 않고 TLS 검증은 유지한다.

현재 VM 방화벽(UFW)은 비활성이다. 별도 방화벽이 있는 설치에서는 필요한 접속 네트워크에서 TCP 8444를 허용해야 한다.

## 접속 문제 확인

- 연결 거부: 관제 서비스, VM 네트워크와 방화벽을 확인한다. VM에서 `ss -lnt`로 0.0.0.0:8444를 확인한다.
- 요청 거부(400/403): 브라우저 주소가 설정된 HTTPS Origin과 일치하는지 확인한다. IP가 바뀌면 URL 설정과 인증서를 함께 갱신한다.
- 인증서 오류: `https://192.168.0.149:8444` 주소, 신뢰 등록한 CA, 인증서 만료 여부를 확인한다.
- 로그인 실패: `.env.admin`만 편집했다면 DB에 반영되지 않는다. 위 재설정 절차를 사용한다.
- LIVE 수신 대기: Webots가 실행되고 관제에 연결되어 있는지 확인한다. GUI 기본 모델은 로컬 MaleCNS이며 외부 GPU는 `real` 프로필로 명시한다.

뇌 API 18444(local)·18443(GPU 터널)는 브라우저 관제 사이트가 아니며 mTLS와 API 토큰을 요구한다. Attack Lab은 현재 제출용 프로젝트에 구현되어 있지 않다.
