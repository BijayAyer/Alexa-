const conversation = document.querySelector("#conversation");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const sendButton = document.querySelector("#send-button");
const speakButton = document.querySelector("#speak-button");
const readAloud = document.querySelector("#read-aloud");
const status = document.querySelector("#status");
const materialStatus = document.querySelector("#material-status");
const topicList = document.querySelector("#topic-list");

function addMessage(label, text, tools = []) {
  const article = document.createElement("article");
  article.className = "message";

  const heading = document.createElement("span");
  heading.className = "message-label";
  heading.textContent = label;
  const content = document.createElement("p");
  content.className = "message-text";
  content.textContent = text;
  article.append(heading, content);

  if (label === "alexa") {
    const log = document.createElement("p");
    log.className = "tool-log";
    log.textContent = `used: ${tools.length ? tools.join(", ") : "none"}`;
    article.append(log);
    if (readAloud.checked && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
    }
  }

  conversation.append(article);
  conversation.scrollTop = conversation.scrollHeight;
}

async function refreshState() {
  try {
    const response = await fetch("/api/state");
    if (!response.ok) throw new Error("state request failed");
    const state = await response.json();
    const scores = new Map(state.last_quiz_scores.map((score) => [score.topic, score]));
    topicList.replaceChildren();

    if (!state.topics.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "No saved topics yet.";
      topicList.append(empty);
      return;
    }

    for (const topic of state.topics) {
      const section = document.createElement("section");
      section.className = "topic";
      const name = document.createElement("h3");
      name.className = "topic-name";
      name.textContent = topic.topic;
      const count = document.createElement("p");
      count.className = "topic-detail";
      count.textContent = `${topic.note_count} ${topic.note_count === 1 ? "note" : "notes"}`;
      section.append(name, count);

      const score = scores.get(topic.topic);
      if (score) {
        const detail = document.createElement("p");
        detail.className = "topic-detail";
        detail.textContent = `last quiz: ${score.correct} of ${score.total}`;
        section.append(detail);
      }
      topicList.append(section);
    }
  } catch {
    topicList.textContent = "Saved topics are unavailable right now.";
  }
}

document.querySelector("#text-material-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  materialStatus.textContent = "Saving notes.";
  try {
    const response = await fetch("/api/materials/text", { method: "POST", body: formData });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not save notes.");
    event.currentTarget.reset();
    materialStatus.textContent = `Notes saved for ${result.topic}. Ask Cram a question or start a quiz.`;
    await refreshState();
  } catch (error) {
    materialStatus.textContent = error.message || "Could not save notes.";
  }
});

document.querySelector("#pdf-material-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const topic = document.querySelector("#material-topic").value.trim();
  const fileInput = document.querySelector("#material-pdf");
  if (!topic) {
    materialStatus.textContent = "Enter a topic before uploading the PDF.";
    document.querySelector("#material-topic").focus();
    return;
  }
  if (!fileInput.files.length) return;
  const formData = new FormData();
  formData.set("topic", topic);
  formData.set("file", fileInput.files[0]);
  materialStatus.textContent = "Reading the PDF.";
  try {
    const response = await fetch("/api/materials/pdf", { method: "POST", body: formData });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not read this PDF.");
    event.currentTarget.reset();
    materialStatus.textContent = `Added ${result.filename} to ${result.topic}. Ask Cram a question or start a quiz.`;
    await refreshState();
  } catch (error) {
    materialStatus.textContent = error.message || "Could not read this PDF.";
  }
});

async function sendMessage(message) {
  const text = message.trim();
  if (!text) return;
  addMessage("you", text);
  input.value = "";
  sendButton.disabled = true;
  status.textContent = "";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error("The chat request failed.");
    addMessage("alexa", result.reply, result.tools_used);
    await refreshState();
  } catch (error) {
    addMessage("alexa", error.message || "I couldn't send that message. Please try again.");
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

document.querySelectorAll("[data-message]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    input.value = link.dataset.message;
    input.focus();
  });
});

document.querySelector("#reset-button").addEventListener("click", async () => {
  try {
    await fetch("/api/reset", { method: "POST" });
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    conversation.replaceChildren();
    status.textContent = "Conversation reset.";
  } catch {
    status.textContent = "The conversation could not be reset.";
  }
});

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  speakButton.hidden = false;
  speakButton.addEventListener("click", () => {
    const recognition = new SpeechRecognition();
    recognition.lang = document.documentElement.lang || "en-US";
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      input.value = event.results[0][0].transcript;
      input.focus();
    };
    recognition.onerror = () => {
      status.textContent = "Speech input was unavailable. You can type your message instead.";
    };
    recognition.start();
    status.textContent = "Listening.";
  });
}

refreshState();