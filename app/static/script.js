const tg = window.Telegram.WebApp;
tg.expand();
const workshop = window.location.pathname.split('/').pop();
document.getElementById('workshop-name').innerText = workshop;

let currentShift = 8;
let workers = [];
let pendingOther = {};

async function loadWorkers() {
    const res = await fetch(`/api/workers/${workshop}`);
    const data = await res.json();
    workers = data.workers;
    renderWorkers();
}

function renderWorkers() {
    const container = document.getElementById('workers-list');
    container.innerHTML = '';
    workers.forEach(w => {
        const card = document.createElement('div');
        card.className = 'worker-card';
        card.dataset.id = w.id;
        card.innerHTML = `
            <span class="worker-name">${w.fullname}</span>
            <div class="worker-actions">
                <select class="ktu-select">
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

    document.querySelectorAll('.present-btn').forEach(btn => {
        btn.onclick = async (e) => {
            const id = parseInt(btn.dataset.id);
            const ktu = parseFloat(btn.parentElement.querySelector('.ktu-select').value);
            await fetch('/api/mark_present', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({worker_id: id, ktu, shift_hours: currentShift})
            });
            // видаляємо картку
            document.querySelector(`.worker-card[data-id="${id}"]`).remove();
            workers = workers.filter(w => w.id !== id);
        };
    });

    document.querySelectorAll('.other-btn').forEach(btn => {
        btn.onclick = () => {
            const id = parseInt(btn.dataset.id);
            showOtherOptions(id);
        };
    });
}

function showOtherOptions(workerId) {
    const options = ['Вщ', 'Пр', 'На', 'Нз'];
    const container = document.getElementById('other-buttons');
    container.innerHTML = '';
    options.forEach(opt => {
        const btn = document.createElement('button');
        btn.innerText = opt;
        btn.style.margin = '5px';
        btn.style.padding = '8px 16px';
        btn.onclick = () => {
            pendingOther[workerId] = opt;
            alert(`Для ${workers.find(w=>w.id===workerId)?.fullname} вибрано: ${opt}`);
            document.getElementById('other-controls').style.display = 'block';
        };
        container.appendChild(btn);
    });
}

document.getElementById('submit-other').onclick = async () => {
    for (const [id, status] of Object.entries(pendingOther)) {
        await fetch('/api/mark_other', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({worker_id: parseInt(id), status})
        });
        document.querySelector(`.worker-card[data-id="${id}"]`)?.remove();
        workers = workers.filter(w => w.id != id);
    }
    pendingOther = {};
    document.getElementById('other-controls').style.display = 'none';
    alert('Відправлено!');
};

document.getElementById('add-worker-btn').onclick = async () => {
    const name = document.getElementById('new-worker-name').value.trim();
    if (!name) return;
    await fetch('/api/worker', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({fullname: name, workshop})
    });
    document.getElementById('new-worker-name').value = '';
    loadWorkers();
};

document.getElementById('show-result').onclick = async () => {
    const res = await fetch('/api/report');
    const data = await res.json();
    let html = '<h3>Результат відмічання</h3><table><tr><th>Працівник</th><th>Статус</th><th>КТУ</th><th>Годин</th></tr>';
    data.forEach(row => {
        html += `<tr><td>${row.fullname}</td><td>${row.status}</td><td>${row.ktu}</td><td>${row.shift_hours}</td></tr>`;
    });
    html += '</table>';
    document.getElementById('result-table').innerHTML = html;
    document.getElementById('result-table').style.display = 'block';
};

loadWorkers();
