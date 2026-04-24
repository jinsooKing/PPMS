from flask import Blueprint, request, jsonify, render_template
from mobile_utils import mobile_render
from models import db, AoiRecord, RepairGroup, RepairBatch
from sqlalchemy import func, true
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
def now_kst():
    return datetime.now(KST).replace(tzinfo=None)

bp = Blueprint('repair', __name__, url_prefix='/api/repair')


# -------------------------------------------------------------------------
# [VIEW]
# -------------------------------------------------------------------------
@bp.route('/view', methods=['GET'])
def repair_view():
    return mobile_render('repair.html', 'mobile_repair.html')


# -------------------------------------------------------------------------
# [API 1] POST /sync?year=&month=
#   해당 월 AOI 스캔 → RepairGroup/Batch lazy creation → 해당 월 전체 반환
#   month 파라미터: "1월분" ~ "12월분" 형식 (AOI DB 저장 형식과 동일)
# -------------------------------------------------------------------------
@bp.route('/sync', methods=['POST'])
def sync_repair_groups():
    try:
        year  = request.args.get('year',  type=int)
        month = request.args.get('month', type=str)  # ex) "3월분"

        if not year or not month:
            return jsonify({'error': 'year, month 파라미터가 필요합니다.'}), 400

        # ── 해당 월 AOI 불량 레코드 집계 ──
        aoi_rows = (
            db.session.query(
                AoiRecord.model,
                AoiRecord.order_year,
                AoiRecord.order_month,
                AoiRecord.lot,
                func.sum(AoiRecord.total_defect).label('total_defect_sum')
            )
            .filter(
                AoiRecord.order_year  == year,
                AoiRecord.order_month == month,
                AoiRecord.total_defect > 0
            )
            .group_by(
                AoiRecord.model,
                AoiRecord.order_year,
                AoiRecord.order_month,
                AoiRecord.lot
            )
            .all()
        )

        new_groups  = 0
        new_batches = 0

        for row in aoi_rows:
            existing = RepairGroup.query.filter_by(
                model=row.model,
                order_year=row.order_year,
                order_month=row.order_month,
                lot=row.lot
            ).first()

            if not existing:
                # 신규 군집 생성
                group = RepairGroup(
                    model=row.model,
                    order_year=row.order_year,
                    order_month=row.order_month,
                    lot=row.lot,
                    status='active'
                )
                db.session.add(group)
                db.session.flush()

                aoi_records = AoiRecord.query.filter_by(
                    model=row.model,
                    order_year=row.order_year,
                    order_month=row.order_month,
                    lot=row.lot
                ).filter(AoiRecord.total_defect > 0).all()

                for rec in aoi_records:
                    db.session.add(RepairBatch(
                        group_id=group.id,
                        aoi_record_id=rec.id,
                        defect_qty=rec.total_defect or 0,
                        aoi_date=rec.date or ''
                    ))
                    new_batches += 1
                new_groups += 1

            else:
                # 기존 군집: 누락 배치만 추가
                existing_aoi_ids = {b.aoi_record_id for b in existing.batches}
                filter_cond = (
                    AoiRecord.id.notin_(existing_aoi_ids)
                    if existing_aoi_ids else true()
                )
                new_records = AoiRecord.query.filter_by(
                    model=row.model,
                    order_year=row.order_year,
                    order_month=row.order_month,
                    lot=row.lot
                ).filter(AoiRecord.total_defect > 0, filter_cond).all()

                for rec in new_records:
                    db.session.add(RepairBatch(
                        group_id=existing.id,
                        aoi_record_id=rec.id,
                        defect_qty=rec.total_defect or 0,
                        aoi_date=rec.date or ''
                    ))
                    new_batches += 1

        db.session.commit()

        # 해당 월 전체 그룹 반환
        groups = RepairGroup.query.filter_by(
            order_year=year, order_month=month
        ).order_by(RepairGroup.id.desc()).all()

        return jsonify({
            'success': True,
            'new_groups': new_groups,
            'new_batches': new_batches,
            'groups': [g.to_dict() for g in groups]
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({'error': str(e), 'detail': traceback.format_exc()}), 500


# -------------------------------------------------------------------------
# [API 2] 배치 완료 토글
# -------------------------------------------------------------------------
@bp.route('/batches/<int:batch_id>/toggle', methods=['PUT'])
def toggle_batch(batch_id):
    try:
        now = now_kst()

        # SELECT 없이 단일 UPDATE — is_done 반전, done_at 조건부 설정
        result = db.session.execute(
            db.text(
                "UPDATE repair_batches "
                "SET is_done = NOT is_done, "
                "    done_at = CASE WHEN is_done THEN :now ELSE NULL END "
                "WHERE id = :id"
            ),
            {'now': now, 'id': batch_id}
        )
        db.session.commit()

        if result.rowcount == 0:
            return jsonify({'success': False, 'message': 'batch not found'}), 404

        # 변경 후 상태 확인 (1행만 조회)
        row = db.session.execute(
            db.text("SELECT is_done, done_at FROM repair_batches WHERE id = :id"),
            {'id': batch_id}
        ).fetchone()

        is_done = bool(row.is_done)
        done_at = row.done_at.strftime('%Y-%m-%d %H:%M') if row.done_at else None

        return jsonify({'success': True, 'is_done': is_done, 'done_at': done_at})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# -------------------------------------------------------------------------
# [API 3] 군집 메모 저장
# -------------------------------------------------------------------------
@bp.route('/groups/<int:group_id>/notes', methods=['PUT'])
def update_group_notes(group_id):
    try:
        group = RepairGroup.query.get_or_404(group_id)
        group.notes = request.json.get('notes', '')
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# -------------------------------------------------------------------------
# [API 4] 배치 폐기 수량 저장
# -------------------------------------------------------------------------
@bp.route('/batches/<int:batch_id>/scrap', methods=['PUT'])
def update_batch_scrap(batch_id):
    try:
        batch = RepairBatch.query.get_or_404(batch_id)
        qty   = max(0, int(request.json.get('scrap_qty', 0)))
        batch.scrap_qty = qty
        db.session.commit()
        return jsonify({'success': True, 'scrap_qty': batch.scrap_qty})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500