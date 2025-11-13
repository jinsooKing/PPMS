# create_user.py
from app import create_app
from models import db, User
from extensions import bcrypt

# 1. Flask 앱 컨텍스트 생성
app = create_app()

# 2. ★★★ 새 사용자 정보 설정 ★★★
NEW_USERNAME = "user"                 # <--- 원하는 'user' 계정 ID를 입력하세요
NEW_PASSWORD = "1234" # <--- 'user' 계정 비밀번호를 입력하세요
NEW_ROLE = "user"                     # <--- (고정) 역할은 'user'입니다
# ★★★★★★★★★★★★★★★★★★★★★★★★★

# 3. 앱 컨텍스트 안에서 DB 작업 수행
with app.app_context():
    try:
        # 4. 해당 계정이 이미 있는지 확인
        existing_user = User.query.filter_by(username=NEW_USERNAME).first()

        if existing_user:
            # 5-1. (계정이 이미 있을 경우) 비밀번호와 역할 업데이트
            hashed_password = bcrypt.generate_password_hash(NEW_PASSWORD).decode('utf-8')
            existing_user.password_hash = hashed_password
            existing_user.role = NEW_ROLE
            print(f"'{NEW_USERNAME}' 계정이 이미 존재하여 비밀번호와 역할을 '{NEW_ROLE}'(으)로 업데이트했습니다.")
        
        else:
            # 5-2. (계정이 없을 경우) 새 계정 생성
            hashed_password = bcrypt.generate_password_hash(NEW_PASSWORD).decode('utf-8')
            new_user = User(
                username=NEW_USERNAME, 
                password_hash=hashed_password, 
                role=NEW_ROLE
            )
            db.session.add(new_user)
            print(f"'{NEW_USERNAME}' ('{NEW_ROLE}' 역할) 계정을 새로 생성했습니다.")

        # 6. DB에 최종 저장
        db.session.commit()
        print("작업 완료!")

    except Exception as e:
        db.session.rollback()
        print(f"오류 발생: {e}")