# routes/dip.py (전체 덮어쓰기 추천)
from flask import Blueprint, request, jsonify
from models import db, DipGroup, DipHistory, ProductionSchedule
from sqlalchemy import or_, and_
from datetime import datetime

bp = Blueprint('dip', __name__, url_prefix='/api/dip')

@bp.route('/groups', methods=['GET'])
def get_groups():
    groups = DipGroup.query.all()
    result = []
    for g in groups:
        g_dict = g.to_dict()
        # (이력 정렬 로직 동일)
        sorted_histories = sorted(g.histories, key=lambda x: (x.date, x.id))
        shipping = []
        receiving = []
        for h in sorted_histories:
            item = h.to_dict()
            item['cumulative'] = 0 
            if h.type == 'ship': shipping.append(item)
            else: receiving.append(item)
        g_dict['shipping'] = shipping
        g_dict['receiving'] = receiving
        del g_dict['histories']
        result.append(g_dict)
    return jsonify(result)

# ▼ [수정] 생산 완료 모델 조회 (년/월 정보 포함)
@bp.route('/production_models', methods=['GET'])
def get_production_models():
    now = datetime.now()
    target_months = []
    for offset in [-1, 0, 1]:
        month = now.month + offset
        year = now.year
        if month < 1:
            month += 12
            year -= 1
        elif month > 12:
            month -= 12
            year += 1
        month_str = f"{month}월분"
        target_months.append((year, month_str))

    date_filters = [
        and_(ProductionSchedule.order_year == t[0], ProductionSchedule.order_month == t[1])
        for t in target_months
    ]

    results = db.session.query(
        ProductionSchedule.model,
        ProductionSchedule.total_quantity,
        ProductionSchedule.order_year,  # [추가]
        ProductionSchedule.order_month  # [추가]
    ).filter(
        or_(*date_filters),
        ProductionSchedule.actual_prod > 0
    ).all()
    
    unique_models = {}
    for r in results:
        # [수정] 키에 년/월 포함
        key = f"{r.model}_{r.order_year}_{r.order_month}_{r.total_quantity}"
        
        if key not in unique_models:
            unique_models[key] = {
                'model': r.model,
                'lot': str(r.total_quantity),
                'year': r.order_year,     # [추가]
                'month': r.order_month    # [추가]
            }
            
    return jsonify(list(unique_models.values()))

# ▼ [수정] 그룹 추가 (년/월 저장)
@bp.route('/groups', methods=['POST'])
def add_group():
    data = request.json
    try:
        # 중복 체크는 DB Constraint가 해줌
        new_group = DipGroup(
            model=data['model'], 
            lot=data['lot'],
            year=data['year'],   # [추가]
            month=data['month']  # [추가]
        )
        db.session.add(new_group)
        db.session.commit()
        return jsonify({'success': True, 'message': '그룹이 생성되었습니다.'})
    except Exception as e:
        db.session.rollback()
        # 중복 키 에러(IntegrityError)일 경우 메시지 처리
        if 'Duplicate entry' in str(e):
             return jsonify({'success': False, 'message': '이미 존재하는 그룹입니다.'}), 400
        return jsonify({'success': False, 'message': str(e)}), 500

# (나머지 delete_group, add_record, update_record, delete_record, complete_group은 기존과 동일)
@bp.route('/groups/<int:group_id>', methods=['DELETE'])
def delete_group(group_id):
    group = DipGroup.query.get_or_404(group_id)
    db.session.delete(group)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/groups/<int:group_id>/complete', methods=['POST'])
def complete_group(group_id):
    try:
        group = DipGroup.query.get_or_404(group_id)
        group.status = 'completed' 
        db.session.commit()
        return jsonify({'success': True, 'message': '그룹이 완료 처리되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
        
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

@bp.route('/records/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    data = request.json
    record = DipHistory.query.get_or_404(record_id)
    record.date = data['date']
    record.quantity = data['quantity']
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    record = DipHistory.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    return jsonify({'success': True})