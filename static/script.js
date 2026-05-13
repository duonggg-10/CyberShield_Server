async function analyze() {
    const message = document.getElementById('messageInput').value.trim();
    const url = document.getElementById('urlInput').value.trim();
    const btn = document.getElementById('scanBtn');
    const resultArea = document.getElementById('resultArea');

    if (!message) {
        alert("Vui lòng nhập nội dung tin nhắn!");
        return;
    }

    // Hiệu ứng Loading
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-circle-notch animate-spin"></i> ĐANG PHÂN TÍCH...`;
    
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: message, urls: url ? [url] : [] })
        });

        const data = await response.json();
        
        if (data.error) {
            alert("Lỗi: " + data.error);
            return;
        }

        renderResult(data.result);
    } catch (error) {
        console.error("Lỗi:", error);
        alert("Có lỗi xảy ra khi kết nối server.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>PHÂN TÍCH NGAY</span><i class="fas fa-bolt-lightning text-yellow-300"></i>`;
    }
}

function renderResult(res) {
    if (!res) return;

    const area = document.getElementById('resultArea');
    const card = document.getElementById('resultCard');
    const icon = document.getElementById('resultIcon');
    const title = document.getElementById('resultTitle');
    const badge = document.getElementById('scoreBadge');
    const reason = document.getElementById('resultReason');
    const recommend = document.getElementById('recommendationBox');

    area.classList.remove('hidden');
    area.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Reset classes
    card.className = "p-8 rounded-[2rem] border-2 flex flex-col md:flex-row gap-8 items-start";
    icon.className = "w-20 h-20 rounded-2xl flex items-center justify-center text-3xl shadow-lg shrink-0";

    if (!res.is_dangerous) {
        card.classList.add('result-safe');
        icon.classList.add('icon-safe');
        icon.innerHTML = `<i class="fas fa-check-shield"></i>`;
        title.innerText = "An Toàn";
        badge.className = "px-4 py-1 rounded-full text-xs font-bold mono bg-green-100 text-green-700";
        badge.innerText = `SCORE: ${res.score}/5`;
    } else {
        const isWarning = res.score <= 3;
        card.classList.add(isWarning ? 'result-warning' : 'result-danger');
        icon.classList.add(isWarning ? 'icon-warning' : 'icon-danger');
        icon.innerHTML = isWarning ? `<i class="fas fa-triangle-exclamation"></i>` : `<i class="fas fa-biohazard"></i>`;
        title.innerText = isWarning ? "Cảnh Báo" : "Nguy Hiểm";
        badge.className = `px-4 py-1 rounded-full text-xs font-bold mono ${isWarning ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`;
        badge.innerText = `THREAT: ${res.score}/5`;
    }

    reason.innerText = res.reason || "Không có lý do cụ thể được cung cấp.";
    recommend.innerText = "Lời khuyên: " + (res.recommend || "Hãy cẩn trọng khi tương tác với nội dung này.");
}

function clearAll() {
    document.getElementById('messageInput').value = "";
    document.getElementById('urlInput').value = "";
    document.getElementById('resultArea').classList.add('hidden');
}

async function pasteText() {
    try {
        const text = await navigator.clipboard.readText();
        document.getElementById('messageInput').value = text;
    } catch (err) {
        console.error('Không thể truy cập clipboard: ', err);
        alert("Không thể truy cập clipboard. Vui lòng cấp quyền hoặc dán thủ công.");
    }
}
