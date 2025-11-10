from flask import Blueprint, request, jsonify
from models import db, ProductionSchedule, Manager, Company  # models.py에서 DB객체와 모델을 가져옴

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
    

    
