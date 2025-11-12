from flask import Blueprint, request, jsonify
from models import db, User
from extensions import bcrypt  
from flask_login import login_user, logout_user, current_user

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        # ▼ [수정] username을 받지 않고, password만 받습니다.
        password = data.get('password')

        if not password:
            return jsonify({"success": False, "message": "비밀번호를 입력하세요."}), 400

        # ▼ [수정] username을 'admin'으로 하드코딩(고정)합니다.
        username_to_check = "admin" 
        
        # 1. DB에서 'admin' 사용자를 찾습니다.
        user = User.query.filter_by(username=username_to_check).first()

        # 2. 'admin' 사용자가 존재하고, 암호화된 비밀번호가 일치하는지 확인
        if user and bcrypt.check_password_hash(user.password_hash, password):
            # 3. Flask-Login을 사용해 '로그인 세션' 생성
            login_user(user, remember=True)
            
            return jsonify({
                "success": True, 
                "message": f"'{user.username}'님, 환영합니다!", 
                "role": user.role
            })
        
        # 4. 로그인 실패
        return jsonify({"success": False, "message": "비밀번호가 잘못되었습니다."}), 401

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/logout', methods=['POST'])
def logout():
    # '로그아웃 세션' 삭제
    logout_user()
    return jsonify({"success": True, "message": "로그아웃 되었습니다."})


@bp.route('/check_session', methods=['GET'])
def check_session():
    # (페이지가 로드될 때 '현재 로그인 상태'를 확인할 때 사용)
    if current_user.is_authenticated:
        return jsonify({
            "is_logged_in": True,
            "username": current_user.username,
            "role": current_user.role
        })
    else:
        return jsonify({"is_logged_in": False}), 401 # 401: 비인증