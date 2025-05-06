from flask import Blueprint

# Create the blueprint for the main routes
main_bp = Blueprint('main', __name__)

# Import routes at the end to avoid circular imports
from app.main import routes