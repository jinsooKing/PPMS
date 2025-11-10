from flask import Blueprint, request, jsonify
# [중요] models.py에서 ProductionSchedule 모델을 가져옵니다.
from models import db, ProductionSchedule

# [신규] 'statistics' 블루프린트를 '/api/statistics' 주소로 생성합니다.
bp = Blueprint('statistics', __name__, url_prefix='/api/statistics')

@bp.route('/order_month_summary', methods=['GET'])
def get_order_month_summary():
    try:
        order_month = request.args.get('order_month')
        year = request.args.get('year')

        if not all([order_month, year]):
            return jsonify({"error": "주문월과 주문 년도를 모두 선택해주세요."}), 400

        schedules = ProductionSchedule.query.filter_by(
                    order_month=order_month,
                    order_year=year
                ).all()
                
        if not schedules:
            return jsonify([])

        grouped_by_model = {}
        orders_accounted_for = {}

        for s in schedules:
            model_name = s.model
            
            # ▼ [수정] '고유 주문 키'에 'order_year'를 추가합니다 (총 3개)
            order_key = (s.model, s.total_quantity, s.order_year) 
            
            if model_name not in grouped_by_model:
                grouped_by_model[model_name] = {
                    'Top_Prod': 0, 'Bot_Prod': 0, 'T/O_Prod': 0, 'B/O_Prod': 0,
                    'Total_Qty': 0
                }
                orders_accounted_for[model_name] = set()
            
            # 1-2. T/B 타입별 '실생산량(actual_prod)' 합산 (기존과 동일)
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

        # --- 2단계: 합산된(SUM) 결과를 바탕으로 MIN/MAX 로직 적용 (기존과 동일) ---
        final_list = []
        for model_name, data in grouped_by_model.items():
            
            final_actual_prod = 0
            if data['T/O_Prod'] > 0 or data['B/O_Prod'] > 0:
                final_actual_prod = data['T/O_Prod'] + data['B/O_Prod'] + data['Top_Prod'] + data['Bot_Prod']
            else:
                final_actual_prod = min(data['Top_Prod'], data['Bot_Prod'])

            # --- 3단계: 최종 달성률 계산 (기존과 동일) ---
            total_qty = data['Total_Qty'] # 이제 올바른 총 주문량 합계
            fulfillment_rate = 0
            if total_qty > 0:
                fulfillment_rate = (final_actual_prod / total_qty) * 100
            
            final_list.append({
                "model": model_name,
                "orderMonth": order_month,
                "orderYear": year,
                "totalQuantity": total_qty,
                "actualProduction": final_actual_prod,
                "fulfillmentRate": fulfillment_rate
            })

        return jsonify(final_list)
    
    except Exception as e:
        print(f"Error in get_order_month_summary: {e}")
        return jsonify({"error": str(e)}), 500