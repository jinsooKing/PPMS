from flask import Blueprint, request, jsonify, render_template
from mobile_utils import mobile_render
from models import db, AoiRecord, ProductionSchedule, ProductModel
from sqlalchemy import func, union
from datetime import datetime
import re

bp = Blueprint('aoi', __name__, url_prefix='/api/aoi')


def normalize_name(name):
    """특수문자·공백 제거 후 대문자 변환 (모델명 중복 체크용)"""
    if not name:
        return ""
    return re.sub(r'[^a-zA-Z0-9가-힣]', '', name).upper()


def _sync_product_model(model_name, section):
    """
    ProductModel 동기화 (정규화 중복 체크 포함).
    정규화된 이름이 이미 존재하면 추가하지 않음.
    예) 'CDP 1000BAL' 과 'CDP 1000BA-L' -> 정규화 동일 -> 중복 추가 방지
    """
    norm_new = normalize_name(model_name)
    if not norm_new:
        return

    existing = ProductModel.query.filter_by(type='model', section=section).all()
    for m in existing:
        if normalize_name(m.name) == norm_new:
            return  # 정규화 기준 중복 -> 추가 안 함

    db.session.add(ProductModel(
        name=model_name,
        type='model',
        section=section,
        company_id=None,
        folder_id=None
    ))
    db.session.commit()

@bp.route('/view', methods=['GET'])
def aoi_view():
    return mobile_render('aoi.html', 'mobile_aoi.html')

# -------------------------------------------------------------------------
# [API 1] 메인 화면 테이블 데이터 조회
# -------------------------------------------------------------------------
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

        # 필터링 조건 (직접 입력한 데이터 기준)
        if model and year and month and lot:
            query = query.filter_by(model=model, order_year=year, order_month=month, lot=lot)
        elif start_date and end_date:
            query = query.filter(AoiRecord.date >= start_date, AoiRecord.date <= end_date)
        else:
            target_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
            query = query.filter_by(date=target_date)

        records = query.order_by(AoiRecord.id.desc()).all()
        
        results = []
        lot_cache = {} 

        for r in records:
            r_dict = r.to_dict()
            lot_key = (r.model, r.order_year, r.order_month, r.lot)
            if lot_key not in lot_cache:
                total_qty = db.session.query(func.sum(AoiRecord.inspection_qty)).filter_by(
                    model=r.model, order_year=r.order_year, order_month=r.order_month, lot=r.lot
                ).scalar()
                lot_cache[lot_key] = total_qty or 0
            r_dict['cumulative_qty'] = lot_cache[lot_key]
            results.append(r_dict)

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------------
# [API 2] 기록 생성 (모델 직접 추가)
# -------------------------------------------------------------------------
@bp.route('/records', methods=['POST'])
def add_aoi_record():
    try:
        data = request.json
        new_record = AoiRecord(
            model=data['model'], order_year=data['year'], order_month=data['month'], lot=str(data['lot']),
            date=data.get('date', datetime.now().strftime('%Y-%m-%d')),
            inspection_point=0, inspection_qty=0,
            reverse=0, missing=0, wrong=0, skewed=0, flipped=0,
            unsoldered=0, damaged=0, manhattan=0, short=0,
            cold=0, lifted=0, detached=0, material=0, dip=0,
            reverse_ref='', missing_ref='', wrong_ref='', skewed_ref='', flipped_ref='',
            unsoldered_ref='', damaged_ref='', manhattan_ref='', short_ref='',
            cold_ref='', lifted_ref='', detached_ref='', material_ref='', dip_ref='',
            total_defect=0, good_qty=0
        )
        db.session.add(new_record)
        db.session.commit()

        # ProductModel 동기화 (정규화 중복 체크 포함)
        _sync_product_model(data['model'], section='aoi')

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# -------------------------------------------------------------------------
# [API 3] 기록 수정 (순수 데이터 업데이트)
# -------------------------------------------------------------------------
@bp.route('/records/<int:record_id>', methods=['PUT'])
def update_aoi_record(record_id):
    try:
        data = request.json
        record = AoiRecord.query.get_or_404(record_id)
        
        editable_fields = [
            'inspection_point', 'inspection_qty', 'total_defect',
            'reverse', 'missing', 'wrong', 'skewed', 'flipped', 'unsoldered',
            'damaged', 'manhattan', 'short', 'cold', 'lifted', 'detached', 'material', 'dip',
            'reverse_ref', 'missing_ref', 'wrong_ref', 'skewed_ref', 'flipped_ref', 
            'unsoldered_ref', 'damaged_ref', 'manhattan_ref', 'short_ref', 
            'cold_ref', 'lifted_ref', 'detached_ref', 'material_ref', 'dip_ref'
        ]
        
        for field in editable_fields:
            if field in data:
                if field.endswith('_ref'): setattr(record, field, str(data[field]))
                else: setattr(record, field, int(data[field]))
    
        # 양품 수량 계산 (검사수량 - 직접 입력한 불량보드수)
        if record.inspection_qty is not None:
            record.good_qty = record.inspection_qty - (record.total_defect or 0)
        else:
            record.good_qty = 0

        db.session.commit()
        # [삭제] 상태 복구(check_and_revert_status) 로직 제거
        return jsonify({'success': True, 'updated_record': record.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# -------------------------------------------------------------------------
# [API 4] 기록 삭제
# -------------------------------------------------------------------------
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
# -------------------------------------------------------------------------
# [API 5] 모델명 자동완성 후보 조회 (ProductModel 기반)
# -------------------------------------------------------------------------
@bp.route('/model_suggestions', methods=['GET'])
def get_model_suggestions():
    try:
        q = request.args.get('q', '').strip().upper()
        if not q:
            return jsonify([])

        # ProductModel 테이블만 조회 (풀스캔 없음)
        rows = ProductModel.query.filter(
            ProductModel.name.ilike(f'%{q}%'),
            ProductModel.type == 'model'
        ).with_entities(ProductModel.name).distinct().all()

        names = sorted(set(row[0] for row in rows if row[0]))[:20]
        return jsonify(names)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------------
# [API 6] 모달 - 기간별 생산 계획 모델 목록 조회
#   production_schedules 기준, aoi_records 검사 수량 집계 포함
#   aoi_done=True 인 항목은 제외
# -------------------------------------------------------------------------
@bp.route('/available_models', methods=['GET'])
def get_available_models():
    try:
        start_year  = request.args.get('start_year',  type=int)
        start_month = request.args.get('start_month', type=int)
        end_year    = request.args.get('end_year',    type=int)
        end_month   = request.args.get('end_month',   type=int)

        # 기간 필터 없으면 빈 배열 반환
        if not all([start_year, start_month, end_year, end_month]):
            return jsonify([])

        # 기간 내 production_schedules 조회 (aoi_done=False 만)
        schedules = ProductionSchedule.query.filter(
            db.or_(
                ProductionSchedule.order_year > start_year,
                db.and_(
                    ProductionSchedule.order_year == start_year,
                    db.cast(ProductionSchedule.order_month, db.String) >= str(start_month)
                )
            ),
            db.or_(
                ProductionSchedule.order_year < end_year,
                db.and_(
                    ProductionSchedule.order_year == end_year,
                    db.cast(ProductionSchedule.order_month, db.String) <= str(end_month)
                )
            ),
            ProductionSchedule.aoi_done == False,
            ProductionSchedule.model.isnot(None),
            ProductionSchedule.model != ''
        ).order_by(
            ProductionSchedule.order_year,
            ProductionSchedule.order_month,
            ProductionSchedule.company
        ).all()

        # AOI 검사 수량 집계 (model, order_year, order_month, lot 기준)
        aoi_agg = db.session.query(
            AoiRecord.model,
            AoiRecord.order_year,
            AoiRecord.order_month,
            AoiRecord.lot,
            func.sum(AoiRecord.inspection_qty).label('aoi_qty')
        ).group_by(
            AoiRecord.model,
            AoiRecord.order_year,
            AoiRecord.order_month,
            AoiRecord.lot
        ).all()

        aoi_map = {
            (r.model, r.order_year, str(r.order_month), r.lot): r.aoi_qty
            for r in aoi_agg
        }

        # 고유주문 키(model, year, month, lot)로 중복 제거 후 회사별 그룹핑
        from collections import defaultdict, OrderedDict
        import re

        # 고유주문 단위로 deduplicate (같은 주문이 여러 라인/주차에 걸쳐 있을 수 있음)
        # 대표 행: 첫 번째 등장 기준, 수량은 total_quantity 기준
        seen = OrderedDict()  # key: (model, order_year, order_month, lot) → schedule row

        for s in schedules:
            month_num = re.sub(r'[^0-9]', '', str(s.order_month or ''))
            month_num = int(month_num) if month_num else 0
            batch = s.batch_quantity or 0
            total = s.total_quantity or 0
            lot_str = f"{batch}/{total}" if total > 0 and batch != total else str(batch)
            key = (s.model, s.order_year, month_num, lot_str)

            if key not in seen:
                seen[key] = {
                    'id':        s.id,
                    'company':   s.company or '기타',
                    'model':     s.model,
                    'year':      s.order_year,
                    'month':     month_num,
                    'lot':       lot_str,
                    'lot_total': total,
                    'recv_qty':  s.assy_actual or 0,
                }

        # AOI 수량 매핑 및 회사별 그룹핑
        company_map = defaultdict(list)
        for key, item in seen.items():
            model, year, month_num, lot_str = key
            aoi_qty = aoi_map.get((model, year, str(month_num), lot_str), 0) or 0
            item['aoi_qty'] = aoi_qty
            company_map[item['company']].append(item)

        result = [
            {'company': company, 'models': models}
            for company, models in company_map.items()
        ]

        return jsonify(result)

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'detail': traceback.format_exc()}), 500


# -------------------------------------------------------------------------
# [API 7] 모달 - 검사 완료 처리 (aoi_done = True)
# -------------------------------------------------------------------------
@bp.route('/groups/<int:schedule_id>/complete', methods=['POST'])
def complete_aoi_group(schedule_id):
    try:
        schedule = ProductionSchedule.query.get_or_404(schedule_id)
        schedule.aoi_done = True
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500