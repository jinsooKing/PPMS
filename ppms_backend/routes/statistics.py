from flask import Blueprint, request, jsonify
# [중요] models.py에서 ProductionSchedule 모델을 가져옵니다.
from models import db, ProductionSchedule

# [신규] 'statistics' 블루프린트를 '/api/statistics' 주소로 생성합니다.
bp = Blueprint('statistics', __name__, url_prefix='/api/statistics')

@bp.route('/order_month_summary', methods=['GET'])
def get_order_month_summary():
    try:
        order_month = request.args.get('order_month')
        year_str = request.args.get('year')

        if not all([order_month, year_str]):
            return jsonify({"error": "주문월과 주문 년도를 모두 선택해주세요."}), 400
        
        try:
            year_int = int(year_str)
        except ValueError:
            return jsonify({"error": "유효하지 않은 연도입니다."}), 400

        schedules = ProductionSchedule.query.filter_by(
                    order_month=order_month,
                    order_year=year_int 
                ).all()
                
        if not schedules:
            return jsonify([])

        # --- 1단계: '모델명' 기준 그룹화 및 합산 (기존과 동일) ---
        grouped_by_model = {}
        orders_accounted_for = {}
        for s in schedules:
            model_name = s.model
            order_key = (s.model, s.total_quantity, s.order_year) 
            if model_name not in grouped_by_model:
                grouped_by_model[model_name] = {
                    'Top_Prod': 0, 'Bot_Prod': 0, 'T/O_Prod': 0, 'B/O_Prod': 0,
                    'Total_Qty': 0
                }
                orders_accounted_for[model_name] = set()
            
            if s.tb == 'Top':
                grouped_by_model[model_name]['Top_Prod'] += s.actual_prod
            elif s.tb == 'Bot':
                grouped_by_model[model_name]['Bot_Prod'] += s.actual_prod
            elif s.tb == 'T/O':
                grouped_by_model[model_name]['T/O_Prod'] += s.actual_prod
            elif s.tb == 'B/O':
                grouped_by_model[model_name]['B/O_Prod'] += s.actual_prod
            
            if order_key not in orders_accounted_for[model_name]:
                grouped_by_model[model_name]['Total_Qty'] += s.total_quantity
                orders_accounted_for[model_name].add(order_key)

        # --- 2단계: MIN/MAX 로직 및 '상태' 판별 ---
        final_list = []
        for model_name, data in grouped_by_model.items():
            
            final_actual_prod = 0
            
            # ▼▼▼ [수정] 'is_pair_product' 변수를 여기서 'False'로 초기화합니다. ▼▼▼
            is_pair_product = False 

            if data['T/O_Prod'] > 0 or data['B/O_Prod'] > 0:
                final_actual_prod = data['T/O_Prod'] + data['B/O_Prod'] + data['Top_Prod'] + data['Bot_Prod']
            else:
                is_pair_product = True # [수정] '페어 제품'임
                final_actual_prod = min(data['Top_Prod'], data['Bot_Prod'])

            # --- 3단계: '총 주문량' 및 '상태' 정의 (기존과 동일) ---
            total_qty = data['Total_Qty']
            status = "normal" 
            
            if is_pair_product and (data['Top_Prod'] != data['Bot_Prod']) and (final_actual_prod == total_qty):
                status = "imbalance" # '숨겨진 잉여' (빨간색)
            elif final_actual_prod != total_qty:
                status = "shortage" # '수량 불일치' (노란색)
            
            # --- 4단계: 최종 달성률 계산 (기존과 동일) ---
            fulfillment_rate = 0
            if total_qty > 0:
                fulfillment_rate = (final_actual_prod / total_qty) * 100
            
            final_list.append({
                "model": model_name,
                "orderMonth": order_month,
                "orderYear": year_int,
                "totalQuantity": total_qty,
                "actualProduction": final_actual_prod,
                "fulfillmentRate": fulfillment_rate,
                "status": status # '상태' 필드
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