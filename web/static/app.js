// Văn phòng ảo — client logic

const rosterList = document.getElementById("roster-list");
const feed = document.getElementById("feed");
const form = document.getElementById("input-form");
const input = document.getElementById("input");
const status = document.getElementById("conn-status");

let socket = null;
let roster = [];
const colorByName = new Map();

async function loadRoster() {
  const res = await fetch("/api/roster");
  const data = await res.json();
  roster = data.members;
  for (const m of roster) colorByName.set(m.name, m.color);

  rosterList.innerHTML = "";
  for (const m of roster) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="avatar" style="background:${m.color}">${m.name[0]}</div>
      <div>
        <span class="name">${m.name}</span>
        <span class="title">${m.title}</span>
      </div>
    `;
    rosterList.appendChild(li);
  }
}

function setStatus(connected) {
  status.textContent = connected ? "online" : "offline";
  status.className = "status " + (connected ? "online" : "offline");
}

function makeBubble(speaker) {
  const color = colorByName.get(speaker) || "#888";
  const wrapper = document.createElement("div");
  wrapper.className = "msg";
  wrapper.innerHTML = `
    <div class="avatar" style="background:${color}">${speaker[0]}</div>
    <div class="body">
      <div class="who" style="color:${color}">${speaker}</div>
      <div class="text"></div>
    </div>
  `;
  feed.appendChild(wrapper);
  feed.scrollTop = feed.scrollHeight;
  return wrapper.querySelector(".text");
}

let currentBubble = null;
let currentSpeaker = null;

function handleEvent(ev) {
  if (ev.error) {
    appendSystem(`⚠️ ${ev.error}`);
    return;
  }
  if (ev.turn_complete) {
    currentBubble = null;
    currentSpeaker = null;
    return;
  }
  if (ev.speaker !== currentSpeaker) {
    currentSpeaker = ev.speaker;
    currentBubble = makeBubble(ev.speaker);
  }
  currentBubble.textContent += ev.text;
  feed.scrollTop = feed.scrollHeight;

  if (ev.final) {
    currentBubble = null;
    currentSpeaker = null;
  }
}

function appendSystem(text) {
  const div = document.createElement("div");
  div.className = "msg";
  div.innerHTML = `<div class="body"><div class="text" style="color:#ed4245">${text}</div></div>`;
  feed.appendChild(div);
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws`);
  socket.onopen  = () => setStatus(true);
  socket.onclose = () => { setStatus(false); setTimeout(connect, 1500); };
  socket.onmessage = (e) => handleEvent(JSON.parse(e.data));
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || !socket || socket.readyState !== WebSocket.OPEN) return;
  appendUserMsg(text);
  socket.send(JSON.stringify({ text }));
  input.value = "";
});

function appendUserMsg(text) {
  const div = document.createElement("div");
  div.className = "msg";
  div.innerHTML = `
    <div class="avatar" style="background:#7289da">U</div>
    <div class="body">
      <div class="who" style="color:#7289da">Bạn</div>
      <div class="text"></div>
    </div>
  `;
  div.querySelector(".text").textContent = text;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
}

(async () => {
  await loadRoster();
  connect();
})();
