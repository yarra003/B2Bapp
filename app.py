from flask import Flask
from models import db

    # Import and register routes
from routes.auth_routes import auth_bp
from routes.dashboard_routes import dashboard_bp
from routes.shop_routes import shop_bp

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///b2b_platform.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = 'your-secret-key'

    db.init_app(app)


    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(shop_bp, url_prefix='/shop')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
