/* NANO Polymarket Dashboard — Interactive Trading */
const API = 'http://localhost:8422';
let closingPosId = null;

function toast(msg, color='#00ff88') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = color;
  t.style.color = color;
  t.style.display = 'block';
  t.style.opacity = 1;
  setTimeout(() => { t.style.opacity = 0; setTimeout(() => t.style.display = 'none', 300); }, 3000);
}

async function refreshPortfolio() {
  try {
    const r = await fetch(API + '/api/portfolio');
    const d = await r.json();
    toast('🔄 Портфель обновлён: $' + d.balance.toFixed(2));
    setTimeout(() => location.reload(), 1500);
  } catch(e) { toast('❌ Ошибка: ' + e.message, '#ff4444'); }
}

async function topUp() {
  try {
    const r = await fetch(API + '/api/topup', {method:'POST'});
    const d = await r.json();
    toast('➕ +$500! Баланс: $' + d.balance.toFixed(2));
    setTimeout(() => location.reload(), 1500);
  } catch(e) { toast('❌ Ошибка: ' + e.message, '#ff4444'); }
}

async function loadSignals() {
  const modal = document.getElementById('signalModal');
  const list = document.getElementById('signalList');
  modal.style.display = 'block';
  list.innerHTML = '<div style="color:#666;text-align:center;padding:20px">⏳ Загрузка сигналов...</div>';
  try {
    const r = await fetch(API + '/api/signals');
    const d = await r.json();
    if (!d.signals || d.signals.length === 0) {
      list.innerHTML = '<div style="color:#666;text-align:center;padding:20px">🐋 Нет активных сигналов</div>';
      return;
    }
    list.innerHTML = d.signals.map(s => {
      const pnlE = s.pnl >= 0 ? '🟢' : '🔴';
      const priceC = (s.cur_price * 100).toFixed(0);
      const mkt = s.market.replace(/'/g, "\\'");
      return `<div style="background:#111;border:1px solid #1a1a3a;border-radius:8px;padding:10px;margin-bottom:8px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="color:#fff;font-size:11px;font-weight:600">${pnlE} ${s.whale}: ${s.outcome} ${s.market.slice(0,35)}</div>
            <div style="color:#888;font-size:10px;margin-top:3px">@ ${priceC}¢ | $${s.value.toFixed(0)} | P&L $${s.pnl.toFixed(0)}</div>
          </div>
          <button onclick="placeBet('${s.whale}','${mkt}','${s.outcome}',${s.cur_price})" style="background:linear-gradient(135deg,#1a3a1a,#0a2a0a);border:1px solid #00ff8855;color:#00ff88;padding:8px 14px;border-radius:6px;cursor:pointer;font-size:10px;font-weight:700;white-space:nowrap">🎰 $50</button>
        </div>
      </div>`;
    }).join('');
  } catch(e) { list.innerHTML = '<div style="color:#ff4444;text-align:center;padding:20px">❌ ' + e.message + '</div>'; }
}

function closeModal() { document.getElementById('signalModal').style.display = 'none'; }

async function placeBet(whale, market, outcome, price) {
  try {
    const r = await fetch(API + '/api/bet', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({whale, market, outcome, price, bet_size: 50})
    });
    const d = await r.json();
    if (d.error) { toast('❌ ' + d.error, '#ff4444'); return; }
    toast('✅ Ставка $50 на ' + outcome + ' @ ' + (price*100).toFixed(0) + '¢!');
    setTimeout(() => { closeModal(); location.reload(); }, 2000);
  } catch(e) { toast('❌ Ошибка: ' + e.message, '#ff4444'); }
}

function showClose(posId, info) {
  closingPosId = posId;
  document.getElementById('closeInfo').textContent = info;
  document.getElementById('closeModal').style.display = 'block';
}

async function closePosition(result) {
  if (!closingPosId) return;
  try {
    const r = await fetch(API + '/api/close', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({position_id: closingPosId, result})
    });
    const d = await r.json();
    if (d.error) { toast('❌ ' + d.error, '#ff4444'); return; }
    const emoji = result === 'win' ? '✅ WIN!' : '❌ LOSS';
    toast(emoji + ' Позиция закрыта');
    document.getElementById('closeModal').style.display = 'none';
    setTimeout(() => location.reload(), 1500);
  } catch(e) { toast('❌ Ошибка: ' + e.message, '#ff4444'); }
}