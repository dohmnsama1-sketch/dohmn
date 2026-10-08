'use strict';
let currentPlan = null;
let activeOrder = null;
let sandboxConfigured = false;
const $ = (s) => document.querySelector(s);
const dollars = (v) => '$' + Number(v).toFixed(2);
const esc = (v) => String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.add('show');
  setTimeout(() => $('#toast').classList.remove('show'), 4500);
}
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.detail || 'The request could not be completed.');
  return result;
}
function resetApproval() {
  $('#approve').checked = false;
  $('#approve').disabled = !sandboxConfigured || !currentPlan?.policy_passed;
  $('#approvalLabel').hidden = !sandboxConfigured;
  $('#checkout').disabled = sandboxConfigured || !currentPlan?.policy_passed;
  $('#checkout').textContent = sandboxConfigured ? 'Approve & continue to PayPal sandbox' : 'View local checkout preview';
  $('#checkoutHelp').textContent = sandboxConfigured ? 'Payer approval is separately required before sandbox capture. Only test money is used.' : 'Read-only preview: no approval is recorded and no request is sent to PayPal. Sandbox credentials are not configured.';
  $('#orderlink').classList.remove('show');
  activeOrder = null;
  $('#modal').classList.remove('open');
}
function renderPlan(p) {
  currentPlan = p;
  $('#summary').textContent = p.summary;
  $('#reasoning').textContent = p.reasoning;
  $('#total').textContent = dollars(p.subtotal);
  $('#snapshotTotal').textContent = dollars(p.subtotal);
  const used = Math.round(100 * Number(p.subtotal) / Number(p.budget_cap));
  $('#budgetPercent').textContent = used + '%';
  $('#budgetBar').style.width = Math.min(100, used) + '%';
  $('#items').innerHTML = p.items.map(x => `<div class="item"><div><strong>${esc(x.name)}</strong><small>${esc(x.supplier)} · ${esc(x.condition)} · ${x.quantity} unit${x.quantity === 1 ? '' : 's'}</small></div><div class="itemprice">${dollars(x.line_total)}</div></div>`).join('');
  $('#evidence').textContent = p.items.map(x => `${x.sku}: ${x.evidence}`).join(' ');
  $('#policyPill').className = p.policy_passed ? 'pill-ok' : 'pill-block';
  $('#policyPill').textContent = p.policy_passed ? 'POLICY PASS' : 'CHECKOUT BLOCKED';
  $('#flowPolicy').textContent = p.policy_passed ? 'POLICY PASSED' : 'POLICY BLOCKED';
  $('#snapshotBadge').textContent = p.policy_passed ? 'POLICY PASS' : 'CHECKOUT BLOCKED';
  $('#snapshotDescription').textContent = p.items.map(x => x.name).join(' + ') || 'No eligible cart';
  $('#snapshotFoot').textContent = `Current synthetic plan: ${dollars(p.subtotal)} / ${dollars(p.budget_cap)} budget. No payment has been made.`;
  $('#findings').innerHTML = [p.catalog_notice, ...p.policy_findings].filter(Boolean).map(x => `<div class="finding">${esc(x)}</div>`).join('');
  const alternatives = (p.candidates || p.alternatives || p.ranked_alternatives || []).filter(x => !x.selected);
  $('#alternatives').innerHTML = alternatives.length ? '<div class="label">Alternatives considered · not added to cart</div>' + alternatives.map(x => `<div class="item"><div><strong>${esc(x.name || x.sku || 'Candidate')}</strong><small>${esc(x.reason || x.reasoning || x.selection_reason || (x.findings || []).join(' ') || (x.eligible ? 'Eligible fallback; kept outside the cart' : 'Blocked by policy'))}</small></div><div class="itemprice">${x.line_total != null ? dollars(x.line_total) : (x.unit_price != null ? dollars(x.unit_price) : '')}</div></div>`).join('') : '';
  const trace = p.decision_trace || p.agent_trace || [];
  $('#agentTrace').textContent = JSON.stringify({planner: p.planner || p.ai || p.ai_metadata || p.planner_metadata, decisions: trace}, null, 2);
  $('#agentTrace').style.whiteSpace = 'pre-wrap';
  $('#agentTrace').style.fontFamily = 'DM Mono, monospace';
  $('#result').classList.add('show');
  resetApproval();
}
$('#makePlan').onclick = async () => {
  const button = $('#makePlan');
  button.disabled = true;
  button.textContent = 'Learning intent, checking candidates…';
  currentPlan = null;
  $('#result').classList.remove('show');
  try {
    renderPlan(await api('/api/plan', {request: $('#request').value, max_budget: Number($('#budget').value), currency: 'USD', repair_first: $('#repairFirst').value === 'true'}));
  } catch (e) { toast(e.message); }
  finally {button.disabled = false; button.textContent = 'Build a purchase plan ↗';}
};
$('#approve').onchange = () => {$('#checkout').disabled = !($('#approve').checked && currentPlan?.policy_passed);};
$('#checkout').onclick = async () => {
  if (!currentPlan?.policy_passed) return;
  if (!sandboxConfigured) {
    const button = $('#checkout'); button.disabled = true;
    try {
      renderOrder(await api('/api/plans/' + encodeURIComponent(currentPlan.plan_id) + '/preview'));
      toast('Local payload preview. No approval or PayPal request was recorded.');
    } catch(e) {toast(e.message);}
    finally {button.disabled = false;}
    return;
  }
  if (!$('#approve').checked) return;
  $('#confirmcopy').textContent = `Authorize ${dollars(currentPlan.subtotal)} USD for ${currentPlan.items.map(x => x.name).join(', ')}. This authorization binds the saved cart; changing the request requires a new plan.`;
  $('#modal').classList.add('open');
};
$('#cancel').onclick = () => $('#modal').classList.remove('open');
$('#confirm').onclick = async () => {
  const button = $('#confirm');
  button.disabled = true;
  button.textContent = 'Preparing sandbox order…';
  try {
    const order = await api('/api/paypal/orders', {plan_id: currentPlan.plan_id, human_approved: true});
    renderOrder(order);
    $('#modal').classList.remove('open');
    toast(order.approval_url ? 'Sandbox order created. Review it with the test payer.' : 'Preview ready. No order was sent to PayPal.');
  } catch (e) {toast(e.message); $('#modal').classList.remove('open');}
  finally {button.disabled = false; button.textContent = 'Confirm sandbox order';}
};
function renderOrder(order) {
  activeOrder = order;
  const box = $('#orderlink');
  if (order.order_id) {
    box.innerHTML = `<strong>PayPal sandbox order ${esc(order.order_id)}</strong><br>Status: <span id="orderStatus">${esc(order.status || 'CREATED')}</span><br>Amount: ${dollars(order.amount ?? currentPlan?.subtotal)} USD.<br>${order.approval_url ? `<a href="${esc(order.approval_url)}" rel="noopener">Review with sandbox payer ↗</a><br>` : ''}<button class="primary" id="captureOrder" style="margin-top:10px">Check payer approval & capture test order</button><div id="receipt"></div>`;
    $('#captureOrder').onclick = async () => {
      const button = $('#captureOrder'); button.disabled = true;
      try {
        const result = await api('/api/paypal/capture', {order_id: order.order_id});
        const provider = result.capture || result;
        const finalStatus = result.status || provider.status;
        $('#orderStatus').textContent = finalStatus;
        const captures = result.captures || (provider.purchase_units || []).flatMap(x => x.payments?.captures || []);
        const paid = captures.length > 0 && captures.every(x => x.status === 'COMPLETED');
        $('#receipt').textContent = `Sandbox order: ${provider.id || order.order_id} · ${finalStatus}. Capture records: ${captures.map(x => `${x.id}: ${x.status}`).join(', ') || 'none'}. This is test money; it is not project revenue.`;
        const terminal = new Set(['COMPLETED', 'DECLINED', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED']);
        if (paid) button.textContent = 'Sandbox capture completed';
        else if (captures.some(x => x.status === 'PENDING')) {
          button.textContent = 'Capture pending — check provider status'; button.disabled = false;
        } else if (captures.length && captures.every(x => terminal.has(x.status))) {
          button.textContent = 'Sandbox capture: ' + [...new Set(captures.map(x => x.status))].join(', ');
        } else {
          button.textContent = 'Check provider capture status'; button.disabled = false;
        }
      } catch (e) {toast(e.message); button.disabled = false;}
    };
  } else {
    box.innerHTML = `<strong>Local checkout preview · ${dollars(order.amount)} USD</strong><br>${order.approval_recorded ? 'A local approval was recorded.' : 'No approval was recorded.'} No request was sent to PayPal. No PayPal order or receipt exists.<details><summary>View unsubmitted PayPal payload</summary><pre style="white-space:pre-wrap;word-break:break-word">${esc(JSON.stringify(order.order || order.order_payload, null, 2))}</pre></details>`;
  }
  box.classList.add('show');
}
async function init() {
  if (location.protocol === 'file:') {
    $('#makePlan').disabled = true;
    $('#mode').textContent = 'Open the working local app';
    const note = document.createElement('div'); note.className = 'banner';
    note.innerHTML = 'This file is the UI source. Start <code>python -m mendcart.app</code>, then open <a href="http://127.0.0.1:8000">the working application</a> to run the agent.';
    $('#makePlan').after(note); return;
  }
  try {
    const data = await api('/api/status');
    sandboxConfigured = Boolean(data.sandbox_credentials_configured);
    $('#mode').textContent = (sandboxConfigured ? 'PayPal sandbox configured' : 'Sandbox preview') + ' · ' + (data.planner_engine === 'local-tfidf-knn-v1' ? 'local ML' : 'external AI');
    const params = new URLSearchParams(location.search);
    if (params.get('paypal') === 'return' && params.get('token')) {
      const order = await api('/api/paypal/orders/' + encodeURIComponent(params.get('token')));
      if (order.plan_id) renderPlan(await api('/api/plans/' + encodeURIComponent(order.plan_id)));
      renderOrder(order);
      toast('Returned from PayPal sandbox. Verify payer approval and capture the test order.');
    } else if (params.get('paypal') === 'cancel') {
      toast('PayPal sandbox approval was cancelled. No capture was requested.');
    }
  } catch(e) {toast(e.message);}
}
init();
