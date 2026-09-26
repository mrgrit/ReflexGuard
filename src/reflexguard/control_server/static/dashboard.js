"use strict";
const feedback = document.getElementById("feedback");
const root = document.getElementById("dashboard") || document.getElementById("login");
async function send(path, body, method="POST") {
  const response = await fetch(path, {method, credentials:"same-origin", headers:{"Content-Type":"application/json", "X-CSRF-Token":root.dataset.csrf}, body:JSON.stringify(body)});
  if (!response.ok) throw new Error("요청이 거부되었습니다. 권한과 연결 상태를 확인하세요.");
  return response.json();
}
function bind(selector, event, handler) {
  document.querySelectorAll(selector).forEach(el => el.addEventListener(event, async e => {
    e.preventDefault();
    try { await handler(el); } catch (error) { feedback.textContent=error.message; }
  }));
}
bind("#login", "submit", async form => { await send("/login", {username:form.elements.username.value,password:form.elements.password.value}); location.assign("/"); });
bind("#logout", "click", async () => { await send("/logout", {}); location.assign("/login"); });
bind(".stop", "click", async button => { await send("/remote", {chair_id:button.dataset.chair,action:"stop"}); feedback.textContent="정지 요청을 보냈습니다. 판단 로그에서 적용 결과를 확인하세요."; });
bind(".speed", "submit", async form => { await send("/remote", {chair_id:form.dataset.chair,action:"speed_limit",speed_limit:Number(form.elements.speed.value)}); feedback.textContent="속도 제한 요청을 보냈습니다."; });
bind(".silence", "submit", async form => { await send("/chairs/"+encodeURIComponent(form.dataset.chair)+"/silence", {neuron_ids:form.elements.neurons.value.split(",").map(x=>x.trim())}); feedback.textContent="침묵 요청을 보냈습니다. 뇌 서버 허용목록에 따라 처리됩니다."; });
bind("#create-user", "submit", async form => {const r=await send("/admin/users",{username:form.elements.username.value,password:form.elements.password.value,role:form.elements.role.value});form.reset();feedback.textContent="생성된 사용자 ID: "+r.id;});
bind("#assign", "submit", async form => {await send("/admin/chairs/"+encodeURIComponent(form.elements.chair.value),{guardian_id:Number(form.elements.guardian.value)},"PATCH");feedback.textContent="보호자 지정 완료";});
bind("#update-user", "submit", async form => {await send("/admin/users/"+Number(form.elements.id.value),{role:form.elements.role.value,active:form.elements.active.checked},"PATCH");feedback.textContent="사용자 변경 완료";});
if (document.getElementById("dashboard")) setTimeout(() => {if (!document.activeElement.matches("input,select")) location.reload();}, 1000);
