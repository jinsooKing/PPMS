from flask import Flask
from flask_cors import CORS
from models import User

# ▼ [수정] 1. 'extensions.py'에서 모든 공용 도구를 가져옵니다.
from extensions import db, bcrypt, login_manager

# ▼ [수정] 2. 'routes/' 폴더에서 모든 부서(블루프린트)를 가져옵니다.
from routes.production import bp as production_bp
from routes.statistics import bp as statistics_bp
from routes.auth import bp as auth_bp

# 'login_manager' 설정 (db, bcrypt는 설정 필요 없음)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- '서버 설계도' 함수 ---
def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True) 

    app.config['SECRET_KEY'] = 'a-very-secret-and-random-key-12345' 
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://ppms_user:ptelcorp@168.107.6.145/ppms_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ▼ [수정] 3. 'extensions.py'의 도구들을 Flask 앱과 '연결(초기화)'합니다.
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # 4. 블루프린트 등록 (기존과 동일)
    app.register_blueprint(production_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(auth_bp)

    # 5. DB 테이블 생성 (기존과 동일)
    with app.app_context():
        db.create_all()

    return app

# --- '엔진 시동 버튼' ---
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)