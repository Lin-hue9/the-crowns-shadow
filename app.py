from flask import Flask, render_template, request, session, redirect
from flask_socketio import SocketIO, emit, join_room
import random
import string

app = Flask(__name__)
app.secret_key = "crown-shadow-key"

# IMPORTANT: avoid eventlet crash issues
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

games = {}

PHASES = ["decree", "intrigue", "petition", "reckoning"]

HOUSES = [
    {"name": "Wolf", "emoji": "🐺"},
    {"name": "Raven", "emoji": "🦅"},
    {"name": "Rose", "emoji": "🌹"},
    {"name": "Lion", "emoji": "🦁"},
]


def code():
    return ''.join(random.choices(string.ascii_uppercase, k=5))


def new_player(name):
    return {
        "name": name,
        "house": random.choice(HOUSES),
        "influence": 0,
        "gold": 5,
        "scandal": 0
    }


def new_game():
    return {
        "players": [],
        "phase": "decree",
        "decree": "The King demands loyalty.",
        "winner": None
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/create", methods=["POST"])
def create():
    c = code()
    games[c] = new_game()
    session["room"] = c
    return redirect(f"/lobby/{c}")


@app.route("/join", methods=["POST"])
def join():
    c = request.form.get("room_code", "").upper()
    if c in games:
        session["room"] = c
        return redirect(f"/lobby/{c}")
    return "Room not found"


@app.route("/lobby/<c>")
def lobby(c):
    return render_template("lobby.html", room=c, game=games[c])


# ---------------- SOCKET ----------------

@socketio.on("join")
def on_join(data):
    room = data["room"]
    name = data["name"]

    join_room(room)
    games[room]["players"].append(new_player(name))

    emit("update", games[room], room=room)


@socketio.on("action")
def action(data):
    room = data["room"]
    name = data["name"]
    act = data["action"]

    for p in games[room]["players"]:
        if p["name"] == name:
            if act == "gold":
                p["gold"] += 2
            elif act == "rumor":
                p["influence"] += 1
            elif act == "sabotage":
                p["scandal"] += 2

    emit("update", games[room], room=room)


@socketio.on("next")
def next_phase(data):
    room = data["room"]
    g = games[room]

    idx = PHASES.index(g["phase"])
    g["phase"] = PHASES[(idx + 1) % len(PHASES)]

    emit("update", g, room=room)


# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=5050, debug=True)