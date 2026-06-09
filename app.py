from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "crown-shadow-secret-key-change-in-production"
socketio = SocketIO(app, cors_allowed_origins="*")

# ==================== DATA STRUCTURES ====================

HOUSES = {
    "ravens": {"name": "House of Ravens", "emoji": "🦅", "power": "Read one sealed letter per season", "color": "#4a5568"},
    "lions": {"name": "House of Lions", "emoji": "🦁", "power": "Start with +2 Influence", "color": "#d4af37"},
    "serpents": {"name": "House of Serpents", "emoji": "🐍", "power": "Forge letters without proof", "color": "#2d5016"},
    "wolves": {"name": "House of Wolves", "emoji": "🐺", "power": "Cannot be bribed", "color": "#8b2635"}
}

VICES = ["Greed", "Wrath", "Pride", "Envy", "Lust"]

REALM_TRACKS = {
    "faith": {"name": "Faith", "min": 0, "max": 100, "value": 60},
    "army": {"name": "Army", "min": 0, "max": 100, "value": 70},
    "grain": {"name": "Grain", "min": 0, "max": 100, "value": 50},
    "unrest": {"name": "Unrest", "min": 0, "max": 100, "value": 30}
}

DECREES = [
    {"text": "All houses must donate 10% of their gold to the crown.", "effect": "gold"},
    {"text": "The army is weakened. Every house must provide 50 soldiers.", "effect": "army"},
    {"text": "A blight has struck the fields. Grain stores are halved.", "effect": "grain"},
    {"text": "The Faith questions the crown. Host a grand sermon or lose influence.", "effect": "faith"},
    {"text": "Peasants are restless. Bribe them or face unrest.", "effect": "unrest"}
]

PHASES = ["intrigue", "petition", "reckoning"]

# In-memory game storage
games = {}

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def new_game(room_code):
    games[room_code] = {
        "players": [],          # list of {name, house_id, vice, influence, gold, favor, scandal, letters, secrets}
        "phase": "intrigue",
        "season": 1,
        "decree": random.choice(DECREES),
        "realm": {k: v["value"] for k, v in REALM_TRACKS.items()},
        "letters": [],          # {author, content, proof_type, signet, is_forged, revealed}
        "accusations": [],
        "action_log": [],
        "game_over": False,
        "winner": None,
        "start_time": datetime.now().isoformat()
    }

def add_player(room_code, name, house_id, vice):
    game = games.get(room_code)
    if not game:
        return False
    # Check if name already exists
    for p in game["players"]:
        if p["name"] == name:
            return False
    house = HOUSES[house_id]
    influence = 5 + (2 if house_id == "lions" else 0)
    player = {
        "name": name,
        "house_id": house_id,
        "house_name": house["name"],
        "house_emoji": house["emoji"],
        "vice": vice,
        "influence": influence,
        "gold": 10,
        "favor": 3,
        "scandal": 0,
        "is_alive": True,
        "legacy_points": 0,
        "letters_written": []
    }
    game["players"].append(player)
    return True

# ==================== SOCKETIO EVENTS ====================

@socketio.on("select_house")
def handle_select_house(data):
    room = data["room"]
    name = data["name"]
    house_id = data["house_id"]
    vice = data["vice"]
    if add_player(room, name, house_id, vice):
        emit("house_selected", {"success": True}, room=request.sid)
        # Broadcast updated players
        game = games[room]
        emit("update_players", game["players"], room=room)
    else:
        emit("house_selected", {"success": False, "error": "Name already taken"}, room=request.sid)

@socketio.on("join_game")
def handle_join(data):
    room = data["room"]
    join_room(room)
    game = games.get(room)
    if game:
        emit("game_state", {
            "phase": game["phase"],
            "season": game["season"],
            "decree": game["decree"],
            "realm": game["realm"],
            "players": game["players"]
        }, room=request.sid)

# ---------- Intrigue: Write a sealed letter ----------
@socketio.on("write_letter")
def handle_write_letter(data):
    room = data["room"]
    author = data["author"]
    content = data["content"]
    proof_type = data.get("proof_type", "none")  # none, forged, real
    target_house = data.get("target", "")
    
    game = games.get(room)
    if not game or game["phase"] != "intrigue":
        emit("error", {"message": "Not intrigue phase"}, room=request.sid)
        return
    
    # Deduct gold if forging proof
    player = next((p for p in game["players"] if p["name"] == author), None)
    if not player:
        return
    
    is_forged = (proof_type == "forged")
    if is_forged and player["house_id"] != "serpents":
        if player["gold"] < 2:
            emit("error", {"message": "Not enough gold to forge"}, room=request.sid)
            return
        player["gold"] -= 2
    
    letter = {
        "id": len(game["letters"]) + 1,
        "author": author,
        "content": content,
        "proof_type": proof_type,
        "is_forged": is_forged,
        "signet": player["house_id"],
        "target": target_house,
        "revealed": False,
        "season": game["season"]
    }
    game["letters"].append(letter)
    player["letters_written"].append(letter["id"])
    
    emit("action_update", {"player": author, "action": f"Wrote a sealed letter: '{content[:30]}...'"}, room=room)

# ---------- Petition: Reveal a letter ----------
@socketio.on("reveal_letter")
def handle_reveal_letter(data):
    room = data["room"]
    letter_id = data["letter_id"]
    game = games.get(room)
    if not game or game["phase"] != "petition":
        emit("error", {"message": "Not petition phase"}, room=request.sid)
        return
    
    letter = next((l for l in game["letters"] if l["id"] == letter_id), None)
    if not letter or letter["revealed"]:
        return
    
    letter["revealed"] = True
    # Broadcast letter content to all
    emit("letter_revealed", {
        "author": letter["author"],
        "content": letter["content"],
        "proof_type": letter["proof_type"],
        "is_forged": letter["is_forged"],
        "target": letter["target"]
    }, room=room)
    
    # If forgery detected, increase scandal for author
    if letter["is_forged"]:
        author = next((p for p in game["players"] if p["name"] == letter["author"]), None)
        if author:
            author["scandal"] += 2
            emit("action_update", {"player": letter["author"], "action": "Their forgery was exposed! Scandal +2"}, room=room)

# ---------- Petition: Challenge a letter ----------
@socketio.on("challenge_letter")
def handle_challenge(data):
    room = data["room"]
    letter_id = data["letter_id"]
    challenger = data["challenger"]
    game = games.get(room)
    if not game:
        return
    letter = next((l for l in game["letters"] if l["id"] == letter_id), None)
    if letter and not letter["revealed"]:
        letter["revealed"] = True
        # Automatically consider forgery if proof is missing
        if letter["proof_type"] == "none":
            letter["is_forged"] = True
            author = next((p for p in game["players"] if p["name"] == letter["author"]), None)
            if author:
                author["scandal"] += 1
                emit("action_update", {"player": letter["author"], "action": f"Challenged by {challenger} - forgery exposed! Scandal +1"}, room=room)
        else:
            emit("action_update", {"player": challenger, "action": f"Challenged letter from {letter['author']} but it seems legitimate."}, room=room)

# ---------- Reckoning: Vote on crisis ----------
@socketio.on("vote_blame")
def handle_vote(data):
    room = data["room"]
    voter = data["voter"]
    accused = data["accused"]
    game = games.get(room)
    if not game or game["phase"] != "reckoning":
        return
    
    # Simple vote tally (in a real game, you'd store votes)
    emit("action_update", {"player": voter, "action": f"Votes to blame {accused} for the crisis."}, room=room)
    
    # After all votes, you could calculate outcome. For now, just log.

# ---------- General actions (Gold/Rumor/Sabotage) ----------
@socketio.on("take_action")
def handle_action(data):
    room = data["room"]
    name = data["name"]
    action = data["action"]
    game = games.get(room)
    if not game:
        return
    
    player = next((p for p in game["players"] if p["name"] == name), None)
    if not player:
        return
    
    # Different actions affect resources
    if action == "💰 Fund Armies":
        if player["gold"] >= 3:
            player["gold"] -= 3
            game["realm"]["army"] = min(100, game["realm"]["army"] + 5)
            emit("action_update", {"player": name, "action": "Funded armies +5 Army strength."}, room=room)
        else:
            emit("error", {"message": "Not enough gold"}, room=request.sid)
    elif action == "🎭 Host Salon":
        if player["gold"] >= 2:
            player["gold"] -= 2
            player["favor"] += 2
            emit("action_update", {"player": name, "action": "Hosted a salon, gained 2 Favor."}, room=room)
    elif action == "💔 Blackmail":
        # Blackmail: costs 1 favor, steal 2 gold from random player
        if player["favor"] >= 1:
            player["favor"] -= 1
            others = [p for p in game["players"] if p["name"] != name and p["gold"] >= 2]
            if others:
                target = random.choice(others)
                target["gold"] -= 2
                player["gold"] += 2
                emit("action_update", {"player": name, "action": f"Blackmailed {target['name']} and stole 2 gold!"}, room=room)
            else:
                emit("action_update", {"player": name, "action": "Blackmail failed - no suitable target."}, room=room)
        else:
            emit("error", {"message": "Not enough favor"}, room=request.sid)
    elif action == "✉️ Forge Letter":
        # Opens a modal - we'll handle via write_letter event
        emit("open_letter_modal", {}, room=request.sid)
    else:
        # Generic
        emit("action_update", {"player": name, "action": action}, room=room)

# ---------- Next Phase ----------
@socketio.on("next_phase")
def handle_next_phase(data):
    room = data["room"]
    game = games.get(room)
    if not game:
        return
    
    current_idx = PHASES.index(game["phase"])
    next_idx = (current_idx + 1) % len(PHASES)
    game["phase"] = PHASES[next_idx]
    
    # When finishing Reckoning, advance season and check end game
    if game["phase"] == "intrigue":
        game["season"] += 1
        # Apply realm decay / crisis
        apply_realm_crisis(room)
        # Generate new decree
        game["decree"] = random.choice(DECREES)
        # Check if game ends after season 5
        if game["season"] > 5:
            end_game(room)
            return
        
        # Clear letters from previous season? Keep for manuscript, but reset revealed? We'll keep all for history.
    
    # Broadcast new state
    emit("update_phase", {
        "phase": game["phase"],
        "season": game["season"],
        "decree": game["decree"],
        "realm": game["realm"]
    }, room=room)

def apply_realm_crisis(room):
    game = games[room]
    # Simple: grain decreases each season, unrest increases if grain low
    game["realm"]["grain"] = max(0, game["realm"]["grain"] - random.randint(5, 15))
    if game["realm"]["grain"] < 20:
        game["realm"]["unrest"] = min(100, game["realm"]["unrest"] + 10)
        emit("action_update", {"player": "Realm", "action": "Famine! Unrest increases."}, room=room)
    # Check any track at 0 => crisis
    for key, val in game["realm"].items():
        if val <= 0:
            emit("action_update", {"player": "Realm", "action": f"Crisis! {key.upper()} has collapsed. Houses lose 2 Influence."}, room=room)
            for p in game["players"]:
                p["influence"] = max(0, p["influence"] - 2)

def end_game(room):
    game = games[room]
    game["game_over"] = True
    # Determine winner: highest influence
    winner = max(game["players"], key=lambda p: p["influence"])
    game["winner"] = winner["name"]
    # Prepare manuscript data
    manuscript = {
        "winner": winner,
        "players": game["players"],
        "letters": game["letters"],
        "actions": game["action_log"],
        "seasons": game["season"],
        "realm_history": [game["realm"]]  # could store more history
    }
    emit("game_end", manuscript, room=room)

# ==================== ROUTES ====================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/create", methods=["POST"])
def create_game():
    code = generate_room_code()
    new_game(code)
    session["room"] = code
    return redirect(url_for("house_selection", room_code=code))

@app.route("/join", methods=["POST"])
def join_game():
    code = request.form.get("room_code").upper()
    if code in games and not games[code]["game_over"]:
        session["room"] = code
        return redirect(url_for("house_selection", room_code=code))
    return "Game not found or already ended", 404

@app.route("/house_selection/<room_code>")
def house_selection(room_code):
    if room_code not in games:
        return "Game not found", 404
    return render_template("house_selection.html", room_code=room_code, houses=HOUSES, vices=VICES)

@app.route("/game/<room_code>")
def game_board(room_code):
    if room_code not in games:
        return "Game not found", 404
    game = games[room_code]
    return render_template("game.html", room_code=room_code, game=game)

@app.route("/manuscript/<room_code>")
def manuscript(room_code):
    if room_code not in games:
        return "Not found", 404
    game = games[room_code]
    return render_template("end_manuscript.html", game=game)

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5050)