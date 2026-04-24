import sys
import os

# ── routes/ 안의 파일들이 mobile_utils를 찾을 수 있도록 루트 경로를 sys.path에 추가 ──
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from flask import Flask, render_template, redirect, url_for, send_from_directory, Response
from flask_cors import CORS
from models import User

from extensions import db, bcrypt, login_manager
from flask_login import current_user

from mobile_utils import mobile_render, is_mobile

# 블루프린트
from routes.production import bp as production_bp
from routes.statistics  import bp as statistics_bp
from routes.auth        import bp as auth_bp
from routes.dip         import bp as dip_bp
from routes.aoi         import bp as aoi_bp
from routes.inspection  import bp as inspection_bp
from routes.smd_check   import bp as smd_check_bp
from routes.chatbot     import bp as chatbot_bp
from routes.repair      import bp as repair_bp
from chatbot_scheduler  import create_scheduler


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True)

    # ══════════════════════════════════════════════════
    #  메인 라우트  /
    # ══════════════════════════════════════════════════
    @app.route('/')
    def index():
        if not current_user.is_authenticated:
            if is_mobile():
                return redirect(url_for('auth.mobile_login_view'))
            return redirect(url_for('auth.login_view'))

        return mobile_render('index.html', 'mobile_index.html')

    # ══════════════════════════════════════════════════
    #  모바일 전용 직접 접속 라우트
    #  (모바일 페이지 내 로고·홈 버튼이 이 경로를 사용)
    # ══════════════════════════════════════════════════
    @app.route('/mobile_index')
    def mobile_index():
        """모바일 메인 홈 — 모든 모바일 페이지의 홈버튼 목적지"""
        if not current_user.is_authenticated:
            return redirect(url_for('auth.mobile_login_view'))
        return render_template('mobile_index.html')

    @app.route('/mobile')
    def mobile_home():
        """/mobile 단축 URL"""
        if not current_user.is_authenticated:
            return redirect(url_for('auth.mobile_login_view'))
        return render_template('mobile_index.html')

    @app.route('/mobile_statistics')
    def mobile_statistics():
        """통계 모바일 직접 접속 (admin_process_map의 통계 카드가 사용)"""
        if not current_user.is_authenticated:
            return redirect(url_for('auth.mobile_login_view'))
        return render_template('mobile_statistics.html')

    # ══════════════════════════════════════════════════
    #  PWA 필수 라우트
    #  — manifest / service-worker는 반드시 루트 경로에서 서빙해야
    #    모든 페이지에 대해 scope가 적용됨
    # ══════════════════════════════════════════════════
    @app.route('/manifest.json')
    def pwa_manifest():
        return send_from_directory('static', 'manifest.json',
                                   mimetype='application/manifest+json')

    @app.route('/sw.js')
    def pwa_sw():
        resp = send_from_directory('static', 'sw.js',
                                   mimetype='application/javascript')
        # Service Worker 캐시 방지 — 항상 최신 버전 사용
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Service-Worker-Allowed'] = '/'
        return resp

    @app.route('/offline')
    def pwa_offline():
        """오프라인 fallback 페이지 — Service Worker가 캐시함"""
        return render_template('mobile_index.html')


    app.config['SECRET_KEY'] = 'a-very-secret-and-random-key-12345'
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'mysql+mysqlconnector://ppms_user:ptelcorp'
        '@168.107.6.145/ppms_db?ssl_disabled=True'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20,
    }

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(production_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dip_bp)
    app.register_blueprint(aoi_bp)
    app.register_blueprint(inspection_bp)
    app.register_blueprint(smd_check_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(repair_bp)

    with app.app_context():
        db.create_all()

    create_scheduler(app)
    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
