from flask import Flask
from config import Config
from extensions import db
from flask_jwt_extended import JWTManager

app = Flask(__name__)

app.config.from_object(Config)

app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
app.config["JWT_COOKIE_SECURE"] = False
app.config["JWT_COOKIE_CSRF_PROTECT"] = False

jwt = JWTManager(app)

db.init_app(app)

# Import models
from models.course import Course
from models.student import Student
from models.grade import Grade
from models.users import User

# Create database tables
with app.app_context():
    db.create_all()

# Load routes AFTER the app is completely initialized
import routes

if __name__ == "__main__":
    app.run(debug=False)