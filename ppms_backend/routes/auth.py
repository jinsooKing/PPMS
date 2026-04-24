from flask import Blueprint, request, jsonify, render_template
from models import db, User
from extensions import bcrypt
from flask_login import login_user, logout_user, current_user
from mobile_utils import mobile_render

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.route('/login', methods=['POST'])
def login():
    try:
        data     = request.json
        username = data.get('username')
        password = data.get('password')

        if not username:
            return jsonify({"success": False, "message": "권한을 선택하세요."}), 400
        if not password:
            return jsonify({"success": False, "message": "비밀번호를 입력하세요."}), 400

        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            return jsonify({
                "success": True,
                "message": f"'{user.username}'님, 환영합니다!",
                "role":     user.role,
                "username": user.username,
            })

        return jsonify({"success": False, "message": "계정 또는 비밀번호가 잘못되었습니다."}), 401

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({"success": True, "message": "로그아웃 되었습니다."})


@bp.route('/check_session', methods=['GET'])
def check_session():
    if current_user.is_authenticated:
        return jsonify({
            "is_logged_in": True,
            "username":     current_user.username,
            "role":         current_user.role,
        })
    return jsonify({"is_logged_in": False}), 401


# ── 로그인 화면 ─────────────────────────────────
@bp.route('/login_view', methods=['GET'])
def login_view():
    """데스크탑/모바일 자동 감지 → 적절한 로그인 페이지 반환"""
    return mobile_render('login.html', 'mobile_login.html')


@bp.route('/mobile_login_view', methods=['GET'])
def mobile_login_view():
    """모바일 로그인 페이지 직접 접속용 (QR 등)"""
    return render_template('mobile_login.html')
