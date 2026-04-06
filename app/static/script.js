const tg = window.Telegram.WebApp;
tg.expand();

const workshop = decodeURIComponent(window.location.pathname.split('/').pop());
document.getElementById('workshop-name').innerText = workshop;

let currentShift = 8;
let workers = [];
let absentMode = false;
let absentSelections = {};

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
        const res = await fetch(`/api/workers/${encodeURIComponent(workshop)}`);
        const data = await res.json();
        workers = data.workers || [];
        absentSelections = {};
        workers.forEach(w => {
            absentSelections[w.id] = 'Вщ';
        });
        renderWorkers();
    } catch(e) {
        console.error('Failed to load workers:', e);
    }
}

async function submitAllAbsent() {
    if (workers.length === 0) {
        tg.showPopup({
            title: "Інформація",
            message: "Немає невідмічених працівників",
            buttons: [{type: "ok"}]
        });
        return;
    }

    tg.showPopup({
        title: "Підтвердження",
        message: `Відправити ${workers.length} працівників як відсутніх?`,
        buttons: [
            {id: "cancel", type: "cancel", text: "Скасувати"},
            {id: "ok", type: "ok", text: "Так, відправити"}
        ]
    }, async (buttonId) => {
        if (buttonId === "ok") {
            for (const w of workers) {
                const status = absentSelections[w.id] || 'Вщ';
                try {
                    await fetch('/api/mark_other', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({worker_id: w.id, status: status})
                    });
                } catch(e) {
                    console.error('Error marking absent:', e);
                }
            }
            workers = [];
            renderWorkers();
            exitAbsentMode();
            tg.showPopup({
                title: "✅ Готово!",
                message: "Всіх відсутніх відправлено",
                buttons: [{type: "ok"}]
            });
        }
    });
}

function exitAbsentMode() {
    absentMode = false;
    const btn = document.getElementById('absent-mode-btn');
    const badge = document.getElementById('mode-badge');
    btn.style.background = '#ff9800';
    btn.innerHTML = '📋 Проставити відсутніх';
    badge.innerHTML = '✅ Режим присутності';
    badge.className = 'mode-badge mode-normal';
    renderWorkers();
}

function renderWorkers() {
    const container = document.getElementById('workers-list');
    container.innerHTML = '';
    
    if (workers.length === 0) {
        container.innerHTML = '<div class="empty-message">✅ Всі працівники відмічені на сьогодні!</div>';
        return;
    }
    
    if (absentMode) {
        workers.forEach(w => {
            const card = document.createElement('div');
            card.className = 'worker-card worker-card-absent';
            card.dataset.id = w.id;
            card.innerHTML = `
                <span class="worker-name">${escapeHtml(w.fullname)}</span>
                <div class="worker-actions">
                    <select class="absent-select" data-id="${w.id}">
                        <option value="Вщ" ${absentSelections[w.id] === 'Вщ' ? 'selected' : ''}>🏖️ Відпустка (Вщ)</option>
                        <option value="Пр" ${absentSelections[w.id] === 'Пр' ? 'selected' : ''}>😷 Прогул (Пр)</option>
                        <option value="На" ${absentSelections[w.id] === 'На' ? 'selected' : ''}>📚 Навчання (На)</option>
                        <option value="Нз" ${absentSelections[w.id] === 'Нз' ? 'selected' : ''}>❌ Неявка (Нз)</option>
                    </select>
                </div>
            `;
            container.appendChild(card);
        });
        
        const finishBtn = document.createElement('button');
        finishBtn.className = 'finish-btn';
        finishBtn.innerHTML = '✅ Завершити та відправити всіх відсутніх';
        finishBtn.onclick = submitAllAbsent;
        container.appendChild(finishBtn);
        
        document.querySelectorAll('.absent-select').forEach(select => {
            select.onchange = (e) => {
                const id = parseInt(select.dataset.id);
                absentSelections[id] = select.value;
            };
        });
    } else {
        workers.forEach(w => {
            const card = document.createElement('div');
            card.className = 'worker-card';
            card.dataset.id = w.id;
            card.innerHTML = `
                <span class="worker-name">${escapeHtml(w.fullname)}</span>
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
            container.appendChild(card);
        });
        
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
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, (m) => {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

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

const absentBtn = document.getElementById('absent-mode-btn');
const modeBadge = document.getElementById('mode-badge');

absentBtn.onclick = () => {
    if (workers.length === 0 && !absentMode) {
        tg.showPopup({
            title: "Інформація",
            message: "Немає невідмічених працівників",
            buttons: [{type: "ok"}]
        });
        return;
    }
    
    if (absentMode) {
        absentMode = false;
        absentBtn.style.background = '#ff9800';
        absentBtn.innerHTML = '📋 Проставити відсутніх';
        modeBadge.innerHTML = '✅ Режим присутності';
        modeBadge.className = 'mode-badge mode-normal';
        renderWorkers();
    } else {
        absentMode = true;
        absentBtn.style.background = '#10b981';
        absentBtn.innerHTML = '🔙 Повернутись до присутності';
        modeBadge.innerHTML = '📋 Режим відсутніх';
        modeBadge.className = 'mode-badge mode-active';
        renderWorkers();
    }
};

document.getElementById('show-result').onclick = async () => {
    try {
        const res = await fetch('/api/report');
        const data = await res.json();
        
        if (!data || data.length === 0) {
            document.getElementById('result-table').innerHTML = '<p>Немає даних за сьогодні</p>';
            document.getElementById('result-table').style.display = 'block';
            return;
        }
        
        let html = '<h3>📋 Результат відмічання</h3><table><tr><th>Працівник</th><th>Статус</th><th>КТУ</th><th>Годин</th></tr>';
        data.forEach(row => {
            let statusDisplay = '';
            if (row.status === 'present') statusDisplay = '✅ Присутній';
            else if (row.status === 'Вщ') statusDisplay = '🏖️ Відпустка';
            else if (row.status === 'Пр') statusDisplay = '😷 Прогул';
            else if (row.status === 'На') statusDisplay = '📚 Навчання';
            else if (row.status === 'Нз') statusDisplay = '❌ Неявка';
            else statusDisplay = row.status;
            
            html += `<tr>
                        <td>${escapeHtml(row.fullname)}</td>
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

loadCurrentShift();
loadWorkers();
