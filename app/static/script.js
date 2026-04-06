const tg = window.Telegram.WebApp;
tg.expand();

const workshop = window.location.pathname.split('/').pop();
document.getElementById('workshop-name').innerText = workshop;

let currentShift = 8;
let workers = [];
let absentMode = false;  // Режим проставлення відсутніх

async function loadCurrentShift() {
    try {
        const res = await fetch('/api/current_shift');
        const data = await res.json();
        currentShift = data.shift_hours;
        document.getElementById('shift-hours').innerText = currentShift;
    } catch(e) {
        console.error('Failed to load shift:', e);
    }
}

async function loadWorkers() {
    try {
        const res = await fetch(`/api/workers/${workshop}`);
        const data = await res.json();
        workers = data.workers;
        renderWorkers();
    } catch(e) {
        console.error('Failed to load workers:', e);
    }
}

function renderWorkers() {
    const container = document.getElementById('workers-list');
    container.innerHTML = '';
    
    if (workers.length === 0) {
        container.innerHTML = '<div class="empty-message" style="text-align:center; padding:20px; color:#666;">✅ Всі працівники відмічені на сьогодні!</div>';
        return;
    }
    
    workers.forEach(w => {
        const card = document.createElement('div');
        card.className = 'worker-card';
        card.dataset.id = w.id;
        
        if (absentMode) {
            // Режим "Проставити відсутніх" - показуємо drop-down замість кнопки "Присутній"
            card.innerHTML = `
                <span class="worker-name">${w.fullname}</span>
                <div class="worker-actions">
                    <select class="ktu-select" data-id="${w.id}" style="margin-right:8px;">
                        <option value="0.9">0.9</option>
                        <option value="1" selected>1</option>
                        <option value="1.1">1.1</option>
                        <option value="1.2">1.2</option>
                        <option value="1.3">1.3</option>
                    </select>
                    <select class="absent-select" data-id="${w.id}" data-status>
                        <option value="">📋 Виберіть статус</option>
                        <option value="Вщ">🏖️ Відпустка (Вщ)</option>
                        <option value="Пр">😷 Прогул (Пр)</option>
                        <option value="На">📚 Навчання (На)</option>
                        <option value="Нз">❌ Неявка (Нз)</option>
                    </select>
                    <button class="absent-submit-btn" data-id="${w.id}">✅ Підтвердити</button>
                </div>
            `;
        } else {
            // Звичайний режим - тільки кнопка "Присутній"
            card.innerHTML = `
                <span class="worker-name">${w.fullname}</span>
                <div class="worker-actions">
                    <select class="ktu-select" data-id="${w.id}">
                        <option value="0.9">0.9</option>
                        <option value="1" selected>1</option>
                        <option value="1.1">1.1</option>
                        <option value="1.2">1.2</option>
                        <option value="1.3">1.3</option>
                    </select>
                    <button class="present-btn" data-id="${w.id}">✅ Присутній</button>
                </div>
            `;
        }
        container.appendChild(card);
    });
    
    // Обробники для звичайного режиму
    if (!absentMode) {
        document.querySelectorAll('.present-btn').forEach(btn => {
            btn.onclick = async (e) => {
                e.stopPropagation();
                const id = parseInt(btn.dataset.id);
                const ktuSelect = document.querySelector(`.ktu-select[data-id="${id}"]`);
                const ktu = parseFloat(ktuSelect.value);
                
                try {
                    await fetch('/api/mark_present', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({worker_id: id, ktu: ktu, shift_hours: currentShift})
                    });
                    const card = document.querySelector(`.worker-card[data-id="${id}"]`);
                    if (card) card.remove();
                    workers = workers.filter(w => w.id !== id);
                } catch(e) {
                    console.error('Error marking present:', e);
                }
            };
        });
    } else {
        // Обробники для режиму "Проставити відсутніх"
        document.querySelectorAll('.absent-submit-btn').forEach(btn => {
            btn.onclick = async (e) => {
                e.stopPropagation();
                const id = parseInt(btn.dataset.id);
                const statusSelect = document.querySelector(`.absent-select[data-id="${id}"]`);
                const status = statusSelect.value;
                const ktuSelect = document.querySelector(`.ktu-select[data-id="${id}"]`);
                const ktu = parseFloat(ktuSelect.value);
                
                if (!status) {
                    tg.showPopup({
                        title: "Помилка",
                        message: "Виберіть статус відсутності",
                        buttons: [{type: "ok"}]
                    });
                    return;
                }
                
                try {
                    await fetch('/api/mark_other', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({worker_id: id, status: status})
                    });
                    const card = document.querySelector(`.worker-card[data-id="${id}"]`);
                    if (card) card.remove();
                    workers = workers.filter(w => w.id !== id);
                } catch(e) {
                    console.error('Error marking absent:', e);
                }
            };
        });
    }
}

// Додавання нового працівника
document.getElementById('add-worker-btn').onclick = async () => {
    const name = document.getElementById('new-worker-name').value.trim();
    if (!name) return;
    
    try {
        await fetch('/api/worker', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({fullname: name, workshop: workshop})
        });
        document.getElementById('new-worker-name').value = '';
        await loadWorkers();
    } catch(e) {
        console.error('Error adding worker:', e);
    }
};

// Кнопка "Проставити відсутніх"
const absentModeBtn = document.getElementById('absent-mode-btn');
const modeBadge = document.getElementById('mode-badge');

absentModeBtn.onclick = () => {
    if (workers.length === 0) {
        tg.showPopup({
            title: "Інформація",
            message: "Немає невідмічених працівників",
            buttons: [{type: "ok"}]
        });
        return;
    }
    
    absentMode = !absentMode;
    
    if (absentMode) {
        absentModeBtn.style.background = '#10b981';
        absentModeBtn.innerHTML = '✅ Повернутись до присутності';
        modeBadge.innerHTML = '📋 Режим відсутніх';
        modeBadge.className = 'mode-badge mode-active';
        tg.showPopup({
            title: "Режим відсутніх",
            message: "Виберіть статус для кожного працівника зі списку",
            buttons: [{type: "ok"}]
        });
    } else {
        absentModeBtn.style.background = '#ff9800';
        absentModeBtn.innerHTML = '📋 Проставити відсутніх';
        modeBadge.innerHTML = '✅ Режим присутності';
        modeBadge.className = 'mode-badge mode-normal';
    }
    
    renderWorkers();
};

// Показати результат
document.getElementById('show-result').onclick = async () => {
    try {
        const res = await fetch('/api/report');
        const data = await res.json();
        
        if (data.length === 0) {
            document.getElementById('result-table').innerHTML = '<p>Немає даних за сьогодні</p>';
            document.getElementById('result-table').style.display = 'block';
            return;
        }
        
        let html = '<h3>📋 Результат відмічання</h3>';
        html += '<table border="1" cellpadding="8" cellspacing="0" style="width:100%; border-collapse: collapse;">';
        html += '<tr style="background:#f0f0f0;"><th>Працівник</th><th>Статус</th><th>КТУ</th><th>Годин</th></tr>';
        
        data.forEach(row => {
            let statusDisplay = '';
            if (row.status === 'present') statusDisplay = '✅ Присутній';
            else if (row.status === 'Вщ') statusDisplay = '🏖️ Відпустка';
            else if (row.status === 'Пр') statusDisplay = '😷 Прогул';
            else if (row.status === 'На') statusDisplay = '📚 Навчання';
            else if (row.status === 'Нз') statusDisplay = '❌ Неявка';
            else statusDisplay = row.status;
            
            html += `<tr>
                        <td>${row.fullname}</td>
                        <td>${statusDisplay}</td>
                        <td>${row.ktu}</td>
                        <td>${row.shift_hours}</td>
                     </tr>`;
        });
        html += '</table>';
        
        document.getElementById('result-table').innerHTML = html;
        document.getElementById('result-table').style.display = 'block';
    } catch(e) {
        console.error('Error loading report:', e);
    }
};

// Ініціалізація
loadCurrentShift();
loadWorkers();
