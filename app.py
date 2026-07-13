from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import secrets, time

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
CORS(app)

# РАЗРЕШАЕМ POLLING (ОБХОДИМ БЛОКИРОВКУ WEBSOCKET)
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    transports=['polling', 'websocket']
)

rooms_data = {}
user_names = {}
room_counter = 0

HTML = r'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>🎙️ Голосовой чат</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;background:#0a0a1a;color:#ccc;height:100vh;display:flex;justify-content:center;align-items:center}
.container{width:100%;max-width:500px;height:95vh;background:linear-gradient(180deg,#1a1a2e,#16213e);border:2px solid #4a4a6a;border-radius:20px;display:flex;flex-direction:column;overflow:hidden;padding:15px}
h1{text-align:center;color:#ffd700;font-size:1.2em;margin-bottom:6px}
#lobby{flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:10px}
#lobby input{padding:10px;width:100%;max-width:280px;background:#1a1a2e;border:2px solid #4a4a6a;border-radius:10px;color:#fff;font-size:15px;text-align:center}
#lobby input:focus{border-color:#ffd700;outline:none}
.btn{padding:10px 20px;border:none;border-radius:10px;font-size:15px;font-weight:bold;color:#fff;cursor:pointer;width:100%;max-width:280px}
.btn:hover{transform:scale(1.02);filter:brightness(1.2)}
.btn-create{background:#2a6a4a}
.btn-join{background:#2a4a8a}
.btn-leave{background:#8a2a2a;padding:6px 14px;font-size:13px;width:auto}
#game{display:none;flex:1;flex-direction:column;gap:6px}
#roomInfo{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:#0f0f23;border-radius:8px}
#roomId{color:#ffd700;font-weight:bold}
#voiceStatus{text-align:center;padding:4px;font-size:0.8em;border-radius:10px}
.status-offline{color:#ff4444;background:#1a0a0a}
.status-online{color:#2ecc71;background:#0a1a0a}
#members{display:flex;flex-wrap:wrap;gap:4px;padding:6px;background:#0f0f23;border-radius:8px;min-height:32px;max-height:60px;overflow-y:auto}
.member{padding:3px 10px;background:#2a2a4a;border-radius:20px;font-size:0.75em;color:#88ccff}
.member.you{background:#2a4a2a;color:#aaddaa}
#controls{display:flex;gap:8px;justify-content:center;padding:10px 0}
.voice-btn{padding:16px 30px;border:none;border-radius:50px;font-size:18px;font-weight:bold;cursor:pointer;flex:1}
.btn-mic-on{background:#2ecc71;color:#fff}
.btn-mic-off{background:#e74c3c;color:#fff}
#roomList{width:100%;max-width:280px;max-height:150px;overflow-y:auto;background:#0f0f23;border-radius:10px;padding:4px}
.room-item{padding:6px 10px;margin:2px 0;background:#1a1a2e;border-radius:6px;cursor:pointer;display:flex;justify-content:space-between;font-size:0.8em}
.room-item:hover{background:#2a2a4a}
.room-item .rname{color:#ffd700}
.room-item .rcount{color:#888}
#chatArea{flex:1;display:flex;flex-direction:column;border-top:1px solid #2a2a4a;padding-top:4px}
#chatMsgs{flex:1;overflow-y:auto;padding:4px;font-size:0.75em;max-height:80px}
.msg-system{color:#ffd700}
.msg-self{color:#88ccff}
.msg-other{color:#ddd}
#chatInputRow{display:flex;gap:4px;padding-top:4px}
#chatInput{flex:1;padding:6px 10px;background:#1a1a2e;border:1px solid #3a3a5a;border-radius:20px;color:#ddd;font-size:13px}
.btn-send{padding:6px 14px;background:#2a4a6a;border:none;border-radius:20px;color:#fff;cursor:pointer}
#statusMsg{font-size:0.7em;color:#666;text-align:center;padding:4px}
</style>
</head>
<body>
<div class="container">
<h1>🎙️ Голосовой чат</h1>
<div id="lobby">
    <input id="playerName" placeholder="Ваше имя" value="Игрок">
    <button class="btn btn-create" onclick="createRoom()">➕ Создать комнату</button>
    <div style="color:#666;font-size:0.8em">— или —</div>
    <input id="roomInput" placeholder="ID комнаты">
    <button class="btn btn-join" onclick="joinRoom()">🔗 Присоединиться</button>
    <div id="statusMsg">⚡ Голос через WebSocket</div>
</div>
<div id="game">
    <div id="roomInfo">
        <span>🏠 <span id="roomId">-</span></span>
        <button class="btn btn-leave" onclick="leaveRoom()">🚪 Выйти</button>
    </div>
    <div id="members"><span style="color:#666;font-size:0.7em">👥 Участники:</span></div>
    <div id="controls">
        <button class="voice-btn btn-mic-on" id="micBtn" onclick="toggleMic()">🎤 Вкл микрофон</button>
    </div>
    <div id="voiceStatus" class="status-offline">🔴 Микрофон выключен</div>
    <div id="chatArea">
        <div id="chatMsgs"></div>
        <div id="chatInputRow">
            <input id="chatInput" placeholder="Текст..." onkeypress="if(event.key==='Enter')sendChat()">
            <button class="btn-send" onclick="sendChat()">📨</button>
        </div>
    </div>
</div>
</div>
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
// ПРИНУДИТЕЛЬНО ИСПОЛЬЗУЕМ POLLING (ОБХОДИМ БЛОКИРОВКУ)
const socket = io({
    transports: ['polling', 'websocket'],
    upgrade: false,
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000
});

let roomId = null, myName = '', audioCtx = null, mediaStream = null, audioProcessor = null, isMicOn = false;

function initAudio(){ if(!audioCtx) audioCtx = new AudioContext(); }
function toggleMic(){ initAudio(); isMicOn ? stopMic() : startMic(); }
async function startMic(){
    try{
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
        const source = audioCtx.createMediaStreamSource(mediaStream);
        const processor = audioCtx.createScriptProcessor(2048,1,1);
        processor.onaudioprocess = (e) => {
            if(!isMicOn) return;
            const data = new Int16Array(e.inputBuffer.getChannelData(0).length);
            for(let i=0;i<data.length;i++) data[i] = e.inputBuffer.getChannelData(0)[i]*32767;
            socket.emit('voice_data', data.buffer);
        };
        source.connect(processor); processor.connect(audioCtx.destination);
        audioProcessor = processor; isMicOn = true; updateUI();
    } catch(e){ alert('❌ Нет доступа к микрофону!'); }
}
function stopMic(){
    if(audioProcessor){ audioProcessor.disconnect(); audioProcessor = null; }
    if(mediaStream){ mediaStream.getTracks().forEach(t=>t.stop()); mediaStream = null; }
    isMicOn = false; updateUI();
}
function updateUI(){
    const btn = document.getElementById('micBtn'), st = document.getElementById('voiceStatus');
    btn.textContent = isMicOn ? '🔴 Выключить' : '🎤 Включить';
    btn.className = 'voice-btn '+(isMicOn?'btn-mic-off':'btn-mic-on');
    st.textContent = isMicOn ? '🟢 Говорите!' : '🔴 Микрофон выключен';
    st.className = isMicOn ? 'status-online' : 'status-offline';
}
function playAudio(data){
    try{
        const buf = audioCtx.createBuffer(1, data.length, 48000);
        const ch = buf.getChannelData(0);
        for(let i=0;i<data.length;i++) ch[i] = data[i]/32768;
        const src = audioCtx.createBufferSource();
        src.buffer = buf; src.connect(audioCtx.destination); src.start();
    } catch(e){}
}
function createRoom(){ myName = document.getElementById('playerName').value.trim()||'Игрок'; socket.emit('create_room',{name:myName}); }
function joinRoom(){ roomId = document.getElementById('roomInput').value.trim(); if(!roomId) return alert('Введите ID!'); myName = document.getElementById('playerName').value.trim()||'Игрок'; socket.emit('join_room',{room:roomId,name:myName}); }
function leaveRoom(){ if(roomId){ stopMic(); socket.emit('leave_room',{room:roomId}); roomId=null; document.getElementById('game').style.display='none'; document.getElementById('lobby').style.display='flex'; document.getElementById('members').innerHTML='<span style="color:#666;font-size:0.7em">👥 Участники:</span>'; document.getElementById('chatMsgs').innerHTML=''; addSystemMsg('👋 Вы вышли'); } }
function sendChat(){ const inp = document.getElementById('chatInput'), msg = inp.value.trim(); if(!msg||!roomId)return; socket.emit('chat_msg',{room:roomId,msg:msg}); inp.value=''; addChatMsg('Я',msg,'msg-self'); }
function addSystemMsg(msg){ document.getElementById('chatMsgs').innerHTML += `<div class="msg-system">📢 ${msg}</div>`; }
function addChatMsg(s,m,c){ document.getElementById('chatMsgs').innerHTML += `<div class="${c}"><b>${s}:</b> ${m}</div>`; }
function updateMembers(members){ let html='<span style="color:#666;font-size:0.7em">👥 Участники:</span> '; members.forEach(n=>{ html+=`<span class="${n===myName?'member you':'member'}">${n}${n===myName?' (Вы)':''}</span>`; }); document.getElementById('members').innerHTML=html; }

socket.on('connect', ()=>{ 
    addSystemMsg('✅ Подключено к серверу');
    console.log('Socket connected!');
});
socket.on('connect_error', (err)=>{ 
    console.error('Ошибка подключения:', err);
    addSystemMsg('⚠️ Ошибка подключения, переподключаемся...');
});
socket.on('room_created', (d)=>{ roomId=d.room_id; document.getElementById('roomId').textContent=roomId; document.getElementById('lobby').style.display='none'; document.getElementById('game').style.display='flex'; addSystemMsg('🏠 Комната создана! ID: '+roomId); updateMembers(d.members); });
socket.on('room_joined', (d)=>{ document.getElementById('roomId').textContent=roomId; document.getElementById('lobby').style.display='none'; document.getElementById('game').style.display='flex'; addSystemMsg('✅ Вы в комнате'); updateMembers(d.members); });
socket.on('room_error', (d)=>{ alert('❌ '+d.msg); });
socket.on('members_update', (d)=>{ updateMembers(d.members); });
socket.on('voice_broadcast', (d)=>{ try{ playAudio(new Int16Array(d)); }catch(e){} });
socket.on('chat_broadcast', (d)=>{ if(d.sender!==myName) addChatMsg(d.sender,d.msg,'msg-other'); });
socket.on('system_msg', (d)=>{ addSystemMsg(d.msg); });
socket.on('disconnect', ()=>{ addSystemMsg('❌ Соединение потеряно...'); });
socket.on('reconnect', ()=>{ addSystemMsg('✅ Переподключено'); if(roomId) socket.emit('join_room',{room:roomId,name:myName}); });

document.addEventListener('click', ()=>{ initAudio(); }, {once:true});
</script>
</body>
</html>'''

@app.route('/')
def index():
    return render_template_string(HTML)

@socketio.on('create_room')
def create_room(data):
    global room_counter
    room_counter += 1
    room_id = secrets.token_hex(4)
    name = data.get('name', 'Игрок')
    rooms_data[room_id] = {'name': f'Комната {room_counter}', 'members': []}
    join_room(room_id)
    rooms_data[room_id]['members'].append(request.sid)
    user_names[request.sid] = name
    emit('room_created', {'room_id': room_id, 'members': [name]})

@socketio.on('join_room')
def join_room_event(data):
    room_id = data.get('room')
    name = data.get('name', 'Игрок')
    if room_id not in rooms_data:
        emit('room_error', {'msg': 'Комната не найдена!'})
        return
    join_room(room_id)
    rooms_data[room_id]['members'].append(request.sid)
    user_names[request.sid] = name
    members = [user_names.get(sid, 'Игрок') for sid in rooms_data[room_id]['members']]
    emit('room_joined', {'members': members})
    emit('system_msg', {'msg': f'👋 {name} присоединился'}, room=room_id)
    emit('members_update', {'members': members}, room=room_id)

@socketio.on('leave_room')
def leave_room_event(data):
    room_id = data.get('room')
    if room_id in rooms_data and request.sid in rooms_data[room_id]['members']:
        rooms_data[room_id]['members'].remove(request.sid)
        name = user_names.get(request.sid, 'Игрок')
        leave_room(room_id)
        emit('system_msg', {'msg': f'👋 {name} покинул'}, room=room_id)
        members = [user_names.get(sid, 'Игрок') for sid in rooms_data[room_id]['members']]
        emit('members_update', {'members': members}, room=room_id)
        if not rooms_data[room_id]['members']:
            del rooms_data[room_id]

@socketio.on('voice_data')
def handle_voice(data):
    for room_id, room in rooms_data.items():
        if request.sid in room['members']:
            emit('voice_broadcast', data, room=room_id, skip_sid=request.sid)
            break

@socketio.on('chat_msg')
def handle_chat(data):
    room_id = data.get('room')
    msg = data.get('msg')
    if room_id in rooms_data and request.sid in rooms_data[room_id]['members']:
        name = user_names.get(request.sid, 'Игрок')
        emit('chat_broadcast', {'sender': name, 'msg': msg}, room=room_id)

@socketio.on('disconnect')
def handle_disconnect():
    for room_id, room in list(rooms_data.items()):
        if request.sid in room['members']:
            room['members'].remove(request.sid)
            name = user_names.get(request.sid, 'Игрок')
            emit('system_msg', {'msg': f'👋 {name} отключился'}, room=room_id)
            members = [user_names.get(sid, 'Игрок') for sid in room['members']]
            emit('members_update', {'members': members}, room=room_id)
            if not room['members']:
                del rooms_data[room_id]
            break
    if request.sid in user_names:
        del user_names[request.sid]

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
