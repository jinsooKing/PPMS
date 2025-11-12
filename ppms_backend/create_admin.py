# create_admin.py
from app import create_app
from models import db, User
from extensions import bcrypt

# 1. Flask 앱 컨텍스트 생성
app = create_app()

# 2. 새 관리자 정보 설정 (중요!)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "ptelcorp" # <--- ★★★ 여기에 실제 사용할 비밀번호를 입력하세요 ★★★

# 3. 앱 컨텍스트 안에서 DB 작업 수행
with app.app_context():
    try:
        # 4. 'admin' 계정이 이미 있는지 확인
        existing_user = User.query.filter_by(username=ADMIN_USERNAME).first()

        if existing_user:
            # 5-1. (계정이 이미 있을 경우) 비밀번호만 업데이트
            hashed_password = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf-8')
            existing_user.password_hash = hashed_password
            existing_user.role = 'admin' # (혹시 모르니 역할도 'admin'으로 강제 설정)
            print(f"'{ADMIN_USERNAME}' 계정이 이미 존재하여 비밀번호를 업데이트했습니다.")
        
        else:
            # 5-2. (계정이 없을 경우) 새 계정 생성
            hashed_password = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf-8')
            new_admin = User(
                username=ADMIN_USERNAME, 
                password_hash=hashed_password, 
                role='admin'
            )
            db.session.add(new_admin)
            print(f"'{ADMIN_USERNAME}' 계정을 새로 생성했습니다.")

        # 6. DB에 최종 저장
        db.session.commit()
        print("작업 완료!")

    except Exception as e:
        db.session.rollback()
        print(f"오류 발생: {e}")