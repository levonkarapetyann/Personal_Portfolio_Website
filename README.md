# Levon Karapetyan — Personal Portfolio

> Responsive personal portfolio website with an AI-powered support chat, voice messaging, and real-time admin panel.

🌐 **Live:** [levonbio.duckdns.org](https://levonbio.duckdns.org)

---

## ✨ Features

### Portfolio
- Responsive design (desktop & mobile)
- Typing effect, scroll progress bar, animated counters
- Smooth reveal animations on scroll
- Downloadable CV

### AI Support Chat
- Powered by **OpenAI GPT-4o-mini** — answers questions about Levon
- **Voice messages** — record audio, transcribed by **OpenAI Whisper**
- **Voice replies** — AI responds with synthesized speech via **OpenAI TTS** (voice: Nova)
- Session memory — no need to re-enter name/email for 30 minutes
- If AI can't answer → Levon gets an email notification automatically

### Admin Panel
- Real-time chat with visitors via **Socket.IO**
- See AI replies alongside user messages
- Send messages to offline users (stored in DB, delivered on reconnect)
- After admin replies → AI stays silent for 1 hour for that user
- Delete users and conversation history

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, JavaScript (Vanilla) |
| Backend | Python, Flask, Flask-SocketIO |
| AI Chat | OpenAI GPT-4o-mini |
| Voice Input | OpenAI Whisper-1 |
| Voice Output | OpenAI TTS (tts-1, nova) |
| Real-time | Socket.IO |
| Database | SQLite + SQLAlchemy |
| Email | Flask-Mail (Gmail SMTP) |
| Infrastructure | Nginx, Gunicorn, AWS |

---

## 🚀 Run Locally

```bash
git clone https://github.com/levonkarapetyann/Biography.git
cd Biography

pip install -r requirements.txt
```

Create a `.env` file:
```env
OPENAI_API_KEY=sk-...
ADMIN_PASSWORD=your_password
```

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000)

---

## 📁 Project Structure

```
Biography/
├── app.py                  # Flask server, AI routes, Socket.IO events
├── templates/
│   ├── support_chat.html   # Base template with chat widget
│   ├── levon_wiki.html     # Main portfolio page
│   ├── admin.html          # Admin panel
│   └── login.html          # Admin login
├── static/
│   ├── css/                # Stylesheets
│   ├── js/                 # Client-side scripts
│   └── img/                # Images & certificates
└── requirements.txt
```

---

## 📬 Contact

**Levon Karapetyan** — [lkaeapetyan@gmail.com](mailto:lkaeapetyan@gmail.com) · [Telegram](https://t.me/@lyovkarapetyan) · [LinkedIn](https://linkedin.com/in/levon-karapetyan-a42b731a4/)