from flask import Flask, send_from_directory

app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/style.css")
def style():
    return send_from_directory(".", "style.css")

@app.route("/script.js")
def script():
    return send_from_directory(".", "script.js")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
