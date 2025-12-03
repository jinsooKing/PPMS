/* calendar.js - 주차별 선택 기능 (프리미엄 테마 호환) */

let calendarState = {
    currentYear: new Date().getFullYear(),
    currentMonth: new Date().getMonth() + 1,
    callback: null
};

/**
 * 주차 선택 달력 초기화 함수
 * @param {string} btnId - 달력을 띄울 버튼 ID
 * @param {function} onSelectCallback - (year, month, week) => void
 */
function setupWeekPicker(btnId, onSelectCallback) {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    calendarState.callback = onSelectCallback;

    // 1. 팝업 HTML 생성 (없으면 생성)
    if (!document.getElementById('custom-calendar-popup')) {
        const popupHtml = `
            <div id="custom-calendar-popup" class="custom-calendar-popup">
                <div class="calendar-header">
                    <button class="calendar-nav-btn" id="prev-month-btn"><i class="uil uil-angle-left"></i></button>
                    <span id="calendar-title" style="font-weight:bold;"></span>
                    <button class="calendar-nav-btn" id="next-month-btn"><i class="uil uil-angle-right"></i></button>
                </div>
                <div class="calendar-days-header">
                    <span style="color:#ff4444">일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span>토</span>
                </div>
                <div class="calendar-body" id="calendar-body"></div>
            </div>
        `;
        // 버튼 바로 뒤에 캘린더 팝업 삽입 (position: absolute 위치 기준)
        btn.insertAdjacentHTML('afterend', popupHtml); 
        
        // 네비게이션 이벤트 연결
        document.getElementById('prev-month-btn').addEventListener('click', (e) => {
            e.stopPropagation(); changeMonth(-1);
        });
        document.getElementById('next-month-btn').addEventListener('click', (e) => {
            e.stopPropagation(); changeMonth(1);
        });
    }

    const popup = document.getElementById('custom-calendar-popup');

    // 2. 버튼 클릭 시 토글
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isVisible = popup.classList.contains('visible');
        
        // 다른 팝업들 닫기
        document.querySelectorAll('.custom-calendar-popup').forEach(el => el.classList.remove('visible'));
        
        if (!isVisible) {
            popup.classList.add('visible');
            renderCalendar(); // 캘린더 다시 그리기
        }
    });

    // 3. 외부 클릭 시 닫기
    document.addEventListener('click', (e) => {
        if (!popup.contains(e.target) && e.target !== btn) {
            popup.classList.remove('visible');
        }
    });
}

// 월 변경 함수
function changeMonth(delta) {
    calendarState.currentMonth += delta;
    if (calendarState.currentMonth > 12) {
        calendarState.currentMonth = 1;
        calendarState.currentYear++;
    } else if (calendarState.currentMonth < 1) {
        calendarState.currentMonth = 12;
        calendarState.currentYear--;
    }
    renderCalendar();
}

// 캘린더 렌더링 함수
function renderCalendar() {
    const body = document.getElementById('calendar-body');
    const title = document.getElementById('calendar-title');
    const { currentYear, currentMonth } = calendarState;

    // 타이틀 업데이트 (YYYY.MM)
    title.textContent = `${currentYear}.${String(currentMonth).padStart(2,'0')}`;
    body.innerHTML = '';

    const firstDay = new Date(currentYear, currentMonth - 1, 1);
    const lastDay = new Date(currentYear, currentMonth, 0);
    
    const startDayOfWeek = firstDay.getDay(); // 0(일) ~ 6(토)
    const totalDays = lastDay.getDate();

    // 날짜 배열 생성 (이전달 빈칸 + 현재달 날짜)
    let daysArray = [];
    for (let i = 0; i < startDayOfWeek; i++) {
        daysArray.push({ type: 'empty' });
    }
    for (let i = 1; i <= totalDays; i++) {
        daysArray.push({ type: 'day', val: i });
    }

    // 주(Row) 단위로 생성
    let weekRow = document.createElement('div');
    weekRow.className = 'calendar-week-row';
    
    daysArray.forEach((dayObj, index) => {
        const cell = document.createElement('div');
        cell.className = 'day-cell';
        
        if (dayObj.type === 'day') {
            cell.textContent = dayObj.val;
            
            // 오늘 날짜 표시
            const today = new Date();
            if (currentYear === today.getFullYear() && currentMonth === today.getMonth() + 1 && dayObj.val === today.getDate()) {
                cell.classList.add('today');
            }
            
            // 일요일 체크 (index % 7 === 0) -> CSS에서 빨간색 처리
            if (index % 7 === 0) cell.classList.add('sunday');
        } else {
            // 빈칸 (이전달/다음달)
            cell.classList.add('other-month');
        }
        
        weekRow.appendChild(cell);

        // 토요일이거나 마지막 날짜면 Row 닫고 body에 추가
        if ((index + 1) % 7 === 0 || index === daysArray.length - 1) {
            // 마지막 주에 남은 빈칸 채우기
            while (weekRow.children.length < 7) {
                const emptyCell = document.createElement('div');
                emptyCell.className = 'day-cell other-month';
                weekRow.appendChild(emptyCell);
            }
            
            // [핵심] 유효한 날짜가 있는 주만 클릭 가능하도록 설정
            const hasRealDay = Array.from(weekRow.children).some(c => c.textContent !== '' && !c.classList.contains('other-month'));
            
            if (hasRealDay) {
                // 해당 주의 유효한 첫 날짜를 가져와 주차 계산
                const firstDateVal = parseInt(weekRow.querySelector('.day-cell:not(.other-month)').textContent);
                const targetDate = new Date(currentYear, currentMonth - 1, firstDateVal);
                const weekNum = getWeekNumber(targetDate); 

                // 클릭 이벤트 (주차 선택)
                weekRow.addEventListener('click', () => {
                    if (calendarState.callback) {
                        calendarState.callback(currentYear, currentMonth, weekNum);
                    }
                    document.getElementById('custom-calendar-popup').classList.remove('visible');
                });
            } else {
                // 날짜가 없는 빈 줄은 클릭 불가
                weekRow.style.cursor = 'default';
                weekRow.style.pointerEvents = 'none';
            }

            body.appendChild(weekRow);
            weekRow = document.createElement('div');
            weekRow.className = 'calendar-week-row'; // 다음 줄 준비
        }
    });
}

// 주차 계산 함수 (매월 1일이 포함된 주를 1주차로 계산)
function getWeekNumber(d) {
    const date = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const firstDay = new Date(date.getFullYear(), date.getMonth(), 1);
    const dayOfWeek = firstDay.getDay(); // 1일의 요일
    
    return Math.ceil((date.getDate() + dayOfWeek) / 7);
}

