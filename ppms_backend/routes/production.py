from flask import Blueprint, request, jsonify
from models import db, ProductionSchedule, Manager, Company, ProductModel, ModelData
import os
from werkzeug.utils import secure_filename
from flask import send_from_directory # send_from_directory 추가

# 'production'이라는 이름의 블루프린트(청사진) 객체 생성
bp = Blueprint('production', __name__, url_prefix='/api/production')


# [GET] /api/production/schedules : 생산 일정 조회
@bp.route('/schedules', methods=['GET'])
def get_schedules():
    try:
        year = request.args.get('year')
        month = request.args.get('month')
        week = request.args.get('weekNum')

        schedules_from_db = ProductionSchedule.query.filter_by(
            prod_year=year,
            prod_month=month,
            prod_week=week
        ).all()
        
        result = [s.to_dict() for s in schedules_from_db]
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def parse_lot_string(lot_string):
    try:
        parts = str(lot_string).split('/')
        
        # 1. '/' 앞의 숫자를 batch_qty로 가져옵니다.
        batch_qty = int(parts[0].strip()) if parts[0].strip() else 0
        
        # 2. '/' 뒤의 숫자가 있는지 확인합니다.
        if len(parts) > 1 and parts[1].strip():
            # Case 1: "50/100" -> total_qty는 100입니다.
            total_qty = int(parts[1].strip())
        else:
            # Case 2: "50" -> total_qty는 batch_qty와 같습니다. (수정된 로직)
            total_qty = batch_qty 
            
        return batch_qty, total_qty
    except:
        return 0, 0

@bp.route('/schedules', methods=['POST'])
def save_schedules():
    try:
        data = request.json
        week_info = data['weekInfo']
        schedules_list = data['schedules']
        
        db_rows = ProductionSchedule.query.filter_by(
            prod_year=week_info['year'],
            prod_month=week_info['month'],
            prod_week=week_info['weekNum']
        ).all()
        db_ids = {row.id for row in db_rows}
        frontend_ids = set()

        for s in schedules_list:
            schedule_id = s.get('id')
            
            # ▼ [신규] 어댑터 사용: "50/100" 문자열을 분리
            batch_qty, total_qty = parse_lot_string(s.get('lot', ''))

            if schedule_id: 
                frontend_ids.add(schedule_id)
                schedule_to_update = db.session.get(ProductionSchedule, schedule_id)
                if schedule_to_update:
                    schedule_to_update.line = s['line']
                    schedule_to_update.company = s['company']
                    schedule_to_update.model = s['model']
                    schedule_to_update.order_year = s.get('orderYear')
                    schedule_to_update.order_month = s.get('orderMonth')
                    schedule_to_update.tb = s['tb']
                    schedule_to_update.start_date = s['startDate']
                    schedule_to_update.end_date = s['endDate']
                    
                    # ▼ [수정] 분리된 숫자를 DB에 저장
                    schedule_to_update.batch_quantity = batch_qty
                    schedule_to_update.total_quantity = total_qty
            else:
                new_schedule = ProductionSchedule(
                    prod_year=week_info['year'],
                    prod_month=week_info['month'],
                    prod_week=week_info['weekNum'],
                    line=s['line'],
                    company=s['company'],
                    model=s['model'],
                    order_year=s.get('orderYear'),
                    order_month=s.get('orderMonth'),
                    tb=s['tb'],
                    start_date=s['startDate'],
                    end_date=s['endDate'],
                    
                    # ▼ [수정] 분리된 숫자를 DB에 저장
                    batch_quantity = batch_qty,
                    total_quantity = total_qty
                )
                db.session.add(new_schedule)

        ids_to_delete = db_ids - frontend_ids
        if ids_to_delete:
            ProductionSchedule.query.filter(ProductionSchedule.id.in_(ids_to_delete)).delete(synchronize_session=False)

        db.session.commit()
        return jsonify({"message": "일정이 성공적으로 동기화되었습니다."}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ▼▼▼ [수정] 'update_schedule' (PUT) 함수 (기존 함수와 교체) ▼▼▼
@bp.route('/schedules/<int:schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    try:
        schedule = ProductionSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({"error": "데이터를 찾을 수 없습니다."}), 404

        data = request.json

        # (계획 데이터)
        schedule.company = data.get('company', schedule.company)
        schedule.model = data.get('model', schedule.model)
        schedule.order_month = data.get('orderMonth', schedule.order_month)
        
        # ▼ [신규] 어댑터 사용: "lot" 문자열을 받아서 분리
        if 'lot' in data:
            batch_qty, total_qty = parse_lot_string(data.get('lot'))
            schedule.batch_quantity = batch_qty
            schedule.total_quantity = total_qty
        
        # (진행 데이터)
        schedule.manager = data.get('manager', schedule.manager)
        schedule.tb = data.get('tb', schedule.tb)
        
        actual_prod_val = data.get('actualProd')
        if actual_prod_val == '':
            schedule.actual_prod = 0
        elif actual_prod_val is not None:
            schedule.actual_prod = actual_prod_val
        
        schedule.actual_start_date = data.get('prodStart', schedule.actual_start_date)
        schedule.actual_end_date = data.get('prodEnd', schedule.actual_end_date)

        db.session.commit()
        return jsonify({"message": "업데이트 성공", "data": schedule.to_dict()})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    

@bp.route('/schedules/<int:schedule_id>/notes', methods=['PATCH'])
def update_note(schedule_id):
    try:
        # 1. DB에서 해당 ID의 데이터를 찾습니다.
        schedule = ProductionSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({"error": "데이터를 찾을 수 없습니다."}), 404

        # 2. 프론트에서 보낸 'notes' 텍스트를 받습니다.
        data = request.json
        if 'notes' not in data:
            return jsonify({"error": "notes 필드가 누락되었습니다."}), 400

        # 3. 'notes' 필드만 수정합니다.
        schedule.notes = data['notes']

        # 4. 변경사항을 DB에 최종 '반영(Commit)'합니다.
        db.session.commit()
        
        return jsonify({"message": "노트 업데이트 성공", "notes": schedule.notes})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@bp.route('/managers', methods=['GET'])
def get_managers():
    try:
        managers = Manager.query.order_by(Manager.name).all()
        # [ { "id": 1, "name": "김유신" }, ... ] 형태로 반환
        result = [{"id": m.id, "name": m.name} for m in managers]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ▼▼▼ [신규] '업체' 목록 조회 API ▼▼▼
@bp.route('/companies', methods=['GET'])
def get_companies():
    try:
        companies = Company.query.order_by(Company.name).all()
        result = [{"id": c.id, "name": c.name} for c in companies]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@bp.route('/schedules', methods=['DELETE'])
def delete_schedules():
    try:
        # 1. 프론트엔드에서 보낸 주차 정보를 받습니다.
        year = request.args.get('year')
        month = request.args.get('month')
        week = request.args.get('weekNum')

        if not all([year, month, week]):
            return jsonify({"error": "주차 정보가 누락되었습니다."}), 400

        # 2. DB에서 해당 주차의 '모든' 데이터를 '삭제(Delete)'합니다.
        num_deleted = ProductionSchedule.query.filter_by(
            prod_year=year,
            prod_month=month,
            prod_week=week
        ).delete()

        # 3. 변경사항을 DB에 최종 '반영(Commit)'합니다.
        db.session.commit()

        return jsonify({"message": f"총 {num_deleted}개의 일정이 삭제되었습니다."})

    except Exception as e:
        db.session.rollback() # 오류 발생 시, 되돌립니다.
        return jsonify({"error": str(e)}), 500
    
    # ==========================================
# [추가] 담당자 (Manager) 관리 API (추가/삭제)
# ==========================================

# 1. 담당자 추가 (POST)
@bp.route('/managers', methods=['POST'])
def add_manager():
    try:
        data = request.json
        name = data.get('name')
        
        if not name:
            return jsonify({"error": "이름이 입력되지 않았습니다."}), 400
            
        # 중복 이름 체크
        if Manager.query.filter_by(name=name).first():
            return jsonify({"error": "이미 존재하는 담당자입니다."}), 409

        new_manager = Manager(name=name)
        db.session.add(new_manager)
        db.session.commit()
        
        return jsonify({"message": "담당자가 추가되었습니다.", "id": new_manager.id}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# 2. 담당자 삭제 (DELETE)
@bp.route('/managers/<int:id>', methods=['DELETE'])
def delete_manager(id):
    try:
        manager = db.session.get(Manager, id)
        if not manager:
            return jsonify({"error": "해당 담당자를 찾을 수 없습니다."}), 404
            
        db.session.delete(manager)
        db.session.commit()
        return jsonify({"message": "담당자가 삭제되었습니다."})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==========================================
# [추가] 업체 (Company) 관리 API (추가/삭제)
# ==========================================

# 1. 업체 추가 (POST)
@bp.route('/companies', methods=['POST'])
def add_company():
    try:
        data = request.json
        name = data.get('name')
        
        if not name:
            return jsonify({"error": "업체명이 입력되지 않았습니다."}), 400
            
        if Company.query.filter_by(name=name).first():
            return jsonify({"error": "이미 존재하는 업체입니다."}), 409

        new_company = Company(name=name)
        db.session.add(new_company)
        db.session.commit()
        
        return jsonify({"message": "업체가 추가되었습니다.", "id": new_company.id}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# 2. 업체 삭제 (DELETE)
@bp.route('/companies/<int:id>', methods=['DELETE'])
def delete_company(id):
    try:
        company = db.session.get(Company, id)
        if not company:
            return jsonify({"error": "해당 업체를 찾을 수 없습니다."}), 404
            
        db.session.delete(company)
        db.session.commit()
        return jsonify({"message": "업체가 삭제되었습니다."})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
    # ==========================================
# [신규] 모델 (ProductModel) 관리 API
# ==========================================

# 1. 특정 업체의 모델 목록 조회 (GET)
# 사용법: /api/production/companies/1/models
@bp.route('/companies/<int:company_id>/models', methods=['GET'])
def get_models_by_company(company_id):
    try:
        models = ProductModel.query.filter_by(company_id=company_id).order_by(ProductModel.name).all()
        result = [m.to_dict() for m in models]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. 모델 추가 (POST)
# 보낼 데이터: { "company_id": 1, "name": "모델A" }
@bp.route('/models', methods=['POST'])
def add_model():
    try:
        data = request.json
        company_id = data.get('company_id')
        name = data.get('name')

        if not company_id or not name:
            return jsonify({"error": "업체ID와 모델명은 필수입니다."}), 400
        
        # 중복 체크 (같은 업체 내에 같은 모델명이 있는지)
        existing = ProductModel.query.filter_by(company_id=company_id, name=name).first()
        if existing:
            return jsonify({"error": "해당 업체에 이미 존재하는 모델명입니다."}), 409

        new_model = ProductModel(company_id=company_id, name=name)
        db.session.add(new_model)
        db.session.commit()

        return jsonify({"message": "모델이 생성되었습니다.", "data": new_model.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# 3. 모델 삭제 (DELETE)
@bp.route('/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    try:
        model = db.session.get(ProductModel, model_id)
        if not model:
            return jsonify({"error": "모델을 찾을 수 없습니다."}), 404
        
        # 모델을 지우면 연결된 데이터(BOM/좌표)도 지울 것인지? (여기서는 같이 삭제 로직 추가 가능)
        # ModelData.query.filter_by(model_id=model_id).delete()
        
        db.session.delete(model)
        db.session.commit()
        return jsonify({"message": "모델이 삭제되었습니다."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==========================================
# [수정] 모델 데이터 (BOM/좌표) 파일 업로드 API
# ==========================================

# 업로드 폴더 경로 설정 (프로젝트 폴더 내 'uploads' 폴더 생성)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 1. 데이터(파일) 저장 (POST) - multipart/form-data 처리
@bp.route('/models/<int:model_id>/data', methods=['POST'])
def save_model_data(model_id):
    try:
        # 1. 파일과 데이터 타입 받기
        if 'file' not in request.files:
            return jsonify({"error": "파일이 없습니다."}), 400
        
        file = request.files['file']
        data_type = request.form.get('type') # 'BOM' or 'COORDINATE'

        if file.filename == '':
            return jsonify({"error": "선택된 파일이 없습니다."}), 400
        
        if not data_type:
            return jsonify({"error": "데이터 타입이 누락되었습니다."}), 400

        # 2. 파일명 안전하게 변환 및 저장
        # 파일명 예시: 1_BOM_filename.xlsx (충돌 방지를 위해 ID와 타입 붙임)
        original_filename = secure_filename(file.filename)
        saved_filename = f"{model_id}_{data_type}_{original_filename}"
        file_path = os.path.join(UPLOAD_FOLDER, saved_filename)
        
        file.save(file_path) # 서버 폴더에 저장

        # 3. DB 정보 업데이트
        existing_data = ModelData.query.filter_by(model_id=model_id, data_type=data_type).first()

        if existing_data:
            existing_data.file_name = original_filename # 원본 이름 (화면 표시용)
            existing_data.content = saved_filename      # 실제 저장된 파일명 (서버 경로용)
            msg = "파일이 업데이트되었습니다."
        else:
            new_data = ModelData(
                model_id=model_id,
                data_type=data_type,
                file_name=original_filename,
                content=saved_filename 
            )
            db.session.add(new_data)
            msg = "파일이 업로드되었습니다."

        db.session.commit()
        return jsonify({"message": msg, "fileName": original_filename}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# [신규] 파일 다운로드 API
@bp.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404

# 2. 특정 모델의 데이터 조회 (GET)
# 사용법: /api/production/models/1/data?type=BOM
@bp.route('/models/<int:model_id>/data', methods=['GET'])
def get_model_data(model_id):
    try:
        data_type = request.args.get('type') # 쿼리 파라미터로 타입 필터링
        
        query = ModelData.query.filter_by(model_id=model_id)
        if data_type:
            query = query.filter_by(data_type=data_type)
            
        data_list = query.all()
        result = [d.to_dict() for d in data_list]
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # ==========================================
# [신규] 모델 존재 여부 확인 및 자동 생성 API
# ==========================================

@bp.route('/models/check-and-create', methods=['POST'])
def check_and_create_model():
    try:
        data = request.json
        company_name = data.get('company')
        model_name = data.get('model')
        create_if_missing = data.get('create', False) # True면 생성, False면 확인만

        if not company_name or not model_name:
            return jsonify({"error": "업체명과 모델명은 필수입니다."}), 400

        # 1. 업체 찾기 (없으면 자동 생성)
        company = Company.query.filter_by(name=company_name).first()
        if not company:
            if create_if_missing:
                company = Company(name=company_name)
                db.session.add(company)
                db.session.flush() # ID 생성을 위해 flush
            else:
                # 업체가 없으면 모델도 당연히 없으므로 missing_company 리턴
                return jsonify({"status": "missing_company", "message": "등록되지 않은 업체입니다."}), 200

        # 2. 모델 찾기
        model = ProductModel.query.filter_by(company_id=company.id, name=model_name).first()
        
        if model:
            return jsonify({"status": "exists", "message": "이미 존재하는 모델입니다.", "model_id": model.id}), 200
        
        # 3. 모델이 없을 때 처리
        if create_if_missing:
            new_model = ProductModel(company_id=company.id, name=model_name)
            db.session.add(new_model)
            db.session.commit()
            return jsonify({"status": "created", "message": "새 폴더(모델)가 생성되었습니다.", "model_id": new_model.id}), 201
        else:
            return jsonify({"status": "missing_model", "message": "등록되지 않은 모델입니다."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
