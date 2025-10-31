let activeSessionId = null;
let renamedOnce = false;
let recognition = null;
let uploadedFiles = [];
let userProfile = {};

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  loadSessions();
  loadProfile();
  loadStats();
  initializeVoiceRecognition();

  // Auto-resize textarea
  const textarea = document.getElementById("user-input");
  textarea.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = this.scrollHeight + "px";
  });

  // Search conversations
  document
    .getElementById("search-conversations")
    .addEventListener("input", filterConversations);

  // File upload
  document.getElementById("file-input").addEventListener("change", handleFiles);
});

// Load user profile
function loadProfile() {
  const saved = localStorage.getItem("fitcoach-profile");
  if (saved) {
    userProfile = JSON.parse(saved);
    document.getElementById("profile-age").value = userProfile.age || "";
    document.getElementById("profile-gender").value = userProfile.gender || "";
    document.getElementById("profile-height").value = userProfile.height || "";
    document.getElementById("profile-weight").value = userProfile.weight || "";
    document.getElementById("profile-goal").value = userProfile.goal || "";
    document.getElementById("profile-activity").value =
      userProfile.activity || "";
    document.getElementById("profile-diet").value = userProfile.diet || "";
    document.getElementById("profile-medical").value =
      userProfile.medical || "";
  }
}

// Load stats
function loadStats() {
  const stats = JSON.parse(
    localStorage.getItem("fitcoach-stats") ||
      '{"sessionsToday": 0, "totalWorkouts": 0, "streakDays": 0}'
  );
  document.getElementById("sessions-today").textContent = stats.sessionsToday;
  document.getElementById("total-workouts").textContent = stats.totalWorkouts;
  document.getElementById("streak-days").textContent =
    stats.streakDays + " days";
}

// Update stats
function updateStats() {
  const stats = JSON.parse(
    localStorage.getItem("fitcoach-stats") ||
      '{"sessionsToday": 0, "totalWorkouts": 0, "streakDays": 0}'
  );
  stats.sessionsToday += 1;
  stats.totalWorkouts += 1;

  const lastSession = localStorage.getItem("last-session-date");
  const today = new Date().toDateString();

  if (lastSession === today) {
    // Same day, no change to streak
  } else if (lastSession === new Date(Date.now() - 86400000).toDateString()) {
    // Previous day, increment streak
    stats.streakDays += 1;
  } else {
    // Reset streak
    stats.streakDays = 1;
  }

  localStorage.setItem("last-session-date", today);
  localStorage.setItem("fitcoach-stats", JSON.stringify(stats));
  loadStats();
}

// Filter conversations
function filterConversations() {
  const search = document
    .getElementById("search-conversations")
    .value.toLowerCase();
  const conversations = document.querySelectorAll("#conversation-list li");

  conversations.forEach((conv) => {
    const text = conv.textContent.toLowerCase();
    conv.style.display = text.includes(search) ? "block" : "none";
  });
}

// Load sessions
async function loadSessions() {
  const res = await fetch("/sessions");
  const sessions = await res.json();

  const list = document.getElementById("conversation-list");
  list.innerHTML = "";

  if (sessions.error) {
    console.error("Error fetching sessions:", sessions.error);
    return;
  }

  sessions.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s.name || `Session ${s.id.slice(0, 6)}`;
    li.onclick = async () => {
      await activateSession(s.id);
    };

    if (s.id === activeSessionId) {
      li.classList.add("active");
    }

    list.appendChild(li);
  });
}

// Fix the createNewConversation function
async function createNewConversation() {
  try {
    // Create a more descriptive default name
    const defaultName = `Workout Session ${new Date().toLocaleDateString()}`;

    const res = await fetch("/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: defaultName,
      }),
    });

    const session = await res.json();

    if (session.error) {
      showToast("❌ Error creating session: " + session.error, "error");
      return;
    }

    await loadSessions();
    await activateSession(session.id);
    showToast("✅ New coaching session started!", "success");
    updateStats();
  } catch (error) {
    console.error("Error creating session:", error);
    showToast("❌ Error creating session", "error");
  }
}
// Activate session
// Activate session
async function activateSession(id) {
  try {
    // 1. Activate the session on the backend
    await fetch(`/sessions/${id}/activate`, { method: "POST" });
    activeSessionId = id;

    // 2. Fetch the session's messages and name
    const msgRes = await fetch(`/sessions/${id}/messages`);
    const messagesData = await msgRes.json();

    if (messagesData.error) {
      console.error("Error fetching messages:", messagesData.error);
      showToast(messagesData.error, "error");
      return;
    }

    // 3. Update the chat title
    document.getElementById("chat-title").textContent =
      "💪 " + (messagesData.session_name || "FitCoach AI");

    // 4. Get the messages array safely
    const messages = messagesData.messages || [];
    renamedOnce = messages.length > 0;

    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "";

    // 5. Display messages or the empty state
    if (messages.length === 0) {
      chatBox.innerHTML = `
            <div class="empty-state">
              <div class="empty-state-icon">💪</div>
              <h3>Welcome to FitCoach AI!</h3>
              <p>Your personal health and sports coach powered by RAGflow. I'm here to help you with workout plans, nutrition advice, form checks, progress tracking, and achieving your fitness goals. Let's start your journey to a healthier you!</p>
            </div>
          `;
    } else {
      messages.forEach((m) => {
        if (m && m.content) {
          displayMessage(m.content, m.role === "user" ? "user" : "assistant");
        }
      });
    }

    chatBox.scrollTop = chatBox.scrollHeight;

    // 6. Refresh the session list to highlight the active one
    await loadSessions();
  } catch (err) {
    console.error("Failed to activate session:", err);
    showToast("Could not switch conversations.", "error");
  }
}

function displayMessage(content, role) {
  const chatBox = document.getElementById("chat-box");

  // Remove empty state if exists
  const emptyState = chatBox.querySelector(".empty-state");
  if (emptyState) {
    emptyState.remove();
  }

  const div = document.createElement("div");
  div.classList.add("message", role);

  const now = new Date();
  const time = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

  // Convert content to string safely
  let messageContent;
  if (typeof content === "string") {
    messageContent = content;
  } else if (typeof content === "object" && content !== null) {
    // Try to extract text from common object properties
    messageContent =
      content.message ||
      content.text ||
      content.content ||
      content.response ||
      JSON.stringify(content);
  } else {
    messageContent = String(content);
  }

  div.innerHTML = `
    <div class="message-content-wrapper">
      ${marked.parse(messageContent)}
    </div>
    <span class="message-timestamp">${time}</span>
    <div class="message-actions">
      <button onclick="copyMessage(this)" title="Copy">📋</button>
      <button onclick="speakMessage(this)" title="Speak">🔊</button>
      ${
        role === "assistant"
          ? '<button onclick="regenerateMessage(this)" title="Regenerate">🔄</button>'
          : ""
      }
    </div>
  `;

  chatBox.appendChild(div);

  // Highlight code blocks if present
  div.querySelectorAll("pre code").forEach((block) => {
    if (typeof hljs !== "undefined") {
      hljs.highlightElement(block);
    }
  });

  chatBox.scrollTop = chatBox.scrollHeight;
  return div;
}
// Copy message
function copyMessage(btn) {
  const message = btn.closest(".message");
  const text = message.textContent
    .replace(/📋🔊🔄\d{1,2}:\d{2}\s[AP]M/g, "")
    .trim();
  navigator.clipboard.writeText(text);
  showToast("📋 Message copied!", "success");
}

// Speak message
function speakMessage(btn) {
  const message = btn.closest(".message");
  const text = message.textContent
    .replace(/📋🔊🔄\d{1,2}:\d{2}\s[AP]M/g, "")
    .trim();

  if ("speechSynthesis" in window) {
    const utterance = new SpeechSynthesisUtterance(text);
    speechSynthesis.speak(utterance);
    showToast("🔊 Speaking...", "success");
  } else {
    showToast("❌ Speech not supported", "error");
  }
}

// Regenerate message
async function regenerateMessage(btn) {
  const message = btn.closest(".message");
  const prevMessage = message.previousElementSibling;

  if (prevMessage && prevMessage.classList.contains("user")) {
    const userText = prevMessage.textContent
      .replace(/📋🔊🔄\d{1,2}:\d{2}\s[AP]M/g, "")
      .trim();
    message.remove();
    await sendMessageWithText(userText);
  }
}

// Rename session
async function renameSession(sessionId, newName) {
  try {
    const res = await fetch(`/sessions/${sessionId}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName }),
    });

    const responseText = await res.text();

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${responseText}`);
    }

    const updated = JSON.parse(responseText);

    if (updated.error) {
      throw new Error(updated.error);
    }

    document.getElementById("chat-title").textContent = "💪 " + updated.name;
    await loadSessions();
    return true;
  } catch (err) {
    console.error("Rename error:", err);
    return false;
  }
}

// Send message
async function sendMessage() {
  const input = document.getElementById("user-input");
  const text = input.value.trim();
  if (!text || !activeSessionId) {
    if (!activeSessionId) {
      showToast("⚠️ Please start a new session first", "error");
    }
    return;
  }

  await sendMessageWithText(text);
  input.value = "";
  input.style.height = "auto";
}

async function sendMessageWithText(text) {
  const chatBox = document.getElementById("chat-box");
  const isFirstMessage = !renamedOnce;

  displayMessage(text, "user");

  const spinnerDiv = document.createElement("div");
  spinnerDiv.classList.add("message", "assistant", "waiting");
  spinnerDiv.innerHTML = `
    <span>Analyzing your request...</span>
    <div class="spinner"></div>
  `;
  chatBox.appendChild(spinnerDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    const eventSource = new EventSource(
      `/ask?question=${encodeURIComponent(text)}`
    );
    let fullText = "";
    let aiDiv = null;

    eventSource.onmessage = (event) => {
      if (event.data === '"END"' || event.data === "END") {
        eventSource.close();

        // Auto-speak if enabled
        if (document.getElementById("auto-speak-toggle")?.checked) {
          const utterance = new SpeechSynthesisUtterance(fullText);
          speechSynthesis.speak(utterance);
        }

        // Save message and handle first message renaming
        setTimeout(async () => {
          try {
            const checkRes = await fetch(`/sessions/${activeSessionId}/check`);
            const checkData = await checkRes.json();

            if (checkData.message_count === 0) {
              await fetch(`/sessions/${activeSessionId}/save_message`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  user_message: text,
                  assistant_message: fullText,
                }),
              });
            }
          } catch (err) {
            console.error("Error checking/saving messages:", err);
          }
        }, 1000);

        if (isFirstMessage && !renamedOnce) {
          renamedOnce = true;
          const newName = text.length > 30 ? text.slice(0, 30) + "…" : text;
          setTimeout(async () => {
            await renameSession(activeSessionId, newName);
          }, 1500);
        }
        return;
      }

      try {
        let data = event.data;

        // Try to parse JSON, but if it fails, use the raw data
        try {
          const parsed = JSON.parse(data);
          data = parsed;
        } catch (e) {
          // If it's not JSON, keep it as string
        }

        // Handle the data whether it's string or object
        if (typeof data === "string") {
          fullText += data;
        } else if (typeof data === "object") {
          // Extract text from object
          const textFromObject =
            data.message ||
            data.text ||
            data.content ||
            data.response ||
            JSON.stringify(data);
          fullText += textFromObject;
        }

        if (!aiDiv) {
          chatBox.removeChild(spinnerDiv);
          aiDiv = displayMessage(fullText, "assistant");
        } else {
          const now = new Date();
          const time = now.toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
          });

          aiDiv.innerHTML = `
            ${marked.parse(fullText)}
            <span class="message-timestamp">${time}</span>
            <div class="message-actions">
              <button onclick="copyMessage(this)" title="Copy">📋</button>
              <button onclick="speakMessage(this)" title="Speak">🔊</button>
              <button onclick="regenerateMessage(this)" title="Regenerate">🔄</button>
            </div>
          `;
        }

        chatBox.scrollTop = chatBox.scrollHeight;
      } catch (err) {
        console.error("Error processing response:", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("EventSource error:", err);
      eventSource.close();

      if (!aiDiv) {
        chatBox.removeChild(spinnerDiv);
        displayMessage(
          "⚠️ Error generating response. Please try again.",
          "assistant"
        );
      }

      if (isFirstMessage && !renamedOnce) {
        renamedOnce = true;
        const newName = text.length > 30 ? text.slice(0, 30) + "…" : text;
        setTimeout(async () => {
          await renameSession(activeSessionId, newName);
        }, 1000);
      }
    };
  } catch (error) {
    console.error("Error creating EventSource:", error);
    chatBox.removeChild(spinnerDiv);
    displayMessage(
      "⚠️ Error connecting to AI service. Please try again.",
      "assistant"
    );
  }
}

// Use suggested prompt
function usePrompt(text) {
  document.getElementById("user-input").value = text;
  document.getElementById("user-input").focus();
}

// Insert emoji
function insertEmoji(emoji) {
  const input = document.getElementById("user-input");
  input.value += emoji;
  input.focus();
}

// Theme toggle
function toggleTheme() {
  document.body.classList.toggle("dark-mode");
  const isDark = document.body.classList.contains("dark-mode");
  document.getElementById("dark-mode-toggle").checked = isDark;
  localStorage.setItem("darkMode", isDark);
}

// Load saved theme
if (localStorage.getItem("darkMode") === "true") {
  document.body.classList.add("dark-mode");
  document.getElementById("dark-mode-toggle").checked = true;
}

// Modals
function toggleProfile() {
  document.getElementById("profile-modal").classList.add("active");
}

function closeProfile() {
  document.getElementById("profile-modal").classList.remove("active");
}

function toggleSettings() {
  document.getElementById("settings-modal").classList.add("active");
}

function closeSettings() {
  document.getElementById("settings-modal").classList.remove("active");
}

// Export plan
async function exportPlan() {
  if (!activeSessionId) {
    showToast("⚠️ No active session to export", "error");
    return;
  }

  const msgRes = await fetch(`/sessions/${activeSessionId}/messages`);
  const messages = await msgRes.json();

  let markdown = `# FitCoach AI - Training Session Export\n\n`;
  markdown += `**Date:** ${new Date().toLocaleDateString()}\n\n`;

  if (userProfile.goal) {
    markdown += `**Goal:** ${userProfile.goal}\n`;
  }
  if (userProfile.activity) {
    markdown += `**Activity Level:** ${userProfile.activity}\n`;
  }
  markdown += `\n---\n\n`;

  messages.forEach((m) => {
    markdown += `## ${m.role === "user" ? "👤 You" : "💪 Coach"}\n${
      m.content
    }\n\n`;
  });

  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `fitcoach-plan-${new Date().toISOString().split("T")[0]}.md`;
  a.click();

  showToast("📥 Training plan exported!", "success");
}

// Load settings
async function loadSettings() {
  try {
    const res = await fetch("/settings");
    const settings = await res.json();

    if (settings && !settings.error) {
      userSettings = { ...userSettings, ...settings };
    } else {
      // Load from localStorage as fallback
      const saved = localStorage.getItem("fitcoach-settings");
      if (saved) {
        userSettings = { ...userSettings, ...JSON.parse(saved) };
      }
    }

    applySettingsToUI();
    console.log("✅ Settings loaded:", userSettings);
  } catch (error) {
    console.error("Error loading settings:", error);
    // Load from localStorage as fallback
    const saved = localStorage.getItem("fitcoach-settings");
    if (saved) {
      userSettings = { ...userSettings, ...JSON.parse(saved) };
      applySettingsToUI();
    }
  }
}

// Apply settings that have immediate effects
function applySettingsImmediately() {
  // Dark mode
  if (userSettings.dark_mode) {
    document.body.classList.add("dark-mode");
  } else {
    document.body.classList.remove("dark-mode");
  }

  // Update UI based on units
  updateUnitsDisplay();

  console.log("🔧 Settings applied:", userSettings);
}

// Convert units for display (you can expand this as needed)
function convertUnits(value, fromUnit, toUnit) {
  if (fromUnit === toUnit) return value;

  if (fromUnit === "cm" && toUnit === "inches") {
    return (value / 2.54).toFixed(1);
  } else if (fromUnit === "inches" && toUnit === "cm") {
    return (value * 2.54).toFixed(1);
  } else if (fromUnit === "kg" && toUnit === "lbs") {
    return (value * 2.20462).toFixed(1);
  } else if (fromUnit === "lbs" && toUnit === "kg") {
    return (value / 2.20462).toFixed(1);
  }

  return value;
}

// Update the profile saving to handle units
async function saveProfile() {
  const profileData = {
    age: document.getElementById("profile-age").value,
    gender: document.getElementById("profile-gender").value,
    height: document.getElementById("profile-height").value,
    weight: document.getElementById("profile-weight").value,
    goal: document.getElementById("profile-goal").value,
    activity: document.getElementById("profile-activity").value,
    diet: document.getElementById("profile-diet").value,
    medical: document.getElementById("profile-medical").value,
  };

  // Show loading state
  const saveBtn = document.querySelector(".new-chat-btn");
  const originalText = saveBtn.textContent;
  saveBtn.textContent = "💾 Updating AI Assistant...";
  saveBtn.disabled = true;

  try {
    // Send profile to backend to update RAGFlow assistant
    const res = await fetch("/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profileData),
    });

    const result = await res.json();

    if (result.success) {
      // Also save to localStorage so we can repopulate the form later
      localStorage.setItem("fitcoach-profile", JSON.stringify(profileData));
      userProfile = profileData;

      closeProfile();
      showToast("💪 " + result.message, "success");
    } else {
      showToast("❌ " + (result.error || "Failed to update profile"), "error");
    }
  } catch (error) {
    console.error("Error saving profile:", error);
    showToast("❌ Network error saving profile", "error");
  } finally {
    // Restore button state
    saveBtn.textContent = originalText;
    saveBtn.disabled = false;
  }
}

// Update settings modal to include save button
// Add this to your settings modal HTML (replace the current content):
function updateSettingsModal() {
  const settingsModal = document.getElementById("settings-modal");
  settingsModal.querySelector(".modal-content").innerHTML += `
        <button class="new-chat-btn" style="margin-top: 20px; width: 100%;" onclick="saveSettings()">
            💾 Save Settings
        </button>
    `;
}

// Settings management
let userSettings = {
  coaching_style: "motivational",
  detail_level: "moderate",
  units: "metric",
  dark_mode: false,
  auto_speak: false,
  reminders: false,
  show_calories: true,
};

// Load both settings and profile
async function loadUserData() {
  try {
    const res = await fetch("/user-data");
    const data = await res.json();

    if (data && !data.error) {
      if (data.profile) {
        userProfile = data.profile;
        applyProfileToForm();
      }
      if (data.settings) {
        userSettings = { ...userSettings, ...data.settings };
        applySettingsToUI();
      }
    } else {
      // Fallback to localStorage
      await loadFromLocalStorage();
    }

    console.log("✅ User data loaded:", {
      profile: userProfile,
      settings: userSettings,
    });
  } catch (error) {
    console.error("Error loading user data:", error);
    // Fallback to localStorage
    await loadFromLocalStorage();
  }
}

// Load from localStorage as fallback
async function loadFromLocalStorage() {
  const savedProfile = localStorage.getItem("fitcoach-profile");
  const savedSettings = localStorage.getItem("fitcoach-settings");

  if (savedProfile) {
    userProfile = JSON.parse(savedProfile);
    applyProfileToForm();
  }
  if (savedSettings) {
    userSettings = { ...userSettings, ...JSON.parse(savedSettings) };
    applySettingsToUI();
  }
}

// Apply profile data to form
function applyProfileToForm() {
  document.getElementById("profile-age").value = userProfile.age || "";
  document.getElementById("profile-gender").value = userProfile.gender || "";
  document.getElementById("profile-height").value = userProfile.height || "";
  document.getElementById("profile-weight").value = userProfile.weight || "";
  document.getElementById("profile-goal").value = userProfile.goal || "";
  document.getElementById("profile-activity").value =
    userProfile.activity || "";
  document.getElementById("profile-diet").value = userProfile.diet || "";
  document.getElementById("profile-medical").value = userProfile.medical || "";
}

// Save settings
async function saveSettings() {
  try {
    // Get current values from UI
    userSettings.coaching_style =
      document.getElementById("coaching-style").value;
    userSettings.detail_level = document.getElementById("detail-level").value;
    userSettings.units = document.getElementById("units").value;
    userSettings.dark_mode =
      document.getElementById("dark-mode-toggle").checked;
    userSettings.auto_speak =
      document.getElementById("auto-speak-toggle").checked;
    userSettings.reminders =
      document.getElementById("reminders-toggle").checked;
    userSettings.show_calories =
      document.getElementById("calories-toggle").checked;

    // Save to backend
    const res = await fetch("/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...userSettings,
        profile_data: userProfile, // Include profile data in the request
      }),
    });

    const result = await res.json();

    if (result.success) {
      // Also save to localStorage as backup
      localStorage.setItem("fitcoach-settings", JSON.stringify(userSettings));
      closeSettings();
      showToast("⚙️ " + result.message, "success");

      // Apply immediate UI changes
      applySettingsImmediately();
    } else {
      showToast("❌ " + (result.error || "Failed to save settings"), "error");
    }
  } catch (error) {
    console.error("Error saving settings:", error);
    showToast("❌ Network error saving settings", "error");
  }
}

// Apply settings to UI elements
function applySettingsToUI() {
  // Set dropdown values
  if (document.getElementById("coaching-style")) {
    document.getElementById("coaching-style").value =
      userSettings.coaching_style;
  }
  if (document.getElementById("detail-level")) {
    document.getElementById("detail-level").value = userSettings.detail_level;
  }
  if (document.getElementById("units")) {
    document.getElementById("units").value = userSettings.units;
  }

  // Set toggle states
  if (document.getElementById("dark-mode-toggle")) {
    document.getElementById("dark-mode-toggle").checked =
      userSettings.dark_mode;
  }
  if (document.getElementById("auto-speak-toggle")) {
    document.getElementById("auto-speak-toggle").checked =
      userSettings.auto_speak;
  }
  if (document.getElementById("reminders-toggle")) {
    document.getElementById("reminders-toggle").checked =
      userSettings.reminders;
  }
  if (document.getElementById("calories-toggle")) {
    document.getElementById("calories-toggle").checked =
      userSettings.show_calories;
  }

  // Apply immediate effects
  applySettingsImmediately();
}

// Update display based on units
function updateUnitsDisplay() {
  const units = userSettings.units;

  // Update profile form labels
  const heightLabel = document.querySelector('label[for="profile-height"]');
  const weightLabel = document.querySelector('label[for="profile-weight"]');

  if (heightLabel) {
    heightLabel.textContent = `Height (${
      units === "metric" ? "cm" : "inches"
    })`;
  }
  if (weightLabel) {
    weightLabel.textContent = `Weight (${units === "metric" ? "kg" : "lbs"})`;
  }
}

// Update the initialization
document.addEventListener("DOMContentLoaded", () => {
  loadSessions();
  loadUserData(); // Replace loadProfile() and loadSettings() with this
  loadStats();
  initializeVoiceRecognition();

  // Auto-resize textarea
  const textarea = document.getElementById("user-input");
  textarea.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = this.scrollHeight + "px";
  });

  // Search conversations
  document
    .getElementById("search-conversations")
    .addEventListener("input", filterConversations);

  // File upload
  document.getElementById("file-input").addEventListener("change", handleFiles);
});

// Initialize settings when page loads
document.addEventListener("DOMContentLoaded", () => {
  loadSessions();
  loadProfile();
  loadSettings(); // Add this line
  loadStats();
  initializeVoiceRecognition();

  // Auto-resize textarea
  const textarea = document.getElementById("user-input");
  textarea.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = this.scrollHeight + "px";
  });

  // Search conversations
  document
    .getElementById("search-conversations")
    .addEventListener("input", filterConversations);

  // File upload
  document.getElementById("file-input").addEventListener("change", handleFiles);
});

// File upload
function handleFiles(e) {
  const files = Array.from(e.target.files);
  const filesContainer = document.getElementById("uploaded-files");

  files.forEach((file) => {
    uploadedFiles.push(file);

    const chip = document.createElement("div");
    chip.className = "file-chip";
    chip.style.cssText = `
          display: inline-flex;
          align-items: center;
          gap: 8px;
          background: var(--bg-light);
          border: 1px solid var(--border);
          padding: 6px 12px;
          border-radius: 20px;
          font-size: 13px;
          margin-right: 8px;
          margin-bottom: 8px;
        `;
    chip.innerHTML = `
          📎 ${file.name}
          <button onclick="removeFile('${file.name}')" style="background: none; border: none; color: var(--error); cursor: pointer; font-weight: bold;">×</button>
        `;
    filesContainer.appendChild(chip);
  });

  showToast(`📎 ${files.length} file(s) attached`, "success");
}

function removeFile(fileName) {
  uploadedFiles = uploadedFiles.filter((f) => f.name !== fileName);
  const filesContainer = document.getElementById("uploaded-files");
  const chips = Array.from(filesContainer.children);
  chips.forEach((chip) => {
    if (chip.textContent.includes(fileName)) {
      chip.remove();
    }
  });
}

// Voice recognition
function initializeVoiceRecognition() {
  if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      document.getElementById("user-input").value = transcript;
      document.getElementById("voice-btn").classList.remove("recording");
    };

    recognition.onerror = () => {
      document.getElementById("voice-btn").classList.remove("recording");
      showToast("❌ Voice recognition error", "error");
    };

    recognition.onend = () => {
      document.getElementById("voice-btn").classList.remove("recording");
    };
  }
}

function toggleVoiceInput() {
  if (!recognition) {
    showToast("❌ Voice input not supported", "error");
    return;
  }

  const voiceBtn = document.getElementById("voice-btn");

  if (voiceBtn.classList.contains("recording")) {
    recognition.stop();
    voiceBtn.classList.remove("recording");
  } else {
    recognition.start();
    voiceBtn.classList.add("recording");
    showToast("🎤 Listening...", "success");
  }
}

// Toast notification
function showToast(message, type = "success") {
  const toast = document.getElementById("toast");
  const toastMessage = document.getElementById("toast-message");
  const toastIcon = document.getElementById("toast-icon");

  toastIcon.textContent = type === "success" ? "✅" : "❌";
  toastMessage.textContent = message;
  toast.className = `toast ${type} active`;

  setTimeout(() => {
    toast.classList.remove("active");
  }, 3000);
}

// Click outside modal to close
window.onclick = function (event) {
  const settingsModal = document.getElementById("settings-modal");
  const profileModal = document.getElementById("profile-modal");

  if (event.target === settingsModal) {
    closeSettings();
  }
  if (event.target === profileModal) {
    closeProfile();
  }
};

var progressChart; // Store chart instance

async function showProgressChart() {
  const chartDiv = document.getElementById("progress-chart");

  // Show the chart container
  chartDiv.style.display = "block";

  // If echarts not loaded for some reason, load it dynamically and retry
  if (typeof echarts === "undefined") {
    // Provide user feedback and load library
    showToast("Loading chart library...", "success");
    const script = document.createElement("script");
    script.src =
      "https://cdn.jsdelivr.net/npm/echarts@5.4.2/dist/echarts.min.js";
    script.onload = () => {
      // retry after library loads
      setTimeout(() => showProgressChart(), 50);
    };
    script.onerror = () =>
      showToast("❌ Failed to load chart library", "error");
    document.head.appendChild(script);
    return;
  }

  // Ensure echarts is available
  if (typeof echarts === "undefined") {
    showToast("❌ Chart library not available", "error");
    return;
  }

  // Initialize chart once
  if (!progressChart) {
    try {
      progressChart = echarts.init(chartDiv);
    } catch (err) {
      console.error("Error initializing chart instance:", err);
      showToast("❌ Error initializing chart", "error");
      return;
    }
  } else {
    try {
      progressChart.clear();
    } catch (e) {
      /* ignore */
    }
  }

  // Try to load workout stats JSON from a few likely paths
  const candidates = [
    "/workout_stats/default_user_workout_stats.json",
    "./workout_stats/default_user_workout_stats.json",
    "workout_stats/default_user_workout_stats.json",
  ];

  let stats = null;
  for (const url of candidates) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      stats = await res.json();
      break;
    } catch (err) {
      // try next
    }
  }

  // Build chart data
  let dates = [];
  let counts = [];
  let avgWeights = [];

  if (stats && Array.isArray(stats.workouts) && stats.workouts.length > 0) {
    const workouts = stats.workouts;
    const dateMap = {}; // date -> { count, weights: [] }

    workouts.forEach((w) => {
      const date =
        w.workout_date ||
        (w.create_date ? w.create_date.split(" ")[0] : null) ||
        (w.create_time
          ? new Date(w.create_time).toISOString().split("T")[0]
          : null);
      if (!date) return;
      if (!dateMap[date]) dateMap[date] = { count: 0, weights: [] };
      dateMap[date].count += 1;
      if (
        w.weight !== null &&
        w.weight !== undefined &&
        !isNaN(Number(w.weight))
      ) {
        dateMap[date].weights.push(Number(w.weight));
      }
    });

    // Sort dates ascending
    dates = Object.keys(dateMap).sort((a, b) => new Date(a) - new Date(b));
    counts = dates.map((d) => dateMap[d].count);
    avgWeights = dates.map((d) => {
      const arr = dateMap[d].weights;
      if (!arr || arr.length === 0) return null;
      const sum = arr.reduce((s, v) => s + v, 0);
      return +(sum / arr.length).toFixed(2);
    });
  }

  // If no real data found, fallback to sample weekly data
  if (!dates.length) {
    dates = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    counts = [1, 2, 1, 3, 1, 2, 1];
    avgWeights = [25, 27, 26, 28, 26, 30, 29];
  }

  // Prepare series
  const series = [
    {
      name: "Workouts",
      type: "bar",
      data: counts,
      itemStyle: { color: "#5470C6" },
      yAxisIndex: 0,
    },
  ];

  // Only include weight series if we have numeric values
  const hasWeights = avgWeights.some((v) => v !== null && v !== undefined);
  if (hasWeights) {
    series.push({
      name: "Avg Weight (kg)",
      type: "line",
      data: avgWeights.map((v) => (v === null ? "-" : v)),
      smooth: true,
      yAxisIndex: 1,
      itemStyle: { color: "#91CC75" },
    });
  }

  const option = {
    title: { text: "Workout Progress", left: "center" },
    tooltip: { trigger: "axis" },
    legend: { top: 30 },
    xAxis: { type: "category", data: dates },
    yAxis: [
      { type: "value", name: "Workouts" },
      { type: "value", name: "Weight (kg)", position: "right", offset: 0 },
    ],
    series,
  };

  try {
    progressChart.setOption(option);
    progressChart.resize();
    showToast("📈 Progress chart updated", "success");
  } catch (err) {
    console.error("Error setting chart option:", err);
    showToast("❌ Error rendering chart", "error");
  }

  // Scroll chat-box to chart
  chartDiv.scrollIntoView({ behavior: "smooth" });
}
