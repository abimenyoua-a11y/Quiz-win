from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import time
import math

app = FastAPI(title="QuizWin ₹1 - Continuous Live Engine")

users_db = {}
rounds_db = {}  # round_id -> {"question": dict, "winners": list, "participants": set}

ROUND_DURATION = 30  # ஒவ்வொரு 30 வினாடிக்கும் ஒரு புதிய சுற்று

QUESTION_BANK = [
    {"q": "இந்தியாவின் தேசிய விலங்கு எது?", "options": ["புலி", "சிங்கம்", "மயில்", "யானை"], "answer": "புலி"},
    {"q": "சூரியனுக்கு மிக அருகில் உள்ள கோள் எது?", "options": ["செவ்வாய்", "புதன்", "வெள்ளி", "வியாழன்"], "answer": "புதன்"},
    {"q": "தமிழ்நாட்டின் தலைநகரம் எது?", "options": ["மதுரை", "கோயம்புத்தூர்", "சென்னை", "சேலம்"], "answer": "சென்னை"},
    {"q": "கணிதத்தின் தந்தை என அழைக்கப்படுபவர் யார்?", "options": ["ஆர்க்கிமிடிஸ்", "நியூட்டன்", "ஐன்ஸ்டீன்", "ராமனுஜன்"], "answer": "ஆர்க்கிமிடிஸ்"},
    {"q": "மகாபாரதத்தை எழுதியவர் யார்?", "options": ["வள்ளுவர்", "கம்பர்", "வியாசர்", "வால்மீகி"], "answer": "வியாசர்"},
    {"q": "உலகின் மிகப்பெரிய பெருங்கடல் எது?", "options": ["அட்லாண்டிக்", "இந்தியப் பெருங்கடல்", "பசிபிக்", "ஆர்க்டிக்"], "answer": "பசிபிக்"},
    {"q": "மனித உடலில் உள்ள எலும்புகளின் எண்ணிக்கை?", "options": ["206", "208", "210", "198"], "answer": "206"},
    {"q": "இந்தியாவின் சிலிக்கான் பள்ளத்தாக்கு எது?", "options": ["சென்னை", "ஹைதராபாத்", "பெங்களூரு", "மும்பை"], "answer": "பெங்களூரு"}
]

def get_current_round_info():
    now = time.time()
    round_id = int(now // ROUND_DURATION)
    elapsed = now % ROUND_DURATION
    remaining = round(ROUND_DURATION - elapsed, 1)
    q_index = round_id % len(QUESTION_BANK)
    
    if round_id not in rounds_db:
        rounds_db[round_id] = {
            "question": QUESTION_BANK[q_index],
            "winners": [],       # Top 10 fastest correct users
            "participants": set(),
            "submissions": {}    # uid -> {"correct": bool, "time": float, "rank": int}
        }
    return round_id, remaining, elapsed, rounds_db[round_id]

class LoginReq(BaseModel):
    uid: str
    name: str

class WalletReq(BaseModel):
    uid: str
    amount: float
    upi_id: str = ""

class JoinReq(BaseModel):
    uid: str

class AnswerReq(BaseModel):
    uid: str
    round_id: int
    answer: str

@app.post("/api/login")
def api_login(req: LoginReq):
    uid = req.uid.strip()
    if uid not in users_db:
        users_db[uid] = {"name": req.name.strip(), "wallet": 10.0, "history": []}
    return {"status": "ok", "user": users_db[uid], "uid": uid}

@app.get("/api/state")
def api_state(uid: str):
    round_id, remaining, elapsed, r_data = get_current_round_info()
    user = users_db.get(uid, {"name": "", "wallet": 0.0, "history": []})
    joined = uid in r_data["participants"]
    sub = r_data["submissions"].get(uid)
    
    return {
        "round_id": round_id,
        "remaining": remaining,
        "total_players": len(r_data["participants"]),
        "winners_count": len(r_data["winners"]),
        "winners_list": r_data["winners"],
        "joined": joined,
        "submitted": sub,
        "question": r_data["question"]["q"] if joined else "போட்டியில் இணைந்தால் கேள்வி தெரியும்",
        "options": r_data["question"]["options"] if joined else [],
        "correct_answer": r_data["question"]["answer"] if sub else None,
        "wallet": user["wallet"],
        "history": user["history"][:15]
    }

@app.post("/api/join")
def api_join(req: JoinReq):
    uid = req.uid
    if uid not in users_db:
        return {"status": "error", "msg": "பயனர் இல்லை"}
    round_id, remaining, elapsed, r_data = get_current_round_info()
    
    if remaining < 3.0:
        return {"status": "error", "msg": "இந்தச் சுற்று முடியப் போகிறது! அடுத்த சுற்றில் இணையவும்."}
    if uid in r_data["participants"]:
        return {"status": "ok", "round_id": round_id}
    if users_db[uid]["wallet"] < 1.0:
        return {"status": "error", "msg": "போதிய வாலட் இருப்பு இல்லை (₹1 தேவை)"}
        
    users_db[uid]["wallet"] -= 1.0
    users_db[uid]["history"].insert(0, f"🎮 சுற்று #{round_id} நுழைவுக் கட்டணம் -₹1")
    r_data["participants"].add(uid)
    return {"status": "ok", "round_id": round_id, "wallet": users_db[uid]["wallet"]}

@app.post("/api/answer")
def api_answer(req: AnswerReq):
    uid = req.uid
    round_id, remaining, elapsed, r_data = get_current_round_info()
    if req.round_id != round_id or uid not in r_data["participants"]:
        return {"status": "error", "msg": "நேரம் முடிந்துவிட்டது!"}
    if uid in r_data["submissions"]:
        return {"status": "ok", "sub": r_data["submissions"][uid]}
        
    is_correct = (req.answer == r_data["question"]["answer"])
    time_taken = round(elapsed, 2)
    rank = 0
    won = False
    
    if is_correct and len(r_data["winners"]) < 10:
        rank = len(r_data["winners"]) + 1
        won = True
        users_db[uid]["wallet"] += 2.0
        users_db[uid]["history"].insert(0, f"🏆 சுற்று #{round_id} வெற்றி (Rank #{rank}) +₹2.00")
        r_data["winners"].append({"rank": rank, "name": users_db[uid]["name"], "time": time_taken})
        
    sub_info = {"correct": is_correct, "time": time_taken, "rank": rank, "won": won}
    r_data["submissions"][uid] = sub_info
    return {"status": "ok", "sub": sub_info, "wallet": users_db[uid]["wallet"]}

@app.post("/api/wallet/add")
def api_add_wallet(req: WalletReq):
    if req.uid in users_db:
        users_db[req.uid]["wallet"] += req.amount
        users_db[req.uid]["history"].insert(0, f"💳 UPI டெபாசிட் +₹{req.amount}")
        return {"status": "ok", "wallet": users_db[req.uid]["wallet"]}
    return {"status": "error"}

@app.post("/api/wallet/withdraw")
def api_withdraw_wallet(req: WalletReq):
    if req.uid in users_db and users_db[req.uid]["wallet"] >= req.amount:
        users_db[req.uid]["wallet"] -= req.amount
        users_db[req.uid]["history"].insert(0, f"🏦 {req.upi_id} கணக்கிற்கு -₹{req.amount}")
        return {"status": "ok", "wallet": users_db[req.uid]["wallet"], "msg": f"₹{req.amount} அனுப்பப்பட்டது!"}
    return {"status": "error", "msg": "போதிய இருப்பு இல்லை"}

@app.get("/", response_class=HTMLResponse)
def mobile_app_ui():
    return """<!DOCTYPE html>
<html lang="ta">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#090d16">
    <meta name="mobile-web-app-capable" content="yes">
    <title>QuizWin ₹1 Live</title>
    <style>
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; -webkit-tap-highlight-color: transparent; user-select: none; }
        body { margin: 0; background: #05080f; color: #f8fafc; display: flex; justify-content: center; height: 100vh; overflow: hidden; }
        .app-shell { width: 100%; max-width: 430px; background: #0b1120; height: 100vh; display: flex; flex-direction: column; position: relative; }
        
        /* Top Bar */
        .header { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; background: #0f172a; border-bottom: 1px solid #1e293b; }
        .brand { display: flex; align-items: center; gap: 8px; font-weight: 800; font-size: 18px; color: #38bdf8; }
        .wallet-chip { background: linear-gradient(135deg, #f59e0b, #d97706); color: #090d16; padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 14px; cursor: pointer; box-shadow: 0 2px 10px rgba(245, 158, 11, 0.3); }
        
        /* Screens */
        .screen { flex: 1; overflow-y: auto; padding: 18px 18px 85px 18px; display: none; animation: fadeIn 0.2s ease; }
        .screen.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        
        /* Live Arena Card */
        .live-banner { background: linear-gradient(135deg, #1d4ed8, #6d28d9); border-radius: 18px; padding: 18px; position: relative; overflow: hidden; box-shadow: 0 10px 25px rgba(29, 78, 216, 0.35); margin-bottom: 16px; }
        .live-badge { display: inline-flex; align-items: center; gap: 6px; background: rgba(0,0,0,0.35); padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; color: #4ade80; }
        .pulse-dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%; animation: pulse 1s infinite; }
        @keyframes pulse { 0% { transform: scale(1); opacity: 1; } 100% { transform: scale(2); opacity: 0; } }
        
        .clock-ring { font-size: 36px; font-weight: 900; text-align: center; margin: 12px 0 4px 0; font-variant-numeric: tabular-nums; }
        .progress-track { width: 100%; height: 6px; background: rgba(255,255,255,0.2); border-radius: 4px; overflow: hidden; margin-bottom: 14px; }
        .progress-fill { height: 100%; background: #4ade80; width: 100%; transition: width 0.2s linear; }
        
        .live-stats { display: flex; justify-content: space-between; background: rgba(9, 13, 22, 0.45); padding: 10px 14px; border-radius: 12px; font-size: 12px; margin-bottom: 14px; }
        
        /* Buttons & Inputs */
        .btn-action { background: linear-gradient(to right, #10b981, #059669); color: white; border: none; padding: 15px; width: 100%; border-radius: 14px; font-size: 16px; font-weight: 800; cursor: pointer; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.35); transition: transform 0.1s; }
        .btn-action:active { transform: scale(0.96); }
        .btn-action:disabled { background: #334155; color: #94a3b8; box-shadow: none; }
        
        .opt-card { background: #1e293b; border: 2px solid #334155; color: white; padding: 14px 16px; width: 100%; border-radius: 14px; font-size: 16px; font-weight: 700; text-align: left; margin-bottom: 10px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
        .opt-card:active { transform: scale(0.98); border-color: #38bdf8; }
        .opt-correct { background: #065f46 !important; border-color: #10b981 !important; }
        .opt-wrong { background: #7f1d1d !important; border-color: #ef4444 !important; }
        
        .card { background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 16px; margin-bottom: 14px; }
        input { width: 100%; padding: 14px; margin: 8px 0; background: #1e293b; border: 1px solid #334155; color: white; border-radius: 12px; font-size: 15px; }
        
        /* Bottom Tab Bar */
        .tab-bar { position: absolute; bottom: 0; width: 100%; background: #0f172a; border-top: 1px solid #1e293b; display: flex; justify-content: space-around; padding: 10px 0 14px 0; }
        .tab { color: #64748b; text-align: center; font-size: 11px; font-weight: 700; cursor: pointer; flex: 1; }
        .tab span { display: block; font-size: 20px; margin-bottom: 2px; }
        .tab.active { color: #38bdf8; }
        
        .winner-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #1e293b; font-size: 13px; }
        .toast { position: fixed; top: 20px; background: #1e293b; border: 1px solid #38bdf8; color: white; padding: 10px 18px; border-radius: 20px; font-size: 13px; font-weight: 600; z-index: 999; display: none; box-shadow: 0 5px 20px rgba(0,0,0,0.5); }
    </style>
</head>
<body>

<div class="toast" id="toast"></div>

<div class="app-shell">
    <!-- Login Screen -->
    <div class="screen active" id="scr-login" style="padding-top: 50px;">
        <div style="text-align:center; margin-bottom: 30px;">
            <div style="font-size: 56px;">⚡</div>
            <h1 style="margin: 8px 0 4px 0; font-size: 28px; letter-spacing: -0.5px;">QuizWin ₹1</h1>
            <p style="color: #94a3b8; font-size: 14px;">ஒவ்வொரு 30 வினாடிக்கும் லைவ் போட்டி!<br>முதல் 10 வெற்றியாளர்களுக்கு உடனடி பரிசு</p>
        </div>
        <div class="card">
            <input type="text" id="inp-uid" placeholder="மொபைல் எண் (எ.கா: 9876543210)">
            <input type="text" id="inp-name" placeholder="உங்கள் பெயர்">
            <button class="btn-action" style="margin-top: 12px;" onclick="doLogin()">ஆப்பிற்குள் நுழையவும் →</button>
        </div>
    </div>

    <!-- App Top Header (Hidden on Login) -->
    <div class="header" id="app-header" style="display:none;">
        <div class="brand">⚡ QuizWin <span style="font-size:11px; background:#1e293b; padding:2px 6px; border-radius:6px; color:#4ade80;">LIVE</span></div>
        <div class="wallet-chip" onclick="switchTab('wallet')">₹<span id="hdr-wallet">0.00</span> +</div>
    </div>

    <!-- Home / Live Arena Screen -->
    <div class="screen" id="scr-home">
        <div class="live-banner">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="live-badge"><div class="pulse-dot"></div> 24x7 லைவ் சுற்று #<span id="lbl-round">0</span></div>
                <div style="font-size:12px; font-weight:700;">🏆 Top 10 பரிசு: ₹2</div>
            </div>
            
            <div class="clock-ring"><span id="lbl-timer">30.0</span>s</div>
            <div class="progress-track"><div class="progress-fill" id="timer-bar"></div></div>
            
            <div class="live-stats">
                <div>👥 விளையாடுபவர்கள்: <b id="lbl-players">0</b> (Unlimited)</div>
                <div>🏅 பரிசு வென்றோர்: <b id="lbl-winners">0</b> / 10</div>
            </div>

            <div id="join-box">
                <button class="btn-action" id="btn-join" onclick="joinRound()">🎮 ₹1 கட்டி இப்போதே இணையுங்கள்</button>
            </div>
        </div>

        <!-- Question & Options Area -->
        <div id="quiz-box" style="display:none;">
            <div class="card" style="border-color: #38bdf8;">
                <div style="font-size:11px; color:#38bdf8; font-weight:800; margin-bottom:6px;">⚡ வேகமாகப் பதிலளியுங்கள் (முதல் 10 பேருக்கு பரிசு)</div>
                <div style="font-size:18px; font-weight:800; line-height:1.4;" id="lbl-question"></div>
            </div>
            <div id="options-list"></div>
        </div>

        <!-- Live Top 10 Winners Leaderboard -->
        <div class="card">
            <div style="font-size:14px; font-weight:800; margin-bottom:8px; color:#facc15;">🏆 இந்தச் சுற்றின் முதல் 10 வெற்றியாளர்கள்</div>
            <div id="winners-feed" style="color:#94a3b8; font-size:13px;">யாரும் இன்னும் பதிலளிக்கவில்லை...</div>
        </div>
    </div>

    <!-- Wallet Screen -->
    <div class="screen" id="scr-wallet">
        <div class="card" style="text-align:center; padding: 24px;">
            <div style="font-size:13px; color:#94a3b8;">தற்போதைய வாலட் இருப்பு</div>
            <div style="font-size:38px; font-weight:900; color:#facc15; margin:6px 0;">₹<span id="wlt-bal">0.00</span></div>
        </div>
        <div class="card">
            <div style="font-weight:700; margin-bottom:10px;">➕ உடனடி ரீசார்ஜ் (UPI)</div>
            <div style="display:flex; gap:10px;">
                <button class="opt-card" style="justify-content:center; margin:0;" onclick="addCash(10)">+ ₹10</button>
                <button class="opt-card" style="justify-content:center; margin:0;" onclick="addCash(50)">+ ₹50</button>
                <button class="opt-card" style="justify-content:center; margin:0;" onclick="addCash(100)">+ ₹100</button>
            </div>
        </div>
        <div class="card">
            <div style="font-weight:700; margin-bottom:8px;">🏦 பணத்தை வங்கிக்கு எடுக்க</div>
            <input type="text" id="inp-upi" placeholder="உங்கள் UPI ID (எ.கா: name@okaxis)">
            <input type="number" id="inp-wamt" placeholder="தொகை (குறைந்தபட்சம் ₹10)">
            <button class="btn-action" style="background:#3b82f6; margin-top:8px;" onclick="withdrawCash()">Withdraw செய்யவும்</button>
        </div>
    </div>

    <!-- History Screen -->
    <div class="screen" id="scr-history">
        <h3 style="margin-top:0;">📜 பரிவர்த்தனை வரலாறு</h3>
        <div class="card" id="history-list" style="font-size:13px; color:#cbd5e1;"></div>
    </div>

    <!-- Bottom Navigation -->
    <div class="tab-bar" id="app-tabs" style="display:none;">
        <div class="tab active" id="tab-home" onclick="switchTab('home')"><span>🎮</span>லைவ் ஆட்டம்</div>
        <div class="tab" id="tab-wallet" onclick="switchTab('wallet')"><span>💳</span>வாலட்</div>
        <div class="tab" id="tab-history" onclick="switchTab('history')"><span>📜</span>வரலாறு</div>
    </div>
</div>

<script>
    let currentUser = "";
    let currentRoundId = -1;
    let pollInterval = null;

    // சவுண்ட் எஃபெக்ட் உருவாக்கும் எஞ்சின் (Web Audio API)
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playTone(freq, type, duration) {
        try {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = type;
            osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start();
            osc.stop(audioCtx.currentTime + duration);
        } catch(e) {}
    }

    function showToast(msg) {
        const t = document.getElementById("toast");
        t.innerText = msg;
        t.style.display = "block";
        setTimeout(() => t.style.display = "none", 2500);
    }

    async function doLogin() {
        const uid = document.getElementById("inp-uid").value.trim();
        const name = document.getElementById("inp-name").value.trim();
        if(!uid || !name) return showToast("எண் மற்றும் பெயரை உள்ளிடவும்!");
        
        playTone(600, 'sine', 0.1);
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({uid, name})
        });
        const data = await res.json();
        currentUser = data.uid;
        
        document.getElementById("scr-login").classList.remove("active");
        document.getElementById("app-header").style.display = "flex";
        document.getElementById("app-tabs").style.display = "flex";
        switchTab('home');
        startLiveSync();
    }

    function switchTab(tab) {
        playTone(450, 'sine', 0.05);
        ['home', 'wallet', 'history'].forEach(t => {
            document.getElementById('scr-' + t).classList.remove('active');
            document.getElementById('tab-' + t).classList.remove('active');
        });
        document.getElementById('scr-' + tab).classList.add('active');
        document.getElementById('tab-' + tab).classList.add('active');
    }

    function startLiveSync() {
        syncState();
        pollInterval = setInterval(syncState, 500); // அரை வினாடிக்கு ஒருமுறை லைவ் அப்டேட்
    }

    async function syncState() {
        if(!currentUser) return;
        const res = await fetch('/api/state?uid=' + encodeURIComponent(currentUser));
        const st = await res.json();
        
        document.getElementById("hdr-wallet").innerText = st.wallet.toFixed(2);
        document.getElementById("wlt-bal").innerText = st.wallet.toFixed(2);
        document.getElementById("lbl-round").innerText = st.round_id;
        document.getElementById("lbl-timer").innerText = st.remaining.toFixed(1);
        document.getElementById("timer-bar").style.width = ((st.remaining / 30) * 100) + "%";
        document.getElementById("timer-bar").style.background = st.remaining < 6 ? "#ef4444" : "#4ade80";
        document.getElementById("lbl-players").innerText = st.total_players;
        document.getElementById("lbl-winners").innerText = st.winners_count;

        // புதிய சுற்று தொடங்கியதும் அறிவிப்பு
        if(currentRoundId !== st.round_id) {
            currentRoundId = st.round_id;
            playTone(800, 'triangle', 0.15);
        }

        const joinBox = document.getElementById("join-box");
        const quizBox = document.getElementById("quiz-box");

        if(!st.joined) {
            joinBox.style.display = "block";
            quizBox.style.display = "none";
            const btn = document.getElementById("btn-join");
            if(st.remaining < 3) {
                btn.disabled = true;
                btn.innerText = "⏳ அடுத்த சுற்று தொடங்கப் போகிறது...";
            } else {
                btn.disabled = false;
                btn.innerText = "🎮 ₹1 கட்டி இப்போதே இணையுங்கள்";
            }
        } else {
            joinBox.style.display = "none";
            quizBox.style.display = "block";
            document.getElementById("lbl-question").innerText = st.question;
            
            let optHtml = "";
            st.options.forEach(opt => {
                let cls = "opt-card";
                let badge = "→";
                if(st.submitted) {
                    if(opt === st.correct_answer) { cls += " opt-correct"; badge = "✅"; }
                    else { cls += " opt-wrong"; badge = "❌"; }
                }
                optHtml += `<button class="${cls}" ${st.submitted ? 'disabled' : ''} onclick="submitAns('${opt}')"><span>${opt}</span><span>${badge}</span></button>`;
            });
            document.getElementById("options-list").innerHTML = optHtml;
        }

        // Top 10 Winners List
        if(st.winners_list.length > 0) {
            document.getElementById("winners-feed").innerHTML = st.winners_list.map(w => 
                `<div class="winner-item"><span><b>#${w.rank}</b> ${w.name} (${w.time}s)</span><span style="color:#4ade80; font-weight:bold;">+₹2.00</span></div>`
            ).join("");
        } else {
            document.getElementById("winners-feed").innerText = "முதல் 10 இடங்களுக்குப் போட்டி நடக்கிறது...";
        }

        // History
        if(st.history.length > 0) {
            document.getElementById("history-list").innerHTML = st.history.map(h => `<div style="padding:8px 0; border-bottom:1px solid #1e293b;">${h}</div>`).join("");
        }
    }

    async function joinRound() {
        const res = await fetch('/api/join', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({uid: currentUser})
        });
        const data = await res.json();
        if(data.status === "error") return showToast(data.msg);
        playTone(700, 'sine', 0.12);
        showToast("சுற்றில் இணைந்துவிட்டீர்கள்! வேகமாகப் பதிலளியுங்கள்!");
        syncState();
    }

    async function submitAns(ans) {
        const res = await fetch('/api/answer', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({uid: currentUser, round_id: currentRoundId, answer: ans})
        });
        const data = await res.json();
        if(data.status === "ok") {
            if(data.sub.won) {
                playTone(900, 'sine', 0.25);
                showToast(`🎉 வெற்றி! Rank #${data.sub.rank} (+₹2 சேர்க்கப்பட்டது)`);
            } else if(data.sub.correct) {
                showToast("👍 சரியான பதில்! ஆனால் முதல் 10 இடங்கள் நிரம்பிவிட்டன.");
            } else {
                playTone(200, 'sawtooth', 0.25);
                showToast("❌ தவறான பதில்!");
            }
            syncState();
        }
    }

    async function addCash(amt) {
        await fetch('/api/wallet/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({uid: currentUser, amount: amt})
        });
        playTone(750, 'sine', 0.1);
        showToast(`₹${amt} வாலட்டில் சேர்க்கப்பட்டது!`);
        syncState();
    }

    async function withdrawCash() {
        const upi = document.getElementById("inp-upi").value.trim();
        const amt = parseFloat(document.getElementById("inp-wamt").value);
        if(!upi || !amt || amt < 10) return showToast("சரியான UPI ID மற்றும் குறைந்தபட்சம் ₹10 உள்ளிடவும்");
        const res = await fetch('/api/wallet/withdraw', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({uid: currentUser, amount: amt, upi_id: upi})
        });
        const data = await res.json();
        showToast(data.msg);
        syncState();
    }
</script>
</body>
</html>"""
