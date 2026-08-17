from flask import Flask
from flask_cors import CORS

from route import route

app = Flask(__name__)

CORS(
    app,
    origins=["https://complaient-analyser.onrender.com"],
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"]
)

app.register_blueprint(route)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )