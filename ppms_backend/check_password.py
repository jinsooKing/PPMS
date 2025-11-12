import sys
from app import create_app
from extensions import db, bcrypt
from models import User

# --- ▼▼▼ 여기에 확인하고 싶은 비밀번호를 입력하세요 ▼▼▼ ---
PASSWORD_TO_CHECK = "my_new_strong_password_456!" 
# --- ▲▲▲ (create_admin.py의 NEW_PASSWORD와 동일하게) ---

def check_admin_password():
    app = create_app()
    with app.app_context():
        
        ADMIN_USERNAME = "admin"
        
        # 1. DB에서 'admin' 사용자를 찾습니다.
        user = User.query.filter_by(username=ADMIN_USERNAME).first()
        
        if not user:
            print(f"오류: '{ADMIN_USERNAME}' 사용자를 DB에서 찾을 수 없습니다.")
            return

        # 2. (핵심) DB에 저장된 해시(user.password_hash)와
        #    방금 입력한 비밀번호(PASSWORD_TO_CHECK)를 비교합니다.
        is_match = bcrypt.check_password_hash(user.password_hash, PASSWORD_TO_CHECK)
        
        # 3. 결과를 출력합니다.
        if is_match:
            print(f"\n✅ [성공] 비밀번호가 일치합니다. 로그인에 문제가 없어야 합니다.")
        else:
            print(f"\n❌ [실패] 비밀번호가 일치하지 않습니다!")
            print(f"    (원인: 'create_admin.py'가 DB에 새 비밀번호를 저장하지 못했습니다.)")

if __name__ == '__main__':
    check_admin_password()