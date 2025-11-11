from flask import Flask
from flask_cors import CORS
from models import db  # models.py에서 db 객체 가져오기

# routes/production.py 파일에서 'bp' (블루프린트)를 가져옵니다.
from routes.production import bp as production_bp
# routes/statistics.py 파일에서 'bp' (블루프린트)를 가져옵니다.
from routes.statistics import bp as statistics_bp

# --- 1. '서버 설계도' 함수 ---
def create_app():
    app = Flask(__name__)
    CORS(app) # CORS 설정

    # ▼▼▼ [최종 수정] OCI VM의 Public IP와 5단계에서 만든 DB 유저 정보로 교체 ▼▼▼
    # (예시: app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://ppms_user:YourStrongPassword123!@140.123.45.67/ppms_db')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://ppms_user:ptelcorp@168.107.6.145/ppms_db'
    
    # (SSL 설정은 필요 없습니다)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 1. Flask 앱(app)과 SQLAlchemy(db)를 연결합니다.
    db.init_app(app)

    # 2. Flask 앱(app)에 블루프린트들을 등록합니다.
    app.register_blueprint(production_bp)
    app.register_blueprint(statistics_bp)

    # 3. DB 테이블 생성 (필요시)
    with app.app_context():
        db.create_all()

    return app

# --- 2. '엔진 시동 버튼' ---
# (python app.py로 실행했을 때만 이 코드가 작동합니다)
if __name__ == '__main__':
    app = create_app() # 1. 설계도(create_app)를 바탕으로 앱을 생성하고
    app.run(debug=True, port=5000) # 2. 5000번 포트로 서버를 실행합니다.