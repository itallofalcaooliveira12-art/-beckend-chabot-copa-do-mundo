const defaultApiUrl = location.hostname === "localhost" || location.hostname === "127.0.0.1"
  ? "http://localhost:5000"
  : "https://SEU-BACKEND.onrender.com";
const API_URL = localStorage.getItem("copabot_api_url") || defaultApiUrl;

const chatArea = document.getElementById("chatArea");
const composer = document.getElementById("composer");
const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const typing = document.getElementById("typing");
const welcome = document.getElementById("welcome");
const historyList = document.getElementById("historyList");
const charCount = document.getElementById("charCount");
const toast = document.getElementById("toast");
const sidebar = document.getElementById("sidebar");

let messages = JSON.parse(localStorage.getItem("copabot_current") || "[]");
let conversations = JSON.parse(localStorage.getItem("copabot_history") || "[]");
let busy = false;
let currentConversationId = null;

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, char => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"
  }[char]));
}

function markdownLite(text) {
  let html = escapeHtml(text);
  html = html.replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(/^\s*[-•]\s+(.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
  html = html.replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>");
  return `<p>${html}</p>`;
}

function save() {
  localStorage.setItem("copabot_current", JSON.stringify(messages));
  localStorage.setItem("copabot_history", JSON.stringify(conversations.slice(-20)));
}

function renderHistory() {
  historyList.innerHTML = "";
  [...conversations].reverse().forEach((conv, index) => {
    const btn = document.createElement("button");
    btn.className = "history-item";
    btn.textContent = conv.title || "Conversa sem título";
    btn.onclick = () => loadConversation(conversations.length - 1 - index);
    historyList.appendChild(btn);
  });
}

function renderMessages() {
  chatArea.innerHTML = "";
  if (!messages.length) {
    chatArea.appendChild(welcome);
    return;
  }
  messages.forEach(addMessageToDOM);
  scrollBottom();
}

function addMessageToDOM(message, target = chatArea) {
  const row = document.createElement("div");
  row.className = `message-row ${message.role}`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = message.role === "user" ? "◉" : "⚽";
  const bubble = document.createElement("div");
  bubble.className = "message";
  bubble.innerHTML = message.role === "user" ? markdownLite(message.content) : markdownLite(message.content);
  if (message.role === "user") {
    row.appendChild(bubble);
    row.appendChild(avatar);
  } else {
    row.appendChild(avatar);
    row.appendChild(bubble);
  }
  target.appendChild(row);
  return bubble;
}

function scrollBottom() {
  chatArea.scrollTop = chatArea.scrollHeight;
}

function setBusy(value) {
  busy = value;
  sendBtn.disabled = value;
  typing.hidden = !value;
  input.disabled = value;
}

function toastMessage(text) {
  toast.textContent = text;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2600);
}

function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
  charCount.textContent = `${input.value.length} / 4000`;
}

async function sendMessage(text) {
  if (busy || !text.trim()) return;
  text = text.trim();

  const historyForApi = messages.slice(-16);
  messages.push({ role: "user", content: text });
  if (welcome.parentNode) welcome.remove();
  addMessageToDOM({ role: "user", content: text });
  scrollBottom();
  input.value = "";
  autosize();
  setBusy(true);

  // Cria um placeholder para resposta progressiva.
  const assistantMessage = { role: "assistant", content: "" };
  messages.push(assistantMessage);
  const bubble = addMessageToDOM(assistantMessage);
  scrollBottom();

  try {
    const response = await fetch(`${API_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: historyForApi })
    });

    if (!response.ok) throw new Error("Servidor indisponível.");
    if (!response.body) throw new Error("Streaming não suportado pelo navegador.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const event of events) {
        const line = event.split("\n").find(item => item.startsWith("data: "));
        if (!line) continue;
        const data = JSON.parse(line.slice(6));

        if (data.type === "token") {
          assistantMessage.content += data.content;
          bubble.innerHTML = markdownLite(assistantMessage.content);
          scrollBottom();
        } else if (data.type === "done") {
          if (data.reply && !assistantMessage.content) {
            assistantMessage.content = data.reply;
            bubble.innerHTML = markdownLite(data.reply);
          }
        } else if (data.type === "error") {
          throw new Error(data.error || "Erro na IA.");
        }
      }
    }

    save();
    saveCurrentConversation();
  } catch (error) {
    assistantMessage.content = `⚠️ ${error.message || "Não foi possível concluir a resposta."}`;
    bubble.innerHTML = markdownLite(assistantMessage.content);
    toastMessage("Não foi possível conectar ao backend.");
  } finally {
    setBusy(false);
    input.focus();
    scrollBottom();
  }
}

function saveCurrentConversation() {
  if (!messages.length) return;
  const firstUser = messages.find(m => m.role === "user");
  if (!firstUser) return;
  const title = firstUser.content.slice(0, 48);

  if (currentConversationId === null) {
    currentConversationId = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    conversations.push({ id: currentConversationId, title, messages: structuredClone(messages) });
  } else {
    const current = conversations.find(c => c.id === currentConversationId);
    if (current) {
      current.title = title;
      current.messages = structuredClone(messages);
    }
  }
  save();
  renderHistory();
}

function loadConversation(index) {
  const conv = conversations[index];
  if (!conv) return;
  messages = structuredClone(conv.messages || []);
  currentConversationId = conv.id || null;
  save();
  renderMessages();
  sidebar.classList.remove("open");
}

function newChat() {
  if (messages.length) saveCurrentConversation();
  messages = [];
  localStorage.removeItem("copabot_current");
  renderMessages();
  input.focus();
}

composer.addEventListener("submit", e => {
  e.preventDefault();
  sendMessage(input.value);
});

input.addEventListener("input", autosize);
input.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    composer.requestSubmit();
  }
});

document.querySelectorAll("[data-prompt]").forEach(btn => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.prompt));
});

document.getElementById("newChatBtn").addEventListener("click", newChat);
document.getElementById("clearBtn").addEventListener("click", () => {
  if (confirm("Limpar a conversa atual?")) newChat();
});
document.getElementById("menuBtn").addEventListener("click", () => sidebar.classList.toggle("open"));

renderHistory();
renderMessages();
autosize();
