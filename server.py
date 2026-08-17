from flask import Flask
from flask_cors import CORS
from route import route
from AiAgent import initialize_database


app = Flask(__name__)
app.register_blueprint(route)
CORS(app, origins=["https://complaient-analyser.onrender.com/"])
initialize_database()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )