async function analyze() {
    const message = document.getElementById('ta').value.trim();
    const url = document.getElementById('url-ta').value.trim();
    const btn = document.getElementById('scanBtn');
    
    // UI Elements
    const rIdle = document.getElementById('r-idle');
    const rLoading = document.getElementById('r-loading');
    const rSafe = document.getElementById('r-safe');
    const rDanger = document.getElementById('r-danger');

    if (!message) {
        alert("Vui lòng nhập nội dung tin nhắn!");
        return;
    }

    // Switch to Loading State
    [rIdle, rSafe, rDanger].forEach(el => el.style.display = 'none');
    rLoading.style.display = 'flex';
    btn.disabled = true;

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: message, urls: url ? [url] : [] })
        });

        const data = await response.json();
        
        if (data.error) {
            alert("Lỗi: " + data.error);
            rLoading.style.display = 'none';
            rIdle.style.display = 'flex';
            return;
        }

        renderResult(data.result);
    } catch (error) {
        console.error("Lỗi:", error);
        alert("Có lỗi xảy ra khi kết nối server.");
        rLoading.style.display = 'none';
        rIdle.style.display = 'flex';
    } finally {
        btn.disabled = false;
    }
}

function renderResult(res) {
    if (!res) return;
    
    const rLoading = document.getElementById('r-loading');
    const rSafe = document.getElementById('r-safe');
    const rDanger = document.getElementById('r-danger');

    rLoading.style.display = 'none';

    if (!res.is_dangerous) {
        rSafe.style.display = 'flex';
        document.getElementById('safe-score').innerText = `SCORE: ${res.score} / 5`;
        document.getElementById('safe-reason').innerText = res.reason || "Không có dấu hiệu độc hại.";
        document.getElementById('safe-recommend').innerText = res.recommend || "Có thể an tâm sử dụng.";
        document.getElementById('safe-types').innerText = (res.types || []).join(', ') || "Bình thường";
    } else {
        rDanger.style.display = 'flex';
        document.getElementById('danger-score').innerText = `THREAT: ${res.score} / 5`;
        document.getElementById('danger-reason').innerText = res.reason || "Phát hiện dấu hiệu nguy hiểm.";
        document.getElementById('danger-recommend').innerText = res.recommend || "Xóa ngay lập tức!";
        document.getElementById('danger-types').innerText = (res.types || []).join(', ') || "Nguy hiểm";
    }
}

function updateCounter() {
    const text = document.getElementById('ta').value;
    document.getElementById('ctr').textContent = `${text.length} / 10000`;
}

function clearAll() {
    document.getElementById('ta').value = "";
    document.getElementById('url-ta').value = "";
    updateCounter();
    document.getElementById('r-safe').style.display = 'none';
    document.getElementById('r-danger').style.display = 'none';
    document.getElementById('r-loading').style.display = 'none';
    document.getElementById('r-idle').style.display = 'flex';
}

async function pasteText() {
    try {
        const text = await navigator.clipboard.readText();
        document.getElementById('ta').value = text;
        updateCounter();
    } catch (err) {
        console.error('Không thể truy cập clipboard: ', err);
        alert("Không thể truy cập clipboard. Vui lòng cấp quyền hoặc dán thủ công.");
    }
}
