from flask import Blueprint, request, jsonify, render_template
from mobile_utils import mobile_render
# [중요] models.py에서 ProductionSchedule 모델을 가져옵니다.
from models import db, ProductionSchedule, AoiRecord
from sqlalchemy import func

# [신규] 'statistics' 블루프린트를 '/api/statistics' 주소로 생성합니다.
bp = Blueprint('statistics', __name__, url_prefix='/api/statistics')

@bp.route('/view', methods=['GET'])
def statistics_view():
    return mobile_render('statistics.html', 'mobile_statistics.html')

@bp.route('/order_month_summary', methods=['GET'])
def get_order_month_summary():
    try:
        # [수정] 조회 기준을 주문월(order_month) → 실제 생산년월(prod_year, prod_month)로 변경
        prod_month_str = request.args.get('prod_month')
        year_str       = request.args.get('year')

        if not all([prod_month_str, year_str]):
            return jsonify({"error": "생산 년도와 생산 월을 모두 선택해주세요."}), 400
        
        try:
            year_int       = int(year_str)
            prod_month_int = int(prod_month_str)
        except ValueError:
            return jsonify({"error": "유효하지 않은 연도 또는 월입니다."}), 400

        # [수정] prod_year, prod_month 기준으로 조회
        schedules = ProductionSchedule.query.filter_by(
                    prod_year=year_int,
                    prod_month=prod_month_int
                ).all()
                
        if not schedules:
            return jsonify([])

        # --- 1단계: '모델명 + 주문키(order_month)' 기준 그룹화 ---
        # order_month는 같은 모델의 서로 다른 주문을 구별하는 보조 키로만 사용
        grouped_by_model = {}
        orders_accounted_for = {}
        for s in schedules:
            model_name = s.model
            # 같은 모델이라도 주문월이 다르면 별개 주문이므로 구별
            group_key = (s.model, s.order_month, s.order_year)
            if group_key not in grouped_by_model:
                grouped_by_model[group_key] = {
                    'model': s.model,
                    'order_month': s.order_month,
                    'order_year': s.order_year,
                    'Top_Prod': 0, 'Bot_Prod': 0, 'T/O_Prod': 0, 'B/O_Prod': 0,
                    'TB_Prod': 0,  # T/B (Top+Bot 동시 작업)
                    'Total_Qty': 0
                }
                orders_accounted_for[group_key] = set()
            
            if s.tb == 'Top':
                grouped_by_model[group_key]['Top_Prod'] += s.actual_prod
            elif s.tb == 'Bot':
                grouped_by_model[group_key]['Bot_Prod'] += s.actual_prod
            elif s.tb == 'T/B':
                grouped_by_model[group_key]['TB_Prod']  += s.actual_prod
            elif s.tb == 'T/O':
                grouped_by_model[group_key]['T/O_Prod'] += s.actual_prod
            elif s.tb == 'B/O':
                grouped_by_model[group_key]['B/O_Prod'] += s.actual_prod
            
            lot_key = (s.model, s.total_quantity, s.order_year, s.order_month)
            if lot_key not in orders_accounted_for[group_key]:
                grouped_by_model[group_key]['Total_Qty'] += s.total_quantity
                orders_accounted_for[group_key].add(lot_key)

        # --- 2단계: MIN/MAX 로직 및 '상태' 판별 ---
        final_list = []
        for group_key, data in grouped_by_model.items():
            
            final_actual_prod = 0
            is_pair_product   = False

            tb_prod  = data['TB_Prod']
            top_prod = data['Top_Prod']
            bot_prod = data['Bot_Prod']
            to_prod  = data['T/O_Prod']
            bo_prod  = data['B/O_Prod']

            if to_prod > 0 or bo_prod > 0:
                # T/O 또는 B/O가 존재하면 단순 합산 (단면 전용 작업 포함)
                final_actual_prod = to_prod + bo_prod + top_prod + bot_prod + tb_prod
            elif tb_prod > 0 and top_prod == 0 and bot_prod == 0:
                # T/B 단독: Top+Bot 동시 작업이므로 그대로 합산 (페어 개념 불필요)
                final_actual_prod = tb_prod
            elif tb_prod > 0:
                # T/B와 별도 Top/Bot 혼재: T/B는 합산, 나머지는 페어 min 계산
                final_actual_prod = tb_prod + min(top_prod, bot_prod)
                is_pair_product   = (top_prod != bot_prod)
            else:
                # Top/Bot만 있는 기존 페어 제품
                is_pair_product   = True
                final_actual_prod = min(top_prod, bot_prod)

            total_qty = data['Total_Qty']
            status = "normal" 
            
            if is_pair_product and (top_prod != bot_prod) and (final_actual_prod == total_qty):
                status = "imbalance"
            elif final_actual_prod != total_qty:
                status = "shortage"
            
            fulfillment_rate = 0
            if total_qty > 0:
                fulfillment_rate = (final_actual_prod / total_qty) * 100
            
            final_list.append({
                "model":             data['model'],
                "orderMonth":        data['order_month'],   # 모달에서 주문 구별용으로만 사용
                "orderYear":         data['order_year'],
                "prodYear":          year_int,
                "prodMonth":         prod_month_int,
                "totalQuantity":     total_qty,
                "actualProduction":  final_actual_prod,
                "fulfillmentRate":   fulfillment_rate,
                "status":            status
            })

        return jsonify(final_list)
    
    except Exception as e:
        print(f"Error in get_order_month_summary: {e}")
        return jsonify({"error": str(e)}), 500
    

@bp.route('/model_details', methods=['GET'])
def get_model_details():
    try:
        # 1. 프론트엔드에서 보낸 3개의 '키'를 받습니다.
        model_name = request.args.get('model')
        order_year = request.args.get('year')
        order_month = request.args.get('month')

        if not all([model_name, order_year, order_month]):
            return jsonify({"error": "필수 파라미터가 누락되었습니다."}), 400

        # 2. DB에서 이 3개의 키와 일치하는 '모든' 원본 데이터를 조회합니다.
        schedules = ProductionSchedule.query.filter_by(
            model=model_name,
            order_year=order_year,
            order_month=order_month
        ).order_by( # 주차별, 라인별로 정렬해서 보기 좋게
            ProductionSchedule.prod_week, 
            ProductionSchedule.line
        ).all()

        if not schedules:
            return jsonify([])

        # 3. 원본 데이터를 'to_dict'로 변환하여 그대로 반환합니다. (MIN/MAX 적용 안 함)
        result = [s.to_dict() for s in schedules]
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Error in get_model_details: {e}")
        return jsonify({"error": str(e)}), 500
    
# -------------------------------------------------------------------------
# [신규 API] AOI 주간/월간 검사 기록 통합 조회
# -------------------------------------------------------------------------
@bp.route('/aoi_performance', methods=['GET'])
def get_aoi_period_stats():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not start_date or not end_date:
            return jsonify([])

        # 1. 해당 기간 내의 기록 조회 (기간 수량 계산용)
        period_records = AoiRecord.query.filter(
            AoiRecord.date >= start_date,
            AoiRecord.date <= end_date
        ).all()

        if not period_records:
            return jsonify([])

        # 2. 데이터 그룹화 (기간 내 합계 계산)
        aggregated_data = {}
        
        # 합산할 숫자 필드들
        sum_fields = [
            'inspection_qty', 'good_qty', 'total_defect',
            'missing', 'wrong', 'reverse', 'skewed', 'flipped',
            'damaged', 'manhattan', 'detached',
            'cold', 'unsoldered', 'short',
            'material', 'dip'
        ]
        # 합칠 문자열 필드들
        ref_fields = [
            'missing_ref', 'wrong_ref', 'reverse_ref', 'skewed_ref', 'flipped_ref',
            'damaged_ref', 'manhattan_ref', 'detached_ref',
            'cold_ref', 'unsoldered_ref', 'short_ref',
            'material_ref', 'dip_ref'
        ]

        for r in period_records:
            # 고유 주문 키: 모델, 연, 월, LOT
            key = (r.model, r.order_year, r.order_month, r.lot)

            if key not in aggregated_data:
                aggregated_data[key] = {
                    'model': r.model,
                    'order_year': r.order_year,
                    'order_month': r.order_month,
                    'lot': r.lot,
                    'inspection_point': r.inspection_point,
                    'dates': set()
                }
                for field in sum_fields:
                    aggregated_data[key][field] = 0
                for field in ref_fields:
                    aggregated_data[key][field] = []

            target = aggregated_data[key]
            target['dates'].add(r.date)

            # (1) 기간 내 수량 합산
            for field in sum_fields:
                val = getattr(r, field) or 0
                target[field] += val
            
            # (2) 레퍼런스 수집
            for field in ref_fields:
                val = getattr(r, field)
                if val:
                    refs = [x.strip() for x in val.split(',') if x.strip()]
                    target[field].extend(refs)

        # 3. 최종 리스트 변환 및 [누적 진행률] 계산
        result_list = []
        for key, data in aggregated_data.items():
            # 레퍼런스 병합
            for field in ref_fields:
                if data[field]:
                    unique_refs = sorted(list(set(data[field])))
                    data[field] = ", ".join(unique_refs)
                else:
                    data[field] = ""
            
            # 기간 정보 텍스트
            date_list = sorted(list(data['dates']))
            if len(date_list) > 1:
                data['period_info'] = f"{date_list[0]} ~ {date_list[-1]}"
            else:
                data['period_info'] = date_list[0]
            del data['dates']

            # ★★★ [핵심 수정] 해당 주문(LOT)의 전체 누적 검사 수량 조회 ★★★
            # 기간 상관없이 DB 전체에서 해당 모델+LOT의 검사 수량을 조회합니다.
            total_cumulative = db.session.query(func.sum(AoiRecord.inspection_qty)).filter_by(
                model=data['model'],
                order_year=data['order_year'],
                order_month=data['order_month'],
                lot=data['lot']
            ).scalar() or 0
            
            # 결과에 누적 수량 추가 (프론트엔드 진행률 바에서 사용)
            data['cumulative_qty'] = total_cumulative

            result_list.append(data)

        return jsonify(result_list)

    except Exception as e:
        print(f"Error stats: {e}")
        return jsonify([])