from flask import Blueprint, request, jsonify
from models import db, DipGroup, DipHistory, ProductionSchedule
from sqlalchemy import or_, and_
from datetime import datetime, timedelta
bp = Blueprint('dip', __name__, url_prefix='/api/dip')

# 1. 모든 그룹 및 이력 조회
@bp.route('/groups', methods=['GET'])
def get_groups():
    groups = DipGroup.query.all()
    result = []
    
    for g in groups:
        g_dict = g.to_dict()
        
        # 이력 데이터를 날짜/시간 순으로 정렬
        sorted_histories = sorted(g.histories, key=lambda x: (x.date, x.id))
        
        # 프론트엔드 포맷에 맞게 분류 (shipping / receiving)
        shipping = []
        receiving = []
        
        # 누계 수량 계산은 프론트엔드 로직과 맞추기 위해 원본 데이터를 보냄
        for h in sorted_histories:
            item = h.to_dict()
            item['cumulative'] = 0 # 프론트에서 계산
            if h.type == 'ship':
                shipping.append(item)
            else:
                receiving.append(item)
                
        g_dict['shipping'] = shipping
        g_dict['receiving'] = receiving
        del g_dict['histories'] # 중복 제거
        result.append(g_dict)
        
    return jsonify(result)

# 2. 생산 완료된 모델 목록 조회 (ProductionSchedule 연동)
@bp.route('/production_models', methods=['GET'])
def get_production_models():
    now = datetime.now()
    
    # 1. 타겟 기간 계산 (전월, 당월, 익월)
    target_months = []
    # -1: 지난달, 0: 이번달, 1: 다음달
    for offset in [-1, 0, 1]:
        # 월 계산 로직
        month = now.month + offset
        year = now.year
        
        if month < 1:   # 작년 12월 등으로 넘어감
            month += 12
            year -= 1
        elif month > 12: # 내년 1월 등으로 넘어감
            month -= 12
            year += 1
            
        # DB의 order_month 형식 ("N월분")에 맞춤
        month_str = f"{month}월분"
        target_months.append((year, month_str))

    # 2. 쿼리 필터 생성 ( (년1 AND 월1) OR (년2 AND 월2) ... )
    date_filters = [
        and_(ProductionSchedule.order_year == t[0], ProductionSchedule.order_month == t[1])
        for t in target_months
    ]

    # 3. DB 조회
    # 조건: (타겟 기간 중 하나) AND (실생산량이 0보다 큼)
    results = db.session.query(
        ProductionSchedule.model,
        ProductionSchedule.total_quantity # [수정] LOT 대신 총주문량 사용
    ).filter(
        or_(*date_filters),
        ProductionSchedule.actual_prod > 0
    ).all()
    
    # 4. 중복 제거 및 포맷팅
    unique_models = {}
    for r in results:
        # Key: 모델명_총주문량 (같은 모델이라도 주문량이 다르면 다른 항목으로 취급)
        key = f"{r.model}_{r.total_quantity}"
        
        if key not in unique_models:
            unique_models[key] = {
                'model': r.model,
                # [수정] LOT 필드에 total_quantity(총주문량) 값을 문자열로 넣음
                'lot': str(r.total_quantity) 
            }
            
    return jsonify(list(unique_models.values()))

# 3. 그룹 추가
@bp.route('/groups', methods=['POST'])
def add_group():
    data = request.json
    try:
        new_group = DipGroup(model=data['model'], lot=data['lot'])
        db.session.add(new_group)
        db.session.commit()
        return jsonify({'success': True, 'message': '그룹이 생성되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': '이미 존재하는 그룹이거나 오류가 발생했습니다.'}), 400

# 4. 그룹 삭제
@bp.route('/groups/<int:group_id>', methods=['DELETE'])
def delete_group(group_id):
    group = DipGroup.query.get_or_404(group_id)
    db.session.delete(group)
    db.session.commit()
    return jsonify({'success': True})

# 5. 출입고 기록 등록
@bp.route('/records', methods=['POST'])
def add_record():
    data = request.json
    try:
        new_record = DipHistory(
            group_id=data['group_id'],
            date=data['date'],
            type=data['type'],
            quantity=data['quantity']
        )
        db.session.add(new_record)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# 6. 출입고 기록 수정
@bp.route('/records/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    data = request.json
    record = DipHistory.query.get_or_404(record_id)
    
    record.date = data['date']
    record.quantity = data['quantity']
    # type 변경은 로직상 복잡할 수 있어 일단 제외 (필요시 추가)
    
    db.session.commit()
    return jsonify({'success': True})

# 7. 출입고 기록 삭제
@bp.route('/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    record = DipHistory.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    return jsonify({'success': True})