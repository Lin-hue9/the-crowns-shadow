from flask import Flask, render_template, request, session, redirect
from flask_socketio import SocketIO, emit, join_room
import random
import string

app = Flask(__name__)
app.secret_key = "crown-shadow-dev-key"

# IMPORTANT: async_mode fix for deployment
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

games = {}

PHASES = ["decree", "intrigue", "petition", "reckoning"]

HOUSES = [
    {"name": "Wolf", "emoji": "🐺"},
    {"name": "Raven", "emoji": "🦅"},
    {"name": "Rose", "emoji": "🌸"},
    {"name": "Lion", "emoji": "🦁"},
]

DECREES = [
    "All houses must send tribute to the crown.",
    "Silence is mandatory in court.",
    "A noble must be publicly shamed or honored.",
    "Trade is restricted this cycle.",
]


def room_code():
    return ''.join(random.choices(string.ascii_uppercase, k=5))


def next_phase(p):
    return PHASES[(PHASES.index(p) + 1) % len(PHASES)]


def new_player(name):
    return {
        "name": name,
        "house": random.choice(HOUSES),
        "influence": 0,
        "gold": 5,
        "scandal": 0
    }


def init_game():
    return {
        "players": [],
        "phase": "decree",
        "decree": random.choice(DECREES),
        "winner": None
    }


def calculate_winner(room):
    players = games[room]["players"]
    if not players:
        return None

    return {
        "regent": max(players, key=lambda p: p["influence"])["name"],
        "traitor": max(players, key=lambda p: p["scandal"])["name"]
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/create", methods=["POST"])
def create():
    code = room_code()
    games[code] = init_game()
    session["room"] = code
    return redirect(f"/lobby/{code}")


@app.route("/join", methods=["POST"])
def join():
    code = request.form.get("room_code", "").upper()
    if code in games:
        session["room"] = code
        return redirect(f"/lobby/{code}")
    return "Room not found", 404


@app.route("/lobby/<code>")
def lobby(code):
    if code not in games:
        return "Invalid room", 404

    g = games[code]
    return render_template("lobby.html", room_code=code, players=g["players"], phase=g["phase"], decree=g["decree"], winner=g["winner"])


# ---------------- SOCKET ----------------

@socketio.on("join_room")
def on_join(data):
    room = data["room"]
    name = data["name"]

    join_room(room)
    games[room]["players"].append(new_player(name))

    emit("sync", games[room], room=room)


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
            elif act == "loyalty":
                p["influence"] += 2
                p["gold"] -= 1

    emit("sync", games[room], room=room)


@socketio.on("next")
def next_phase(data):
    room = data["room"]

    g = games[room]
    g["phase"] = next_phase(g["phase"])

    if g["phase"] == "decree":
        g["decree"] = random.choice(DECREES)

    if g["phase"] == "reckoning":
        g["winner"] = calculate_winner(room)
        emit("game_over", g["winner"], room=room)

    emit("sync", g, room=room)


# ---------------- RUN ----------------

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)