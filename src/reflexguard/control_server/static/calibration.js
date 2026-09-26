"use strict";
const root = document.getElementById("calibration");
const form = document.getElementById("calibration-form");
const feedback = document.getElementById("feedback");
const changed = document.getElementById("changed");
const timeText = ms => ms ? new Date(ms).toLocaleString("ko-KR") : "기본 배포값";
changed.textContent = timeText(Number(changed.dataset.ms));
async function save(reset) {
  const body = {expected_revision: root.dataset.revision};
  if (!reset) {
    if (!form.reportValidity()) return;
    body.calibration = Object.fromEntries(Array.from(form.querySelectorAll("input[name]"), input => [input.name, Number(input.value)]));
  }
  const buttons = form.querySelectorAll("button");
  buttons.forEach(button => { button.disabled = true; });
  try {
    const response = await fetch("/api/settings/control" + (reset ? "/reset" : ""), {
      method: "POST", credentials: "same-origin",
      headers: {"Content-Type": "application/json", "X-CSRF-Token": root.dataset.csrf}, body: JSON.stringify(body)
    });
    if (!response.ok) {
      const messages = {401: "로그인 후 다시 시도하세요.", 403: "설정 변경 권한을 확인하세요.",
        409: "다른 화면에서 설정이 바뀌었습니다. 새로고침한 뒤 다시 수정하세요.",
        422: "입력 범위와 해제 값 < 진입 값 조건을 확인하세요."};
      feedback.textContent = messages[response.status] || "저장하지 못했습니다. 서버 상태를 확인하세요.";
      return;
    }
    const snapshot = await response.json();
    root.dataset.revision = snapshot.revision;
    for (const input of form.querySelectorAll("input[name]")) input.value = snapshot.calibration[input.name];
    document.getElementById("actor").textContent = snapshot.actor;
    changed.textContent = timeText(snapshot.changed_ms);
    feedback.textContent = "저장했습니다. 이 VM의 Webots 시뮬레이션을 다시 시작하면 적용됩니다.";
  } catch {
    feedback.textContent = "저장 결과를 확인할 수 없습니다. 새로고침하여 저장된 값을 확인하세요.";
  } finally {
    buttons.forEach(button => { button.disabled = false; });
  }
}
form.addEventListener("submit", event => { event.preventDefault(); save(false); });
document.getElementById("reset-calibration").addEventListener("click", () => save(true));
