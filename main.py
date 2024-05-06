from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
from pymongo import MongoClient

from functions import railFence
railFenceKey=3

app = Flask(__name__)
app.config["SECRET_KEY"] = "hjhjsdahhds"
socketio = SocketIO(app)

# Connect to MongoDB
client = MongoClient("mongodb+srv://zahrabehzad:platinco@clustertrain.vkkabwu.mongodb.net/?retryWrites=true&w=majority&appName=ClusterTrain")
db = client["chat_app"]
messages_collection = db["messages"]



rooms_collection = db["rooms"]

@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)
        
        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms_collection.insert_one({"room_code": room, "members": 0, "messages": []})
        elif not room_exists(room):
            return render_template("home.html", error="Room does not exist.", code=code, name=name)
        
        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")

@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or not room_exists(room):
        return redirect(url_for("home"))
    
    return render_template("room.html", code=room, messages=get_room_messages(room))


from flask import request

@app.route('/decrypt', methods=['POST'])
def decrypt_message():
    cipher = request.json.get('cipher')
    key = request.json.get('key')
    print(cipher)
    print(key)
    decrypted_message = railFence.decryptRailFence(cipher, key)
    return decrypted_message




@socketio.on("message")
def message(data):
    room = session.get("room")
    if not room_exists(room):
        return 
    
    content = {
        "name": session.get("name"),
        "message": railFence.encryptRailFence(data["data"], railFenceKey)
    }
    send(content, to=room)
    rooms_collection.update_one({"room_code": room}, {"$push": {"messages": content}})
    
    print(f"{session.get('name')} said: {data['data']}")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if not room_exists(room):
        leave_room(room)
        return
    
    join_room(room)
    send({"name": name, "message": (railFence.encryptRailFence("has entered the room", railFenceKey))}, to=room)
    rooms_collection.update_one({"room_code": room}, {"$inc": {"members": 1}})
    print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room_exists(room):
        rooms_collection.update_one({"room_code": room}, {"$inc": {"members": -1}})
    
    send({"name": name, "message": (railFence.encryptRailFence("has left the room", railFenceKey))}, to=room)
    print(f"{name} has left the room {room}")

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        if not room_exists(code):
            break
    
    return code

def room_exists(code):
    return rooms_collection.count_documents({"room_code": code}) > 0

def get_room_messages(code):
    room = rooms_collection.find_one({"room_code": code})
    if room:
        decrypted_messages = []
        for message in room["messages"]:
            decrypted_messages.append(railFence.decryptRailFence(message["message"], railFenceKey))
        return decrypted_messages
    else:
        return []

    # return railFence.decryptRailFence(room["messages"], railFenceKey) if room else []

if __name__ == "__main__":
    socketio.run(app, debug=True)