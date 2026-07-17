class NotificacionesManager {
    constructor(options = {}) {
        this.pollInterval = options.pollInterval || 15000;
        this.apiBase = options.apiBase || '/notificaciones/api/';
        this.csrfToken = options.csrfToken || '';
        this.dropdownEl = null;
        this.badgeEl = null;
        this.bellEl = null;
        this.lastCount = -1;
        this.init();
    }

    init() {
        this.bellEl = document.querySelector('.notif-bell-btn');
        this.dropdownEl = document.getElementById('notif-dropdown');
        this.badgeEl = document.getElementById('notif-badge-count');
        if (!this.bellEl) return;

        this.bellEl.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggleDropdown();
        });
        document.addEventListener('click', (e) => {
            if (this.dropdownEl && !e.target.closest('.notif-bell-wrapper')) {
                this.dropdownEl.classList.remove('open');
            }
        });
        this.startPolling();
    }

    startPolling() {
        this.poll();
        setInterval(() => this.poll(), this.pollInterval);
    }

    async poll() {
        try {
            const [countRes, notifsRes] = await Promise.all([
                fetch(this.apiBase + 'conteo/'),
                fetch(this.apiBase + 'no-leidas/')
            ]);
            const countData = await countRes.json();
            const notifsData = await notifsRes.json();
            this.updateBadge(countData.count);
            if (countData.count > this.lastCount && this.lastCount >= 0) {
                this.playSound();
            }
            this.lastCount = countData.count;
            if (this.dropdownEl && this.dropdownEl.classList.contains('open')) {
                this.renderDropdown(notifsData.notificaciones, countData.count);
            }
            this.updateCachedData(notifsData.notificaciones, countData.count);
        } catch (e) {
            // silent
        }
    }

    updateBadge(count) {
        if (this.badgeEl) {
            this.badgeEl.textContent = count > 99 ? '99+' : count;
            this.badgeEl.style.display = count > 0 ? 'flex' : 'none';
        }
    }

    toggleDropdown() {
        if (!this.dropdownEl) return;
        const isOpen = this.dropdownEl.classList.toggle('open');
        if (isOpen) {
            this.loadDropdown();
        }
    }

    async loadDropdown() {
        try {
            const [countRes, notifsRes] = await Promise.all([
                fetch(this.apiBase + 'conteo/'),
                fetch(this.apiBase + 'no-leidas/')
            ]);
            const countData = await countRes.json();
            const notifsData = await notifsRes.json();
            this.renderDropdown(notifsData.notificaciones, countData.count);
        } catch (e) {
            this.renderDropdown([], 0);
        }
    }

    renderDropdown(notifs, count) {
        if (!this.dropdownEl) return;
        let html = '';
        html += `<div class="notif-dropdown-header">
            <span>Notificaciones</span>
            <a href="${this.getPageUrl()}" data-notif-link>Ver todas</a>
        </div>`;
        html += `<div class="notif-dropdown-body">`;
        if (notifs.length === 0) {
            html += `<div class="notif-dropdown-empty">
                <ion-icon name="notifications-off-outline"></ion-icon>
                <p>No hay notificaciones nuevas</p>
            </div>`;
        } else {
            notifs.forEach(n => {
                const link = n.enlace || '#';
                const moduloClass = (n.modulo || '').toLowerCase().replace(/\s+/g, '_');
                html += `<a href="${link}" class="notif-item unread" data-id="${n.id}">
                    <div class="notif-item-icon ${n.tipo.toLowerCase()}">
                        <ion-icon name="${n.icono || 'information-circle'}"></ion-icon>
                    </div>
                    <div class="notif-item-content">
                        <div class="notif-item-title">${this.escapeHtml(n.titulo)}</div>
                        <div class="notif-item-msg">${this.escapeHtml(n.mensaje)}</div>
                        <div class="notif-item-time">${n.tiempo || ''}
                            <span class="notif-modulo-badge ${moduloClass}">${n.modulo || ''}</span>
                        </div>
                    </div>
                </a>`;
            });
        }
        html += `</div>`;
        html += `<div class="notif-dropdown-footer">
            <a href="${this.getPageUrl()}" data-notif-link>Ir al Centro de Notificaciones</a>
        </div>`;
        this.dropdownEl.innerHTML = html;
        this.dropdownEl.querySelectorAll('.notif-item').forEach(el => {
            el.addEventListener('click', (e) => {
                const id = el.dataset.id;
                if (id) this.markAsRead(id);
            });
        });
        this.dropdownEl.querySelectorAll('[data-notif-link]').forEach(el => {
            el.addEventListener('click', () => {
                this.dropdownEl.classList.remove('open');
            });
        });
    }

    markAsRead(id) {
        fetch(this.apiBase + 'marcar-leida/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({ notif_id: id })
        }).catch(() => {});
        if (this.badgeEl) {
            const curr = parseInt(this.badgeEl.textContent) || 0;
            this.badgeEl.textContent = Math.max(0, curr - 1);
            if (parseInt(this.badgeEl.textContent) <= 0) {
                this.badgeEl.style.display = 'none';
            }
        }
    }

    updateCachedData(notifs, count) {
        // store for potential use
        this._cachedNotifs = notifs;
        this._cachedCount = count;
    }

    getPageUrl() {
        const path = window.location.pathname;
        if (path.startsWith('/portalsub/')) {
            return '/portalsub/notificaciones/';
        }
        return '/notificaciones/';
    }

    playSound() {
        try {
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACAf39/f4B/f3+AgH9/f3+AgIB/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f3+AgH9/f4B/f3+AgIB/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4B/f3+AgH9/f4');
            audio.volume = 0.3;
            audio.play().catch(() => {});
        } catch (e) {}
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

function initNotificaciones(options) {
    return new NotificacionesManager(options);
}
