// let activeSessionId = null;
// let renamedOnce = false;
// let recognition = null;
// let uploadedFiles = [];
// let userProfile = {};
//
// // Initialize - THIS IS THE KEY CHANGE
// document.addEventListener("DOMContentLoaded", async () => {
//   await loadCurrentSession(); // Load active session FIRST
//   await loadSessions(); // Then load session list
//   loadProfile();
//   loadStats();
//   initializeVoiceRecognition();
//
//   const textarea = document.getElementById('user-input');
//   textarea.addEventListener('input', function() {
//     this.style.height = 'auto';
//     this.style.height = this.scrollHeight + 'px';
//   });
//
//   document.getElementById('search-conversations').addEventListener('input', filterConversations);
//   document.getElementById('file-input').addEventListener('change', handleFiles);
// });
//
// // NEW FUNCTION: Load current active session on page load
// async function loadCurrentSession() {
//   try {
//     const res = await fetch("/current-session");
//     const data = await res.json();
//
//     if (data.active_session) {
//       activeSessionId = data.active_session;
//       console.log('Restored active session:', activeSessionId);
//
//       // Update title
//       document.getElementById("chat-title").textContent =
//         "💪 " + (data.session_name || "FitCoach AI");
//
//       // Load messages
//       const chatBox = document.getElementById("chat-box");
//       chatBox.innerHTML = "";
//
//       if (data.messages && data.messages.length > 0) {
//         renamedOnce = true; // Session has messages, so it's been renamed
//         data.messages.forEach(m => {
//           displayMessage(m.content, m.role === "user" ? "user" : "assistant");
//         });
//       } else {
//         // Show empty state
//         chatBox.innerHTML = `
//           <div class="empty-state">
//             <div class="empty-state-icon">💪</div>
//             <h3>Welcome to FitCoach AI!</h3>
//             <p>Your personal health and sports coach powered by RAGflow. I'm here to help you with workout plans, nutrition advice, form checks, progress tracking, and achieving your fitness goals. Let's start your journey to a healthier you!</p>
//           </div>
//         `;
//       }
//
//       chatBox.scrollTop = chatBox.scrollHeight;
//     } else {
//       console.log('No active session found');
//     }
//   } catch (err) {
//     console.error('Error loading current session:', err);
//   }
// }
//
// // Load user profile
// function loadProfile() {
//   const saved = localStorage.getItem('fitcoach-profile');
//   if (saved) {
//     userProfile = JSON.parse(saved);
//     document.getElementById('profile-age').value = userProfile.age || '';
//     document.getElementById('profile-gender').value = userProfile.gender || '';
//     document.getElementById('profile-height').value = userProfile.height || '';
//     document.getElementById('profile-weight').value = userProfile.weight || '';
//     document.getElementById('profile-goal').value = userProfile.goal || '';
//     document.getElementById('profile-activity').value = userProfile.activity || '';
//     document.getElementById('profile-diet').value = userProfile.diet || '';
//     document.getElementById('profile-medical').value = userProfile.medical || '';
//   }
// }
//
// function saveProfile() {
//   userProfile = {
//     age: document.getElementById('profile-age').value,
//     gender: document.getElementById('profile-gender').value,
//     height: document.getElementById('profile-height').value,
//     weight: document.getElementById('profile-weight').value,
//     goal: document.getElementById('profile-goal').value,
//     activity: document.getElementById('profile-activity').value,
//     diet: document.getElementById('profile-diet').value,
//     medical: document.getElementById('profile-medical').value
//   };
//
//   localStorage.setItem('fitcoach-profile', JSON.stringify(userProfile));
//   closeProfile();
//   showToast('💾 Profile saved successfully!', 'success');
// }
//
// function loadStats() {
//   const stats = JSON.parse(localStorage.getItem('fitcoach-stats') || '{"sessionsToday": 0, "totalWorkouts": 0, "streakDays": 0}');
//   document.getElementById('sessions-today').textContent = stats.sessionsToday;
//   document.getElementById('total-workouts').textContent = stats.totalWorkouts;
//   document.getElementById('streak-days').textContent = stats.streakDays + ' days';
// }
//
// function updateStats() {
//   const stats = JSON.parse(localStorage.getItem('fitcoach-stats') || '{"sessionsToday": 0, "totalWorkouts": 0, "streakDays": 0}');
//   stats.sessionsToday += 1;
//   stats.totalWorkouts += 1;
//
//   const lastSession = localStorage.getItem('last-session-date');
//   const today = new Date().toDateString();
//
//   if (lastSession === today) {
//     // Same day
//   } else if (lastSession === new Date(Date.now() - 86400000).toDateString()) {
//     stats.streakDays += 1;
//   } else {
//     stats.streakDays = 1;
//   }
//
//   localStorage.setItem('last-session-date', today);
//   localStorage.setItem('fitcoach-stats', JSON.stringify(stats));
//   loadStats();
// }
//
// function filterConversations() {
//   const search = document.getElementById('search-conversations').value.toLowerCase();
//   const conversations = document.querySelectorAll('#conversation-list li');
//
//   conversations.forEach(conv => {
//     const text = conv.textContent.toLowerCase();
//     conv.style.display = text.includes(search) ? 'block' : 'none';
//   });
// }
//
// async function loadSessions() {
//   const res = await fetch("/sessions");
//   const sessions = await res.json();
//
//   const list = document.getElementById("conversation-list");
//   list.innerHTML = "";
//
//   if (sessions.error) {
//     console.error("Error fetching sessions:", sessions.error);
//     return;
//   }
//
//   sessions.forEach(s => {
//     const li = document.createElement("li");
//     li.textContent = s.name || `Session ${s.id.slice(0, 6)}`;
//     li.onclick = async () => {
//       await activateSession(s.id);
//     };
//
//     if (s.id === activeSessionId) {
//       li.classList.add("active");
//     }
//
//     list.appendChild(li);
//   });
// }
//
// async function createNewConversation() {
//   const res = await fetch("/sessions", { method: "POST" });
//   const session = await res.json();
//   if (session.error) {
//     showToast("Error creating session", "error");
//     return;
//   }
//   await loadSessions();
//   await activateSession(session.id);
//   showToast("New coaching session started!", "success");
//   updateStats();
// }
//
// async function activateSession(id) {
//       try {
//         // 1. Activate the session on the backend
//         await fetch(`/sessions/${id}/activate`, { method: "POST" });
//         activeSessionId = id;
//
//         // 2. Fetch the session's messages and name
//         const msgRes = await fetch(`/sessions/${id}/messages`);
//         const messagesData = await msgRes.json();
//
//         if (messagesData.error) {
//           console.error("Error fetching messages:", messagesData.error);
//           showToast(messagesData.error, "error");
//           return;
//         }
//
//         // 3. Update the chat title
//         document.getElementById("chat-title").textContent =
//           "💪 " + (messagesData.session_name || "FitCoach AI");
//
//         // 4. Get the messages array safely
//         const messages = messagesData.messages || [];
//         renamedOnce = messages.length > 0;
//
//         const chatBox = document.getElementById("chat-box");
//         chatBox.innerHTML = "";
//
//         // 5. Display messages or the empty state
//         if (messages.length === 0) {
//           chatBox.innerHTML = `
//             <div class="empty-state">
//               <div class="empty-state-icon">💪</div>
//               <h3>Welcome to FitCoach AI!</h3>
//               <p>Your personal health and sports coach powered by RAGflow. I'm here to help you with workout plans, nutrition advice, form checks, progress tracking, and achieving your fitness goals. Let's start your journey to a healthier you!</p>
//             </div>
//           `;
//         } else {
//           messages.forEach(m => {
//             if (m && m.content) {
//               displayMessage(m.content, m.role === "user" ? "user" : "assistant");
//             }
//           });
//         }
//
//         chatBox.scrollTop = chatBox.scrollHeight;
//
//         // 6. Refresh the session list to highlight the active one
//         await loadSessions();
//
//       } catch (err) {
//         console.error("Failed to activate session:", err);
//         showToast("Could not switch conversations.", "error");
//       }
//     }
//
// function sanitizeMessageContent(content) {
//   if (!content || typeof content !== "string") return "";
//   if (content.startsWith("`") && content.endsWith("`")) {
//     return content.slice(1, -1);
//   }
//   return content;
// }
//
// function displayMessage(content, role) {
//   const chatBox = document.getElementById("chat-box");
//
//   const emptyState = chatBox.querySelector('.empty-state');
//   if (emptyState) {
//     emptyState.remove();
//   }
//
//   const div = document.createElement("div");
//   div.classList.add("message", role);
//
//   const now = new Date();
//   const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
//
//   // ✅ Ensure content is sanitized and converted to a string
//   const safeContent = sanitizeMessageContent(String(content));
//
//   div.innerHTML = `
//     <div class="message-content-wrapper">
//       ${marked.parse(safeContent)}
//     </div>
//     <span class="message-timestamp">${time}</span>
//     <div class="message-actions">
//       <button onclick="copyMessage(this)" title="Copy">📋</button>
//       <button onclick="speakMessage(this)" title="Speak">🔊</button>
//       ${role === 'assistant' ? '<button onclick="regenerateMessage(this)" title="Regenerate">🔄</button>' : ''}
//     </div>
//   `;
//
//   chatBox.appendChild(div);
//
//   // Highlight code blocks if present
//   div.querySelectorAll('pre code').forEach((block) => {
//     if (typeof hljs !== 'undefined') {
//       hljs.highlightElement(block);
//     }
//   });
//
//   return div;
// }
//
//
// function copyMessage(btn) {
//   const message = btn.closest('.message');
//   const text = message.textContent.replace(/📋🔊🔄\d{1,2}:\d{2}\s[AP]M/g, '').trim();
//   navigator.clipboard.writeText(text);
//   showToast("Message copied!", "success");
// }
//
// function speakMessage(btn) {
//   const message = btn.closest('.message');
//   const text = message.textContent.replace(/📋🔊🔄\d{1,2}:\d{2}\s[AP]M/g, '').trim();
//
//   if ('speechSynthesis' in window) {
//     const utterance = new SpeechSynthesisUtterance(text);
//     speechSynthesis.speak(utterance);
//     showToast("Speaking...", "success");
//   } else {
//     showToast("Speech not supported", "error");
//   }
// }
//
// async function regenerateMessage(btn) {
//   const message = btn.closest('.message');
//   const prevMessage = message.previousElementSibling;
//
//   if (prevMessage && prevMessage.classList.contains('user')) {
//     const userText = prevMessage.textContent.replace(/📋🔊🔄\d{1,2}:\d{2}\s[AP]M/g, '').trim();
//     message.remove();
//     await sendMessageWithText(userText);
//   }
// }
//
// async function renameSession(sessionId, newName) {
//   try {
//     const res = await fetch(`/sessions/${sessionId}/rename`, {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ name: newName })
//     });
//
//     const responseText = await res.text();
//
//     if (!res.ok) {
//       throw new Error(`HTTP ${res.status}: ${responseText}`);
//     }
//
//     const updated = JSON.parse(responseText);
//
//     if (updated.error) {
//       throw new Error(updated.error);
//     }
//
//     document.getElementById("chat-title").textContent = "💪 " + updated.name;
//     await loadSessions();
//     return true;
//
//   } catch (err) {
//     console.error("Rename error:", err);
//     return false;
//   }
// }
//
// async function sendMessage() {
//   const input = document.getElementById("user-input");
//   const text = input.value.trim();
//   if (!text || !activeSessionId) {
//     if (!activeSessionId) {
//       showToast("Please start a new session first", "error");
//     }
//     return;
//   }
//
//   await sendMessageWithText(text);
//   input.value = "";
//   input.style.height = 'auto';
// }
//
// async function sendMessageWithText(text) {
//   const chatBox = document.getElementById("chat-box");
//   const isFirstMessage = !renamedOnce;
//
//   displayMessage(text, "user");
//
//   const spinnerDiv = document.createElement("div");
//   spinnerDiv.classList.add("message", "assistant", "waiting");
//   spinnerDiv.innerHTML = `
//     <span>Analyzing your request...</span>
//     <div class="spinner"></div>
//   `;
//   chatBox.appendChild(spinnerDiv);
//   chatBox.scrollTop = chatBox.scrollHeight;
//
//   // Capture the session ID at the time of the request to prevent race conditions
//   const sessionIdForRequest = activeSessionId;
//   const eventSource = new EventSource(`/ask?question=${encodeURIComponent(text)}&session_id=${sessionIdForRequest}`);
//
//   let fullText = "";
//   let aiDiv = null;
//
//   const handleStreamEnd = () => {
//       eventSource.close();
//
//       if (aiDiv && document.getElementById('auto-speak-toggle')?.checked) {
//           const textToSpeak = aiDiv.dataset.rawContent;
//           const utterance = new SpeechSynthesisUtterance(textToSpeak);
//           speechSynthesis.speak(utterance);
//       }
//
//       if (isFirstMessage) {
//           renamedOnce = true;
//           const newName = text.length > 30 ? text.slice(0, 30) + "…" : text;
//           // Use sessionIdForRequest to ensure you rename the correct session
//           renameSession(sessionIdForRequest, newName);
//       }
//   };
//
//   eventSource.onmessage = (event) => {
//     try {
//       const data = JSON.parse(event.data);
//
//       if (data.done) {
//         handleStreamEnd();
//         return;
//       }
//
//       if (data.error) {
//           throw new Error(data.error);
//       }
//
//       if (data.content) {
//         fullText += data.content;
//
//         if (!aiDiv) {
//           chatBox.removeChild(spinnerDiv);
//           aiDiv = displayMessage(fullText, "assistant");
//         } else {
//           // Update the existing message div instead of replacing innerHTML
//           aiDiv.dataset.rawContent = fullText; // Update raw content
//           const contentContainer = aiDiv.querySelector('.message-content-wrapper'); // Assuming you add a wrapper div
//           contentContainer.innerHTML = marked.parse(fullText);
//           // This is more efficient and preserves event listeners if you had any
//         }
//         chatBox.scrollTop = chatBox.scrollHeight;
//       }
//     } catch (err) {
//       console.error("Error processing stream:", err, "Raw data:", event.data);
//       // If an error occurs, we should also end the stream
//       handleStreamEnd();
//     }
//   };
//
//   eventSource.onerror = (err) => {
//     console.error("EventSource failed:", err);
//     eventSource.close();
//     chatBox.removeChild(spinnerDiv);
//     displayMessage("Sorry, an error occurred while connecting. Please check your connection and try again.", "assistant");
//   };
// }
//
// function usePrompt(text) {
//   document.getElementById('user-input').value = text;
//   document.getElementById('user-input').focus();
// }
//
// function insertEmoji(emoji) {
//   const input = document.getElementById('user-input');
//   input.value += emoji;
//   input.focus();
// }
//
// function toggleTheme() {
//   document.body.classList.toggle('dark-mode');
//   const isDark = document.body.classList.contains('dark-mode');
//   const toggle = document.getElementById('dark-mode-toggle');
//   if (toggle) toggle.checked = isDark;
//   localStorage.setItem('darkMode', isDark);
// }
//
// if (localStorage.getItem('darkMode') === 'true') {
//   document.body.classList.add('dark-mode');
//   const toggle = document.getElementById('dark-mode-toggle');
//   if (toggle) toggle.checked = true;
// }
//
// function toggleProfile() {
//   document.getElementById('profile-modal').classList.add('active');
// }
//
// function closeProfile() {
//   document.getElementById('profile-modal').classList.remove('active');
// }
//
// function toggleSettings() {
//   document.getElementById('settings-modal').classList.add('active');
// }
//
// function closeSettings() {
//   document.getElementById('settings-modal').classList.remove('active');
// }
//
// async function exportPlan() {
//   if (!activeSessionId) {
//     showToast("No active session to export", "error");
//     return;
//   }
//
//   const msgRes = await fetch(`/sessions/${activeSessionId}/messages`);
//   const data = await msgRes.json();
//   const messages = data.messages || data;
//
//   let markdown = `# FitCoach AI - Training Session Export\n\n`;
//   markdown += `**Date:** ${new Date().toLocaleDateString()}\n\n`;
//
//   if (userProfile.goal) {
//     markdown += `**Goal:** ${userProfile.goal}\n`;
//   }
//   if (userProfile.activity) {
//     markdown += `**Activity Level:** ${userProfile.activity}\n`;
//   }
//   markdown += `\n---\n\n`;
//
//   messages.forEach(m => {
//     markdown += `## ${m.role === 'user' ? '👤 You' : '💪 Coach'}\n${m.content}\n\n`;
//   });
//
//   const blob = new Blob([markdown], { type: 'text/markdown' });
//   const url = URL.createObjectURL(blob);
//   const a = document.createElement('a');
//   a.href = url;
//   a.download = `fitcoach-plan-${new Date().toISOString().split('T')[0]}.md`;
//   a.click();
//
//   showToast("Training plan exported!", "success");
// }
//
// function handleFiles(e) {
//   const files = Array.from(e.target.files);
//   const filesContainer = document.getElementById('uploaded-files');
//
//   files.forEach(file => {
//     uploadedFiles.push(file);
//
//     const chip = document.createElement('div');
//     chip.className = 'file-chip';
//     chip.style.cssText = `
//       display: inline-flex;
//       align-items: center;
//       gap: 8px;
//       background: var(--bg-light);
//       border: 1px solid var(--border);
//       padding: 6px 12px;
//       border-radius: 20px;
//       font-size: 13px;
//       margin-right: 8px;
//       margin-bottom: 8px;
//     `;
//     chip.innerHTML = `
//       📎 ${file.name}
//       <button onclick="removeFile('${file.name}')" style="background: none; border: none; color: var(--error); cursor: pointer; font-weight: bold;">×</button>
//     `;
//     filesContainer.appendChild(chip);
//   });
//
//   showToast(`${files.length} file(s) attached`, "success");
// }
//
// function removeFile(fileName) {
//   uploadedFiles = uploadedFiles.filter(f => f.name !== fileName);
//   const filesContainer = document.getElementById('uploaded-files');
//   const chips = Array.from(filesContainer.children);
//   chips.forEach(chip => {
//     if (chip.textContent.includes(fileName)) {
//       chip.remove();
//     }
//   });
// }
//
// function initializeVoiceRecognition() {
//   if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
//     const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
//     recognition = new SpeechRecognition();
//     recognition.continuous = false;
//     recognition.interimResults = false;
//
//     recognition.onresult = (event) => {
//       const transcript = event.results[0][0].transcript;
//       document.getElementById('user-input').value = transcript;
//       document.getElementById('voice-btn').classList.remove('recording');
//     };
//
//     recognition.onerror = () => {
//       document.getElementById('voice-btn').classList.remove('recording');
//       showToast("Voice recognition error", "error");
//     };
//
//     recognition.onend = () => {
//       document.getElementById('voice-btn').classList.remove('recording');
//     };
//   }
// }
//
// function toggleVoiceInput() {
//   if (!recognition) {
//     showToast("Voice input not supported", "error");
//     return;
//   }
//
//   const voiceBtn = document.getElementById('voice-btn');
//
//   if (voiceBtn.classList.contains('recording')) {
//     recognition.stop();
//     voiceBtn.classList.remove('recording');
//   } else {
//     recognition.start();
//     voiceBtn.classList.add('recording');
//     showToast("Listening...", "success");
//   }
// }
//
// function showToast(message, type = 'success') {
//   const toast = document.getElementById('toast');
//   const toastMessage = document.getElementById('toast-message');
//   const toastIcon = document.getElementById('toast-icon');
//
//   toastIcon.textContent = type === 'success' ? '✅' : '❌';
//   toastMessage.textContent = message;
//   toast.className = `toast ${type} active`;
//
//   setTimeout(() => {
//     toast.classList.remove('active');
//   }, 3000);
// }
//
// window.onclick = function(event) {
//   const settingsModal = document.getElementById('settings-modal');
//   const profileModal = document.getElementById('profile-modal');
//
//   if (event.target === settingsModal) {
//     closeSettings();
//   }
//   if (event.target === profileModal) {
//     closeProfile();
//   }
// }