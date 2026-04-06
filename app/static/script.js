const tg = window.Telegram.WebApp;
tg.expand();

const workshop = window.location.pathname.split('/').pop();
document.getElementById('workshop-name').innerText = workshop;

let currentShift = 8;
let workers = [];
let pendingOther = {};

// Список тестових працівників для різних цехів
const testWorkers = {
    "DMT": [
        "Коваленко Андрій Миколайович",
        "Шевченко Ольга Петрівна",
        "Бондаренко Сергій Іванович",
        "Мельник Тетяна Володимирівна",
        "Лисенко Віктор Олексійович"
    ],
    "Пакування": [
        "Гончаренко Ірина Василівна",
        "Руденко Олег Михайлович",
        "Ткаченко Наталія Сергіївна",
        "Кравчук Дмитро Андрійович",
        "Савченко Людмила Ігорівна"
    ]
};

// Отримуємо поточну зміну
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

// Завантажуємо працівників
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

// Додавання тестових працівників
async function addTestWorkers() {
    const workersList = testWorkers[workshop] || testWorkers["DMT"];
    let added = 0;
    
    tg.showPopup({
        title: "Додавання працівників",
        message: `Додати ${workersList.length} тестових працівників для цеху ${workshop}?`,
        buttons: [
            {id: "cancel", type: "cancel", text: "Скасувати"},
            {id: "ok", type: "ok", text: "Додати"}
        ]
    }, async (buttonId) => {
        if (buttonId === "ok") {
            tg.showPopup({title: "Зачекайте", message: "Додаємо працівників...", buttons: []});
            
            for (const name of workersList) {
                try {
                    await fetch('/api/worker', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({fullname: name, workshop: workshop})
                    });
                    added++;
                } catch(e) {
                    console.error(`Failed to add ${name}:`, e);
                }
            }
            
            tg.showPopup({
                title: "Готово!",
                message: `Додано ${added} з ${workersList.length} працівників`,
                buttons: [{type: "ok"}]
            });
            
            await loadWorkers();
        }
    });
}

function renderWorkers() {
    const container = document.getElementById('workers-list');
    container.innerHTML = '';
    
    if (workers.length === 0) {
        container.innerHTML = '<div class="empty-message" style="text-align:center; padding:20px; color:#666;">✅ Всі працівники відмічені на сьогодні!<br>Натисніть "Додати тестових працівників" для початку</div>';
        return;
    }
    
    workers.forEach(w => {
        const card = document.createElement('div');
        card.className = 'worker-card';
        card.dataset.id = w.id;
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
                <button class="other-btn" data-id="${w.id}">❓ Інше</button>
            </div>
        `;
        container.appendChild(card);
    });
    
    // Обробники для кнопок "Присутній"
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
                    body: JSON.stringify({
                        worker_id: id, 
                        ktu: ktu, 
                        shift_hours: currentShift
                    })
                });
                // Видаляємо картку
                const card = document.querySelector(`.worker-card[data-id="${id}"]`);
                if (card) card.remove();
                workers = workers.filter(w => w.id !== id);
                tg.showPopup({title: "Успішно", message: "Працівника відмічено!", buttons: [{type: "ok"}]});
            } catch(e) {
                console.error('Error marking present:', e);
                tg.showPopup({title: "Помилка", message: "Не вдалося відмітити", buttons: [{type: "ok"}]});
            }
        };
    });
    
    // Обробники для кнопок "Інше"
    document.querySelectorAll('.other-btn').forEach(btn => {
        btn.onclick = () => {
            const id = parseInt(btn.dataset.id);
            showOtherOptions(id);
        };
    });
}

let currentOtherWorkerId = null;

function showOtherOptions(workerId) {
    currentOtherWorkerId = workerId;
    const worker = workers.find(w => w.id === workerId);
    const options = [
        {code: 'Вщ', name: '🏖️ Відпустка', emoji: '🏖️'},
        {code: 'Пр', name: '😷 Прогул', emoji: '😷'},
        {code: 'На', name: '📚 Навчання', emoji: '📚'},
        {code: 'Нз', name: '❌ Неявка', emoji: '❌'}
    ];
    
    const container = document.getElementById('other-buttons');
    container.innerHTML = '';
    options.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'other-option-btn';
        btn.innerHTML = `${opt.emoji} ${opt.name}`;
        btn.style.margin = '5px';
        btn.style.padding = '10px 16px';
        btn.style.border = 'none';
        btn.style.borderRadius = '28px';
        btn.style.backgroundColor = '#f59e0b';
        btn.style.color = 'white';
        btn.style.cursor = 'pointer';
        btn.onclick = () => {
            pendingOther[workerId] = opt.code;
            tg.showPopup({
                title: "Вибрано",
                message: `Для ${worker?.fullname} вибрано: ${opt.name}`,
                buttons: [{type: "ok"}]
            });
            document.getElementById('other-controls').style.display = 'block';
        };
        container.appendChild(btn);
    });
    
    document.getElementById('other-controls').style.display = 'block';
}

document.getElementById('submit-other').onclick = async () => {
    for (const [id, status] of Object.entries(pendingOther)) {
        try {
            await fetch('/api/mark_other', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({worker_id: parseInt(id), status: status})
            });
            const card = document.querySelector(`.worker-card[data-id="${id}"]`);
            if (card) card.remove();
            workers = workers.filter(w => w.id != id);
        } catch(e) {
            console.error('Error marking other:', e);
        }
    }
    pendingOther = {};
    document.getElementById('other-controls').style.display = 'none';
    currentOtherWorkerId = null;
    tg.showPopup({title: "Успішно", message: "Всі невиходи відправлено!", buttons: [{type: "ok"}]});
};

// Додавання нового працівника
document.getElementById('add-worker-btn').onclick = async () => {
    const name = document.getElementById('new-worker-name').value.trim();
    if (!name) {
        tg.showPopup({title: "Помилка", message: "Введіть ПІБ працівника", buttons: [{type: "ok"}]});
        return;
    }
    try {
        await fetch('/api/worker', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({fullname: name, workshop: workshop})
        });
        document.getElementById('new-worker-name').value = '';
        await loadWorkers();
        tg.showPopup({title: "Успішно", message: "Працівника додано!", buttons: [{type: "ok"}]});
    } catch(e) {
        console.error('Error adding worker:', e);
        tg.showPopup({title: "Помилка", message: "Не вдалося додати", buttons: [{type: "ok"}]});
    }
};

// Кнопка для додавання тестових працівників
document.getElementById('add-test-workers-btn').onclick = addTestWorkers;

// Показати результат
document.getElementById('show-result').onclick = async () => {
    try {
        const res = await fetch('/api/report');
        const data = await res.json();
        
        if (data.length === 0) {
            tg.showPopup({title: "Інформація", message: "Немає даних про відмічання за сьогодні", buttons: [{type: "ok"}]});
            return;
        }
        
        let html = '<h3>📋 Результат відмічання за сьогодні</h3>';
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
        
        tg.showPopup({title: "Інформація", message: `Всього відмічено: ${data.length} працівників`, buttons: [{type: "ok"}]});
    } catch(e) {
        console.error('Error loading report:', e);
        tg.showPopup({title: "Помилка", message: "Не вдалося завантажити звіт", buttons: [{type: "ok"}]});
    }
};

// Ініціалізація
loadCurrentShift();
loadWorkers();
