# init_db.py (수정본)
from app import create_app, db
# ModelFolder도 import에 포함시켜 주세요!
from models import ProductionSchedule, Manager, Company, ProductModel, ModelData, ModelFolder

app = create_app()

with app.app_context():
    try:
        print("데이터베이스 초기화 시작...")
        
        # [추가됨] 기존 테이블을 모두 삭제합니다. (주의: 데이터 날아감!)
        db.drop_all()
        print("🗑️ 기존 테이블 삭제 완료")

        # 새로 생성 (이제 folder_id 컬럼도 확실히 생깁니다)
        db.create_all()
        print("✅ 성공: 모든 테이블이 새로운 구조로 생성되었습니다.")
        
    except Exception as e:
        print(f"❌ 실패: {e}")