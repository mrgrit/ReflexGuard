"use strict";
(() => {
  const root = document.getElementById("activity");
  if (!root) return;
  const get = id => document.getElementById(id);
  const svgNode = (tag, attributes = {}, label) => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
    if (label !== undefined) element.textContent = label;
    return element;
  };
  const nodes = new Map(), edges = [];
  let graph, latest = new Map(), selected = null;
  const states = {waiting: "수신 대기", malecns: "LIVE · MaleCNS 모델 일치", mock: "MOCK · 실제 신경회로 아님", stale: "수신 지연 · 마지막 값은 실시간 아님", unverified: "모델 또는 뉴런 데이터 확인 필요", offline: "연결 끊김 · 상태 확인 필요"};
  const reasons = {user: "사용자 조종", idle: "입력 대기", risk_monitoring: "위험 감지 · 감속", avoid_left: "왼쪽 회피", avoid_right: "오른쪽 회피", avoid_passing: "장애물 옆 통과", avoid_clearance_recovery: "여유 공간 확보", control_recovering: "진행 방향 복귀", control_recovered: "사용자 조종 복귀", path_blocked: "회피 공간 없음 · 정지", brain_failure: "뇌 통신 오류 · 정지", sensor_failure: "거리 센서 오류 · 정지", control_failure: "관제 오류 · 정지", remote_stop: "원격 정지", hazard_stop: "위험 감지 · 정지"};
  function detail() {
    if (!selected) return;
    const node = nodes.get(selected).node;
    const rate = latest.get(selected);
    get("neuron-detail").textContent = `${node.cell_type} · ${node.side} · ID ${node.id} · ${rate === undefined ? "수신 값 없음" : rate.toFixed(2) + " Hz"}`;
  }
  function build() {
    const svg = get("circuit");
    const indexes = {L: 0, R: 0};
    for (const node of graph.nodes) {
      const output = node.cell_type === "DNp01";
      const index = indexes[node.side];
      if (!output) indexes[node.side]++;
      const x = output ? 790 : 85 + (index % 10) * 25;
      const y = output ? (node.side === "L" ? 200 : 500) : (node.side === "L" ? 80 : 385) + Math.floor(index / 10) * 25;
      nodes.set(node.id, {node, x, y, output});
    }
    for (const edge of graph.edges) {
      const a = nodes.get(edge.source), b = nodes.get(edge.target);
      const path = svgNode("path", {d: `M ${a.x} ${a.y} C 450 ${a.y}, 570 ${b.y}, ${b.x} ${b.y}`, fill: "none", stroke: "#294154", "stroke-width": Math.min(2.5, .4 + edge.synapses / 120), opacity: .25});
      path.append(svgNode("title", {}, `${edge.source} → ${edge.target}: ${edge.synapses} 시냅스`));
      svg.append(path); edges.push({path, source: edge.source});
    }
    for (const item of nodes.values()) {
      const {node, x, y, output} = item;
      const circle = svgNode("circle", {cx: x, cy: y, r: output ? 30 : 7, fill: "#687482", tabindex: 0, role: "button", "aria-label": `${node.cell_type} ${node.side} ${node.id}`});
      const title = svgNode("title", {}, `${node.id}: 수신 값 없음`);
      circle.append(title);
      const choose = () => { selected = node.id; detail(); };
      circle.addEventListener("click", choose);
      circle.addEventListener("focus", choose);
      circle.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); } });
      item.circle = circle; item.title = title; svg.append(circle);
      if (output) svg.append(svgNode("text", {x, y: y + 60, "text-anchor": "middle", class: "circuit-label"}, `DNp01 ${node.side} · ${node.id}`));
    }
    for (const [y, label] of [[45, "LPLC2 L · 94개"], [350, "LPLC2 R · 91개"]]) svg.append(svgNode("text", {x: 75, y, class: "circuit-label"}, label));
    svg.append(svgNode("text", {x: 465, y: 650, class: "circuit-label"}, "185개 연결 · 원본 시냅스 수에 비례한 선 두께"));
  }
  function paint(data) {
    const live = data.state === "malecns";
    const frame = data.frame;
    get("stream-state").textContent = states[data.state] || states.unverified;
    get("stream-state").classList.toggle("live", live);
    get("sample-time").textContent = frame ? `시뮬레이션 ${(frame.t_ms / 1000).toFixed(2)}초 · 수신 ${data.age_ms}ms 전` : "새 데이터 대기";
    latest = new Map(live ? frame.neuron_activity.map(n => [n.id, n.rate_hz]) : []);
    for (const [id, item] of nodes) {
      const rate = latest.get(id);
      const color = rate === undefined ? "#687482" : rate === 0 ? "#24405a" : `hsl(${175 - Math.min(rate / 200, 1) * 145} 85% 60%)`;
      item.circle.setAttribute("fill", color);
      item.title.textContent = `${id}: ${rate === undefined ? "수신 값 없음" : rate.toFixed(2) + " Hz"}`;
      if (item.output) get(item.node.side === "L" ? "output-left" : "output-right").textContent = rate === undefined ? "—" : `${rate.toFixed(2)} Hz`;
    }
    for (const edge of edges) edge.path.setAttribute("opacity", live && latest.get(edge.source) > 0 ? .65 : .15);
    const current = frame && ["malecns", "mock", "unverified"].includes(data.state);
    for (const [name, key] of [["left", "left_looming"], ["right", "right_looming"], ["escape", "escape"]]) {
      get(name + "-value").textContent = current ? frame[key].toFixed(3) : "—";
      get(name + "-meter").value = current ? frame[key] : 0;
    }
    get("motion-state").textContent = current ? (reasons[frame.reason] || frame.reason) : "새 판단 대기";
    get("motion-value").textContent = current ? `${frame.forward.toFixed(2)} m/s · 조향 ${frame.turn.toFixed(2)} rad/s` : "—";
    get("motion-mode").textContent = frame && frame.navigation_mode === "range_assisted" ? "신경회로: 위험 출력 / 로컬 거리 센서: 빈 공간으로 회피 조향" : "신경회로 위험 출력 기반 정지·공유 제어";
    get("model-identity").textContent = frame ? `${frame.model_version} · 가중치 SHA-256 ${frame.weights_sha256 || "미수신"}` : "실행 모델 확인 대기";
    const points = (data.history || []).map((row, i, all) => `${i * 300 / Math.max(1, all.length - 1)},${89 - row.escape * 88}`).join(" ");
    get("history-line").setAttribute("points", points);
    const table = get("neuron-table"); table.replaceChildren();
    if (live) {
      const ranked = [...frame.neuron_activity].sort((a, b) => b.rate_hz - a.rate_hz || a.id.localeCompare(b.id)).slice(0, 12);
      for (const neuron of ranked) {
        const row = document.createElement("tr");
        for (const value of [neuron.id, neuron.type, nodes.get(neuron.id).node.side, neuron.rate_hz.toFixed(2)]) {
          const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
        }
        table.append(row);
      }
    } else {
      const row = document.createElement("tr"), cell = document.createElement("td"); cell.colSpan = 4; cell.textContent = states[data.state]; row.append(cell); table.append(row);
    }
    detail();
  }
  async function json(url) {
    const response = await fetch(url, {credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(3000)});
    if (!response.ok) throw new Error("Unavailable");
    return response.json();
  }
  async function poll() {
    try {
      if (!graph) { graph = await json("/assets/malecns-circuit.json"); build(); }
      paint(await json(`/api/chairs/${encodeURIComponent(root.dataset.chair)}/activity`));
    } catch (_) { paint({state: "offline", frame: null, history: []}); }
    window.setTimeout(poll, 500);
  }
  poll();
})();
