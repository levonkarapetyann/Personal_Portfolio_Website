import eventlet
eventlet.monkey_patch()


import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messages.db'
app.secret_key = 'my_very_secret_key'
db = SQLAlchemy(app)
load_dotenv()
messages_history = []
user_sessions = {}

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

@socketio.on('user_msg')
def handle_user_message(data):
    user_name = data.get('user_name', 'Guest')
    user_email = data.get('user_email', 'No email')
    message = data.get('message', '')
    try:
       m = Messages(username=user_name, message=message)
       db.session.add(m)
       db.session.commit()
    except:
       db.session.rollback()
       flash('Error')
    messages_history.append({'user_name': user_name, 'message': message, 'type': 'user'})
    sid = request.sid
    user_sessions[user_name] = sid
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
               body=f"User {user_name} ({user_email}) write you in chat: {message}\n\n"
               f"Open admin panel ( http://10.167.163.168:8001/admin )",
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
    else:
       emit('user_receive', data, broadcast=True)

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
        sender_type = 'admin' if m.username == 'admin' else 'user'
        
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
