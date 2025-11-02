const s={temperature:24,rain:!1,soil:'جيدة',wind:10,humidity:65,rainProb:10,forecast:'غائم جزئياً',realtime:!1,pumpOn:!1,motorOn:!1,pumpAdvice:"",protectionAdvice:""},
kb={"pluie forte":"غطي الطماطم بالأغطية وتفقدي المصارف.","vent fort":"قوي دعامات الطماطم واحمِي الشتلات الصغيرة.","température haute":"اسقي في المساء.","température basse":"احمي الطماطم من البرد.","normal":"الأحوال مستقرة."},
$=id=>document.getElementById(id);

// Voice Assistant Configuration
const voiceAssistant = {
    speaking: false,
    // Queue for managing multiple voice messages
    queue: [],
    // Available messages based on conditions
    messages: {
        humidity: {
            low: "الرطوبة منخفضة. يجب تشغيل نظام الري.",
            high: "الرطوبة عالية. لا داعي للري الآن.",
            normal: "مستوى الرطوبة مناسب."
        },
        temperature: {
            high: "درجة الحرارة مرتفعة. يفضل الري في المساء.",
            low: "درجة الحرارة منخفضة. احمي المحاصيل من البرد.",
            normal: "درجة الحرارة مناسبة للنمو."
        },
        rain: {
            alert: "تنبيه! تم رصد أمطار. يجب حماية المحاصيل.",
            warning: "احتمال هطول أمطار غداً. استعدي للحماية.",
            clear: "لا يوجد خطر من الأمطار."
        },
        wind: {
            strong: "الرياح قوية. قومي بتثبيت الدعامات.",
            normal: "سرعة الرياح عادية."
        },
        soil: {
            good: "جودة التربة جيدة.",
            poor: "التربة تحتاج إلى تحسين."
        }
    },
    
    speak(text) {
        if (!text) return;
        
        // Add to queue
        this.queue.push(text);
        
        // If not speaking, start
        if (!this.speaking) {
            this.processQueue();
        }
    },
    
    async processQueue() {
        if (this.queue.length === 0) {
            this.speaking = false;
            return;
        }
        
        this.speaking = true;
        const text = this.queue.shift();
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'ar';
        utterance.onend = () => this.processQueue();
        
        speechSynthesis.speak(utterance);
    },
    
    analyzeAndSpeak() {
        const messages = [];
        
        // Check humidity
        if (s.humidity < 40) {
            messages.push(this.messages.humidity.low);
        } else if (s.humidity > 65) {
            messages.push(this.messages.humidity.high);
        }
        
        // Check temperature
        if (s.temperature > 35) {
            messages.push(this.messages.temperature.high);
        } else if (s.temperature < 10) {
            messages.push(this.messages.temperature.low);
        }
        
        // Check rain
        if (s.realtime) {
            messages.push(this.messages.rain.alert);
        } else if (s.rainProb > 60) {
            messages.push(this.messages.rain.warning);
        }
        
        // Check wind
        if (s.wind > 40) {
            messages.push(this.messages.wind.strong);
        }
        
        // If no warnings, give general status
        if (messages.length === 0) {
            messages.push("الأحوال مستقرة. لا توجد تحذيرات.");
        }
        
        // Speak all messages
        messages.forEach(msg => this.speak(msg));
    }
};

const updateUI=k=>{try{const v=$(`val-${k}`);if(!v)return;v.innerText=k==='temperature'?s[k]+' °C':k==='wind'?s[k]+' كم/س':k==='humidity'||k==='rainProb'?s[k]+' %':s[k]+(k==='realtime'?s[k]?'يعمل':'متوقف':'')}catch(e){}};

const analyze=()=>{
    const dry=s.humidity<40,wet=s.humidity>65;
    s.pumpOn=!s.realtime&&s.rainProb<60&&dry;
    s.motorOn=s.pumpOn;
    s.pumpAdvice=s.realtime?"المطر يهطل. توقف.":dry?"التربة جافة. سقي.":"رطوبة كافية.";
    s.protectionAdvice=s.realtime?kb["pluie forte"]:s.wind>40?kb["vent fort"]:s.temperature>35?kb["température haute"]:s.temperature<10?kb["température basse"]:kb["normal"];
    ['pumpOn','motorOn'].forEach(updateUI);
    $('val-advice').innerText=s.pumpAdvice+"\n"+s.protectionAdvice;
};

// WebSocket Connection
let ws = null;
const connectWebSocket = () => {
    try {
        ws = new WebSocket('ws://localhost:8000/ws');
        ws.onopen = () => {
            $('ws-dot').style.backgroundColor = '#22c55e';
            $('ws-text').innerText = 'متصل';
        };
        ws.onclose = () => {
            $('ws-dot').style.backgroundColor = '#d1d5db';
            $('ws-text').innerText = 'غير متصل';
            setTimeout(connectWebSocket, 5000);
        };
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'chat') {
                addChatMessage(message.text, false);
            } else if (message.type === 'state') {
                // Merge new state from server and update UI
                const st = message.state || {};
                Object.keys(st).forEach(k => { if (k in s) s[k] = st[k]; });
                Object.keys(s).forEach(updateUI);
                analyze();
            }
        };
    } catch (error) {
        console.error('WebSocket connection error:', error);
    }
};

const addChatMessage = (text, isUser = false) => {
    const messagesDiv = $('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `flex ${isUser ? 'justify-end' : 'justify-start'}`;
    messageDiv.innerHTML = `
        <div class="max-w-md ${isUser ? 'bg-green-100' : 'bg-white'} rounded-2xl shadow p-4">
            <div class="${isUser ? 'text-green-800' : 'text-gray-800'}">${text}</div>
        </div>
    `;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
};

// Event Listeners
const updateWeather = async () => {
    try {
        const response = await fetch('/get-recommendation');
        const data = await response.json();
        if (data.recommendation) {
            $('val-advice').innerText = data.recommendation;
            voiceAssistant.speak(data.recommendation);
        }
    } catch (error) {
        console.error('Error fetching weather:', error);
    }
};

document.addEventListener('DOMContentLoaded',()=>{
    // Initialize UI
    Object.keys(s).forEach(updateUI);
    analyze();
    connectWebSocket();
    
    // Enhanced button controls
    const weatherBtn = $('weatherBtn');
    const assistantBtn = $('assistantBtn');

    // Pump and Motor buttons
    ['pumpToggleBtn','motorToggleBtn'].forEach(id=>{
        const btn=$(id);
        if(!btn)return;
        btn.onclick=e=>{
            e.stopPropagation();
            const k=id.includes('pump')?'pumpOn':'motorOn';
            s[k]=!s[k];
            if(k==='pumpOn')s.motorOn=s.pumpOn;
            updateUI(k);
            analyze();
            // notify backend about the state change
            if (ws && ws.readyState === WebSocket.OPEN) {
                const payload = {};
                payload[k] = s[k];
                // keep motor/pump in sync
                if (k === 'pumpOn') payload['motorOn'] = s.motorOn;
                ws.send(JSON.stringify({ type: 'set_state', payload }));
            }
        };
    });

    // Send message button
    const sendMessage = () => {
        const input = $('userInput');
        const text = input.value.trim();
        if (text && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'chat', text }));
            addChatMessage(text, true);
            input.value = '';
        }
    };

    $('sendBtn').onclick = sendMessage;
    $('userInput').onkeypress = (e) => {
        if (e.key === 'Enter') sendMessage();
    };

    // Card click handlers
    document.querySelectorAll('[data-key]').forEach(card => {
        if (card.hasAttribute('role') && card.getAttribute('role') === 'button') {
            card.onclick = () => {
                const key = card.getAttribute('data-key');
                const value = s[key];
                const input = $('userInput');
                input.value = `ما هو تأثير ${value} على المحصول؟`;
                input.focus();
            };
        }
    });

    // Voice input button
    let recognition = null;
    try {
        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'ar';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onresult = (event) => {
            const text = event.results[0][0].transcript;
            $('userInput').value = text;
        };
    } catch (e) {
        console.warn('Speech recognition not supported');
    }

    $('micBtn').onclick = () => {
        if (recognition) {
            recognition.start();
            $('micBtn').classList.add('bg-red-500');
            setTimeout(() => $('micBtn').classList.remove('bg-red-500'), 3000);
        }
    };

    // Enhanced button controls
    if (weatherBtn) {
        weatherBtn.onclick = () => {
            updateWeather();
            weatherBtn.classList.add('animate-pulse');
            setTimeout(() => weatherBtn.classList.remove('animate-pulse'), 2000);
        };
    }
    
    if (assistantBtn) {
        assistantBtn.onclick = () => {
            voiceAssistant.analyzeAndSpeak();
            assistantBtn.classList.add('animate-pulse');
            setTimeout(() => assistantBtn.classList.remove('animate-pulse'), 2000);
        };
    }
    
    // Read page button (now more specific)
    $('readPageBtn').onclick = () => {
        const advice = $('val-advice').innerText;
        if (advice && advice !== '...جاري التحليل') {
            voiceAssistant.speak(advice);
            $('readPageBtn').classList.add('animate-pulse');
            setTimeout(() => $('readPageBtn').classList.remove('animate-pulse'), 2000);
        } else {
            voiceAssistant.speak("لم يتم تحليل البيانات بعد. الرجاء الانتظار.");
        }
    };
});

// Auto update simulation
setInterval(()=>{
    if(!s.pumpOn&&s.humidity>35)s.humidity--;
    else if(s.pumpOn&&s.humidity<70)s.humidity++;
    s.humidity=Math.max(0,Math.min(100,s.humidity));
    updateUI('humidity');
    analyze();
},5000);
