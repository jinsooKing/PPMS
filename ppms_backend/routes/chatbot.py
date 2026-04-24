"""
PPMS KakaoTalk Chatbot - Webhook Handler
routes/chatbot.py
"""

import re
import calendar
from collections import defaultdict
from flask import Blueprint, request, Response
from extensions import db
from models import (AoiRecord, ProductionSchedule, SmdEquipmentCheck,
                    VisionInspection, EsdInspection, EnvironmentCheck, AcLeakageCheck)
from datetime import datetime, timedelta, date
import json

bp = Blueprint('chatbot', __name__)

# ─────────────────────────────────────────────────────────────────
# AOI 불량 컬럼 정의
# ─────────────────────────────────────────────────────────────────
DEFECT_COLS = [
    ('missing',    '미삽',    'missing_ref'),
    ('wrong',      '오삽',    'wrong_ref'),
    ('reverse',    '극성불량', 'reverse_ref'),
    ('skewed',     '틀어짐',  'skewed_ref'),
    ('flipped',    '뒤집힘',  'flipped_ref'),
    ('damaged',    '파손',    'damaged_ref'),
    ('manhattan',  '맨하탄',  'manhattan_ref'),
    ('detached',   '들뜸',    'detached_ref'),
    ('cold',       '냉납',    'cold_ref'),
    ('unsoldered', '미납',    'unsoldered_ref'),
    ('short',      '단락',    'short_ref'),
    ('lifted',     '리프팅',  'lifted_ref'),
    ('material',   '재료불량', 'material_ref'),
    ('dip',        'DIP불량', 'dip_ref'),
]

def _sec(name):
    """섹션 헤더 포맷: [ 섹션명 ]"""
    return f"[ {name} ]"


# ─────────────────────────────────────────────────────────────────
# 카카오 응답 헬퍼
# ─────────────────────────────────────────────────────────────────
def kakao_response(data):
    return Response(
        json.dumps(data, ensure_ascii=False),
        content_type='application/json; charset=utf-8'
    )

def kakao_text(text, back_msg=None):
    """텍스트 응답 + 이전/홈 버튼"""
    quick = []
    if back_msg:
        quick.append({"label": "이전", "action": "message", "messageText": back_msg})
    quick.append({"label": "메인 메뉴", "action": "message", "messageText": "메뉴"})
    return kakao_response({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}],
            "quickReplies": quick[:10]
        }
    })

def kakao_buttons(text, buttons, back_msg=None, show_home=True):
    """버튼 응답. 이전/홈 자동 추가 (총 10개 제한)"""
    all_btns = list(buttons)
    if back_msg:
        all_btns.append({"label": "이전", "action": "message", "messageText": back_msg})
    if show_home:
        all_btns.append({"label": "메인 메뉴", "action": "message", "messageText": "메뉴"})
    return kakao_response({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}],
            "quickReplies": all_btns[:10]
        }
    })


# ─────────────────────────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────────────────────────
def _clean(text):
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', text).lower()

def _current_prod_week():
    now  = datetime.now()
    week = (now.day - 1) // 7 + 1
    return now.year, now.month, week

def _week_date_range(year, month, week):
    start_day = (week - 1) * 7 + 1
    last_day  = calendar.monthrange(year, month)[1]
    end_day   = min(week * 7, last_day)
    return (
        date(year, month, start_day).strftime('%Y-%m-%d'),
        date(year, month, end_day).strftime('%Y-%m-%d')
    )

def _truncate(text, limit=950):
    return text if len(text) <= limit else text[:limit] + "\n...(이하 생략)"

def _btn(label, msg):
    return {"label": label[:14], "action": "message", "messageText": msg}


def kakao_list_card(title, items, buttons=None):
    """
    listCard 응답 - 모델명 등 긴 텍스트를 버튼보다 넓게 표시 가능
    items: [{"title": "모델명", "description": "설명", "action": "message", "messageText": "전송"}]
    buttons: quickReplies 버튼 목록 (선택)
    """
    card = {
        "listCard": {
            "header": {"title": title},
            "items":  items[:5],   # listCard 최대 5개
        }
    }
    response = {
        "version": "2.0",
        "template": {
            "outputs": [card],
        }
    }
    if buttons:
        response["template"]["quickReplies"] = buttons[:10]
    return kakao_response(response)

def _month_key(s):
    try:
        return int(re.sub(r'[^0-9]', '', s))
    except:
        return 99

def _normalize_month(m):
    # '1' -> '1월분', '3월분' -> '3월분'
    m = str(m).strip()
    if m.endswith('월분'):
        return m
    num = re.sub(r'[^0-9]', '', m)
    return f"{num}월분" if num else m

def _month_variants(month_str):
    # '1월분' -> ['1', '1월분'] 원본 패턴 모두 반환
    num = re.sub(r'[^0-9]', '', str(month_str))
    if not num:
        return [month_str]
    return [num, f"{num}월분"]

def _lot_total_int(lot_str):
    """
    lot 문자열에서 전체 LOT 숫자를 반환.
    '500/2000' -> 2000 / '1500' -> 1500
    """
    if not lot_str:
        return 0
    s   = str(lot_str).strip()
    val = s.split('/', 1)[-1].strip()
    return int(val) if val.isdigit() else 0


def _defect_per_lot(records):
    """
    AOI 불량 집계 (고유주문 기준)
    반환: (total_defect, lot_order_count, total_lot_qty, rate)
      - total_defect    : 총 불량 수
      - lot_order_count : 고유주문 개수 (검사 LOT수 표시용)
      - total_lot_qty   : 전체 LOT 수량 합산 (불량률 분모)
      - rate            : 총불량수 / total_lot_qty * 100 (%)

    예) '500/2000' 배치 2개, '300/1500' 배치 1개
      → 고유주문 2개, 전체 LOT 수량 3500개
    """
    total_defect = sum(r.total_defect or 0 for r in records)

    # 고유주문 키: (model, order_year, order_month, 전체LOT문자열)
    seen = {}
    for r in records:
        tp  = str(r.lot or '').split('/', 1)[-1].strip()
        key = (r.model, r.order_year, r.order_month, tp)
        if key not in seen:
            seen[key] = int(tp) if tp.isdigit() else 0

    lot_order_count = len(seen)               # 고유주문 개수
    total_lot_qty   = sum(seen.values()) or 1 # 전체 LOT 수량 합산
    rate = round(total_defect / total_lot_qty * 100, 1)
    return total_defect, lot_order_count, total_lot_qty, rate

def _match(text, keywords):
    return any(kw in text.lower() for kw in keywords)


# ─────────────────────────────────────────────────────────────────
# 메인 Webhook
# ─────────────────────────────────────────────────────────────────
@bp.route('/api/chatbot', methods=['POST'])
def chatbot():
    body      = request.get_json(silent=True) or {}
    utterance = body.get('userRequest', {}).get('utterance', '').strip()

    if _match(utterance, ['메뉴', '시작', '처음', '안녕', 'hello', 'hi']):
        return _menu()

    if _match(utterance, ['생산일정', '일정조회']):
        return _schedule_current_week()

    if utterance == 'aoi조회':
        return _aoi_menu()

    if utterance == '현재주차aoi':
        return _aoi_current_week()

    if utterance == '주문단위aoi':
        return _aoi_order_year_select()

    if utterance.startswith('aoi연도_'):
        parts = utterance.split('_', 1)
        if len(parts) == 2 and parts[1].isdigit():
            return _aoi_order_month_select(int(parts[1]))
        return _aoi_menu()

    if utterance.startswith('aoi결과_'):
        parts = utterance.split('_', 2)
        if len(parts) == 3:
            return _aoi_final(int(parts[1]), parts[2])
        return _aoi_menu()

    if _match(utterance, ['불량조회', '실시간불량', '중복불량']):
        return _defect_duplicate()

    if _match(utterance, ['점검현황', '점검상태', '미완료점검']):
        return _inspection_status()

    if utterance.startswith('모델상세_'):
        return _model_detail(utterance[len('모델상세_'):])

    if utterance.startswith('모델목록_'):
        parts = utterance.split('_', 2)
        if len(parts) == 3:
            return _model_search_list(parts[1], int(parts[2]))
        return _menu()

    if utterance:
        return _model_search_list(utterance, 0)

    return _menu()


# ─────────────────────────────────────────────────────────────────
# 1. 메인 메뉴
# ─────────────────────────────────────────────────────────────────
def _menu():
    text = (
        "원하는 메뉴를 선택하거나\n"
        "모델명을 직접 입력하세요.\n\n"
        "[생산일정 조회] 현재 주차\n"
        "[AOI 조회]\n"
        "[실시간 불량조회] 현재 주차\n"
        "[점검 현황]"
    )
    buttons = [
        _btn("생산일정 조회",   "생산일정 조회"),
        _btn("AOI 조회",        "aoi조회"),
        _btn("실시간 불량조회", "불량조회"),
        _btn("점검 현황",       "점검현황"),
    ]
    return kakao_buttons(text, buttons, show_home=False)


# ─────────────────────────────────────────────────────────────────
# 2. 생산일정 조회 (현재 주차)
# ─────────────────────────────────────────────────────────────────
def _schedule_current_week():
    year, month, week = _current_prod_week()

    records = ProductionSchedule.query.filter(
        ProductionSchedule.prod_year  == year,
        ProductionSchedule.prod_month == month,
        ProductionSchedule.prod_week  == week
    ).order_by(ProductionSchedule.line).all()

    if not records:
        return kakao_text(
            f"{year}년 {month}월 {week}주차 생산일정\n\n"
            "등록된 일정이 없습니다.",
            back_msg="메뉴"
        )

    lines = []
    for r in records:
        plan   = r.total_quantity or 0
        actual = r.actual_prod    or 0
        assy   = r.assy_actual    or 0
        mgr    = r.manager        or '-'
        rate   = int(actual / plan * 100) if plan > 0 else 0
        entry  = (
            f"{_sec(r.line)}\n"
            f"모델: {r.model or '-'}\n"
            f"생산: {actual:,}/{plan:,}개 ({rate}%)\n"
            f"조립: {assy:,}개  담당: {mgr}"
        )
        if r.notes:
            entry += f"\n비고: {r.notes}"
        lines.append(entry)

    text = (
        f"{year}년 {month}월 {week}주차 생산일정\n\n"
        + '\n\n'.join(lines)
    )
    return kakao_text(_truncate(text), back_msg="메뉴")


# ─────────────────────────────────────────────────────────────────
# 3. AOI 조회
# ─────────────────────────────────────────────────────────────────
def _aoi_menu():
    text = (
        "AOI 조회\n\n"
        "조회 방식을 선택하세요."
    )
    buttons = [
        _btn("현재주차 AOI", "현재주차aoi"),
        _btn("주문단위 AOI", "주문단위aoi"),
    ]
    return kakao_buttons(text, buttons, back_msg="메뉴")


def _aoi_current_week():
    year, month, week = _current_prod_week()
    start, end = _week_date_range(year, month, week)

    records = AoiRecord.query.filter(
        AoiRecord.date >= start,
        AoiRecord.date <= end
    ).all()

    if not records:
        return kakao_text(
            f"{year}년 {month}월 {week}주차 AOI\n\n"
            "조회된 기록이 없습니다.",
            back_msg="aoi조회"
        )

    return _build_aoi_analysis(
        records,
        title=f"{year}년 {month}월 {week}주차 AOI 분석",
        back_msg="aoi조회"
    )


def _aoi_order_year_select():
    years = db.session.query(AoiRecord.order_year).filter(
        AoiRecord.order_year != None
    ).distinct().order_by(AoiRecord.order_year.desc()).all()

    years = [y[0] for y in years if y[0]]
    if not years:
        return kakao_text("AOI 기록이 없습니다.", back_msg="aoi조회")

    buttons = [_btn(f"{y}년", f"aoi연도_{y}") for y in years[:8]]
    return kakao_buttons(
        "주문단위 AOI 조회\n\n조회할 연도를 선택하세요.",
        buttons, back_msg="aoi조회"
    )


def _aoi_order_month_select(year):
    months = db.session.query(AoiRecord.order_month).filter(
        AoiRecord.order_year  == year,
        AoiRecord.order_month != None
    ).distinct().all()  # raw results

    # 정규화 후 중복 제거 ('1' 과 '1월분' -> '1월분' 하나만)
    norm_set = {}
    for (m,) in months:
        if not m:
            continue
        norm = _normalize_month(m)
        norm_set[norm] = norm

    months_norm = sorted(norm_set.keys(), key=_month_key, reverse=True)
    if not months_norm:
        return kakao_text(
            f"{year}년 AOI 기록이 없습니다.",
            back_msg="주문단위aoi"
        )

    buttons = [_btn(m, f"aoi결과_{year}_{m}") for m in months_norm[:8]]
    return kakao_buttons(
        f"{year}년 주문단위 AOI\n\n조회할 주문월을 선택하세요.",
        buttons, back_msg="주문단위aoi"
    )


def _aoi_final(year, month_str):
    # '1월분' -> ['1', '1월분'] 모두 포함해서 조회
    variants = _month_variants(month_str)
    records = AoiRecord.query.filter(
        AoiRecord.order_year  == year,
        AoiRecord.order_month.in_(variants)
    ).all()

    if not records:
        return kakao_text(
            f"{year}년 {month_str} AOI\n\n"
            "조회된 기록이 없습니다.",
            back_msg=f"aoi연도_{year}"
        )

    return _build_aoi_analysis(
        records,
        title=f"{year}년 {month_str} AOI 분석",
        back_msg=f"aoi연도_{year}"
    )


def _build_aoi_analysis(records, title, back_msg):
    # 고유주문 키: (model, order_year, order_month, 전체LOT문자열)
    order_map = defaultdict(lambda: {
        'lot_qty':    0,
        'lot_count':  0,
        'defect':     0,
        'defect_map': defaultdict(int),
    })

    for r in records:
        tp    = str(r.lot or '').split('/', 1)[-1].strip()
        lot_n = int(tp) if tp.isdigit() else 0
        key   = (r.model, r.order_year, r.order_month, tp)

        s = order_map[key]
        if s['lot_qty'] == 0:
            s['lot_qty'] = lot_n
        s['lot_count'] += 1
        s['defect']    += r.total_defect or 0
        for col, name, _ in DEFECT_COLS:
            cnt = getattr(r, col, 0) or 0
            if cnt > 0:
                s['defect_map'][name] += cnt

    # 불량률 계산 후 정렬 (높은 순)
    order_list = []
    for (model, yr, mo, tp), s in order_map.items():
        lot_qty = s['lot_qty'] or 1
        rate    = round(s['defect'] / lot_qty * 100, 1)
        order_list.append({
            'model':      model,
            'lot_qty':    s['lot_qty'],
            'lot_count':  s['lot_count'],
            'defect':     s['defect'],
            'rate':       rate,
            'defect_map': dict(s['defect_map']),
        })

    order_list.sort(key=lambda x: x['rate'], reverse=True)

    total_orders  = len(order_list)
    display_list  = order_list[:5]

    lines = [f"{title}\n"]

    for o in display_list:
        top_defects = sorted(o['defect_map'].items(), key=lambda x: x[1], reverse=True)[:3]
        defect_str  = ', '.join(f"{k} {v}건" for k, v in top_defects) or "없음"

        lines.append(
            f"{_sec(o['model'])}\n"
            f"  LOT: {o['lot_qty']:,}개 ({o['lot_count']}배치)\n"
            f"  불량: {o['defect']}건 / 불량률: {o['rate']}%\n"
            f"  주요불량: {defect_str}"
        )

    if total_orders > 5:
        lines.append(f"\n  외 {total_orders - 5}개 모델 생략")

    return kakao_text(_truncate('\n\n'.join(lines)), back_msg=back_msg)


# ─────────────────────────────────────────────────────────────────
# 4. 실시간 불량조회 (오늘 AOI 기록)
# ─────────────────────────────────────────────────────────────────
def _defect_duplicate():
    today = date.today().strftime('%Y-%m-%d')

    records = AoiRecord.query.filter(
        AoiRecord.date == today
    ).all()

    if not records:
        return kakao_text(
            f"실시간 불량조회\n{today}\n\n오늘 AOI 기록이 없습니다.",
            back_msg="메뉴"
        )

    return _build_aoi_analysis(
        records,
        title=f"실시간 불량조회\n{today}",
        back_msg="메뉴"
    )


# ─────────────────────────────────────────────────────────────────
# 5. 모델 검색 및 상세
# ─────────────────────────────────────────────────────────────────
PAGE_SIZE = 6

def _model_search_list(query, page):
    cleaned = _clean(query)
    if not cleaned:
        return _menu()

    cutoff = datetime.now().year - 3
    all_models = db.session.query(ProductionSchedule.model).filter(
        ProductionSchedule.model     != None,
        ProductionSchedule.model     != '',
        ProductionSchedule.prod_year >= cutoff
    ).distinct().all()

    matches = sorted(set(
        m[0] for m in all_models
        if m[0] and cleaned in _clean(m[0])
    ))

    if not matches:
        return kakao_text(
            f"'{query}' 검색 결과\n\n"
            "일치하는 모델이 없습니다.\n"
            "다른 모델명을 입력해 주세요.",
            back_msg="메뉴"
        )

    if len(matches) == 1:
        return _model_detail(matches[0])

    total      = len(matches)
    total_page = (total + PAGE_SIZE - 1) // PAGE_SIZE
    start      = page * PAGE_SIZE
    end        = min(start + PAGE_SIZE, total)

    # listCard: 모델명 전체 표시 (최대 5개 / 페이지)
    items = [
        {
            "title":       m,
            "description": "모델 상세 조회",
            "action":      "message",
            "messageText": f"모델상세_{m}"
        }
        for m in matches[start:end]
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(_btn("이전 페이지", f"모델목록_{query}_{page-1}"))
    if end < total:
        nav_buttons.append(_btn("다음 페이지", f"모델목록_{query}_{page+1}"))
    nav_buttons.append({"label": "메인 메뉴", "action": "message", "messageText": "메뉴"})

    return kakao_list_card(
        title=f"'{query}' {page+1}/{total_page}p (총{total}개)",
        items=items,
        buttons=nav_buttons
    )


def _model_detail(model_name):
    cutoff_year = datetime.now().year - 3

    aoi_records = AoiRecord.query.filter(
        AoiRecord.model.ilike(f'%{model_name}%'),
        AoiRecord.order_year >= cutoff_year
    ).all()

    grouped = defaultdict(list)
    for r in aoi_records:
        grouped[(r.order_year, r.order_month)].append(r)

    high_defect = []
    for (yr, mo), recs in grouped.items():
        total_defect, lot_order_count, total_lot_qty, rate = _defect_per_lot(recs)
        if rate >= 5.0:
            defects = {
                name: sum(getattr(r, col, 0) or 0 for r in recs)
                for col, name, _ in DEFECT_COLS
                if sum(getattr(r, col, 0) or 0 for r in recs) > 0
            }
            high_defect.append({
                'year': yr, 'month': mo,
                'rate': rate, 'total': total_defect,
                'lot_count': lot_order_count,
                'lot_qty': total_lot_qty,
                'defects': defects
            })

    high_defect.sort(
        key=lambda x: (x['year'], _month_key(x['month'] or '')),
        reverse=True
    )

    note_records = ProductionSchedule.query.filter(
        ProductionSchedule.model.ilike(f'%{model_name}%'),
        ProductionSchedule.notes != None,
        ProductionSchedule.notes != ''
    ).order_by(
        ProductionSchedule.prod_year.desc(),
        ProductionSchedule.prod_month.desc()
    ).limit(5).all()

    lines = [f"{model_name} 모델 상세\n"]

    if high_defect:
        lines.append(f"{_sec('불량/LOT 5.0 이상 주문월')} (최근 3년)")
        for m in high_defect[:5]:
            defect_str = ', '.join(f"{k} {v}건" for k, v in m['defects'].items())
            lines.append(
                f"\n  {m['year']}년 {m['month']}\n"
                f"  불량률: {m['rate']}%  "
                f"(총 {m['total']}건 / {m['lot_count']}LOT / {m['lot_qty']:,}개)\n"
                f"  {defect_str}"
            )
    else:
        lines.append(f"{_sec('불량률 이력')}\n  최근 3년 불량률 5% 이상 없음")

    lines.append("")

    if note_records:
        lines.append(f"{_sec('비고')} (최근 {len(note_records)}건)")
        for r in note_records:
            lines.append(
                f"\n  {r.prod_year}년 {r.prod_month}월 {r.line}\n"
                f"  {r.notes}"
            )
    else:
        lines.append(f"{_sec('비고')}\n  등록된 비고 없음")

    return kakao_text(_truncate('\n'.join(lines)), back_msg="메뉴")


# ─────────────────────────────────────────────────────────────────
# 6. 점검 현황 (수동 조회)
# ─────────────────────────────────────────────────────────────────
def _inspection_status():
    today      = date.today()
    incomplete = _get_incomplete_daily(today)

    if not incomplete:
        return kakao_text(
            f"점검 현황\n{today}\n\n"
            "오늘 모든 점검 완료.",
            back_msg="메뉴"
        )

    items = '\n'.join(f"  - {item}" for item in incomplete)
    text  = (
        f"점검 현황\n{today}\n\n"
        f"{_sec('미완료 항목')} ({len(incomplete)}건)\n"
        f"{items}"
    )
    return kakao_text(text, back_msg="메뉴")


def _get_incomplete_daily(target_date):
    incomplete = []

    # 비전 점검
    for mid in [1, 2]:
        if not VisionInspection.query.filter_by(
            date=target_date, machine_id=mid
        ).first():
            incomplete.append(f"비전검사 {mid}호기")

    # SMD 설비 점검 - 단일 항목
    done_count = db.session.query(SmdEquipmentCheck.id).filter(
        SmdEquipmentCheck.date   == target_date,
        SmdEquipmentCheck.status != ''
    ).count()
    if done_count == 0:
        incomplete.append("SMD 일일 설비 점검")

    # 환경 점검
    done_env = {e[0] for e in db.session.query(EnvironmentCheck.check_type).filter(
        EnvironmentCheck.date == target_date
    ).distinct().all()}
    for ct, label in [
        ('fridge',  '냉장고 온도'),
        ('room',    '실내 온습도'),
        ('dehumid', '제습함 온습도')
    ]:
        if ct not in done_env:
            incomplete.append(f"환경점검 - {label}")

    # ESD(제전화) 점검 - 담당자별
    from models import Manager
    all_managers = Manager.query.order_by(Manager.name).all()
    done_mgr_ids = {e[0] for e in db.session.query(EsdInspection.manager_id).filter(
        EsdInspection.date == target_date
    ).distinct().all()}
    for mgr in all_managers:
        if mgr.id not in done_mgr_ids:
            incomplete.append(f"제전화 점검 - {mgr.name}")

    return incomplete