# 파일명: init_vision_db.py
from app import create_app
from models import db, VisionInspection  # 모델을 가져와야 인식합니다.

app = create_app()

with app.app_context():
    # 현재 models.py에 정의되어 있지만, DB에는 없는 테이블을 자동으로 감지해 생성합니다.
    db.create_all()
    print("=========================================")
    print(" [성공] vision_inspection 테이블이 생성되었습니다! ")
    print("=========================================")