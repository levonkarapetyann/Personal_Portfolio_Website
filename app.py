import eventlet
eventlet.monkey_patch()


import os
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messages.db'
app.secret_key = 'my_very_secret_key'
db = SQLAlchemy(app)
load_dotenv()
messages_history = []
user_sessions = {}

ai_sleep_until = {}
AI_SLEEP_SECONDS = 3600

class Messages(db.Model):
      id = db.Column(db.Integer, primary_key=True)
      username = db.Column(db.String(80))
      message = db.Column(db.String(500), nullable=True)
      

      def __repr__(self):
          return f"<{self.message}>"

admin_password = os.getenv('ADMIN_PASSWORD')
users = {
    'admin': {
        'password': generate_password_hash(admin_password)
    }
}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_DEBUG'] = True
app.config['MAIL_USERNAME'] = 'lkaeapetyan@gmail.com'
app.config['MAIL_DEFAULT_SENDER'] = 'lkaeapetyan@gmail.com'
app.config['MAIL_PASSWORD'] = 'pntc fshh ebyx hyvm'

socketio = SocketIO(app, cors_allowed_origins="*")
mail = Mail(app)
sent_emails = {}

class User(UserMixin):
   def __init__(self, id):
       self.id = id


@login_manager.user_loader
def load_user(user_id):
    if user_id not in users:
        return None
    return User(user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user_data = users.get(username)
        if user_data and check_password_hash(user_data['password'], password):
            user = User(username)
            login_user(user)
            login_user(user, remember=False)
            return redirect(url_for('admin'))
        else: 
            flash('Incorrect login or password')
    return render_template('login.html')


@app.route('/home')
@app.route('/')
def index():
    return render_template('levon_wiki.html')



@app.route('/admin')
@login_required
def admin():
    users_from_db = db.session.query(Messages.username).order_by(Messages.id.desc()).distinct().all()

    existing_users = []
    for user in users_from_db:
        name = user[0]
        sid = user_sessions.get(name, None)
        existing_users.append({
            'username': name,
            'sid': sid
        })
    existing_users.sort(key=lambda x: x['sid'] is not None, reverse=True)
    return render_template('admin.html', existing_users=existing_users)

@app.route('/get_users')
@login_required
def get_users():
    return jsonify(user_sessions)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

LEVON_SYSTEM_PROMPT = """You are an AI assistant on Levon Karapetyan's personal website. 
Your job is to answer questions about Levon in a friendly and informative way.
Always answer in THIRD person — never say "I", "me", "my", "myself". Always say "Levon", "he", "his".
Answer only in the language the user writes in.
Keep answers concise (2-4 sentences max).
 
Here is everything you know about Levon:
 
PERSONAL:
- Full name: Levon Karapetyan
- Location: Yerevan, Armenia
- Email: lkaeapetyan@gmail.com
- Phone: +37477784221
- LinkedIn: linkedin.com/in/levon-karapetyan-a42b731a4/
- GitHub: github.com/levonkarapetyann
- Instagram: instagram.com/lyov._333/
- Telegram: t.me/@lyovkarapetyan
 
EDUCATION:
- Russian-Armenian University (RAU), Yerevan
- Bachelor of Engineering Physics — specialization in Quantum Informatics
- Started: 2021, currently in 3rd year
- Focus: physics, mathematics, computational technologies, quantum information
 
EXPERIENCE:
- TUMO Labs, Yerevan — Student/Trainee at Climate Net Project (March 2026 – Present)
  6-month web development program: JavaScript, Python, Socket.IO, Nginx, Gunicorn, client-server architecture
- Aerodynamic Company — Intern Engineer, UAV Development (Sep 2021 – Dec 2021)
  Designed and optimized UAV aerodynamic components, 3D modeling with Fusion 360 and Autodesk tools
 
ACHIEVEMENTS:
- 1st place, Team Technical Project — Summer University, Krasnoyarsk (2024)
- Best Project on National Statistical Systems award
- Selected Participant — CIS Summer School (2025)
- Selected Participant — Winter University, Veliky Novgorod (2025)
- Hackathon Participant — Ministry of High-Tech Industry of Armenia (May 2026)
  Developed and pitched an LCNC platform concept and demo with team "inHub" within 72 hours
 
TECHNICAL SKILLS: JavaScript, Python, SQL, CSS, HTML, Socket.IO, Flask, Nginx, Gunicorn, Fusion 360, Autodesk
 
LANGUAGES: Russian (Native), Armenian (Native), English (B1)
 
If someone asks something you don't know about Levon, say you don't have that information and suggest they leave a message in the chat — Levon will respond personally."""

WHISPER_PROMPT = (
    "Transcribe only Russian or English speech. "
    "Proper nouns and names to recognize correctly: "
    "Levon, Karapetyan, TUMO, RAU, Yerevan, Groq, Flask, Nginx, Gunicorn. "
    "If the audio contains a name that sounds like 'Levon', always write it as 'Levon'. "
    "If the audio contains a name that sounds like 'Karapetyan', always write it as 'Karapetyan'. "
    "Ignore any speech in other languages."
)

@app.route('/voice_chat', methods=['POST'])
def voice_chat():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400

    audio_file = request.files['audio']
    user_name = request.form.get('user_name', 'Someone')
    user_email = request.form.get('user_email', '')

    sleep_until = ai_sleep_until.get(user_name, 0)
    if time.time() < sleep_until:
        return jsonify({'transcript': None, 'reply': None})

    try:
        transcribe_response = requests.post(
            'https://api.groq.com/openai/v1/audio/transcriptions',
            headers={'Authorization': f"Bearer {os.getenv('GROQ_API_KEY')}"},
            files={
                'file': (audio_file.filename or 'audio.webm', audio_file.stream, audio_file.mimetype or 'audio/webm')
            },
            data={
                'model': 'whisper-large-v3',
                'language': 'ru', 
                'prompt': WHISPER_PROMPT,
                'response_format': 'json'
            },
            timeout=15
        )
        transcribe_response.raise_for_status()
        transcript = transcribe_response.json().get('text', '').strip()

        if not transcript:
            return jsonify({'error': 'Could not transcribe audio'}), 400

        groq_response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f"Bearer {os.getenv('GROQ_API_KEY')}",
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.1-8b-instant',
                'max_tokens': 300,
                'messages': [
                    {'role': 'system', 'content': LEVON_SYSTEM_PROMPT},
                    {'role': 'user', 'content': transcript}
                ]
            },
            timeout=10
        )
        groq_response.raise_for_status()
        reply = groq_response.json()['choices'][0]['message']['content']

        broadcast_ai_reply(user_name, reply)
        return jsonify({'transcript': transcript, 'reply': reply})

    except Exception as e:
        print(f"Voice chat error: {e}")
        try:
            msg = Message(
                subject="⚠️ AI voice service is down",
                recipients=[app.config['MAIL_USERNAME']],
                body=f"Voice transcription or AI failed.\n\nPlease check the admin panel:\nhttp://10.167.163.168:8001/admin"
            )
            mail.send(msg)
        except Exception as mail_err:
            print(f"Mail error: {mail_err}")
        return jsonify({
            'reply': "I'm having trouble with voice right now. I've notified Levon and he'll get back to you soon! 🙏"
        }), 200


def broadcast_ai_reply(user_name, reply):
    """Save AI reply to DB and notify admin panel."""
    try:
        m = Messages(username='ai_bot', message=reply)
        db.session.add(m)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"DB error saving AI reply: {e}")
    socketio.emit('admin_receive', {
        'user_name': f'🤖 AI → {user_name}',
        'message': reply,
        'sid': None,
        'is_ai': True
    })

@app.route('/ai_chat', methods=['POST'])
def ai_chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    user_name = data.get('user_name', 'Someone')
    user_email = data.get('user_email', '')
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    sleep_until = ai_sleep_until.get(user_name, 0)
    if time.time() < sleep_until:
        return jsonify({'reply': None})

    try:
        groq_response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f"Bearer {os.getenv('GROQ_API_KEY')}",
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.1-8b-instant',
                'max_tokens': 300,
                'messages': [
                    {'role': 'system', 'content': LEVON_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_message}
                ]
            },
            timeout=10
        )
        groq_response.raise_for_status()
        reply = groq_response.json()['choices'][0]['message']['content']

        cant_answer_phrases = [
            "i don't have", "i do not have", "don't have this information",
            "don't have information", "no information", "i'm not sure",
            "i am not sure", "i don't know", "i do not know", "not sure about",
            "i'm unable to", "i am unable to", "unable to provide",
            "i cannot provide", "i can't provide", "i cannot answer",
            "i can't answer", "i lack", "i'm afraid i don't",
            "i'm afraid i can't", "i apologize", "unfortunately i don't",
            "unfortunately, i don't", "unfortunately i cannot",
            "i have no information", "no details available",
            "leave a message", "contact levon", "reach out to levon",
            "levon will respond", "levon can answer",
            "не имею информации", "нет информации", "не могу ответить",
            "не знаю", "не знаком", "не располагаю",
            "у меня нет информации", "у меня нет данных",
            "не могу сказать", "мне неизвестно", "мне не известно",
            "не уверен", "не уверена", "к сожалению не знаю",
            "к сожалению, не знаю", "к сожалению не могу",
            "к сожалению, не могу", "не могу предоставить",
            "эта информация мне недоступна", "не располагаю данными",
            "оставьте сообщение", "напишите левону", "левон ответит",
            "свяжитесь с левоном", "обратитесь к левону"
        ]
        if any(p.lower() in reply.lower() for p in cant_answer_phrases):
            try:
                msg = Message(
                    subject="⚠️ AI не смог ответить на вопрос",
                    recipients=[app.config['MAIL_USERNAME']],
                    body=(
                        f"AI не смог ответить на вопрос пользователя.\n\n"
                        f"Вопрос: {user_message}\n\n"
                        f"Ответ AI: {reply}\n\n"
                        f"Зайди в админ панель и ответь вручную:\n"
                        f"http://10.167.163.168:8001/admin"
                    )
                )
                mail.send(msg)
            except Exception as mail_err:
                print(f"Mail error: {mail_err}")

        broadcast_ai_reply(user_name, reply)
        return jsonify({'reply': reply})

    except Exception as e:
        print(f"AI error: {e}")
        try:
            msg = Message(
                subject="⚠️ AI сервис недоступен",
                recipients=[app.config['MAIL_USERNAME']],
                body=(
                    f"AI не смог обработать запрос (техническая ошибка).\n\n"
                    f"Вопрос: {user_message}\n\n"
                    f"Зайди в админ панель:\nhttp://10.167.163.168:8001/admin"
                )
            )
            mail.send(msg)
        except Exception as mail_err:
            print(f"Mail error: {mail_err}")
        return jsonify({
            'reply': "I'm having trouble answering right now. I've notified Levon and he'll get back to you as soon as possible! 🙏"
        }), 200


@socketio.on('register_session')
def handle_register_session(data):
    """Just registers the user's socket session — no message saved, no email sent."""
    user_name = data.get('user_name', 'Guest')
    user_sessions[user_name] = request.sid

@socketio.on('user_msg')
def handle_user_message(data):
    user_name = data.get('user_name', 'Guest')
    user_email = data.get('user_email', 'No email')
    message = data.get('message', '')
    sid = request.sid
    user_sessions[user_name] = sid

    try:
       m = Messages(username=user_name, message=message)
       db.session.add(m)
       db.session.commit()
    except:
       db.session.rollback()
       flash('Error')

    messages_history.append({'user_name': user_name, 'message': message, 'type': 'user'})
    print(f"Message from {user_name}: {message}")
    emit('admin_receive', {
        'user_name': user_name,
        'message': message,
        'sid': sid
    }, broadcast=True)

    if sid not in sent_emails:
        try:
           msg = Message(
               subject=f"New message in chat from: {user_name}",
               recipients=[app.config['MAIL_USERNAME']],
               body=f"User {user_name} ({user_email}) wrote in chat: {message}\n\n"
               f"Open admin panel: http://10.167.163.168:8001/admin",
               reply_to=user_email
           )
           mail.send(msg)
           sent_emails[sid] = True
        except Exception as e:
             print(f"Error: {e}")

@socketio.on('admin_reply')
def handle_admin_reply(data):
    message_text = data.get('message')
    target_sid = data.get('target_sid')
    target_username = data.get('target_username')

    if target_username:
        ai_sleep_until[target_username] = time.time() + AI_SLEEP_SECONDS
        print(f"[AI] Sleeping for {target_username} until {ai_sleep_until[target_username]}")

    try:
        m = Messages(username='admin', message=message_text)
        db.session.add(m)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Database error: {e}")

    messages_history.append({'user_name': 'You', 'message': message_text, 'type': 'admin'})

    if target_sid:
        emit('user_receive', data, room=target_sid)
    elif target_username:
        current_sid = user_sessions.get(target_username)
        if current_sid:
            emit('user_receive', data, room=current_sid)

@app.route('/delete_user/<username>', methods=['POST'])
@login_required
def delete_user(username):
    try:
        Messages.query.filter(Messages.username == username).delete()
        db.session.commit()
        
        if username in user_sessions:
            del user_sessions[username]
            
        return jsonify({'status': 'success', 'message': f'User {username} deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    all_messages = Messages.query.order_by(Messages.id.asc()).all()
    
    history = []
    for m in all_messages:
        if m.username == 'admin':
            sender_type = 'admin'
        elif m.username == 'ai_bot':
            sender_type = 'ai_bot'
        else:
            sender_type = 'user'
        
        history.append({
            'username': m.username,
            'message': m.message,
            'sender_type': sender_type
        })

    emit('lsmg', history)

if __name__ == '__main__':
    with app.app_context():
         db.create_all()
    socketio.run(app, debug=True, port=5000)