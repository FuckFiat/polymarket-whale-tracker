/* NANO Polymarket Dashboard - Interactive Trading v3.1
   Uses Telegram Bot deep links for actions (works from any device!)
   API on localhost:8422 for local use, falls back to Telegram bot.
*/
const BOT = 'ClowwwwwBot';
const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8422'
  : null;  // null = use Telegram bot links instead
let closingPosId = null;

function toast(msg, color) {
  color = color || '#00ff88';
  const t = document.getElementById('toast');
  if (!t) { alert(msg); return; }
  t.textContent = msg;
  t.style.borderColor = color;
  t.style.color = color;
  t.style.display = 'block';
  t.style.opacity = '1';
  setTimeout(function() {
    t.style.opacity = '0';
    setTimeout(function() { t.style.display = 'none'; }, 300);
  }, 3000);
}

function tgLink(cmd) {
  return 'https://t.me/' + BOT + '?start=' + encodeURIComponent(cmd);
}

function openTg(cmd) {
  const url = tgLink(cmd);
  window.open(url, '_blank');
  toast('📱 Открыто в Telegram...');
}

async function refreshPortfolio() {
  if (API) {
    try {
      const r = await fetch(API + '/api/portfolio');
      const d = await r.json();
      toast('🔄 Портфель: $' + d.balance.toFixed(2));
      setTimeout(function() { location.reload(); }, 1500);
    } catch(e) { toast('❌ ' + e.message, '#ff4444'); }
  } else {
    openTg('deposit');
  }
}

async function topUp() {
  if (API) {
    try {
      const r = await fetch(API + '/api/topup', {method: 'POST'});
      const d = await r.json();
      toast('➕ +$500! Баланс: $' + d.balance.toFixed(2));
      setTimeout(function() { location.reload(); }, 1500);
    } catch(e) { toast('❌ ' + e.message, '#ff4444'); }
  } else {
    openTg('topup');
  }
}

async function loadSignals() {
  if (API) {
    var modal = document.getElementById('signalModal');
    var list = document.getElementById('signalList');
    modal.style.display = 'block';
    list.innerHTML = '<div style="color:#666;text-align:center;padding:20px">⏳ Загрузка...</div>';
    try {
      var r = await fetch(API + '/api/signals');
      var d = await r.json();
      if (!d.signals || d.signals.length === 0) {
        list.innerHTML = '<div style="color:#666;text-align:center;padding:20px">🐋 Нет сигналов</div>';
        return;
      }
      var html = '';
      for (var i = 0; i < d.signals.length; i++) {
        var s = d.signals[i];
        var pnlE = s.pnl >= 0 ? '🟢' : '🔴';
        var priceC = (s.cur_price * 100).toFixed(0);
        var mkt = s.market.replace(/'/g, "\\'");
        html += '<div style="background:#111;border:1px solid #1a1a3a;border-radius:8px;padding:10px;margin-bottom:8px">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center">';
        html += '<div>';
        html += '<div style="color:#fff;font-size:11px;font-weight:600">' + pnlE + ' ' + s.whale + ': ' + s.outcome + ' ' + s.market.slice(0, 35) + '</div>';
        html += '<div style="color:#888;font-size:10px;margin-top:3px">@ ' + priceC + '\u00a2 | $' + s.value.toFixed(0) + ' | P&L $' + s.pnl.toFixed(0) + '</div>';
        html += '</div>';
        html += '<button onclick="placeBet(\'' + s.whale + '\',\'' + mkt + '\',\'' + s.outcome + '\',' + s.cur_price + ')" style="background:linear-gradient(135deg,#1a3a1a,#0a2a0a);border:1px solid #00ff8855;color:#00ff88;padding:8px 14px;border-radius:6px;cursor:pointer;font-size:10px;font-weight:700;white-space:nowrap">\uD83C\uDFB0 $50</button>';
        html += '</div></div>';
      }
      list.innerHTML = html;
    } catch(e) {
      list.innerHTML = '<div style="color:#ff4444;text-align:center;padding:20px">\u274C ' + e.message + '</div>';
    }
  } else {
    openTg('bet');
  }
}

function closeModal() {
  var modal = document.getElementById('signalModal');
  if (modal) modal.style.display = 'none';
}

async function placeBet(whale, market, outcome, price) {
  if (API) {
    try {
      var r = await fetch(API + '/api/bet', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({whale: whale, market: market, outcome: outcome, price: price, bet_size: 50})
      });
      var d = await r.json();
      if (d.error) { toast('\u274C ' + d.error, '#ff4444'); return; }
      toast('\u2705 Ставка $50 на ' + outcome + ' @ ' + (price * 100).toFixed(0) + '\u00a2!');
      setTimeout(function() { closeModal(); location.reload(); }, 2000);
    } catch(e) { toast('\u274C ' + e.message, '#ff4444'); }
  } else {
    openTg('bet_' + whale + '_' + outcome + '_' + (price * 100).toFixed(0));
  }
}

function showClose(posId, info) {
  if (API) {
    closingPosId = posId;
    var el = document.getElementById('closeInfo');
    if (el) el.textContent = info;
    var modal = document.getElementById('closeModal');
    if (modal) modal.style.display = 'block';
  } else {
    openTg('close');
  }
}

async function closePosition(result) {
  if (!closingPosId) return;
  if (API) {
    try {
      var r = await fetch(API + '/api/close', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({position_id: closingPosId, result: result})
      });
      var d = await r.json();
      if (d.error) { toast('\u274C ' + d.error, '#ff4444'); return; }
      var emoji = result === 'win' ? '\u2705 WIN!' : '\u274C LOSS';
      toast(emoji + ' Позиция закрыта');
      var modal = document.getElementById('closeModal');
      if (modal) modal.style.display = 'none';
      setTimeout(function() { location.reload(); }, 1500);
    } catch(e) { toast('\u274C ' + e.message, '#ff4444'); }
  }
}