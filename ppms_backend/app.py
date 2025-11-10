from flask import Flask
from flask_cors import CORS
from models import db  # models.py에서 db 객체 가져오기

# routes/production.py 파일에서 'bp' (블루프린트)를 가져옵니다.
from routes.production import bp as production_bp
from routes.statistics import bp as statistics_bp

def create_app():
    app = Flask(__name__)
    CORS(app) # CORS 설정

    # DB 연결 설정
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://ppms_user:1234@localhost/ppms_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 1. Flask 앱(app)과 SQLAlchemy(db)를 연결합니다.
    db.init_app(app)

    # 2. Flask 앱(app)에 'production' 블루프린트를 등록합니다.
    app.register_blueprint(production_bp)
    app.register_blueprint(statistics_bp)
    # (나중에 'app.register_blueprint(aoi_bp)' 처럼 추가)

    # 3. (필요시) DB 테이블 생성
    with app.app_context():
        db.create_all()

    return app

# --- Flask 앱 실행 ---
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)