from flask import Flask, render_template, redirect, url_for # redirect, url_for 추가
from flask_cors import CORS
from models import User

# 1. 'extensions.py'에서 모든 공용 도구 가져오기
from extensions import db, bcrypt, login_manager
# 2. Flask-Login 상태 확인을 위한 import 추가
from flask_login import current_user 

# 'routes/' 폴더에서 모든 블루프린트 가져오기
from routes.production import bp as production_bp
from routes.statistics import bp as statistics_bp
from routes.auth import bp as auth_bp
from routes.dip import bp as dip_bp
from routes.aoi import bp as aoi_bp

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app():
    app = Flask(__name__)
    # credentials 허용 설정 유지
    CORS(app, supports_credentials=True) 

    # --- [수정] 메인 페이지 라우트: 보안 강화 ---
    @app.route('/')
    def index():
        # 로그인이 되어 있지 않다면, 로그인 화면(/api/auth/login_view)으로 강제 이동
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login_view'))
        
        # 로그인된 상태라면 정상적으로 index.html을 보여줌
        return render_template('index.html')

    app.config['SECRET_KEY'] = 'a-very-secret-and-random-key-12345' 
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://ppms_user:ptelcorp@168.107.6.145/ppms_db?ssl_disabled=True'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20
    }

    # 도구 초기화
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # 블루프린트 등록
    app.register_blueprint(production_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dip_bp)
    app.register_blueprint(aoi_bp)

    with app.app_context():
        db.create_all()

    return app

app = create_app()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    
# sudo systemctl restart ppms << 수정 후 서버 재시작 코드.