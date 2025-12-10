from flask import Blueprint, request, jsonify
from models import db, AoiRecord, ProductionSchedule
from sqlalchemy import or_, and_, func
from datetime import datetime
from dateutil.relativedelta import relativedelta

bp = Blueprint('aoi', __name__, url_prefix='/api/aoi')

# [API 1] 생산완료 모델 목록 조회 (모달창용)
@bp.route('/available_models', methods=['GET'])
def get_available_models():
    try:
        s_year = request.args.get('start_year')
        s_month = request.args.get('start_month')
        e_year = request.args.get('end_year')
        e_month = request.args.get('end_month')
        
        now = datetime.now()
        
        if not all([s_year, s_month, e_year, e_month]):
            start_dt = now - relativedelta(months=1)
            end_dt = now + relativedelta(months=1)
        else:
            start_dt = datetime(int(s_year), int(s_month), 1)
            end_dt = datetime(int(e_year), int(e_month), 1)

        target_periods = []
        curr = start_dt
        while curr <= end_dt:
            month_str = f"{curr.month}월분" 
            target_periods.append((curr.year, month_str))
            curr += relativedelta(months=1)

        period_filters = [
            and_(ProductionSchedule.order_year == y, ProductionSchedule.order_month == m)
            for y, m in target_periods
        ]

        query = db.session.query(
            ProductionSchedule.company,
            ProductionSchedule.model,
            ProductionSchedule.order_year,
            ProductionSchedule.order_month,
            ProductionSchedule.total_quantity
        ).filter(
            ProductionSchedule.actual_prod > 0,
            or_(*period_filters)
        ).group_by(
            ProductionSchedule.company, ProductionSchedule.model,
            ProductionSchedule.order_year, ProductionSchedule.order_month,
            ProductionSchedule.total_quantity
        ).order_by(
            ProductionSchedule.company, 
            ProductionSchedule.order_year.desc(), 
            ProductionSchedule.order_month.desc()
        )

        models = query.all()
        
        grouped = {}
        for m in models:
            comp = m.company if m.company else '미지정'
            if comp not in grouped: grouped[comp] = []
            
            month_display = m.order_month.replace('월분', '') 
            
            grouped[comp].append({
                'model': m.model,
                'year': m.order_year,
                'month': month_display,
                'lot': str(m.total_quantity)
            })

        return jsonify([{'company': k, 'models': v} for k, v in grouped.items()])

    except Exception as e:
        print(f"Error fetching models: {e}")
        return jsonify({'error': str(e)}), 500

# [API 2] 메인 화면 테이블 데이터 조회 (누적 수량 계산 포함)
@bp.route('/records', methods=['GET'])
def get_aoi_records():
    try:
        model = request.args.get('model')
        year = request.args.get('year')
        month = request.args.get('month')
        lot = request.args.get('lot')
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = AoiRecord.query

        if model and year and month and lot:
            query = query.filter_by(
                model=model,
                order_year=year,
                order_month=month,
                lot=lot
            )
        elif start_date and end_date:
            query = query.filter(
                AoiRecord.date >= start_date,
                AoiRecord.date <= end_date
            )
        else:
            target_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
            query = query.filter_by(date=target_date)

        records = query.order_by(AoiRecord.id.desc()).all()
        
        results = []
        lot_cache = {} 

        for r in records:
            r_dict = r.to_dict()
            
            # 누적 수량 계산 (모델+연+월+LOT 기준)
            lot_key = (r.model, r.order_year, r.order_month, r.lot)
            
            if lot_key not in lot_cache:
                total_qty = db.session.query(func.sum(AoiRecord.inspection_qty)).filter_by(
                    model=r.model,
                    order_year=r.order_year,
                    order_month=r.order_month,
                    lot=r.lot
                ).scalar()
                lot_cache[lot_key] = total_qty or 0
            
            r_dict['cumulative_qty'] = lot_cache[lot_key]
            results.append(r_dict)

        return jsonify(results)

    except Exception as e:
        print(f"Error fetching records: {e}")
        return jsonify({"error": str(e)}), 500

# [API 3] 기록 생성
@bp.route('/records', methods=['POST'])
def add_aoi_record():
    try:
        data = request.json
        new_record = AoiRecord(
            model=data['model'],
            order_year=data['year'],
            order_month=data['month'],
            lot=str(data['lot']),
            date=data.get('date', datetime.now().strftime('%Y-%m-%d')),
            
            inspection_point=0, inspection_qty=0,
            reverse=0, missing=0, wrong=0, skewed=0, flipped=0,
            unsoldered=0, damaged=0, manhattan=0, short=0,
            cold=0, lifted=0, detached=0, material=0, dip=0,
            
            # 레퍼런스 초기화
            reverse_ref='', missing_ref='', wrong_ref='', skewed_ref='', flipped_ref='',
            unsoldered_ref='', damaged_ref='', manhattan_ref='', short_ref='',
            cold_ref='', lifted_ref='', detached_ref='', material_ref='', dip_ref='',
            
            total_defect=0, good_qty=0
        )
        db.session.add(new_record)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# [API 4] 기록 수정 (수량 및 레퍼런스 업데이트)
@bp.route('/records/<int:record_id>', methods=['PUT'])
def update_aoi_record(record_id):
    try:
        data = request.json
        record = AoiRecord.query.get_or_404(record_id)
        
        # 업데이트 허용 필드 (수량 + 레퍼런스)
        editable_fields = [
            'inspection_point', 'inspection_qty', 
            # 수량
            'reverse', 'missing', 'wrong', 'skewed', 'flipped', 'unsoldered',
            'damaged', 'manhattan', 'short', 'cold', 'lifted', 'detached', 'material', 'dip',
            # 레퍼런스 (문자열)
            'reverse_ref', 'missing_ref', 'wrong_ref', 'skewed_ref', 'flipped_ref', 'unsoldered_ref',
            'damaged_ref', 'manhattan_ref', 'short_ref', 'cold_ref', 'lifted_ref', 'detached_ref', 'material_ref', 'dip_ref'
        ]
        
        for field in editable_fields:
            if field in data:
                # _ref로 끝나는 필드는 문자열, 나머지는 숫자로 처리
                if field.endswith('_ref'):
                    setattr(record, field, str(data[field]))
                else:
                    setattr(record, field, int(data[field]))
        
        # 총 불량 및 양품 재계산
        total_defect = (
            record.reverse + record.missing + record.wrong + record.skewed + 
            record.flipped + record.unsoldered + record.damaged + record.manhattan + 
            record.short + record.cold + record.lifted + record.detached + 
            record.material + record.dip
        )
        record.total_defect = total_defect
        
        if record.inspection_qty:
            record.good_qty = record.inspection_qty - total_defect
        else:
            record.good_qty = 0

        db.session.commit()
        return jsonify({'success': True, 'updated_record': record.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
@bp.route('/records/<int:record_id>', methods=['DELETE'])
def delete_aoi_record(record_id):
    try:
        record = AoiRecord.query.get_or_404(record_id)
        db.session.delete(record)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500