"""Render the reviewed control-to-code-to-test index; never infer compliance from names."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def render(data):
    source=data["source"]
    lines=["# KISA Python 시큐어코딩 매핑", "", "기준 애플리케이션: **"+data["application_version"]+"**. 이 표는 현재 구현의 검증 범위를 설명하며 KISA 인증이나 전체 가이드 준수를 선언하지 않는다.", "",
        "출처: [KISA 공식 게시물]("+source["official"]+") · [공식 보호나라 게시물]("+source["official_alternative"]+"). 항목명과 인쇄 쪽수는 2023 개정본을 기준으로 했다.", "",
        "공식 첨부 오류로 [대학 자료실의 KISA 원문 사본]("+source["read_copy_page"]+")을 열람했다. 2023 표지와 목차를 확인했고 열람 파일 SHA-256은 `"+source["read_copy_sha256"]+"`이다. 공급자 공표 해시/서명으로 오해하지 않는다. PDF 원문·예제는 재배포하지 않는다.", "",
        "한 행은 한 가이드 항목에 대응한다. 같은 함수·테스트가 여러 항목에 대응할 수 있다. ‘적용’도 아래 적힌 경로/조건에만 해당한다. 새 위협 부재나 완전성을 의미하지 않는다.", "",
        "| ID / KISA 항목명 (인쇄 쪽) | 적용 위치 파일:함수 | 대응 방식·범위 | 검증 테스트명 |", "|---|---|---|---|"]
    for row in data["controls"]:
        refs="<br>".join("`"+ref+"`" for ref in row["code"])
        tests="<br>".join("`"+ref+"`" for ref in row["tests"])
        status="적용" if row["status"]=="implemented" else "부분 적용"
        approach="**"+status+"** — "+row["approach"]
        if row["limit"]:approach+=" 제한: "+row["limit"]
        lines.append("| "+row["id"]+" · "+row["item"]+" (p."+str(row["printed_page"])+") | "+refs+" | "+approach+" | "+tests+" |")
    lines += ["", "## 검증 기준과 후속 범위", "",
        "`security_controls.json`이 표의 편집 원본이다. `scripts/render_security_docs.py`로 재생성한다. `tests/test_security_docs.py`가 함수·테스트 참조의 실재 여부, 표 동기화, SBOM/잠금/설치 버전 일치 여부를 검사한다. 참조가 존재한다는 사실만으로 보안 효과를 증명하지 않으며 연결된 동작 시험을 함께 실행해야 한다.", "",
        "모델 자산 공개키 서명 검증, 저장 데이터 암호화, 운영 인증서 수명 관리, 유출 비밀번호 차단은 미완료다. 현재 HMAC 명령 검증은 공유 키 메시지 인증이며 가이드의 전자서명 확인 항목을 완료 처리하지 않는다. XML/LDAP/파일 업로드 기능은 현재 없으므로 대응 행을 억지로 만들지 않았다. 새 기능이 생기면 범위를 다시 검토한다.", "",
        "원문 가이드는 KISA 고지에 따라 출처를 표시한다. 사용 조건은 공식 게시물에서 확인한다. 본 표의 구현 분석과 검증 결과는 ReflexGuard 저장소에 대한 자체 평가다.", ""]
    return "\n".join(lines)

def main():
    data=json.loads((ROOT/"docs/security_controls.json").read_text())
    (ROOT/"docs/kisa_mapping.md").write_text(render(data),encoding="utf-8")

if __name__=="__main__":
    main()
