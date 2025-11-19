/**
 * 공용 주차 선택 달력 (Week Picker) 모듈
 * @param {string} triggerBtnId - 달력을 띄울 버튼의 ID
 * @param {function} onSelectCallback - 날짜 선택 시 실행할 콜백 함수 (year, month, weekNum)
 */
function setupWeekPicker(triggerBtnId, onSelectCallback) {
    const triggerBtn = document.getElementById(triggerBtnId);
    if (!triggerBtn) return;

    // 1. 달력 HTML 동적 생성 (이미 없으면 생성)
    let calendarPopup = document.getElementById('custom-calendar-popup');
    if (!calendarPopup) {
        calendarPopup = document.createElement('div');
        calendarPopup.id = 'custom-calendar-popup';
        calendarPopup.className = 'custom-calendar-popup';
        calendarPopup.innerHTML = `
            <div class="calendar-header">
                <button class="calendar-nav-btn" id="cal-prev-month">&lt;</button>
                <span id="cal-current-month"></span>
                <button class="calendar-nav-btn" id="cal-next-month">&gt;</button>
            </div>
            <div class="calendar-days-header">
                <div>일</div><div>월</div><div>화</div><div>수</div><div>목</div><div>금</div><div>토</div>
            </div>
            <div class="calendar-body" id="cal-grid"></div>
        `;
        // 버튼 내부에 달력을 넣습니다 (위치 잡기 편함)
        triggerBtn.appendChild(calendarPopup);
    }

    // 요소 참조
    const calTitle = calendarPopup.querySelector('#cal-current-month');
    const calGrid = calendarPopup.querySelector('#cal-grid');
    const prevBtn = calendarPopup.querySelector('#cal-prev-month');
    const nextBtn = calendarPopup.querySelector('#cal-next-month');
    
    let calDate = new Date(); // 현재 달력 기준 날짜

    // 2. 렌더링 함수
    function render() {
        const year = calDate.getFullYear();
        const month = calDate.getMonth(); // 0~11
        calTitle.textContent = `${year}년 ${month + 1}월`;
        calGrid.innerHTML = '';

        const firstDayOfMonth = new Date(year, month, 1);
        const startDate = new Date(firstDayOfMonth);
        startDate.setDate(startDate.getDate() - startDate.getDay()); // 일요일부터 시작

        let currentDate = new Date(startDate);
        
        for (let i = 0; i < 6; i++) { // 6주 표시
            const row = document.createElement('div');
            row.className = 'calendar-week-row';
            
            // 주차 계산용 날짜 (목요일 기준)
            const weekCheckDate = new Date(currentDate);
            weekCheckDate.setDate(weekCheckDate.getDate() + 4); 
            
            const targetYear = weekCheckDate.getFullYear();
            const targetMonth = weekCheckDate.getMonth() + 1;
            const targetWeekNum = _getWeekNum(weekCheckDate);

            // 클릭 이벤트
            row.addEventListener('click', (e) => {
                e.stopPropagation();
                console.log(`[Calendar] 선택: ${targetYear}년 ${targetMonth}월 ${targetWeekNum}주차`);
                calendarPopup.classList.remove('visible');
                if (typeof onSelectCallback === 'function') {
                    onSelectCallback(targetYear, targetMonth, targetWeekNum);
                }
            });

            for (let j = 0; j < 7; j++) {
                const cell = document.createElement('div');
                cell.className = 'day-cell';
                cell.textContent = currentDate.getDate();
                if (currentDate.getMonth() !== month) cell.classList.add('other-month');
                if (currentDate.getDay() === 0) cell.classList.add('sunday');
                
                row.appendChild(cell);
                currentDate.setDate(currentDate.getDate() + 1);
            }
            calGrid.appendChild(row);
        }
    }

    // 3. 이벤트 리스너
    triggerBtn.addEventListener('click', (e) => {
        // 달력 내부 클릭 시 닫히지 않도록 방지
        if (e.target.closest('.custom-calendar-popup')) return;
        
        const isVisible = calendarPopup.classList.contains('visible');
        if (!isVisible) {
            render();
            calendarPopup.classList.add('visible');
        } else {
            calendarPopup.classList.remove('visible');
        }
    });

    // 외부 클릭 시 닫기
    document.addEventListener('click', (e) => {
        if (calendarPopup.classList.contains('visible') && !triggerBtn.contains(e.target)) {
            calendarPopup.classList.remove('visible');
        }
    });

    prevBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        calDate.setMonth(calDate.getMonth() - 1);
        render();
    });

    nextBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        calDate.setMonth(calDate.getMonth() + 1);
        render();
    });

    // 내부 헬퍼: 월 단위 주차 계산
    function _getWeekNum(date) {
        const dayOfMonth = date.getDate();
        const firstDayOfMonth = new Date(date.getFullYear(), date.getMonth(), 1).getDay();
        return Math.ceil((dayOfMonth + firstDayOfMonth) / 7);
    }
}