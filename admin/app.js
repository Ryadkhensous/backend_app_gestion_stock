/**
 * PORTAIL ADMIN & ANALYTICS - APPLICATION CLIENT JAVASCRIPT
 * Gestion de l'authentification, KPIs financiers, Graphiques Chart.js,
 * Gestion des Vendeurs et Matrice Granulaire des Autorisations.
 */

class AdminApp {
  constructor() {
    this.apiBase = '/api';
    this.token = localStorage.getItem('stockpro_admin_token') || null;
    this.currentUser = null;
    this.currentTenant = null;
    this.currentPeriod = 'all';
    this.activeTab = 'dashboard';
    this.theme = localStorage.getItem('stockpro_theme') || 'dark';

    // Données en cache
    this.dashboardData = null;
    this.sellers = [];
    this.selectedSellerId = null;
    this.pointsOfSale = [];
    this.documents = [];

    // Instances Chart.js
    this.charts = {
      trend: null,
      payments: null,
    };

    // Profils de permissions prédéfinis
    this.permissionPresets = {
      RESTRICTED: {
        can_discount: false,
        max_discount_percent: 0.0,
        can_edit_price: false,
        can_view_margin: false,
        can_cancel_sale: false,
        can_give_credit: false,
        can_manage_stock: false,
        restricted_to_pos: true,
      },
      STANDARD: {
        can_discount: true,
        max_discount_percent: 5.0,
        can_edit_price: false,
        can_view_margin: false,
        can_cancel_sale: false,
        can_give_credit: true,
        can_manage_stock: false,
        restricted_to_pos: true,
      },
      COMMERCIAL: {
        can_discount: true,
        max_discount_percent: 15.0,
        can_edit_price: true,
        can_view_margin: false,
        can_cancel_sale: false,
        can_give_credit: true,
        can_manage_stock: false,
        restricted_to_pos: false,
      },
      MANAGER: {
        can_discount: true,
        max_discount_percent: 30.0,
        can_edit_price: true,
        can_view_margin: true,
        can_cancel_sale: true,
        can_give_credit: true,
        can_manage_stock: true,
        restricted_to_pos: false,
      },
    };

    this.init();
  }

  /* ==========================================================================
     INITIALISATION & ÉVÉNEMENTS
     ========================================================================== */

  init() {
    this.applyTheme(this.theme);
    this.bindEvents();
    this.checkSession();
  }

  bindEvents() {
    // Thème toggle
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => this.toggleTheme());
    }

    // Déconnexion
    const logoutBtn = document.getElementById('btn-logout');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => this.logout());
    }

    // Bouton rafraîchir
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.refreshActiveTab());
    }

    // Sélecteurs de périodes
    document.querySelectorAll('.period-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.period-btn').forEach((b) => b.classList.remove('active'));
        e.target.classList.add('active');
        this.currentPeriod = e.target.getAttribute('data-period');
        this.loadDashboardData();
      });
    });

    // Navigation dans la sidebar
    document.querySelectorAll('.sidebar-nav .nav-item').forEach((item) => {
      item.addEventListener('click', () => {
        const tab = item.getAttribute('data-tab');
        if (tab) this.switchTab(tab);
      });
    });

    // Mobile sidebar toggle
    const sidebarToggle = document.getElementById('sidebar-toggle-btn');
    const sidebar = document.querySelector('.sidebar');
    if (sidebarToggle && sidebar) {
      sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
      });
    }

    // Formulaire de connexion
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
      loginForm.addEventListener('submit', (e) => this.handleLogin(e));
    }

    // Recherche et tri de rentabilité
    const profitSearch = document.getElementById('profit-search-input');
    if (profitSearch) {
      profitSearch.addEventListener('input', () => this.renderProfitTable());
    }
    const profitSort = document.getElementById('profit-sort-select');
    if (profitSort) {
      profitSort.addEventListener('change', () => this.renderProfitTable());
    }

    // Recherche de documents
    const docSearch = document.getElementById('docs-search-input');
    if (docSearch) {
      docSearch.addEventListener('input', () => this.renderDocumentsTable());
    }

    // Changement de vendeur dans la matrice des autorisations
    const permSellerSelect = document.getElementById('perm-seller-select');
    if (permSellerSelect) {
      permSellerSelect.addEventListener('change', (e) => {
        const sellerId = parseInt(e.target.value, 10);
        if (sellerId) {
          this.loadSellerPermissions(sellerId);
        }
      });
    }

    // Switch remise toggle (affiche/masque le plafond %)
    const canDiscountSwitch = document.getElementById('perm-can-discount');
    const discountCapRow = document.getElementById('perm-discount-cap-row');
    if (canDiscountSwitch && discountCapRow) {
      canDiscountSwitch.addEventListener('change', (e) => {
        discountCapRow.style.opacity = e.target.checked ? '1' : '0.4';
      });
    }
  }

  /* ==========================================================================
     THÈMES (SOMBRE / CLAIR)
     ========================================================================== */

  applyTheme(theme) {
    this.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('stockpro_theme', theme);

    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');
    if (sunIcon && moonIcon) {
      if (theme === 'light') {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
      } else {
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
      }
    }

    if (this.charts.trend) {
      this.updateChartTheme(this.charts.trend);
    }
  }

  toggleTheme() {
    const newTheme = this.theme === 'dark' ? 'light' : 'dark';
    this.applyTheme(newTheme);
  }

  updateChartTheme(chart) {
    const isDark = this.theme === 'dark';
    const textColor = isDark ? '#94a3b8' : '#64748b';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)';

    if (chart.options.scales && chart.options.scales.x) {
      chart.options.scales.x.ticks.color = textColor;
      chart.options.scales.x.grid.color = gridColor;
    }
    if (chart.options.scales && chart.options.scales.y) {
      chart.options.scales.y.ticks.color = textColor;
      chart.options.scales.y.grid.color = gridColor;
    }
    chart.update();
  }

  /* ==========================================================================
     AUTHENTIFICATION & REQUÊTES API
     ========================================================================== */

  async fetchApi(endpoint, options = {}) {
    const headers = options.headers || {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(`${this.apiBase}${endpoint}`, {
        ...options,
        headers,
      });

      if (response.status === 401) {
        this.logout();
        throw new Error('Session expirée ou non autorisée');
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Erreur serveur (${response.status})`);
      }

      return await response.json();
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  }

  async checkSession() {
    const authModal = document.getElementById('auth-modal');
    if (!this.token) {
      if (authModal) authModal.style.display = 'flex';
      return;
    }

    try {
      const data = await this.fetchApi('/auth/me');
      this.currentUser = data.user;
      this.currentTenant = data.tenant;
      this.updateUserInterface();
      if (authModal) authModal.style.display = 'none';

      // Chargement initial des données
      this.loadDashboardData();
      this.loadSellersList();
      this.loadPointsOfSale();
    } catch (err) {
      console.warn('Session non valide, invite de connexion:', err.message);
      if (authModal) authModal.style.display = 'flex';
    }
  }

  async handleLogin(e) {
    e.preventDefault();
    const usernameInput = document.getElementById('login-username');
    const passwordInput = document.getElementById('login-password');
    const errorBanner = document.getElementById('login-error');
    const loginBtn = document.getElementById('btn-login');

    if (errorBanner) errorBanner.style.display = 'none';
    if (loginBtn) {
      loginBtn.disabled = true;
      loginBtn.innerHTML = `<span>Connexion en cours...</span>`;
    }

    try {
      const res = await fetch(`${this.apiBase}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: usernameInput.value.trim(),
          password: passwordInput.value,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Identifiant ou mot de passe incorrect.');
      }

      this.token = data.access_token;
      this.currentUser = data.user;
      this.currentTenant = data.tenant;
      localStorage.setItem('stockpro_admin_token', this.token);

      this.showToast(`Bienvenue, ${this.currentUser.full_name || this.currentUser.username} !`, 'success');

      const authModal = document.getElementById('auth-modal');
      if (authModal) authModal.style.display = 'none';

      this.updateUserInterface();
      this.loadDashboardData();
      this.loadSellersList();
      this.loadPointsOfSale();
    } catch (err) {
      if (errorBanner) {
        errorBanner.textContent = err.message;
        errorBanner.style.display = 'block';
      }
    } finally {
      if (loginBtn) {
        loginBtn.disabled = false;
        loginBtn.innerHTML = `
          <span>Se Connecter au Tableau de Bord</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
        `;
      }
    }
  }

  logout() {
    this.token = null;
    this.currentUser = null;
    this.currentTenant = null;
    localStorage.removeItem('stockpro_admin_token');
    const authModal = document.getElementById('auth-modal');
    if (authModal) authModal.style.display = 'flex';
    this.showToast('Vous avez été déconnecté.', 'info');
  }

  updateUserInterface() {
    if (this.currentUser) {
      const nameEl = document.getElementById('current-user-name');
      const avatarEl = document.getElementById('current-user-avatar');
      const roleEl = document.getElementById('current-user-role');

      const displayName = this.currentUser.full_name || this.currentUser.username;
      if (nameEl) nameEl.textContent = displayName;
      if (avatarEl) avatarEl.textContent = displayName.charAt(0).toUpperCase();
      if (roleEl) roleEl.textContent = this.currentUser.role;
    }

    if (this.currentTenant) {
      const storeBadge = document.getElementById('store-name-badge');
      if (storeBadge) storeBadge.textContent = this.currentTenant.name;
    }
  }

  /* ==========================================================================
     GESTION DES ONGLETS & NAVIGATION
     ========================================================================== */

  switchTab(tabId) {
    this.activeTab = tabId;

    // Fermer sidebar mobile si ouverte
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.classList.remove('open');

    // Mettre à jour les boutons du menu
    document.querySelectorAll('.sidebar-nav .nav-item').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });

    // Afficher le bon contenu
    document.querySelectorAll('.tab-content').forEach((sec) => {
      sec.classList.remove('active');
    });
    const targetSection = document.getElementById(`tab-${tabId}`);
    if (targetSection) targetSection.classList.add('active');

    // Titres dynamiques de la page
    const titleMap = {
      dashboard: {
        title: "Tableau de Bord Général",
        sub: "Indicateurs clés de performance et synthèse des ventes",
      },
      analytics: {
        title: "Rentabilité & Analyse des Marges",
        sub: "Étude détaillée du chiffre d'affaires, des coûts et des bénéfices par produit",
      },
      sellers: {
        title: "Gestion des Vendeurs",
        sub: "Pilotage des commerciaux à leur compte, suivi du chiffre et calcul des commissions",
      },
      permissions: {
        title: "Matrice des Autorisations Vendeurs",
        sub: "Attribution fine des droits d'accès caisse, rabais, modifications et restrictions",
      },
      'points-of-sale': {
        title: "Boutiques, Dépôts & Points de Vente",
        sub: "Gestion du réseau de distribution physique et état des magasins",
      },
      documents: {
        title: "Journal des Ventes & Documents",
        sub: "Traçabilité des bons de livraison, commandes et tickets de caisse",
      },
    };

    const headerInfo = titleMap[tabId] || { title: "StockPro Admin", sub: "Supervision" };
    const titleEl = document.getElementById('page-title');
    const subEl = document.getElementById('page-subtitle');
    if (titleEl) titleEl.textContent = headerInfo.title;
    if (subEl) subEl.textContent = headerInfo.sub;

    // Déclencher le chargement spécifique
    if (tabId === 'dashboard') {
      this.loadDashboardData();
    } else if (tabId === 'analytics') {
      this.renderProfitTable();
    } else if (tabId === 'sellers') {
      this.loadSellersList();
    } else if (tabId === 'permissions') {
      this.populatePermissionsSellerSelect();
    } else if (tabId === 'points-of-sale') {
      this.loadPointsOfSale();
    } else if (tabId === 'documents') {
      this.loadDocuments();
    }
  }

  refreshActiveTab() {
    const icon = document.querySelector('.spin-on-click');
    if (icon) {
      icon.style.transform = 'rotate(360deg)';
      icon.style.transition = 'transform 0.6s ease';
      setTimeout(() => {
        icon.style.transform = '';
        icon.style.transition = '';
      }, 600);
    }

    this.switchTab(this.activeTab);
    this.showToast('Données actualisées avec succès', 'info');
  }

  /* ==========================================================================
     DONNÉES DU DASHBOARD & KPI
     ========================================================================== */

  async loadDashboardData() {
    try {
      const data = await this.fetchApi('/analytics/comprehensive-dashboard');
      this.dashboardData = data;
      this.renderKPIs(data);
      this.renderDailyTrendChart(data.daily_trend);
      this.renderPaymentMethodsChart(data.payment_methods);
      this.renderTopSellersTable(data.top_sellers);
      this.renderLowStockAlerts(data.low_stock_items);
      this.renderProfitTable();
    } catch (err) {
      this.showToast(`Échec du chargement : ${err.message}`, 'error');
    }
  }

  renderKPIs(data) {
    if (!data || !data.kpis) return;
    const kpis = data.kpis;
    const periods = data.periods || {};

    let rev = kpis.total_revenue;
    let orders = kpis.total_orders;
    let profit = kpis.total_profit;
    let margin = kpis.margin_percentage;

    // Filtre de période dynamique
    if (this.currentPeriod === 'today' && periods.today) {
      rev = periods.today.revenue;
      orders = periods.today.orders;
      profit = rev * (kpis.margin_percentage / 100);
    } else if (this.currentPeriod === 'week' && periods.last_7_days) {
      rev = periods.last_7_days.revenue;
      orders = periods.last_7_days.orders;
      profit = rev * (kpis.margin_percentage / 100);
    } else if (this.currentPeriod === 'month' && periods.this_month) {
      rev = periods.this_month.revenue;
      orders = periods.this_month.orders;
      profit = rev * (kpis.margin_percentage / 100);
    }

    const elRev = document.getElementById('kpi-total-revenue');
    const elOrders = document.getElementById('kpi-orders-count');
    const elProfit = document.getElementById('kpi-total-profit');
    const elMargin = document.getElementById('kpi-margin-pct');
    const elInventory = document.getElementById('kpi-inventory-value');
    const elStockUnits = document.getElementById('kpi-stock-units');
    const elCommissions = document.getElementById('kpi-commissions-total');
    const elActiveSellers = document.getElementById('kpi-active-sellers');

    if (elRev) elRev.textContent = this.formatCurrency(rev);
    if (elOrders) elOrders.textContent = `${orders} vente${orders > 1 ? 's' : ''}`;
    if (elProfit) elProfit.textContent = this.formatCurrency(profit);
    if (elMargin) elMargin.textContent = `${margin.toFixed(1)}% Marge`;
    if (elInventory) elInventory.textContent = this.formatCurrency(kpis.inventory_sale_value);
    if (elStockUnits) elStockUnits.textContent = `${kpis.total_stock_units} articles répertoriés (${kpis.total_products_count} réf.)`;
    if (elCommissions) elCommissions.textContent = this.formatCurrency(kpis.total_commissions_earned);
    if (elActiveSellers) elActiveSellers.textContent = `${kpis.active_sellers_count} vendeur${kpis.active_sellers_count > 1 ? 's' : ''}`;
  }

  /* ==========================================================================
     GRAPHIQUES CHART.JS
     ========================================================================== */

  renderDailyTrendChart(dailyTrend) {
    const canvas = document.getElementById('chart-daily-trend');
    if (!canvas || !dailyTrend) return;

    if (this.charts.trend) {
      this.charts.trend.destroy();
    }

    const labels = dailyTrend.map((d) => {
      const parts = d.date.split('-');
      return parts.length === 3 ? `${parts[2]}/${parts[1]}` : d.date;
    });
    const revenues = dailyTrend.map((d) => d.revenue);
    const profits = dailyTrend.map((d) => d.profit);

    const isDark = this.theme === 'dark';
    const textColor = isDark ? '#94a3b8' : '#64748b';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)';

    const ctx = canvas.getContext('2d');

    // Dégradés
    const revGradient = ctx.createLinearGradient(0, 0, 0, 280);
    revGradient.addColorStop(0, 'rgba(99, 102, 241, 0.45)');
    revGradient.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

    const profitGradient = ctx.createLinearGradient(0, 0, 0, 280);
    profitGradient.addColorStop(0, 'rgba(16, 185, 129, 0.4)');
    profitGradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

    this.charts.trend = new Chart(canvas, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: "Chiffre d'Affaires",
            data: revenues,
            borderColor: '#6366f1',
            backgroundColor: revGradient,
            borderWidth: 2.5,
            tension: 0.35,
            fill: true,
            pointBackgroundColor: '#6366f1',
            pointRadius: 4,
            pointHoverRadius: 6,
          },
          {
            label: 'Bénéfice Réalisé',
            data: profits,
            borderColor: '#10b981',
            backgroundColor: profitGradient,
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointBackgroundColor: '#10b981',
            pointRadius: 3,
            pointHoverRadius: 5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false,
        },
        plugins: {
          legend: {
            position: 'top',
            labels: {
              color: textColor,
              font: { family: 'Inter', size: 12 },
              usePointStyle: true,
              pointStyle: 'circle',
            },
          },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            titleColor: '#f1f5f9',
            bodyColor: '#cbd5e1',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (context) => {
                return ` ${context.dataset.label} : ${this.formatCurrency(context.parsed.y)}`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: textColor, font: { family: 'Inter', size: 11 } },
            grid: { color: gridColor },
          },
          y: {
            ticks: {
              color: textColor,
              font: { family: 'Inter', size: 11 },
              callback: (value) => `${(value / 1000).toFixed(0)}k DA`,
            },
            grid: { color: gridColor },
          },
        },
      },
    });
  }

  renderPaymentMethodsChart(pmData) {
    const canvas = document.getElementById('chart-payment-methods');
    const legendEl = document.getElementById('payment-methods-legend');
    if (!canvas || !pmData) return;

    if (this.charts.payments) {
      this.charts.payments.destroy();
    }

    const methodNames = {
      CASH: 'Espèces (Cash)',
      CARD: 'Carte Bancaire / CIB',
      CREDIT: 'Crédit Client',
    };

    const colors = {
      CASH: '#10b981',
      CARD: '#6366f1',
      CREDIT: '#f59e0b',
    };

    const keys = Object.keys(pmData);
    const labels = keys.map((k) => methodNames[k] || k);
    const totals = keys.map((k) => pmData[k].amount || 0);
    const chartColors = keys.map((k) => colors[k] || '#06b6d4');

    const hasData = totals.some((t) => t > 0);

    this.charts.payments = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [
          {
            data: hasData ? totals : [1],
            backgroundColor: hasData ? chartColors : ['#334155'],
            borderWidth: 0,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => {
                if (!hasData) return ' Aucun encaissement';
                return ` ${context.label} : ${this.formatCurrency(context.raw)}`;
              },
            },
          },
        },
      },
    });

    if (legendEl) {
      if (!hasData) {
        legendEl.innerHTML = `<span class="text-muted text-center" style="font-size:0.8rem; display:block; padding: 10px 0;">Aucun encaissement sur la période</span>`;
      } else {
        legendEl.innerHTML = keys
          .map(
            (k) => `
            <div class="legend-item">
              <span style="display:flex; align-items:center;">
                <span class="legend-dot" style="background: ${colors[k] || '#06b6d4'}"></span>
                <span>${methodNames[k] || k}</span>
              </span>
              <span style="font-weight: 600; color: var(--text-main);">${pmData[k].percentage.toFixed(1)}%</span>
            </div>
          `
          )
          .join('');
      }
    }
  }

  /* ==========================================================================
     TABLEAUX : TOP VENDEURS & ALERTES STOCK
     ========================================================================== */

  renderTopSellersTable(sellers) {
    const tbody = document.getElementById('top-sellers-tbody');
    if (!tbody) return;

    if (!sellers || sellers.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Aucune vente enregistrée pour le moment.</td></tr>`;
      return;
    }

    tbody.innerHTML = sellers
      .map(
        (s) => `
        <tr>
          <td>
            <strong>${this.escapeHtml(s.full_name || s.username)}</strong>
            <div class="text-dim" style="font-size: 0.75rem;">@${this.escapeHtml(s.username)}</div>
          </td>
          <td>${s.sales_count}</td>
          <td><span class="text-success">${this.formatCurrency(s.turnover)}</span></td>
          <td><span class="text-primary">${this.formatCurrency(s.commissions)}</span></td>
          <td><span class="badge badge-accent">${s.commission_rate || 0}%</span></td>
        </tr>
      `
      )
      .join('');
  }

  renderLowStockAlerts(alerts) {
    const tbody = document.getElementById('low-stock-tbody');
    const badgeCount = document.getElementById('low-stock-badge-count');
    if (!tbody) return;

    const count = alerts ? alerts.length : 0;
    if (badgeCount) {
      badgeCount.textContent = `${count} alerte${count > 1 ? 's' : ''}`;
      badgeCount.className = count > 0 ? 'badge badge-danger' : 'badge badge-success';
    }

    if (!alerts || alerts.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Tous les stocks sont à des niveaux sains.</td></tr>`;
      return;
    }

    tbody.innerHTML = alerts
      .map(
        (p) => `
        <tr>
          <td><strong>${this.escapeHtml(p.name)}</strong></td>
          <td><code>${this.escapeHtml(p.sku || '-')}</code></td>
          <td><span class="text-danger font-bold">${p.quantity}</span></td>
          <td>${p.min_stock_alert}</td>
          <td>
            <button class="btn btn-sm btn-outline" onclick="app.showToast('Article: ${this.escapeHtml(p.name)} - Seuil atteint (${p.quantity}/${p.min_stock_alert})', 'warning')">Réappro</button>
          </td>
        </tr>
      `
      )
      .join('');
  }

  /* ==========================================================================
     TAB 2 : RENTABILITÉ & MARGES PAR PRODUIT
     ========================================================================== */

  renderProfitTable() {
    const tbody = document.getElementById('profit-table-tbody');
    if (!tbody) return;

    if (!this.dashboardData || !this.dashboardData.top_products_profit) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Aucune donnée de rentabilité disponible.</td></tr>`;
      return;
    }

    let products = [...this.dashboardData.top_products_profit];

    // Calcul du % de marge unitaire pour chaque article
    products = products.map((p) => {
      const margin = p.revenue > 0 ? ((p.profit / p.revenue) * 100) : 0;
      const unitSale = p.quantity > 0 ? (p.revenue / p.quantity) : 0;
      const unitCost = p.quantity > 0 ? (p.cost / p.quantity) : 0;
      return {
        ...p,
        margin_percent: margin,
        unit_sale_price: unitSale,
        unit_cost_price: unitCost,
      };
    });

    // Filtrage
    const searchInput = document.getElementById('profit-search-input');
    if (searchInput && searchInput.value.trim() !== '') {
      const q = searchInput.value.toLowerCase().trim();
      products = products.filter(
        (p) => p.name.toLowerCase().includes(q) || (p.sku && p.sku.toLowerCase().includes(q))
      );
    }

    // Tri
    const sortSelect = document.getElementById('profit-sort-select');
    const sortKey = sortSelect ? sortSelect.value : 'profit_desc';

    products.sort((a, b) => {
      switch (sortKey) {
        case 'profit_desc': return b.profit - a.profit;
        case 'revenue_desc': return b.revenue - a.revenue;
        case 'quantity_desc': return b.quantity - a.quantity;
        case 'margin_desc': return b.margin_percent - a.margin_percent;
        default: return 0;
      }
    });

    if (products.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Aucun article ne correspond à votre filtre.</td></tr>`;
      return;
    }

    tbody.innerHTML = products
      .map(
        (p) => `
        <tr>
          <td><strong>${this.escapeHtml(p.name)}</strong></td>
          <td><code>${this.escapeHtml(p.sku || '-')}</code></td>
          <td>${this.formatCurrency(p.unit_sale_price)}</td>
          <td>${this.formatCurrency(p.unit_cost_price)}</td>
          <td><span class="badge badge-dim">${p.quantity}</span></td>
          <td><span class="text-primary">${this.formatCurrency(p.revenue)}</span></td>
          <td><span class="text-success">${this.formatCurrency(p.profit)}</span></td>
          <td>
            <span class="badge ${p.margin_percent >= 25 ? 'badge-success' : p.margin_percent >= 10 ? 'badge-warning' : 'badge-danger'}">
              ${p.margin_percent.toFixed(1)}%
            </span>
          </td>
        </tr>
      `
      )
      .join('');
  }

  /* ==========================================================================
     TAB 3 : GESTION DES VENDEURS
     ========================================================================== */

  async loadSellersList() {
    try {
      const sellers = await this.fetchApi('/sellers/');
      this.sellers = sellers;

      // Badge dans le menu
      const badge = document.getElementById('sellers-count-badge');
      if (badge) badge.textContent = sellers.length;

      this.renderSellersTable();
      this.populatePermissionsSellerSelect();
    } catch (err) {
      this.showToast(`Erreur chargement vendeurs : ${err.message}`, 'error');
    }
  }

  renderSellersTable() {
    const tbody = document.getElementById('sellers-table-tbody');
    if (!tbody) return;

    if (!this.sellers || this.sellers.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">Aucun vendeur enregistré. Cliquez sur "Ajouter un Vendeur" pour démarrer.</td></tr>`;
      return;
    }

    tbody.innerHTML = this.sellers
      .map(
        (s) => `
        <tr>
          <td>
            <strong>${this.escapeHtml(s.full_name || s.username)}</strong>
            <div class="text-dim" style="font-size:0.75rem;">${s.point_of_sale_name || 'Toutes boutiques'}</div>
          </td>
          <td><code>${this.escapeHtml(s.username)}</code></td>
          <td>${this.escapeHtml(s.phone || '-')}</td>
          <td><span class="badge badge-accent">${s.commission_rate}%</span></td>
          <td>${s.total_sales_count || 0}</td>
          <td><span class="text-success">${this.formatCurrency(s.total_turnover || 0)}</span></td>
          <td><span class="text-primary">${this.formatCurrency(s.total_commission || 0)}</span></td>
          <td>
            <span class="badge ${s.is_active ? 'badge-success' : 'badge-danger'}">
              ${s.is_active ? 'Actif' : 'Désactivé'}
            </span>
          </td>
          <td class="text-right">
            <div style="display:inline-flex; gap: 6px;">
              <button class="btn btn-sm btn-secondary" title="Voir Fiche & Ventes" onclick="app.viewSellerDetails(${s.id})">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
              </button>
              <button class="btn btn-sm btn-outline" title="Autorisations" onclick="app.openSellerPermissionsDirect(${s.id})">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
              </button>
              <button class="btn btn-sm btn-secondary" title="Modifier" onclick="app.editSeller(${s.id})">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
              </button>
              <button class="btn btn-sm btn-danger" title="Supprimer" onclick="app.deleteSeller(${s.id})">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              </button>
            </div>
          </td>
        </tr>
      `
      )
      .join('');
  }

  openNewSellerModal() {
    document.getElementById('seller-modal-title').textContent = 'Nouveau Vendeur';
    document.getElementById('seller-form-id').value = '';
    document.getElementById('seller-fullname').value = '';
    document.getElementById('seller-username').value = '';
    document.getElementById('seller-password').value = '';
    document.getElementById('seller-pwd-hint').textContent = '(requis)';
    document.getElementById('seller-password').required = true;
    document.getElementById('seller-phone').value = '';
    document.getElementById('seller-commission-rate').value = '5.0';
    document.getElementById('seller-is-active').checked = true;

    this.populatePosDropdown('seller-pos-id');
    this.openModal('seller-modal');
  }

  editSeller(id) {
    const seller = this.sellers.find((s) => s.id === id);
    if (!seller) return;

    document.getElementById('seller-modal-title').textContent = `Modifier ${seller.full_name || seller.username}`;
    document.getElementById('seller-form-id').value = seller.id;
    document.getElementById('seller-fullname').value = seller.full_name || '';
    document.getElementById('seller-username').value = seller.username;
    document.getElementById('seller-password').value = '';
    document.getElementById('seller-pwd-hint').textContent = '(laisser vide pour conserver)';
    document.getElementById('seller-password').required = false;
    document.getElementById('seller-phone').value = seller.phone || '';
    document.getElementById('seller-commission-rate').value = seller.commission_rate || '0.0';
    document.getElementById('seller-is-active').checked = seller.is_active;

    this.populatePosDropdown('seller-pos-id', seller.point_of_sale_id);
    this.openModal('seller-modal');
  }

  async handleSellerSubmit(e) {
    e.preventDefault();
    const id = document.getElementById('seller-form-id').value;
    const isEdit = !!id;

    const payload = {
      full_name: document.getElementById('seller-fullname').value.trim(),
      username: document.getElementById('seller-username').value.trim().toLowerCase(),
      phone: document.getElementById('seller-phone').value.trim() || null,
      commission_rate: parseFloat(document.getElementById('seller-commission-rate').value) || 0.0,
      is_active: document.getElementById('seller-is-active').checked,
      point_of_sale_id: document.getElementById('seller-pos-id').value ? parseInt(document.getElementById('seller-pos-id').value, 10) : null,
    };

    const pwd = document.getElementById('seller-password').value;
    if (pwd) {
      payload.password = pwd;
    }

    try {
      if (isEdit) {
        await this.fetchApi(`/sellers/${id}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        this.showToast('Vendeur mis à jour avec succès', 'success');
      } else {
        if (!pwd) {
          throw new Error('Le mot de passe est obligatoire pour créer un vendeur.');
        }
        await this.fetchApi('/sellers/', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        this.showToast('Vendeur créé avec succès', 'success');
      }

      this.closeModal('seller-modal');
      this.loadSellersList();
      this.loadDashboardData();
    } catch (err) {
      this.showToast(`Erreur : ${err.message}`, 'error');
    }
  }

  async deleteSeller(id) {
    const seller = this.sellers.find((s) => s.id === id);
    if (!seller) return;

    if (!confirm(`Êtes-vous sûr de vouloir supprimer ou désactiver le vendeur "${seller.full_name || seller.username}" ?`)) {
      return;
    }

    try {
      await this.fetchApi(`/sellers/${id}`, { method: 'DELETE' });
      this.showToast('Vendeur supprimé / désactivé', 'info');
      this.loadSellersList();
      this.loadDashboardData();
    } catch (err) {
      this.showToast(`Échec de la suppression : ${err.message}`, 'error');
    }
  }

  async viewSellerDetails(id) {
    try {
      const data = await this.fetchApi(`/sellers/${id}/stats`);
      const s = data.seller;

      document.getElementById('detail-seller-name').textContent = s.full_name || s.username;
      document.getElementById('detail-seller-sub').textContent = `@${s.username} • Taux commission: ${s.commission_rate}% • ${s.point_of_sale_name || 'Toutes boutiques'}`;
      document.getElementById('detail-sales-count').textContent = s.total_sales_count || 0;
      document.getElementById('detail-turnover').textContent = this.formatCurrency(s.total_turnover || 0);
      document.getElementById('detail-commissions').textContent = this.formatCurrency(s.total_commission || 0);

      const tbody = document.getElementById('detail-sales-tbody');
      const salesList = data.recent_sales || data.sales || [];
      if (salesList.length > 0) {
        tbody.innerHTML = salesList
          .map(
            (sale) => `
            <tr>
              <td><code>${this.escapeHtml(sale.reference_number)}</code></td>
              <td>${sale.issue_date ? new Date(sale.issue_date).toLocaleDateString('fr-FR') : (sale.date ? new Date(sale.date).toLocaleDateString('fr-FR') : '-')}</td>
              <td>${this.escapeHtml(sale.partner_name || sale.customer_name || 'Client comptoir')}</td>
              <td><span class="text-success">${this.formatCurrency(sale.total_amount)}</span></td>
              <td><span class="text-primary">${this.formatCurrency(sale.commission_amount || 0)}</span></td>
            </tr>
          `
          )
          .join('');
      } else {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Aucune vente enregistrée pour ce vendeur.</td></tr>`;
      }

      this.openModal('seller-details-modal');
    } catch (err) {
      this.showToast(`Erreur chargement détails : ${err.message}`, 'error');
    }
  }

  /* ==========================================================================
     TAB 4 : MATRICE DES AUTORISATIONS VENDEURS
     ========================================================================== */

  populatePermissionsSellerSelect() {
    const select = document.getElementById('perm-seller-select');
    if (!select) return;

    if (this.sellers.length === 0) {
      select.innerHTML = `<option value="">Aucun vendeur disponible</option>`;
      return;
    }

    select.innerHTML = this.sellers
      .map(
        (s) => `<option value="${s.id}" ${this.selectedSellerId === s.id ? 'selected' : ''}>${this.escapeHtml(s.full_name || s.username)} (@${s.username})</option>`
      )
      .join('');

    // Si aucun sélectionné, prendre le premier
    if (!this.selectedSellerId && this.sellers.length > 0) {
      this.selectedSellerId = this.sellers[0].id;
    }

    if (this.selectedSellerId) {
      this.loadSellerPermissions(this.selectedSellerId);
    }
  }

  openSellerPermissionsDirect(sellerId) {
    this.selectedSellerId = sellerId;
    this.switchTab('permissions');
  }

  async loadSellerPermissions(sellerId) {
    this.selectedSellerId = sellerId;
    const select = document.getElementById('perm-seller-select');
    if (select) select.value = sellerId;

    try {
      const perms = await this.fetchApi(`/sellers/${sellerId}/permissions`);
      this.setPermissionsFormValues(perms);
    } catch (err) {
      this.showToast(`Erreur chargement permissions : ${err.message}`, 'error');
    }
  }

  setPermissionsFormValues(perms) {
    if (!perms) return;

    const discountCheckbox = document.getElementById('perm-can-discount');
    const discountCapInput = document.getElementById('perm-max-discount-percent');
    const editPriceCheckbox = document.getElementById('perm-can-edit-price');
    const viewMarginCheckbox = document.getElementById('perm-can-view-margin');
    const cancelSaleCheckbox = document.getElementById('perm-can-cancel-sale');
    const giveCreditCheckbox = document.getElementById('perm-can-give-credit');
    const manageStockCheckbox = document.getElementById('perm-can-manage-stock');
    const restrictedPosCheckbox = document.getElementById('perm-restricted-to-pos');

    if (discountCheckbox) discountCheckbox.checked = !!perms.can_discount;
    if (discountCapInput) discountCapInput.value = perms.max_discount_percent !== undefined ? perms.max_discount_percent : 5.0;
    if (editPriceCheckbox) editPriceCheckbox.checked = !!perms.can_edit_price;
    if (viewMarginCheckbox) viewMarginCheckbox.checked = !!perms.can_view_margin;
    if (cancelSaleCheckbox) cancelSaleCheckbox.checked = !!perms.can_cancel_sale;
    if (giveCreditCheckbox) giveCreditCheckbox.checked = !!perms.can_give_credit;
    if (manageStockCheckbox) manageStockCheckbox.checked = !!perms.can_manage_stock;
    if (restrictedPosCheckbox) restrictedPosCheckbox.checked = perms.restricted_to_pos !== undefined ? perms.restricted_to_pos : true;

    // Visibilité du champ plafond remise
    const discountCapRow = document.getElementById('perm-discount-cap-row');
    if (discountCapRow) {
      discountCapRow.style.opacity = perms.can_discount ? '1' : '0.4';
    }
  }

  applyPermissionPreset(presetKey) {
    const preset = this.permissionPresets[presetKey];
    if (!preset) return;

    this.setPermissionsFormValues(preset);

    document.querySelectorAll('.preset-chips .btn-chip').forEach((btn) => {
      btn.classList.remove('active');
    });
    if (window.event && window.event.target) {
      window.event.target.classList.add('active');
    }

    this.showToast(`Profil "${presetKey}" appliqué sur l'interface. Cliquez sur Enregistrer pour valider.`, 'info');
  }

  async saveCurrentSellerPermissions() {
    if (!this.selectedSellerId) {
      this.showToast('Veuillez d\'abord sélectionner un vendeur.', 'warning');
      return;
    }

    const payload = {
      permissions: {
        can_discount: document.getElementById('perm-can-discount').checked,
        max_discount_percent: parseFloat(document.getElementById('perm-max-discount-percent').value) || 0.0,
        can_edit_price: document.getElementById('perm-can-edit-price').checked,
        can_view_margin: document.getElementById('perm-can-view-margin').checked,
        can_cancel_sale: document.getElementById('perm-can-cancel-sale').checked,
        can_give_credit: document.getElementById('perm-can-give-credit').checked,
        can_manage_stock: document.getElementById('perm-can-manage-stock').checked,
        restricted_to_pos: document.getElementById('perm-restricted-to-pos').checked,
      },
    };

    const saveBtn = document.getElementById('btn-save-permissions');
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = `<span>Enregistrement en cours...</span>`;
    }

    try {
      const res = await this.fetchApi(`/sellers/${this.selectedSellerId}/permissions`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });

      this.showToast('Autorisations du vendeur enregistrées avec succès !', 'success');

      // Mettre à jour en cache local
      const seller = this.sellers.find((s) => s.id === this.selectedSellerId);
      if (seller) {
        seller.permissions = res.permissions;
      }
    } catch (err) {
      this.showToast(`Échec de l'enregistrement : ${err.message}`, 'error');
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
          <span>Enregistrer les Autorisations de ce Vendeur</span>
        `;
      }
    }
  }

  /* ==========================================================================
     TAB 5 : POINTS DE VENTE & DÉPÔTS
     ========================================================================== */

  async loadPointsOfSale() {
    try {
      const posList = await this.fetchApi('/points-of-sale/');
      this.pointsOfSale = posList;
      this.renderPointsOfSaleTable();
    } catch (err) {
      console.warn('Points de vente non chargés:', err.message);
    }
  }

  renderPointsOfSaleTable() {
    const tbody = document.getElementById('pos-table-tbody');
    if (!tbody) return;

    if (!this.pointsOfSale || this.pointsOfSale.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">Aucun point de vente répertorié.</td></tr>`;
      return;
    }

    const posStatsMap = {};
    if (this.dashboardData && this.dashboardData.sales_by_pos) {
      this.dashboardData.sales_by_pos.forEach((p) => {
        posStatsMap[p.id] = p;
      });
    }

    tbody.innerHTML = this.pointsOfSale
      .map((pos) => {
        const stats = posStatsMap[pos.id] || { sales_count: 0, turnover: 0 };
        return `
          <tr>
            <td>
              <strong>${this.escapeHtml(pos.name)}</strong>
              <div class="text-dim" style="font-size:0.75rem;">${this.escapeHtml(pos.code || '')}</div>
            </td>
            <td>${this.escapeHtml(pos.city || pos.address || '-')}</td>
            <td>${this.escapeHtml(pos.manager_name || 'Non assigné')}</td>
            <td>${this.escapeHtml(pos.phone || '-')}</td>
            <td><span class="badge badge-dim">${stats.sales_count}</span></td>
            <td><span class="text-success">${this.formatCurrency(stats.turnover)}</span></td>
            <td>
              <span class="badge ${pos.is_active ? 'badge-success' : 'badge-danger'}">
                ${pos.is_active ? 'Ouvert' : 'Inactif'}
              </span>
            </td>
          </tr>
        `;
      })
      .join('');
  }

  populatePosDropdown(elementId, selectedId = null) {
    const select = document.getElementById(elementId);
    if (!select) return;

    select.innerHTML = '<option value="">Tous les points de vente</option>';
    this.pointsOfSale.forEach((pos) => {
      const option = document.createElement('option');
      option.value = pos.id;
      option.textContent = pos.name;
      if (selectedId && pos.id === selectedId) {
        option.selected = true;
      }
      select.appendChild(option);
    });
  }

  /* ==========================================================================
     TAB 6 : AUDIT DES VENTES & DOCUMENTS COMMERCIAUX
     ========================================================================== */

  async loadDocuments() {
    try {
      const docs = await this.fetchApi('/documents/');
      this.documents = docs;
      this.renderDocumentsTable();
    } catch (err) {
      this.showToast(`Erreur chargement documents : ${err.message}`, 'error');
    }
  }

  renderDocumentsTable() {
    const tbody = document.getElementById('documents-table-tbody');
    if (!tbody) return;

    if (!this.documents || this.documents.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Aucun document commercial enregistré.</td></tr>`;
      return;
    }

    let docs = [...this.documents];
    const searchInput = document.getElementById('docs-search-input');
    if (searchInput && searchInput.value.trim() !== '') {
      const q = searchInput.value.toLowerCase().trim();
      docs = docs.filter(
        (d) =>
          d.reference_number.toLowerCase().includes(q) ||
          (d.partner_name && d.partner_name.toLowerCase().includes(q)) ||
          (d.seller_name && d.seller_name.toLowerCase().includes(q))
      );
    }

    tbody.innerHTML = docs
      .slice(0, 50)
      .map(
        (doc) => `
        <tr>
          <td><code>${this.escapeHtml(doc.reference_number)}</code></td>
          <td>${new Date(doc.created_at).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })}</td>
          <td>${this.escapeHtml(doc.partner_name || 'Client comptoir')}</td>
          <td>${this.escapeHtml(doc.point_of_sale_name || 'Caisse Centrale')}</td>
          <td>
            ${
              doc.seller_name
                ? `<span class="badge badge-accent">@${this.escapeHtml(doc.seller_name)}</span>`
                : '<span class="text-dim">Gérant / Non attribué</span>'
            }
          </td>
          <td><span class="text-success font-bold">${this.formatCurrency(doc.total_amount)}</span></td>
          <td><span class="text-primary">${this.formatCurrency(doc.commission_amount || 0)}</span></td>
          <td>
            <span class="badge ${
              doc.status === 'DELIVERED' || doc.status === 'VALIDATED'
                ? 'badge-success'
                : doc.status === 'CANCELLED'
                ? 'badge-danger'
                : 'badge-warning'
            }">
              ${doc.status}
            </span>
          </td>
        </tr>
      `
      )
      .join('');
  }

  /* ==========================================================================
     UTILITAIRES & MODALES
     ========================================================================== */

  openModal(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.style.display = 'flex';
  }

  closeModal(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.style.display = 'none';
  }

  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
      success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`,
      error: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`,
      warning: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`,
      info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`,
    };

    toast.innerHTML = `
      ${icons[type] || icons.info}
      <span>${this.escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(60px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  formatCurrency(value) {
    if (value === null || value === undefined || isNaN(value)) return '0,00 DA';
    return new Intl.NumberFormat('fr-DZ', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value) + ' DA';
  }

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Initialisation globale
let app;
window.addEventListener('DOMContentLoaded', () => {
  app = new AdminApp();
});
