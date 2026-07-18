let currentWs = null;
let currentOrderId = null;

const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
// IMPORTANT: Verify this is your exact Render URL (without https://)
const RENDER_HOST = "rto-guardian-backend.onrender.com";

const BACKEND_HTTP = isLocal ? "http://localhost:8080" : `https://${RENDER_HOST}`;
const BACKEND_WS = isLocal ? "ws://localhost:8080" : `wss://${RENDER_HOST}`;

const profiles = {
    low: { customer_name: "Ravi Kumar", address: "Flat 402, Block B, Prestige Residency, Outer Ring Road, Bangalore, Karnataka - 560103", user_history_rto_rate: 0.0, user_total_orders: 8, orders_in_last_7days: 1, order_value: 450, pincode_rto_rate: 0.1, payment_mode: "PREPAID" },
    medium: { customer_name: "Priya Sharma", address: "House no 12, Sector 4, New Delhi - 110022", user_history_rto_rate: 0.3, user_total_orders: 6, orders_in_last_7days: 2, order_value: 850, pincode_rto_rate: 0.4, payment_mode: "COD" },
    high: { customer_name: "Vayu", address: "House no 12, Sector 4, New Delhi", user_history_rto_rate: 0.5, user_total_orders: 5, orders_in_last_7days: 2, order_value: 2000, pincode_rto_rate: 0.4, payment_mode: "COD" }
};

function autofill(type) {
    const p = profiles[type];
    document.getElementById('customer_name').value = p.customer_name;
    document.getElementById('address').value = p.address;
    document.getElementById('user_history_rto_rate').value = p.user_history_rto_rate;
    document.getElementById('user_total_orders').value = p.user_total_orders;
    document.getElementById('orders_in_last_7days').value = p.orders_in_last_7days;
    document.getElementById('order_value').value = p.order_value;
    document.getElementById('pincode_rto_rate').value = p.pincode_rto_rate;
    document.getElementById('payment_mode').value = p.payment_mode;
}

function resetViews() {
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    document.getElementById('chat').innerHTML = '';
    document.getElementById('json-debug').style.display = 'none';
    if (currentWs) { currentWs.close(); currentWs = null; }
    document.getElementById('botAvatar').classList.remove('speaking');
    document.getElementById('userAvatar').classList.remove('user-speaking');
}

function setProgress(msg, bg = 'white', color = 'var(--text-gray)') {
    const p = document.getElementById('progress');
    p.innerText = msg;
    p.style.backgroundColor = bg;
    p.style.color = color;
    p.style.borderColor = color === 'var(--text-gray)' ? 'rgba(0,0,0,0.05)' : color;
}

async function processOrder() {
    resetViews();
    currentOrderId = "ORD-" + Math.floor(Math.random() * 10000);
    setProgress(`Orchestrating Order: ${currentOrderId}...`, '#f0f9ff', '#0369a1');

    const payload = {
        order_id: currentOrderId,
        customer_name: document.getElementById('customer_name').value,
        phone: "9999999999",
        address: document.getElementById('address').value,
        pincode: "110001",
        user_history_rto_rate: parseFloat(document.getElementById('user_history_rto_rate').value),
        user_total_orders: parseInt(document.getElementById('user_total_orders').value),
        orders_in_last_7days: parseInt(document.getElementById('orders_in_last_7days').value),
        order_value: parseFloat(document.getElementById('order_value').value),
        pincode_rto_rate: parseFloat(document.getElementById('pincode_rto_rate').value),
        payment_mode: document.getElementById('payment_mode').value
    };

    const debugEl = document.getElementById('json-debug');
    debugEl.style.display = 'block';
    debugEl.innerText = "// Request to Backend\n" + JSON.stringify(payload, null, 2);

    try {
        const res = await fetch(`${BACKEND_HTTP}/orders/process`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        debugEl.innerText += "\n\n// Response from Orchestrator\n" + JSON.stringify(data, null, 2);
        setProgress(`Risk: ${data.risk_score} | Tier: ${data.risk_tier} | Routed to: ${data.agent_type}`, '#fdf2f8', 'var(--meesho-pink)');

        if (data.agent_type === "auto_approve") {
            document.getElementById('auto-approve-view').classList.add('active');
        } else if (data.agent_type === "whatsapp") {
            document.getElementById('chat-view').classList.add('active');
            startChatAgent();
        } else if (data.agent_type === "voice_call") {
            document.getElementById('voice-view').classList.add('active');
            const statusEl = document.getElementById('voice-status');
            statusEl.innerText = "Ready. Tap Connect to Call.";
            statusEl.style.color = "#a7f3d0";
        }
    } catch (err) {
        setProgress(`Connection Error: ${err.message}`, '#fef2f2', '#ef4444');
    }
}

function startChatAgent() {
    const chat = document.getElementById("chat");
    currentWs = new WebSocket(`${BACKEND_WS}/ws/chat/${currentOrderId}`);

    currentWs.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const typing = document.getElementById("typing");
        if (typing) typing.remove();

        if (data.type === "typing") {
            chat.innerHTML += `<div id="typing" class="typing">Typing...</div>`;
        } else if (data.error) {
            chat.innerHTML += `<div class="msg system">[Error: ${data.error}]</div>`;
        } else if (data.type === "message") {
            chat.innerHTML += `<div class="msg bot">${data.text}</div>`;
            if (data.buttons) {
                let btnHtml = `<div class="button-container">`;
                data.buttons.forEach(b => {
                    btnHtml += `<button class="chat-btn" onclick="sendChatReply('${b.id}', '${b.label}', this)">${b.label}</button>`;
                });
                btnHtml += `</div>`;
                chat.innerHTML += btnHtml;
            }
        } else if (data.type === "outcome") {
            chat.innerHTML += `<div class="msg bot" style="background:#e0f2fe; border: 1px solid #7dd3fc; text-align:center;">Final Outcome: <b>${data.outcome}</b></div>`;
        }
        chat.scrollTop = chat.scrollHeight;
    };
}

window.sendChatReply = function (id, label, btnEl) {
    btnEl.parentElement.remove();
    document.getElementById("chat").innerHTML += `<div class="msg user">${label}</div>`;
    if (currentWs) currentWs.send(JSON.stringify({ action: id }));
}

let mediaRecorder;
let audioChunks = [];
let voiceTranscript = null;

function addVoiceMessage(type, text, state = null) {
    if (!voiceTranscript) {
        voiceTranscript = document.getElementById('voice-transcript');
        voiceTranscript.innerHTML = '';
    }

    const msgDiv = document.createElement('div');
    msgDiv.className = `voice-message ${type}`;

    let icon = '';
    if (type === 'bot') icon = '🤖 ';
    else if (type === 'user') icon = '👤 ';

    msgDiv.innerHTML = icon + text;

    if (state) {
        const stateSpan = document.createElement('span');
        stateSpan.className = 'voice-state';
        stateSpan.textContent = state;
        msgDiv.appendChild(stateSpan);
    }

    voiceTranscript.appendChild(msgDiv);
    voiceTranscript.scrollTop = voiceTranscript.scrollHeight;
}

async function connectVoice() {
    const statusEl = document.getElementById('voice-status');
    const connectBtn = document.getElementById('connectBtn');
    const speakBtn = document.getElementById('speakBtn');
    const botAvatar = document.getElementById('botAvatar');
    const userAvatar = document.getElementById('userAvatar');
    voiceTranscript = document.getElementById('voice-transcript');

    statusEl.innerText = "Connecting...";
    addVoiceMessage('system', 'Establishing secure WebRTC channel...');

    currentWs = new WebSocket(`${BACKEND_WS}/ws/voice/${currentOrderId}`);
    currentWs.binaryType = "blob";

    currentWs.onopen = async () => {
        statusEl.innerText = "Connected";
        statusEl.style.color = "#34d399";
        addVoiceMessage('system', 'Call connected. Awaiting AI greeting.');
        connectBtn.style.display = "none";

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                statusEl.innerText = "Processing...";
                currentWs.send(audioBlob);
                audioChunks = [];
            };

            speakBtn.disabled = false;
            speakBtn.classList.add('active');
        } catch (err) {
            addVoiceMessage('system', `Mic error: ${err.message}`);
            statusEl.innerText = "Mic Denied";
            statusEl.style.color = "#f87171";
        }
    };

    currentWs.onmessage = async (event) => {
        if (typeof event.data === 'string') {
            const data = JSON.parse(event.data);

            if (data.type === 'state') {
                if (data.state) addVoiceMessage('system', data.message, data.state);
            } else if (data.type === 'bot_message') {
                addVoiceMessage('bot', data.text, data.state);
                botAvatar.classList.add('speaking');
                statusEl.innerText = "AI is speaking...";
            } else if (data.type === 'user_message') {
                addVoiceMessage('user', data.text, data.state);
            } else if (data.type === 'call_ended') {
                statusEl.innerText = `Call Ended: ${data.outcome}`;
                statusEl.style.color = "#9ca3af";
                addVoiceMessage('system', `Call terminated. Outcome: ${data.outcome}`);
                speakBtn.disabled = true;
                speakBtn.classList.remove('active');
                botAvatar.classList.remove('speaking');
                userAvatar.classList.remove('user-speaking');
                connectBtn.style.display = "flex";
                connectBtn.innerHTML = "📞";
            }
        }
        else if (event.data instanceof Blob) {
            botAvatar.classList.add('speaking');
            statusEl.innerText = "AI is speaking...";

            const audioBlob = event.data;
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);

            audio.onended = () => {
                botAvatar.classList.remove('speaking');
                statusEl.innerText = "Tap 🎤 to speak";
            };
            await audio.play();
        }
    };

    currentWs.onclose = () => {
        if (!statusEl.innerText.includes('Call Ended')) {
            statusEl.innerText = "Disconnected";
            statusEl.style.color = "#f87171";
            addVoiceMessage('system', 'Connection lost.');
        }
        speakBtn.disabled = true;
        speakBtn.classList.remove('active', 'recording');
        botAvatar.classList.remove('speaking');
        userAvatar.classList.remove('user-speaking');
        connectBtn.style.display = "flex";
    };

    speakBtn.onclick = () => {
        if (!mediaRecorder) return;

        if (mediaRecorder.state === "inactive") {
            // Start Recording
            mediaRecorder.start();
            speakBtn.classList.add('recording');
            userAvatar.classList.add('user-speaking');
            statusEl.innerText = "Recording... (Tap to stop)";
        } else if (mediaRecorder.state === "recording") {
            // Stop Recording
            mediaRecorder.stop();
            speakBtn.classList.remove('recording');
            userAvatar.classList.remove('user-speaking');
            statusEl.innerText = "Sending audio...";
        }
    };
}