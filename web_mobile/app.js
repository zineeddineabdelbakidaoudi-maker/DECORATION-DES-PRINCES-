/**
 * PeintPro Mobile PWA Application Logic.
 * Fully optimized for iPhone Safari & Native Home Screen App mode.
 */

// Register Service Worker for iOS Home Screen App
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(err => console.log('SW reg error:', err));
}

let state = {
  products: [],
  clients: [],
  suppliers: [],
  cart: [],
};

// ══════════════════════════════════════════════════════════════════
// INITIALIZATION & TAB NAVIGATION
// ══════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  loadDashboardData();
  loadProducts();
  loadClientsAndSuppliers();
  setupEventListeners();
});

function setupNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  const plusNavItems = document.querySelectorAll('.nav-item-plus');

  function switchTab(targetTab) {
    document.querySelectorAll('.tab-view').forEach(view => view.classList.remove('active'));
    document.getElementById(targetTab).classList.add('active');

    if (targetTab === 'tab-dashboard') loadDashboardData();
    if (targetTab === 'tab-stock') loadProducts();
    if (targetTab === 'tab-payments') loadClientsAndSuppliers();
    
    // New Tabs
    if (targetTab === 'tab-reports') loadReports('today');
    if (targetTab === 'tab-suppliers') loadSupplierInsights();
    if (targetTab === 'tab-clients') loadClientInsights();
    if (targetTab === 'tab-inventories') loadInventories();
  }

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      if (item.id === 'nav-item-plus') {
        document.getElementById('modal-plus-menu').classList.add('active');
        return;
      }
      
      const targetTab = item.getAttribute('data-tab');
      navItems.forEach(nav => nav.classList.remove('active'));
      item.classList.add('active');
      
      switchTab(targetTab);
    });
  });

  plusNavItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetTab = item.getAttribute('data-tab');
      navItems.forEach(nav => nav.classList.remove('active'));
      document.getElementById('nav-item-plus').classList.add('active');
      document.getElementById('modal-plus-menu').classList.remove('active');
      
      switchTab(targetTab);
    });
  });
  
  document.getElementById('btn-close-plus').addEventListener('click', () => {
    document.getElementById('modal-plus-menu').classList.remove('active');
  });
}

// ══════════════════════════════════════════════════════════════════
// API CALLS & DATA LOADING
// ══════════════════════════════════════════════════════════════════

async function loadDashboardData() {
  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();
    
    document.getElementById('dash-sales').innerText = data.today_sales_formatted || '0 DA';
    document.getElementById('dash-encaisse').innerText = data.net_encaissement_formatted || '0 DA';
    document.getElementById('dash-debts').innerText = data.client_debts_formatted || '0 DA';
    document.getElementById('dash-stock-low').innerText = data.low_stock_count || 0;

    const salesRes = await fetch('/api/sales?limit=10');
    const salesData = await salesRes.json();
    renderRecentSales(salesData);
  } catch (err) {
    console.error('Error loading dashboard:', err);
  }
}

function renderRecentSales(sales) {
  const container = document.getElementById('recent-sales-list');
  if (!sales || sales.length === 0) {
    container.innerHTML = '<div style="color: var(--text-sub); text-align: center; padding: 20px;">Aucune vente enregistrée</div>';
    return;
  }

  container.innerHTML = sales.map(s => `
    <div class="list-item">
      <div class="item-info">
        <div class="item-name">Vente #${s.id} — ${s.client_name || 'Client Passager'}</div>
        <div class="item-meta">${s.sale_date} · Mode: ${s.payment_method}</div>
      </div>
      <div style="font-size: 15px; font-weight: 800; color: ${s.is_debt ? 'var(--accent-red)' : 'var(--accent-green)'};">
        ${s.grand_total.toLocaleString('fr-DZ')} DA
      </div>
    </div>
  `).join('');
}

async function loadProducts() {
  try {
    const res = await fetch('/api/products');
    state.products = await res.json();
    renderStockList(state.products);
    populatePosProductSelect(state.products);
  } catch (err) {
    console.error('Error loading products:', err);
  }
}

function renderStockList(products) {
  const container = document.getElementById('stock-list');
  if (!products || products.length === 0) {
    container.innerHTML = '<div style="color: var(--text-sub); text-align: center; padding: 20px;">Aucun produit trouvé</div>';
    return;
  }

  container.innerHTML = products.map(p => {
    const stockClass = p.stock_qty <= 5 ? 'stock-low' : 'stock-ok';
    const price = p.unit_type === 'KG' ? p.price_per_kg : p.sell_price;
    return `
      <div class="list-item" onclick="openStockEditModal(${p.id})">
        <div class="item-info">
          <div class="item-name">${p.name}</div>
          <div class="item-meta">Prix: <b>${(price || 0).toLocaleString('fr-DZ')} DA</b> / ${p.unit_type}</div>
        </div>
        <div class="stock-tag ${stockClass}">
          ${p.stock_qty} ${p.unit_type} ✏️
        </div>
      </div>
    `;
  }).join('');
}

async function loadClientsAndSuppliers() {
  try {
    const [resC, resS] = await Promise.all([
      fetch('/api/clients'),
      fetch('/api/suppliers')
    ]);
    state.clients = await resC.json();
    state.suppliers = await resS.json();

    // Populate POS client dropdown
    const posClientSelect = document.getElementById('pos-client-select');
    posClientSelect.innerHTML = '<option value="">Client Passager (Comptoir)</option>' +
      state.clients.map(c => `<option value="${c.id}">${c.name} ${c.total_debt > 0 ? `(Dette: ${c.total_debt.toLocaleString('fr-DZ')} DA)` : ''}</option>`).join('');

    // Populate Vers Client select
    const versClientSelect = document.getElementById('vers-client-select');
    versClientSelect.innerHTML = '<option value="">Sélectionnez le client...</option>' +
      state.clients.map(c => `<option value="${c.id}">${c.name} — Dette: ${(c.total_debt || 0).toLocaleString('fr-DZ')} DA</option>`).join('');

    // Populate Vers Supplier select
    const versSuppSelect = document.getElementById('vers-supp-select');
    versSuppSelect.innerHTML = '<option value="">Sélectionnez le fournisseur...</option>' +
      state.suppliers.map(s => `<option value="${s.id}">${s.name} — Dette: ${(s.net_debt || 0).toLocaleString('fr-DZ')} DA</option>`).join('');
  } catch (err) {
    console.error('Error loading clients/suppliers:', err);
  }
}

// ══════════════════════════════════════════════════════════════════
// MOBILE POS / CART MANAGEMENT
// ══════════════════════════════════════════════════════════════════

function populatePosProductSelect(products) {
  const select = document.getElementById('pos-prod-select');
  select.innerHTML = '<option value="">Choisir un produit...</option>' +
    products.map(p => {
      const price = p.unit_type === 'KG' ? p.price_per_kg : p.sell_price;
      return `<option value="${p.id}">${p.name} (${p.unit_type}) — ${(price || 0).toLocaleString('fr-DZ')} DA</option>`;
    }).join('');
}

function setupEventListeners() {
  // Stock Search
  document.getElementById('stock-search').addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    const filtered = state.products.filter(p => 
      p.name.toLowerCase().includes(q) || (p.barcode && p.barcode.toLowerCase().includes(q))
    );
    renderStockList(filtered);
  });

  // Product Selection in POS
  document.getElementById('pos-prod-select').addEventListener('change', (e) => {
    const pid = parseInt(e.target.value);
    const p = state.products.find(x => x.id === pid);
    if (p) {
      const price = p.unit_type === 'KG' ? p.price_per_kg : p.sell_price;
      document.getElementById('pos-price').value = price || 0;
    }
  });

  // Add Item to Cart
  document.getElementById('btn-add-pos-item').addEventListener('click', () => {
    const pid = parseInt(document.getElementById('pos-prod-select').value);
    const qty = parseFloat(document.getElementById('pos-qty').value);
    const price = parseFloat(document.getElementById('pos-price').value);

    if (!pid || !qty || qty <= 0) {
      alert("Veuillez sélectionner un produit et une quantité valide.");
      return;
    }

    const p = state.products.find(x => x.id === pid);
    state.cart.push({
      product_id: p.id,
      product_name: p.name,
      unit_type: p.unit_type,
      quantity: qty,
      unit_price: price,
      subtotal: qty * price
    });

    renderCart();
    document.getElementById('pos-prod-select').value = '';
    document.getElementById('pos-qty').value = 1.0;
  });

  // Payment Mode toggle
  document.getElementById('pos-payment-mode').addEventListener('change', (e) => {
    const isCredit = e.target.value === 'credit';
    document.getElementById('versement-input-group').style.display = isCredit ? 'block' : 'none';
  });

  // Submit Sale
  document.getElementById('btn-submit-sale').addEventListener('click', async () => {
    if (state.cart.length === 0) {
      alert("Votre panier est vide.");
      return;
    }

    const clientId = document.getElementById('pos-client-select').value;
    const clientSelect = document.getElementById('pos-client-select');
    const clientName = clientId ? clientSelect.options[clientSelect.selectedIndex].text.split('(')[0].trim() : 'Client Passager';
    const isCredit = document.getElementById('pos-payment-mode').value === 'credit';
    const versement = isCredit ? parseFloat(document.getElementById('pos-versement').value) : 0;

    const payload = {
      client_id: clientId ? parseInt(clientId) : null,
      client_name: clientName,
      is_debt: isCredit ? 1 : 0,
      versement_total: versement,
      remise: 0,
      payment_method: isCredit ? 'Crédit' : 'Espèces',
      items: state.cart
    };

    try {
      const res = await fetch('/api/sales/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const resData = await res.json();
      if (resData.status === 'success') {
        alert(`✅ Vente #${resData.sale_id} enregistrée avec succès !`);
        state.cart = [];
        renderCart();
        loadDashboardData();
        loadProducts();
      } else {
        alert(`Erreur : ${resData.detail}`);
      }
    } catch (err) {
      alert(`Erreur d'envoi : ${err}`);
    }
  });

  // Versement Type toggle
  document.getElementById('vers-type').addEventListener('change', (e) => {
    const isSupp = e.target.value === 'supplier';
    document.getElementById('group-vers-client').style.display = isSupp ? 'none' : 'block';
    document.getElementById('group-vers-supplier').style.display = isSupp ? 'block' : 'none';
  });

  // Submit Versement
  document.getElementById('btn-submit-versement').addEventListener('click', async () => {
    const type = document.getElementById('vers-type').value;
    const amount = parseFloat(document.getElementById('vers-amount').value);
    const notes = document.getElementById('vers-notes').value;

    if (!amount || amount <= 0) {
      alert("Veuillez saisir un montant supérieur à 0.");
      return;
    }

    let url = '/api/versements/client';
    let payload = { amount, notes };

    if (type === 'client') {
      const cid = document.getElementById('vers-client-select').value;
      if (!cid) { alert("Veuillez sélectionner un client."); return; }
      payload.client_id = parseInt(cid);
    } else {
      url = '/api/versements/supplier';
      const sid = document.getElementById('vers-supp-select').value;
      if (!sid) { alert("Veuillez sélectionner un fournisseur."); return; }
      payload.supplier_id = parseInt(sid);
    }

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const resData = await res.json();
      if (resData.status === 'success') {
        alert("✅ Versement enregistré avec succès !");
        document.getElementById('vers-amount').value = '';
        document.getElementById('vers-notes').value = '';
        loadDashboardData();
        loadClientsAndSuppliers();
      } else {
        alert(`Erreur : ${resData.detail}`);
      }
    } catch (err) {
      alert(`Erreur : ${err}`);
    }
  });

  // Modal actions
  document.getElementById('btn-close-modal').addEventListener('click', closeModal);
  document.getElementById('btn-save-stock').addEventListener('click', saveStockEdit);
}

function renderCart() {
  const container = document.getElementById('cart-list');
  const totalElem = document.getElementById('cart-total');

  if (state.cart.length === 0) {
    container.innerHTML = '<div style="color: var(--text-sub); text-align: center; padding: 12px; border: 1px dashed var(--border-color); border-radius: 10px;">Le panier est vide</div>';
    totalElem.innerText = '0.00 DA';
    return;
  }

  let total = 0;
  container.innerHTML = state.cart.map((item, idx) => {
    total += item.subtotal;
    return `
      <div class="list-item">
        <div class="item-info">
          <div class="item-name">${item.product_name}</div>
          <div class="item-meta">${item.quantity} ${item.unit_type} × ${item.unit_price.toLocaleString('fr-DZ')} DA</div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-weight: 700;">${item.subtotal.toLocaleString('fr-DZ')} DA</span>
          <button onclick="removeFromCart(${idx})" style="background: none; border: none; font-size: 16px; cursor: pointer;">❌</button>
        </div>
      </div>
    `;
  }).join('');

  totalElem.innerText = `${total.toLocaleString('fr-DZ')} DA`;
}

function removeFromCart(idx) {
  state.cart.splice(idx, 1);
  renderCart();
}

// ══════════════════════════════════════════════════════════════════
// STOCK EDIT MODAL
// ══════════════════════════════════════════════════════════════════

function openStockEditModal(pid) {
  const p = state.products.find(x => x.id === pid);
  if (!p) return;

  document.getElementById('edit-prod-id').value = p.id;
  document.getElementById('modal-item-title').innerText = `Modifier ${p.name}`;
  document.getElementById('edit-prod-qty').value = p.stock_qty;
  document.getElementById('edit-prod-price').value = p.unit_type === 'KG' ? p.price_per_kg : p.sell_price;
  document.getElementById('edit-prod-buy').value = p.unit_type === 'KG' ? p.buy_price_per_kg : p.buy_price;

  document.getElementById('modal-edit-stock').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-edit-stock').classList.remove('active');
}

async function saveStockEdit() {
  const pid = parseInt(document.getElementById('edit-prod-id').value);
  const qty = parseFloat(document.getElementById('edit-prod-qty').value);
  const price = parseFloat(document.getElementById('edit-prod-price').value);
  const buy = parseFloat(document.getElementById('edit-prod-buy').value);

  try {
    const res = await fetch('/api/products/update_stock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: pid, stock_qty: qty, sell_price: price, buy_price: buy })
    });
    const resData = await res.json();
    if (resData.status === 'success') {
      closeModal();
      loadProducts();
    } else {
      alert(`Erreur : ${resData.detail}`);
    }
  } catch (err) {
    alert(`Erreur : ${err}`);
  }
}


// --- FACTURE PROFORMA / DEVIS ---
const btnPrintDevis = document.getElementById('btn-print-devis');
if (btnPrintDevis) {
    btnPrintDevis.addEventListener('click', async () => {
      if (cart.length === 0) {
        alert('Le panier est vide');
        return;
      }
      
      const clientSelect = document.getElementById('pos-client-select');
      const clientName = clientSelect.options[clientSelect.selectedIndex].text;
      
      const payload = {
        items: cart,
        client_name: clientName,
        remise: 0
      };

      try {
        btnPrintDevis.disabled = true;
        btnPrintDevis.innerText = 'Génération...';

        const res = await fetch('/api/sales/devis', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          const blob = await res.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.style.display = 'none';
          a.href = url;
          a.download = `Devis_${clientName}.pdf`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
        } else {
          const err = await res.json();
          alert('Erreur devis : ' + err.detail);
        }
      } catch (error) {
        console.error(error);
        alert('Erreur réseau');
      } finally {
        btnPrintDevis.disabled = false;
        btnPrintDevis.innerText = '📄 Imprimer Devis / Proforma';
      }
    });
}

// ══════════════════════════════════════════════════════════════════
// NEW TABS DATA LOADING LOGIC
// ══════════════════════════════════════════════════════════════════

// -- REPORTS --
document.getElementById('report-period').addEventListener('change', (e) => {
  const period = e.target.value;
  document.getElementById('report-custom-dates').style.display = period === 'custom' ? 'grid' : 'none';
  if (period !== 'custom') {
    loadReports(period);
  }
});

document.getElementById('btn-refresh-report').addEventListener('click', () => {
  const period = document.getElementById('report-period').value;
  loadReports(period);
});

async function loadReports(period) {
  try {
    let url = `/api/reports?period=${period}`;
    if (period === 'custom') {
      const from = document.getElementById('report-date-from').value;
      const to = document.getElementById('report-date-to').value;
      if (!from || !to) return alert("Veuillez sélectionner les dates.");
      url += `&date_from=${from}&date_to=${to}`;
    }
    const res = await fetch(url);
    const data = await res.json();
    
    document.getElementById('rep-ca').innerText = data.revenue_net_fmt || '0 DA';
    document.getElementById('rep-achats').innerText = data.purchases_net_fmt || '0 DA';
    document.getElementById('rep-benefice').innerText = data.profit_fmt || '0 DA';
    document.getElementById('rep-nb-ventes').innerText = data.sale_count || 0;
    
    document.getElementById('rep-encaissement').innerText = data.total_encaissements_fmt || '0 DA';
    const ventesVers = (data.cash_sales + data.initial_versements).toLocaleString('fr-DZ') + ' DA';
    document.getElementById('rep-ventes-vers').innerText = ventesVers;
    document.getElementById('rep-reglements').innerText = (data.post_reglements || 0).toLocaleString('fr-DZ') + ' DA';
    document.getElementById('rep-tresorerie').innerText = data.tresorerie_nette_fmt || '0 DA';

    const topProdContainer = document.getElementById('rep-top-products');
    if (data.top_products && data.top_products.length > 0) {
      topProdContainer.innerHTML = data.top_products.map(p => `
        <div class="list-item" style="padding:10px;">
          <div class="item-info">
            <div class="item-name">${p.name}</div>
            <div class="item-meta">Vendus: ${p.qty}</div>
          </div>
          <div style="font-weight:bold; color:var(--accent-blue)">${(p.revenue || 0).toLocaleString('fr-DZ')} DA</div>
        </div>
      `).join('');
    } else {
      topProdContainer.innerHTML = '<div style="text-align:center;color:var(--text-sub);padding:10px;">Aucune donnée</div>';
    }
  } catch (err) {
    console.error(err);
  }
}

// -- SUPPLIERS INSIGHTS --
async function loadSupplierInsights() {
  try {
    const res = await fetch('/api/insights/suppliers');
    const data = await res.json();
    const container = document.getElementById('supplier-insights-list');
    
    container.innerHTML = data.map((s, idx) => `
      <div class="list-item" style="flex-direction:column; align-items:stretch;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div class="item-info">
            <div class="item-name">${s.name}</div>
            <div class="item-meta">Achats Totaux: ${(s.total_purchases || 0).toLocaleString('fr-DZ')} DA</div>
          </div>
          <div style="font-weight:bold; color:var(--accent-red)">Dette: ${(s.net_debt || 0).toLocaleString('fr-DZ')} DA</div>
        </div>
        <button class="expand-btn" onclick="toggleExpand('supp-exp-${idx}')">Voir détails ▼</button>
        <div id="supp-exp-${idx}" class="expandable-content">
          <div class="detail-row"><span>Total Paiements:</span> <span>${(s.total_payments || 0).toLocaleString('fr-DZ')} DA</span></div>
          <div class="detail-row"><span>Total Retours:</span> <span>${(s.total_returns || 0).toLocaleString('fr-DZ')} DA</span></div>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error(err);
  }
}

// -- CLIENTS INSIGHTS --
async function loadClientInsights() {
  try {
    const res = await fetch('/api/insights/clients');
    const data = await res.json();
    const container = document.getElementById('client-insights-list');
    
    container.innerHTML = data.map((c, idx) => `
      <div class="list-item" style="flex-direction:column; align-items:stretch;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div class="item-info">
            <div class="item-name">${idx + 1}. ${c.name}</div>
            <div class="item-meta">Achats: ${(c.total_purchased || 0).toLocaleString('fr-DZ')} DA | Ventes: ${c.sale_count}</div>
          </div>
          <div style="font-weight:bold; color:var(--accent-red)">Dette: ${(c.total_debt || 0).toLocaleString('fr-DZ')} DA</div>
        </div>
        <button class="expand-btn" onclick="toggleExpand('cli-exp-${idx}')">Voir dettes actives ▼</button>
        <div id="cli-exp-${idx}" class="expandable-content">
          ${c.active_debts && c.active_debts.length > 0 ? c.active_debts.map(d => `
            <div class="detail-row"><span>Vente #${d.sale_id} (${d.date})</span> <span>Reste: ${d.remaining.toLocaleString('fr-DZ')} DA</span></div>
          `).join('') : '<div style="color:var(--text-sub);font-size:12px;">Aucune dette active</div>'}
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error(err);
  }
}

function toggleExpand(id) {
  document.getElementById(id).classList.toggle('active');
}

// -- INVENTORIES --
let inventorySessions = [];
async function loadInventories() {
  try {
    const res = await fetch('/api/inventories');
    inventorySessions = await res.json();
    const container = document.getElementById('inv-sessions-list');
    
    const cmp1 = document.getElementById('inv-cmp-1');
    const cmp2 = document.getElementById('inv-cmp-2');
    
    let options = '<option value="">Choisir session...</option>';
    let listHTML = '';
    
    inventorySessions.forEach(inv => {
      options += `<option value="${inv.id}">#${inv.id} - ${inv.date}</option>`;
      const isPositive = inv.total_abs_diff >= 0;
      const badgeCls = inv.status === 'validé' ? 'badge-blue' : (isPositive ? 'badge-green' : 'badge-red');
      
      listHTML += `
        <div class="list-item" style="cursor:pointer;" onclick="loadInventoryDetail(${inv.id})">
          <div class="item-info">
            <div class="item-name">Inv #${inv.id} - ${inv.date}</div>
            <div class="item-meta">${inv.item_count} articles modifiés</div>
          </div>
          <div class="badge ${badgeCls}">${inv.status}</div>
        </div>
      `;
    });
    
    cmp1.innerHTML = options;
    cmp2.innerHTML = options;
    container.innerHTML = listHTML || '<div style="text-align:center;color:var(--text-sub);">Aucun inventaire</div>';
  } catch (err) {
    console.error(err);
  }
}

async function loadInventoryDetail(id) {
  try {
    const res = await fetch(`/api/inventories/${id}`);
    const data = await res.json();
    
    document.getElementById('inv-detail-title').innerText = `Détails Inventaire #${data.inventory.id}`;
    
    let html = `<div style="margin-bottom:10px; font-size:14px;">Total Écart: <b>${(data.total_ecart_valeur || 0).toLocaleString('fr-DZ')} DA</b></div>`;
    
    html += `<table class="report-table">
      <tr><th>Produit</th><th>Théor.</th><th>Réel</th><th>Diff</th></tr>
      ${data.items.map(i => `
        <tr>
          <td>${i.product_name}</td>
          <td>${i.expected_qty}</td>
          <td>${i.actual_qty}</td>
          <td style="color:${i.diff_qty < 0 ? 'var(--accent-red)' : 'var(--accent-green)'}"><b>${i.diff_qty > 0 ? '+'+i.diff_qty : i.diff_qty}</b></td>
        </tr>
      `).join('')}
    </table>`;
    
    document.getElementById('inv-detail-content').innerHTML = html;
    document.getElementById('modal-inv-detail').classList.add('active');
  } catch (err) {
    console.error(err);
  }
}

document.querySelectorAll('.btn-close-inv').forEach(btn => {
  btn.addEventListener('click', () => {
    document.getElementById('modal-inv-detail').classList.remove('active');
  });
});
document.getElementById('btn-close-inv').addEventListener('click', () => {
    document.getElementById('modal-inv-detail').classList.remove('active');
});

document.getElementById('btn-compare-inv').addEventListener('click', async () => {
  const id1 = document.getElementById('inv-cmp-1').value;
  const id2 = document.getElementById('inv-cmp-2').value;
  if (!id1 || !id2 || id1 === id2) return alert("Sélectionnez 2 sessions différentes.");
  
  try {
    const res = await fetch(`/api/inventories/compare?id1=${id1}&id2=${id2}`);
    const data = await res.json();
    const resDiv = document.getElementById('inv-cmp-results');
    
    let html = `<table class="report-table">
      <tr><th>Produit</th><th>Inv 1</th><th>Inv 2</th><th>Evol.</th></tr>
      ${data.comparison.map(c => `
        <tr>
          <td>${c.product_name}</td>
          <td>${c.inv1_actual}</td>
          <td>${c.inv2_actual}</td>
          <td style="color:${c.evolution < 0 ? 'var(--accent-red)' : 'var(--accent-green)'}">${c.evolution > 0 ? '+'+c.evolution : c.evolution}</td>
        </tr>
      `).join('')}
    </table>`;
    
    resDiv.innerHTML = html;
    resDiv.style.display = 'block';
  } catch (err) {
    console.error(err);
  }
});
