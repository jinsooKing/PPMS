/* calendar_day.js - 동적 높이 조절 및 현재 월 초기화 적용 버전 */

let dayPickerState = {
    currentYear: new Date().getFullYear(),
    currentMonth: new Date().getMonth() + 1,
    callback: null,
    anchorBtn: null // [추가] 위치 보정을 위해 현재 활성화된 버튼을 기억
};

function setupDatePicker(btnId, onSelectCallback) {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    const popupId = 'custom-calendar-popup-day'; 
    
    // 1. 팝업 HTML 생성
    if (!document.getElementById(popupId)) {
        const popupHtml = `
            <div id="${popupId}" class="custom-calendar-popup day-mode-popup">
                <div class="calendar-header">
                    <button class="calendar-nav-btn" id="day-prev-btn"><i class="uil uil-angle-left"></i></button>
                    <span id="day-calendar-title" style="font-weight:bold;"></span>
                    <button class="calendar-nav-btn" id="day-next-btn"><i class="uil uil-angle-right"></i></button>
                </div>
                <div class="calendar-days-header">
                    <span style="color:#ff4444">일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span>토</span>
                </div>
                <div class="calendar-body" id="day-calendar-body"></div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', popupHtml);
        
        document.getElementById('day-prev-btn').onclick = (e) => { e.stopPropagation(); changeDayMonth(-1); };
        document.getElementById('day-next-btn').onclick = (e) => { e.stopPropagation(); changeDayMonth(1); };
        document.getElementById(popupId).addEventListener('click', (e) => e.stopPropagation());
    }

    const popup = document.getElementById(popupId);

    // 닫기 헬퍼 함수
    const hidePopup = () => {
        popup.classList.remove('visible');
        popup.style.display = '';
        popup.style.visibility = '';
        dayPickerState.anchorBtn = null; // 닫을 때 앵커 초기화
    };

    // 2. 버튼 클릭 이벤트
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        
        // 열려있으면 닫기
        if (popup.classList.contains('visible')) {
            hidePopup();
            return;
        }

        // 다른 팝업 정리
        document.querySelectorAll('.custom-calendar-popup').forEach(el => {
            el.classList.remove('visible');
            el.style.display = '';
        });

        // [핵심 1] 열 때마다 '현재 월'로 상태 리셋
        const now = new Date();
        dayPickerState.currentYear = now.getFullYear();
        dayPickerState.currentMonth = now.getMonth() + 1;
        
        // 상태 설정
        dayPickerState.callback = onSelectCallback;
        dayPickerState.anchorBtn = btn; // 현재 버튼을 앵커로 등록

        // 높이 계산을 위해 미리 display:block 설정 (보이지는 않게)
        popup.style.visibility = 'hidden';
        popup.style.display = 'block';

        // 렌더링 및 위치 잡기
        renderDayCalendar(); 

        // 최종 표시
        popup.style.visibility = 'visible';
        popup.classList.add('visible');
    });

    // 외부 클릭 닫기
    document.addEventListener('click', (e) => {
        if (popup.classList.contains('visible') && !popup.contains(e.target) && e.target !== btn) {
            hidePopup();
        }
    });
}

function changeDayMonth(delta) {
    dayPickerState.currentMonth += delta;
    if (dayPickerState.currentMonth > 12) {
        dayPickerState.currentMonth = 1;
        dayPickerState.currentYear++;
    } else if (dayPickerState.currentMonth < 1) {
        dayPickerState.currentMonth = 12;
        dayPickerState.currentYear--;
    }
    // [핵심 2] 월 변경 시에도 렌더링 함수가 호출되어 위치를 재계산함
    renderDayCalendar();
}

function renderDayCalendar() {
    const body = document.getElementById('day-calendar-body');
    const title = document.getElementById('day-calendar-title');
    const { currentYear, currentMonth } = dayPickerState;

    // --- 달력 그리기 로직 ---
    title.textContent = `${currentYear}.${String(currentMonth).padStart(2,'0')}`;
    body.innerHTML = '';

    const firstDay = new Date(currentYear, currentMonth - 1, 1);
    const lastDay = new Date(currentYear, currentMonth, 0);
    const startDayOfWeek = firstDay.getDay();
    const totalDays = lastDay.getDate();

    let daysArray = [];
    for (let i = 0; i < startDayOfWeek; i++) daysArray.push({ type: 'empty' });
    for (let i = 1; i <= totalDays; i++) daysArray.push({ type: 'day', val: i });

    const grid = document.createElement('div');
    grid.className = 'day-calendar-grid';

    daysArray.forEach((dayObj, index) => {
        const cell = document.createElement('div');
        cell.className = 'day-cell';
        if (dayObj.type === 'day') {
            cell.textContent = dayObj.val;
            const today = new Date();
            if (currentYear === today.getFullYear() && currentMonth === today.getMonth() + 1 && dayObj.val === today.getDate()) {
                cell.classList.add('today');
            }
            if ((index % 7) === 0) cell.classList.add('sunday');
            cell.classList.add('clickable');
            cell.onclick = (e) => {
                e.stopPropagation();
                if (dayPickerState.callback) {
                    const dateStr = `${currentYear}-${String(currentMonth).padStart(2,'0')}-${String(dayObj.val).padStart(2,'0')}`;
                    dayPickerState.callback(dateStr);
                }
                // 닫기
                const popup = document.getElementById('custom-calendar-popup-day');
                popup.classList.remove('visible');
                popup.style.display = ''; 
                popup.style.visibility = '';
                dayPickerState.anchorBtn = null;
            };
        } else {
            cell.classList.add('empty');
        }
        grid.appendChild(cell);
    });
    body.appendChild(grid);

    // --- [핵심 3] 렌더링 직후 위치 재계산 (동적 높이 대응) ---
    if (dayPickerState.anchorBtn) {
        updatePopupPosition(dayPickerState.anchorBtn);
    }
}

// [신규] 팝업 위치 계산 전용 함수 (높이 변화에 대응)
function updatePopupPosition(btn) {
    const popup = document.getElementById('custom-calendar-popup-day');
    if (!popup) return;

    const rect = btn.getBoundingClientRect();
    const popupHeight = popup.offsetHeight; // 현재 렌더링된 높이 가져오기
    const popupWidth = 280;
    const spaceAbove = rect.top;

    popup.style.position = 'fixed';
    popup.style.bottom = 'auto'; 
    popup.style.right = 'auto';

    // 좌우 배치
    let leftPos = rect.right - popupWidth;
    if (leftPos < 10) leftPos = 10;
    popup.style.left = leftPos + 'px';

    // 상하 배치 (공간 확인 후 재설정)
    // 10px 여유를 두고 위쪽 공간이 충분하면 위로, 아니면 아래로
    if (spaceAbove > popupHeight + 10) {
        // 위로 열기 (높이가 변하면 top 위치가 바뀌어 버튼 위쪽 라인을 유지함)
        popup.style.top = (rect.top - popupHeight - 10) + 'px';
        popup.style.transformOrigin = "bottom right";
    } else {
        // 아래로 열기
        popup.style.top = (rect.bottom + 10) + 'px';
        popup.style.transformOrigin = "top right";
    }
}