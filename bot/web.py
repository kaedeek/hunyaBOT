from flask import Flask, request
from bot.config import PORT

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    return f"認証コード: {code} を Discord の /verify に貼ってください"
