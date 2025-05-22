from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_app(app):
    """Initialize the Flask app with SQLAlchemy."""
    db.init_app(app)
