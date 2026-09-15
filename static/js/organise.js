/**
 * organise.js — Life Organisation Tracker
 * Handles CRUD for the Organise section (vehicles, insurance, bills, etc.)
 */
(function () {
    'use strict';

    let organiseItems = [];
    let editingItemId = null;
    let pendingPhotoFile = null;
    let photoRemoved = false;
    let currentItemKind = 'other'; // vehicle | renewal | other
    let pickCarResolver = null;

    const serviceCache = {};
    const openServicePanels = new Set();
    let editingServiceId = null;
    let editingServiceItemId = null;
    let editingStatusItemId = null;
    let statusFocusField = 'km';

    const CATEGORY_ICONS = {
        Car: '🚗',
        Property: '🏠',
        Finance: '💰',
        Health: '🏥',
        Insurance: '🛡️',
        General: '📋',
    };

    const KNOWN_RENEWAL_TITLES = new Set([
        'Registration / Rego',
        'CTP / Green Slip',
        'Comprehensive Insurance',
        'Roadworthy Certificate',
        'Road Tax',
        'Roadside Assistance',
        'E-Tag / Toll Account',
        'Warranty',
        'Car Loan',
        'Parking Permit',
    ]);

    const EMOJI_DATA = [
        { label: 'Vehicles', emojis: ['🚗', '🚕', '🚙', '🏎', '🚓', '🚑', '🚒', '🛻', '🚐', '🚌', '🏍', '🛵', '🚲', '🚜', '✈️', '🚁', '🚢', '⛵', '🚂'] },
        { label: 'Places', emojis: ['🏠', '🏡', '🏢', '🏥', '🏦', '⛽', '🏪', '🏫', '🏨', '🏗', '🏛'] },
        { label: 'Finance', emojis: ['💰', '💵', '💳', '💎', '📈', '💹', '💸', '🪙', '🏦'] },
        { label: 'Health', emojis: ['💊', '🩺', '🩻', '💉', '🦷', '❤️', '🧬', '🏃'] },
        { label: 'Time', emojis: ['📅', '📆', '🗓', '⏰', '⏱', '⌚', '🕐'] },
        { label: 'Tools', emojis: ['🔧', '🔨', '⚙️', '🔩', '🪛', '🛠️', '🔋', '🧰', '🪜'] },
        { label: 'Docs', emojis: ['📋', '📄', '📃', '📑', '🗂', '📁', '📂', '🗃', '🔖'] },
        { label: 'Symbols', emojis: ['⚡', '🔑', '🛡️', '⭐', '🎯', '🔔', '✅', '⚠️', '🚨', '🔥', '💡', '🌟', '🎉', '🏆', '🪪', '🔐'] },
    ];

    function formatDate(iso) {
        if (!iso) return '—';
        const d = new Date(iso + 'T00:00:00');
        return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    function daysLabel(days) {
        if (days === null || days === undefined) return '';
        if (days < 0) return `${Math.abs(days)}d overdue`;
        if (days === 0) return 'Due today';
        return `${days}d away`;
    }

    function isoDateParts(dt) {
        return [
            dt.getFullYear(),
            String(dt.getMonth() + 1).padStart(2, '0'),
            String(dt.getDate()).padStart(2, '0'),
        ].join('-');
    }

    function todayISO() {
        return isoDateParts(new Date());
    }

    function addOneYear(iso) {
        const [y, m, d] = String(iso).split('-').map(Number);
        return isoDateParts(new Date(y + 1, m - 1, d));
    }

    function nextDueDate(iso) {
        let next = addOneYear(iso);
        const today = todayISO();
        let guard = 0;
        while (next < today && guard < 10) {
            next = addOneYear(next);
            guard += 1;
        }
        return next;
    }

    function statusClass(status) {
        if (status === 'overdue') return 'org-status-overdue';
        if (status === 'due_soon') return 'org-status-soon';
        return 'org-status-ok';
    }

    function statusLabel(status) {
        if (status === 'overdue') return '⚠️ Overdue';
        if (status === 'due_soon') return '🔔 Due soon';
        return '✅ OK';
    }

    function groupBy(arr, key) {
        return arr.reduce((acc, item) => {
            const k = item[key] || 'General';
            (acc[k] = acc[k] || []).push(item);
            return acc;
        }, {});
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function hasVehicleDetails(item) {
        return !!(item && (item.vehicle_make || item.vehicle_model || item.vehicle_year || item.vehicle_rego));
    }

    function isKnownRenewalTitle(title) {
        return KNOWN_RENEWAL_TITLES.has(String(title || '').trim());
    }

    function isVehicle(item) {
        return item.category === 'Car' && !item.parent_id && (hasVehicleDetails(item) || !isKnownRenewalTitle(item.title));
    }

    function isOrphanRenewal(item) {
        return !item.parent_id && !hasVehicleDetails(item) && isKnownRenewalTitle(item.title);
    }

    function carLabel(item) {
        if (!item) return 'Car';
        const parts = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean);
        const name = parts.length ? parts.join(' ') : item.title;
        return item.vehicle_rego ? `${name} · ${item.vehicle_rego}` : name;
    }

    function vehicleItems() {
        return organiseItems.filter(isVehicle);
    }

    function childItems(carId) {
        return organiseItems.filter(i => i.parent_id === carId);
    }

    function carHasChildren(carId) {
        return organiseItems.some(i => i.parent_id === carId);
    }

    function currentKm(item, services) {
        const fromServices = (services || []).filter(s => s.mileage != null).map(s => s.mileage);
        const serviceMax = fromServices.length ? Math.max(...fromServices) : null;
        if (item && item.current_odometer != null) {
            return serviceMax != null ? Math.max(item.current_odometer, serviceMax) : item.current_odometer;
        }
        return serviceMax;
    }

    function nextServiceInfo(item, services) {
        const list = services || [];
        const fromSvc = list.filter(s => s.next_service_date || s.next_service_mileage != null);
        fromSvc.sort((a, b) => String(a.next_service_date || '9999').localeCompare(String(b.next_service_date || '9999')));
        const fallback = fromSvc[0] || null;
        const date = (item && item.next_service_date) || (fallback && fallback.next_service_date) || null;
        const km = (item && item.next_service_mileage != null)
            ? item.next_service_mileage
            : (fallback && fallback.next_service_mileage != null ? fallback.next_service_mileage : null);
        return { date, km };
    }

    function lastServiceInfo(services) {
        return (services && services.length) ? services[0] : null;
    }

    function serviceDueClass(dateIso) {
        if (!dateIso) return 'neutral';
        const today = new Date(); today.setHours(0, 0, 0, 0);
        const nextDate = new Date(dateIso + 'T00:00:00');
        const diffDays = Math.round((nextDate - today) / 86400000);
        if (diffDays < 0) return 'overdue';
        if (diffDays <= 30) return 'due_soon';
        return 'ok';
    }

    function buildEmojiPickerHtml() {
        return EMOJI_DATA.map(group => `
            <div class="org-ep-group">
                <div class="org-ep-group-label">${group.label}</div>
                <div class="org-ep-row">
                    ${group.emojis.map(e => `<button type="button" class="org-ep-emoji" data-emoji="${e}">${e}</button>`).join('')}
                </div>
            </div>
        `).join('');
    }

    function openEmojiPicker() {
        const popup = document.getElementById('org-emoji-popup');
        if (!popup) return;
        if (!popup.dataset.built) {
            popup.innerHTML = buildEmojiPickerHtml();
            popup.dataset.built = '1';
        }
        const isOpen = popup.style.display !== 'none' && popup.style.display !== '';
        popup.style.display = isOpen ? 'none' : 'block';
    }

    function selectEmoji(emoji) {
        document.getElementById('org-input-icon').value = emoji;
        document.getElementById('org-emoji-display').textContent = emoji;
        document.getElementById('org-emoji-popup').style.display = 'none';
    }

    function clearEmoji() {
        document.getElementById('org-input-icon').value = '';
        document.getElementById('org-emoji-display').textContent = '☺';
        const popup = document.getElementById('org-emoji-popup');
        if (popup) popup.style.display = 'none';
    }

    function renderOrganise() {
        const container = document.getElementById('organise-items-container');
        if (!container) return;

        if (!organiseItems.length) {
            container.innerHTML = '<p class="org-empty">No items yet. Add a car first, then attach registration, insurance and other documents to it.</p>';
            return;
        }

        const cars = vehicleItems();
        const orphans = organiseItems.filter(isOrphanRenewal);
        const linkedIds = new Set(organiseItems.filter(i => i.parent_id).map(i => i.id));
        const others = organiseItems.filter(i => !isVehicle(i) && !isOrphanRenewal(i) && !linkedIds.has(i.id));

        let html = '';

        if (cars.length) {
            html += `<div class="org-category-group">
                <h3 class="org-category-heading">🚗 Cars</h3>
                <div class="org-car-list">
                    ${cars.map(renderCarCard).join('')}
                </div>
            </div>`;
        }

        if (orphans.length) {
            html += `<div class="org-category-group">
                <h3 class="org-category-heading">🔗 Needs a car</h3>
                <p class="org-orphan-hint">These were added from a car template but are not linked yet. Attach them so they sit on the right vehicle.</p>
                <div class="org-cards-row">
                    ${orphans.map(renderItemCard).join('')}
                </div>
            </div>`;
        }

        if (others.length) {
            const grouped = groupBy(others, 'category');
            const categories = Object.keys(grouped).sort();
            html += categories.map(cat => {
                const icon = CATEGORY_ICONS[cat] || '📋';
                const items = grouped[cat];
                return `
                <div class="org-category-group">
                    <h3 class="org-category-heading">${icon} ${escapeHtml(cat)}</h3>
                    <div class="org-cards-row">
                        ${items.map(renderItemCard).join('')}
                    </div>
                </div>`;
            }).join('');
        }

        container.innerHTML = html || '<p class="org-empty">No items yet. Click <b>+ Add</b> to get started.</p>';

        cars.forEach(c => {
            renderCarWidgets(c.id);
            fetchServiceSummary(c.id);
        });

        openServicePanels.forEach(id => {
            const panel = document.getElementById(`svc-panel-${id}`);
            const chevron = document.getElementById(`svc-chevron-${id}`);
            if (!panel) return;
            panel.style.display = '';
            if (chevron) chevron.style.transform = 'rotate(180deg)';
            renderServicePanel(id);
        });
    }

    function renderCarCard(item) {
        const photoStr = item.photo_url
            ? `<div class="org-car-thumb"><img src="${escapeHtml(item.photo_url)}" alt="Photo" class="org-photo-zoomable" loading="lazy" onclick="orgOpenLightbox(this.src,this.alt)"></div>`
            : `<div class="org-car-thumb org-car-thumb--placeholder">${item.icon || '🚗'}</div>`;
        const parts = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean);
        const vehicleName = parts.length ? escapeHtml(parts.join(' ')) : escapeHtml(item.title);
        const regoStr = item.vehicle_rego
            ? `<span class="org-rego-badge">${escapeHtml(item.vehicle_rego)}</span>` : '';
        const notesStr = item.notes
            ? `<div class="org-card-notes">${escapeHtml(item.notes)}</div>` : '';

        return `
        <div class="org-car-card" data-id="${item.id}">
            <div class="org-car-header">
                ${photoStr}
                <div class="org-car-info">
                    <div class="org-car-title">
                        <span class="org-car-name">${vehicleName}</span>
                        ${regoStr}
                    </div>
                    ${notesStr}
                </div>
                <div class="org-car-actions admin-only">
                    <button class="org-btn-edit" onclick="organiseEdit(${item.id})" title="Edit car"><i class="fas fa-pencil-alt"></i></button>
                    <button class="org-btn-delete" onclick="organiseDelete(${item.id})" title="Delete car"><i class="fas fa-trash"></i></button>
                </div>
            </div>
            <div class="org-widget-grid" id="car-widgets-${item.id}">
                <div class="org-widget org-widget--placeholder"><span class="org-svc-loading">Loading…</span></div>
            </div>
            <div class="org-svc-toggle-bar">
                <button class="org-svc-toggle-btn" onclick="toggleServicePanel(${item.id})">
                    <i class="fas fa-wrench"></i> Service history
                    <i class="fas fa-chevron-down org-svc-chevron" id="svc-chevron-${item.id}"></i>
                </button>
                <button class="org-svc-add-btn admin-only" onclick="openServiceModal(${item.id}, null)" title="Add service record">
                    <i class="fas fa-plus"></i> Log service
                </button>
            </div>
            <div class="org-svc-panel" id="svc-panel-${item.id}" style="display:none;">
                <div class="org-svc-list" id="svc-list-${item.id}">
                    <span class="org-svc-loading">Loading…</span>
                </div>
            </div>
        </div>`;
    }

    function widgetMarkup(opts) {
        const status = opts.status ? ` org-widget--${opts.status}` : '';
        const extra = opts.extraClass ? ` ${opts.extraClass}` : '';
        const action = opts.onclick ? ` onclick="${opts.onclick}"` : '';
        const hint = opts.hint ? ` title="${escapeHtml(opts.hint)}"` : '';
        const meta = opts.meta ? `<div class="org-widget-meta">${opts.meta}</div>` : '';
        const edit = opts.editable
            ? '<span class="org-widget-edit"><i class="fas fa-pen"></i></span>'
            : '';
        return `
        <button type="button" class="org-widget${status}${extra}"${action}${hint}>
            ${edit}
            <span class="org-widget-label">${opts.icon || ''} ${opts.label}</span>
            <span class="org-widget-value">${opts.value}</span>
            ${meta}
        </button>`;
    }

    function fetchServiceSummary(itemId) {
        fetch(`/api/organise/${itemId}/services`)
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    serviceCache[itemId] = res.services;
                    renderCarWidgets(itemId);
                    const panel = document.getElementById(`svc-panel-${itemId}`);
                    if (panel && panel.style.display !== 'none') renderServicePanel(itemId);
                }
            })
            .catch(() => {});
    }

    function renderCarWidgets(itemId) {
        const grid = document.getElementById(`car-widgets-${itemId}`);
        if (!grid) return;
        const item = organiseItems.find(i => i.id === itemId);
        if (!item) return;
        const services = serviceCache[itemId] || [];
        const docs = childItems(itemId);
        const km = currentKm(item, services);
        const next = nextServiceInfo(item, services);
        const last = lastServiceInfo(services);
        const nextStatus = serviceDueClass(next.date);
        let remainingKm = null;
        if (km != null && next.km != null) remainingKm = next.km - km;

        const widgets = [];
        widgets.push(widgetMarkup({
            label: 'Kilometres',
            icon: '<i class="fas fa-tachometer-alt"></i>',
            value: km != null ? `${km.toLocaleString()} km` : 'Set km',
            meta: km != null ? 'Tap to update' : 'No odometer yet',
            hint: 'Edit current kilometres',
            editable: true,
            extraClass: 'org-widget--km',
            onclick: `organiseEditStatus(${itemId},'km')`,
        }));

        const nextValue = next.date || next.km != null
            ? (next.date ? formatDate(next.date) : 'Date not set')
            : 'Set next service';
        const nextMetaParts = [];
        if (next.km != null) nextMetaParts.push(`${next.km.toLocaleString()} km`);
        if (remainingKm != null) {
            nextMetaParts.push(remainingKm <= 0 ? 'Overdue' : `${remainingKm.toLocaleString()} km to go`);
        }
        widgets.push(widgetMarkup({
            label: 'Next service',
            icon: '<i class="fas fa-calendar-check"></i>',
            value: nextValue,
            meta: nextMetaParts.join(' · ') || 'Tap to set date or km',
            hint: 'Edit next service',
            editable: true,
            status: (next.date || next.km != null) ? nextStatus : 'neutral',
            extraClass: 'org-widget--service',
            onclick: `organiseEditStatus(${itemId},'service')`,
        }));

        widgets.push(widgetMarkup({
            label: 'Last service',
            icon: '<i class="fas fa-wrench"></i>',
            value: last ? escapeHtml(last.service_type) : 'No records',
            meta: last
                ? `${last.service_date ? formatDate(last.service_date) : 'No date'}${last.mileage != null ? ' · ' + last.mileage.toLocaleString() + ' km' : ''}`
                : 'Tap to log a service',
            hint: last ? 'Edit last service record' : 'Log a service',
            editable: true,
            extraClass: 'org-widget--last',
            onclick: last ? `organiseEditService(${itemId},${last.id})` : `openServiceModal(${itemId}, null)`,
        }));

        docs.forEach(doc => {
            const sc = doc.paid ? 'ok' : (doc.status || 'neutral');
            const due = doc.due_date
                ? `${formatDate(doc.due_date)}${!doc.paid && doc.days_until_due != null ? ' · ' + daysLabel(doc.days_until_due) : ''}`
                : 'No due date';
            const extra = [
                doc.provider ? escapeHtml(doc.provider) : '',
                doc.paid ? 'Paid' : '',
                doc.cost != null ? `$${parseFloat(doc.cost).toFixed(2)}` : '',
            ].filter(Boolean).join(' · ');
            widgets.push(widgetMarkup({
                label: escapeHtml(doc.title),
                icon: doc.icon || '<i class="fas fa-file-alt"></i>',
                value: due,
                meta: extra || 'Tap to edit',
                hint: `Edit ${doc.title}`,
                editable: true,
                status: sc,
                extraClass: 'org-widget--doc',
                onclick: `organiseEdit(${doc.id})`,
            }));
        });

        widgets.push(`
        <button type="button" class="org-widget org-widget--add" onclick="organiseAddRenewal(${itemId})" title="Add a document">
            <span class="org-widget-label"><i class="fas fa-plus"></i> Document</span>
            <span class="org-widget-value">Add renewal</span>
            <div class="org-widget-meta">Rego, insurance, CTP…</div>
        </button>`);

        let progress = '';
        if (km != null && next.km != null && next.km > 0) {
            const targetMileage = next.km;
            const remaining = targetMileage - km;
            const interval = Math.max(1000, targetMileage - Math.max(0, targetMileage - 10000));
            const currentProgress = Math.max(0, km - Math.max(0, targetMileage - interval));
            const pct = Math.min(100, Math.max(0, Math.round((currentProgress / interval) * 100)));
            let barStatus = '';
            if (remaining <= 0 || remaining <= 1000) barStatus = 'is-danger';
            else if (remaining <= 2500) barStatus = 'is-warning';
            const remainingLabel = remaining <= 0
                ? '<span class="org-progress-overdue"><i class="fas fa-exclamation-circle"></i> Service overdue</span>'
                : `<span>${remaining.toLocaleString()} km until service</span>`;
            progress = `
            <button type="button" class="org-widget org-widget--wide" onclick="organiseEditStatus(${itemId},'service')">
                <span class="org-widget-edit"><i class="fas fa-pen"></i></span>
                <span class="org-widget-label"><i class="fas fa-road"></i> Service interval</span>
                <div class="org-service-milestone-header">
                    <span>${km.toLocaleString()} / ${targetMileage.toLocaleString()} km (${pct}%)</span>
                    ${remainingLabel}
                </div>
                <div class="org-service-milestone-bar-bg">
                    <div class="org-service-milestone-bar-fill ${barStatus}" style="width:${pct}%;"></div>
                </div>
            </button>`;
        }

        grid.innerHTML = widgets.join('') + progress;
    }

    function toggleServicePanel(itemId) {
        const panel = document.getElementById(`svc-panel-${itemId}`);
        const chevron = document.getElementById(`svc-chevron-${itemId}`);
        if (!panel) return;
        const isOpen = panel.style.display !== 'none';
        panel.style.display = isOpen ? 'none' : '';
        if (chevron) chevron.style.transform = isOpen ? '' : 'rotate(180deg)';
        if (isOpen) openServicePanels.delete(itemId);
        else openServicePanels.add(itemId);
        if (!isOpen) loadServicePanel(itemId);
    }

    function loadServicePanel(itemId) {
        fetch(`/api/organise/${itemId}/services`)
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    serviceCache[itemId] = res.services;
                    renderServicePanel(itemId);
                    renderCarWidgets(itemId);
                }
            })
            .catch(() => {
                const list = document.getElementById(`svc-list-${itemId}`);
                if (list) list.innerHTML = '<span class="org-svc-empty">Failed to load.</span>';
            });
    }

    function renderServicePanel(itemId) {
        const list = document.getElementById(`svc-list-${itemId}`);
        if (!list) return;
        const services = serviceCache[itemId] || [];
        if (!services.length) {
            list.innerHTML = '<span class="org-svc-empty">No service records yet. Click <b>+ Add Service</b> to log one.</span>';
            return;
        }
        list.innerHTML = services.map(s => {
            const dateStr = s.service_date ? formatDate(s.service_date) : '—';
            const odomStr = s.mileage != null ? `<span class="org-svc-odometer"><i class="fas fa-tachometer-alt"></i> ${s.mileage.toLocaleString()} km</span>` : '';
            const costStr = s.cost != null ? `<span class="org-svc-cost">$${parseFloat(s.cost).toFixed(2)}</span>` : '';
            const provStr = s.provider ? `<span class="org-svc-provider"><i class="fas fa-building"></i> ${escapeHtml(s.provider)}</span>` : '';
            const notesStr = s.notes ? `<div class="org-svc-notes">${escapeHtml(s.notes)}</div>` : '';
            return `
            <div class="org-svc-row" data-svc-id="${s.id}">
                <div class="org-svc-row-main">
                    <div class="org-svc-type">${escapeHtml(s.service_type)}</div>
                    <div class="org-svc-meta">
                        <span class="org-svc-date"><i class="fas fa-calendar-alt"></i> ${dateStr}</span>
                        ${odomStr}${provStr}${costStr}
                    </div>
                    ${notesStr}
                </div>
                <div class="org-svc-row-actions admin-only">
                    <button class="org-btn-edit" onclick="organiseEditService(${itemId},${s.id})" title="Edit"><i class="fas fa-pencil-alt"></i></button>
                    <button class="org-btn-delete" onclick="organiseDeleteService(${itemId},${s.id})" title="Delete"><i class="fas fa-trash"></i></button>
                </div>
            </div>`;
        }).join('');
    }

    function renderItemCard(item) {
        const sc = statusClass(item.status);
        const sl = statusLabel(item.status);
        const dl = item.due_date ? daysLabel(item.days_until_due) : '';
        const paidBadge = item.paid
            ? '<span class="org-paid-badge">Paid ✓</span>'
            : '<span class="org-unpaid-badge">Unpaid</span>';
        const costStr = item.cost != null ? ` · $${parseFloat(item.cost).toFixed(2)}` : '';
        const providerStr = item.provider
            ? `<div class="org-card-provider"><i class="fas fa-building"></i> ${escapeHtml(item.provider)}</div>` : '';
        const dueDateStr = item.due_date
            ? `<div class="org-card-date"><i class="fas fa-calendar-alt"></i> Due: <b>${formatDate(item.due_date)}</b> <span class="org-days-label ${sc}">${dl}</span></div>`
            : '';
        const lastDateStr = item.last_date
            ? `<div class="org-card-date org-last-date"><i class="fas fa-history"></i> Last: ${formatDate(item.last_date)}</div>`
            : '';
        const notesStr = item.notes
            ? `<div class="org-card-notes"><i class="fas fa-sticky-note"></i> ${escapeHtml(item.notes)}</div>`
            : '';

        let vehicleStr = '';
        if (item.category === 'Car' && !item.parent_id) {
            const parts = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean);
            if (parts.length || item.vehicle_rego) {
                vehicleStr = `<div class="org-card-vehicle">`;
                if (parts.length) vehicleStr += `<i class="fas fa-car" style="opacity:.6; margin-right:4px;"></i>${escapeHtml(parts.join(' '))}`;
                if (item.vehicle_rego) vehicleStr += ` <span class="org-rego-badge">${escapeHtml(item.vehicle_rego)}</span>`;
                vehicleStr += `</div>`;
            }
        }

        const photoStr = item.photo_url
            ? `<div class="org-card-photo"><img src="${escapeHtml(item.photo_url)}" alt="Photo" class="org-card-photo-img org-photo-zoomable" loading="lazy" onclick="orgOpenLightbox(this.src,this.alt)"></div>`
            : '';

        const attachBtn = isOrphanRenewal(item)
            ? `<button class="org-btn-attach" onclick="organiseAttachToCar(${item.id})" title="Attach to a car"><i class="fas fa-link"></i></button>`
            : '';

        return `
        <div class="org-card ${sc}" data-id="${item.id}">
            ${photoStr}
            <div class="org-card-header">
                <span class="org-card-icon">${item.icon || CATEGORY_ICONS[item.category] || '📋'}</span>
                <span class="org-card-title">${escapeHtml(item.title)}</span>
                <span class="org-status-dot ${sc}" title="${sl}"></span>
            </div>
            ${vehicleStr}
            ${providerStr}
            ${dueDateStr}
            ${lastDateStr}
            <div class="org-card-footer">
                ${paidBadge}${costStr ? `<span class="org-cost">${costStr}</span>` : ''}
                ${notesStr}
            </div>
            <div class="org-card-actions admin-only">
                ${attachBtn}
                <button class="org-btn-edit" onclick="organiseEdit(${item.id})" title="Edit"><i class="fas fa-pencil-alt"></i></button>
                <button class="org-btn-toggle-paid" onclick="organiseTogglePaid(${item.id})" title="${item.paid ? 'Mark unpaid' : 'Mark paid and set next due date'}">
                    ${item.paid ? '<i class="fas fa-times-circle"></i>' : '<i class="fas fa-check-circle"></i>'}
                </button>
                <button class="org-btn-delete" onclick="organiseDelete(${item.id})" title="Delete"><i class="fas fa-trash"></i></button>
            </div>
        </div>`;
    }

    function setItemKind(kind) {
        currentItemKind = kind;
        document.querySelectorAll('#org-kind-toggle .org-kind-btn').forEach(btn => {
            btn.classList.toggle('is-active', btn.dataset.kind === kind);
        });
        updateFormVisibility();
    }

    function fillCarSelect(selectedId) {
        const sel = document.getElementById('org-input-parent-id');
        if (!sel) return;
        const cars = vehicleItems().filter(c => c.id !== editingItemId);
        const current = selectedId != null ? String(selectedId) : '';
        sel.innerHTML = '<option value="">Select a car…</option>' + cars.map(c =>
            `<option value="${c.id}">${escapeHtml(carLabel(c))}</option>`
        ).join('');
        sel.value = current && cars.some(c => String(c.id) === current) ? current : '';
    }

    function updateCustomCategoryVisibility() {
        const sel = document.getElementById('org-input-category');
        const customWrap = document.getElementById('org-custom-category-wrap');
        if (sel && customWrap) {
            customWrap.style.display = sel.value === '__custom__' ? '' : 'none';
        }
    }

    function updateFormVisibility() {
        const cat = document.getElementById('org-input-category');
        const kindWrap = document.getElementById('org-car-kind-wrap');
        const linkedWrap = document.getElementById('org-linked-car-wrap');
        const vf = document.getElementById('org-vehicle-fields');
        const isCarCategory = cat && cat.value === 'Car';
        const editingVehicle = editingItemId && carHasChildren(editingItemId);

        if (kindWrap) {
            kindWrap.style.display = isCarCategory && !editingVehicle ? '' : 'none';
        }
        if (!isCarCategory && currentItemKind !== 'renewal') {
            currentItemKind = 'other';
        }

        const showLinked = currentItemKind === 'renewal';
        const showVehicle = isCarCategory && currentItemKind === 'vehicle';
        if (linkedWrap) linkedWrap.style.display = showLinked ? '' : 'none';
        if (vf) vf.style.display = showVehicle ? '' : 'none';
        const renewalFields = document.getElementById('org-renewal-fields');
        if (renewalFields) renewalFields.style.display = showVehicle ? 'none' : '';
    }

    function openModal(item, preset) {
        preset = preset || {};
        editingItemId = item ? item.id : null;
        pendingPhotoFile = null;
        photoRemoved = false;

        const modal = document.getElementById('organise-modal');
        if (!modal) return;

        const isRenewal = !!(item && item.parent_id) || preset.kind === 'renewal' || !!(item && isOrphanRenewal(item));
        const isCar = !!(item && isVehicle(item)) || preset.kind === 'vehicle';
        currentItemKind = isRenewal ? 'renewal' : (isCar || (!item && (preset.kind || 'vehicle') === 'vehicle') ? 'vehicle' : 'other');
        if (!item && !preset.kind && !preset.category) currentItemKind = 'vehicle';
        if (preset.kind) currentItemKind = preset.kind;

        const titleDefault = item ? item.title : (preset.title || '');
        document.getElementById('org-modal-title').textContent = item
            ? (isRenewal ? 'Edit document' : (isCar ? 'Edit car' : 'Edit Item'))
            : (currentItemKind === 'renewal' ? 'Add document' : (currentItemKind === 'vehicle' ? 'Add car' : 'Add Item'));
        document.getElementById('org-input-title').value = titleDefault;
        document.getElementById('org-input-category').value = item
            ? item.category
            : (preset.category || (currentItemKind === 'standalone' ? 'General' : 'Car'));
        if (preset.category) document.getElementById('org-input-category').value = preset.category;
        if (item && !['Car', 'Property', 'Finance', 'Health', 'Insurance', 'General'].includes(item.category)) {
            document.getElementById('org-input-category').value = '__custom__';
        }
        document.getElementById('org-input-custom-category').value =
            (item && !['Car', 'Property', 'Finance', 'Health', 'Insurance', 'General'].includes(item.category)) ? item.category : '';
        document.getElementById('org-input-provider').value = item ? (item.provider || '') : '';
        document.getElementById('org-input-due-date').value = item ? (item.due_date || '') : '';
        document.getElementById('org-input-last-date').value = item ? (item.last_date || '') : '';
        document.getElementById('org-input-cost').value = item ? (item.cost != null ? item.cost : '') : '';
        document.getElementById('org-input-reminder').value = item ? (item.reminder_days || 30) : 30;
        document.getElementById('org-input-paid').checked = item ? Boolean(item.paid) : false;
        document.getElementById('org-input-notes').value = item ? (item.notes || '') : '';

        const icon = item ? (item.icon || '') : (preset.icon || '');
        document.getElementById('org-input-icon').value = icon;
        document.getElementById('org-emoji-display').textContent = icon || '☺';
        const popup = document.getElementById('org-emoji-popup');
        if (popup) popup.style.display = 'none';

        document.getElementById('org-input-vehicle-make').value = item ? (item.vehicle_make || '') : '';
        document.getElementById('org-input-vehicle-model').value = item ? (item.vehicle_model || '') : '';
        document.getElementById('org-input-vehicle-year').value = item ? (item.vehicle_year || '') : '';
        document.getElementById('org-input-vehicle-rego').value = item ? (item.vehicle_rego || '') : '';
        const odoInput = document.getElementById('org-input-odometer');
        if (odoInput) odoInput.value = item && item.current_odometer != null ? item.current_odometer : '';

        const parentId = item ? item.parent_id : preset.parentId;
        fillCarSelect(parentId);

        const photoInput = document.getElementById('org-input-photo');
        if (photoInput) photoInput.value = '';
        const preview = document.getElementById('org-photo-preview');
        const previewImg = document.getElementById('org-photo-preview-img');
        if (preview && previewImg) {
            if (item && item.photo_url) {
                previewImg.src = item.photo_url;
                preview.style.display = '';
            } else {
                previewImg.src = '';
                preview.style.display = 'none';
            }
        }

        setItemKind(currentItemKind);
        updateCustomCategoryVisibility();
        modal.style.display = 'flex';
        setTimeout(() => document.getElementById('org-input-title').focus(), 80);
    }

    function closeModal() {
        const modal = document.getElementById('organise-modal');
        if (modal) modal.style.display = 'none';
        editingItemId = null;
        pendingPhotoFile = null;
        photoRemoved = false;
        currentItemKind = 'other';
    }

    function getFormData() {
        const categorySel = document.getElementById('org-input-category').value;
        const customCat = document.getElementById('org-input-custom-category').value.trim();
        const category = categorySel === '__custom__' ? (customCat || 'General') : categorySel;
        const parentRaw = document.getElementById('org-input-parent-id')?.value;
        const isRenewal = currentItemKind === 'renewal';
        const odoVal = document.getElementById('org-input-odometer')?.value;
        const data = {
            title: document.getElementById('org-input-title').value.trim(),
            category: isRenewal ? 'Car' : category,
            provider: document.getElementById('org-input-provider').value.trim(),
            due_date: document.getElementById('org-input-due-date').value || null,
            last_date: document.getElementById('org-input-last-date').value || null,
            cost: document.getElementById('org-input-cost').value !== ''
                ? parseFloat(document.getElementById('org-input-cost').value) : null,
            reminder_days: parseInt(document.getElementById('org-input-reminder').value, 10) || 30,
            paid: document.getElementById('org-input-paid').checked,
            notes: document.getElementById('org-input-notes').value.trim(),
            icon: document.getElementById('org-input-icon').value,
            vehicle_make: isRenewal ? '' : document.getElementById('org-input-vehicle-make').value.trim(),
            vehicle_model: isRenewal ? '' : document.getElementById('org-input-vehicle-model').value.trim(),
            vehicle_year: isRenewal ? null : (document.getElementById('org-input-vehicle-year').value
                ? parseInt(document.getElementById('org-input-vehicle-year').value, 10) : null),
            vehicle_rego: isRenewal ? '' : document.getElementById('org-input-vehicle-rego').value.trim(),
            current_odometer: isRenewal ? null : (odoVal !== '' && odoVal != null ? parseInt(odoVal, 10) : null),
            parent_id: isRenewal ? (parentRaw ? parseInt(parentRaw, 10) : null) : null,
        };
        if (!data.title && currentItemKind === 'vehicle') {
            data.title = [data.vehicle_year, data.vehicle_make, data.vehicle_model].filter(Boolean).join(' ') || 'Car';
        }
        return data;
    }

    async function saveItem() {
        const data = getFormData();
        if (!data.title) {
            alert('Please enter a title.');
            return;
        }
        if (currentItemKind === 'renewal' && !data.parent_id) {
            alert('Choose which car this document belongs to.');
            return;
        }

        const url = editingItemId ? `/api/organise/${editingItemId}` : '/api/organise';
        const method = editingItemId ? 'PUT' : 'POST';

        let res;
        try {
            const r = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            res = await r.json();
        } catch (_) {
            alert('Network error — please try again.');
            return;
        }

        if (!res.success) {
            alert(res.error || 'Failed to save');
            return;
        }

        const itemId = res.item.id;
        if (pendingPhotoFile) {
            const fd = new FormData();
            fd.append('photo', pendingPhotoFile);
            try {
                const pr = await fetch(`/api/organise/${itemId}/photo`, { method: 'POST', body: fd });
                const pres = await pr.json();
                if (!pres.success) alert('Item saved but photo upload failed: ' + (pres.error || 'unknown error'));
            } catch (_) {
                alert('Item saved but photo upload failed (network error).');
            }
        }

        closeModal();
        loadOrganise();
    }

    function openServiceModal(itemId, service) {
        editingServiceItemId = itemId;
        editingServiceId = service ? service.id : null;
        const modal = document.getElementById('vehicle-service-modal');
        if (!modal) return;
        const car = organiseItems.find(i => i.id === itemId);
        const carBit = car ? ` — ${carLabel(car)}` : '';
        document.getElementById('svc-modal-title').textContent = (service ? 'Edit Service Record' : 'Add Service Record') + carBit;
        document.getElementById('svc-input-type').value = service ? service.service_type : '';
        document.getElementById('svc-input-date').value = service ? (service.service_date || '') : todayISO();
        document.getElementById('svc-input-mileage').value = service
            ? (service.mileage != null ? service.mileage : '')
            : (car && car.current_odometer != null ? car.current_odometer : '');
        document.getElementById('svc-input-provider').value = service ? (service.provider || '') : '';
        document.getElementById('svc-input-cost').value = service ? (service.cost != null ? service.cost : '') : '';
        document.getElementById('svc-input-notes').value = service ? (service.notes || '') : '';
        document.getElementById('svc-input-next-date').value = service
            ? (service.next_service_date || '')
            : (car && car.next_service_date ? car.next_service_date : '');
        document.getElementById('svc-input-next-mileage').value = service
            ? (service.next_service_mileage != null ? service.next_service_mileage : '')
            : (car && car.next_service_mileage != null ? car.next_service_mileage : '');
        modal.style.display = 'flex';
        setTimeout(() => document.getElementById('svc-input-type').focus(), 80);
    }

    function closeServiceModal() {
        const modal = document.getElementById('vehicle-service-modal');
        if (modal) modal.style.display = 'none';
        editingServiceId = null;
        editingServiceItemId = null;
    }

    async function saveServiceRecord() {
        const typeVal = document.getElementById('svc-input-type').value.trim();
        if (!typeVal) { alert('Please enter a service type.'); return; }
        const payload = {
            service_type: typeVal,
            service_date: document.getElementById('svc-input-date').value || null,
            mileage: document.getElementById('svc-input-mileage').value !== '' ? parseInt(document.getElementById('svc-input-mileage').value, 10) : null,
            provider: document.getElementById('svc-input-provider').value.trim() || null,
            cost: document.getElementById('svc-input-cost').value !== '' ? parseFloat(document.getElementById('svc-input-cost').value) : null,
            notes: document.getElementById('svc-input-notes').value.trim() || null,
            next_service_date: document.getElementById('svc-input-next-date').value || null,
            next_service_mileage: document.getElementById('svc-input-next-mileage').value !== '' ? parseInt(document.getElementById('svc-input-next-mileage').value, 10) : null,
        };
        const url = editingServiceId
            ? `/api/organise/${editingServiceItemId}/services/${editingServiceId}`
            : `/api/organise/${editingServiceItemId}/services`;
        const method = editingServiceId ? 'PUT' : 'POST';
        try {
            const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const res = await r.json();
            if (!res.success) { alert(res.error || 'Failed to save'); return; }
        } catch (_) {
            alert('Network error — please try again.');
            return;
        }
        const savedItemId = editingServiceItemId;
        closeServiceModal();
        if (savedItemId) openServicePanels.add(savedItemId);
        loadOrganise();
    }

    function closeCarPicker(result) {
        const overlay = document.getElementById('org-car-picker');
        if (overlay) overlay.style.display = 'none';
        const resolve = pickCarResolver;
        pickCarResolver = null;
        if (resolve) resolve(result);
    }

    function pickCar(title, hint) {
        const cars = vehicleItems();
        if (!cars.length) {
            alert('Add a car first, then attach this to it.');
            openModal(null, { kind: 'vehicle', title: '', icon: '🚗', category: 'Car' });
            return Promise.resolve(null);
        }
        if (cars.length === 1) return Promise.resolve(cars[0].id);

        return new Promise(resolve => {
            pickCarResolver = resolve;
            const overlay = document.getElementById('org-car-picker');
            const list = document.getElementById('org-car-picker-list');
            const titleEl = document.getElementById('org-car-picker-title');
            const hintEl = document.getElementById('org-car-picker-hint');
            if (!overlay || !list) { resolve(null); return; }
            if (titleEl) titleEl.textContent = title || 'Which car?';
            if (hintEl) hintEl.textContent = hint || 'Choose the car this belongs to.';
            list.innerHTML = cars.map(c => `
                <button type="button" class="org-car-picker-item" data-car-id="${c.id}">
                    <span class="org-card-icon">${c.icon || '🚗'}</span>
                    <span>${escapeHtml(carLabel(c))}</span>
                </button>
            `).join('');
            overlay.style.display = 'flex';
        });
    }

    function applyCarTemplate(itemEl) {
        const kind = itemEl.dataset.kind || (itemEl.dataset.type === 'service' ? 'service' : 'renewal');
        const title = itemEl.dataset.title || '';
        const icon = itemEl.dataset.icon || '';
        const category = itemEl.dataset.category || 'Car';

        if (kind === 'vehicle') {
            openModal(null, { kind: 'vehicle', title: '', icon: icon || '🚗', category: 'Car' });
            return;
        }
        if (kind === 'standalone') {
            openModal(null, { kind: 'other', title, icon, category });
            return;
        }
        if (kind === 'service') {
            pickCar('Log a service', 'Choose which car this service is for.').then(carId => {
                if (!carId) return;
                openServiceModal(carId, null);
                if (title) document.getElementById('svc-input-type').value = title;
            });
            return;
        }

        pickCar(title || 'Attach to a car', 'This document will stay on the car you pick so you can edit it later.').then(carId => {
            if (!carId) return;
            openModal(null, { kind: 'renewal', parentId: carId, title, icon, category: 'Car' });
        });
    }

    window.orgOpenLightbox = function (src, alt) {
        const lb = document.getElementById('org-lightbox');
        const img = document.getElementById('org-lightbox-img');
        if (!lb || !img) return;
        img.src = src;
        img.alt = alt || '';
        lb.style.display = 'flex';
    };

    window.organiseEditStatus = function (itemId, focus) {
        openStatusModal(itemId, focus);
    };

    function openStatusModal(itemId, focus) {
        const item = organiseItems.find(i => i.id === itemId);
        if (!item) return;
        editingStatusItemId = itemId;
        statusFocusField = focus || 'km';
        const services = serviceCache[itemId] || [];
        const km = currentKm(item, services);
        const next = nextServiceInfo(item, services);
        const modal = document.getElementById('org-status-modal');
        const title = document.getElementById('org-status-modal-title');
        const hint = document.getElementById('org-status-modal-hint');
        if (!modal) return;
        if (title) {
            title.textContent = statusFocusField === 'service'
                ? `Next service — ${carLabel(item)}`
                : `Kilometres — ${carLabel(item)}`;
        }
        if (hint) {
            hint.textContent = statusFocusField === 'service'
                ? 'Update the next service date or kilometre target. You can also log a full service from the history below.'
                : 'Update the current odometer. Logging a service with a higher reading will also raise this.';
        }
        document.getElementById('org-status-odometer').value = km != null ? km : '';
        document.getElementById('org-status-next-date').value = next.date || '';
        document.getElementById('org-status-next-km').value = next.km != null ? next.km : '';
        modal.style.display = 'flex';
        setTimeout(() => {
            const focusEl = statusFocusField === 'service'
                ? document.getElementById('org-status-next-date')
                : document.getElementById('org-status-odometer');
            focusEl?.focus();
        }, 80);
    }

    function closeStatusModal() {
        const modal = document.getElementById('org-status-modal');
        if (modal) modal.style.display = 'none';
        editingStatusItemId = null;
        statusFocusField = 'km';
    }

    async function saveStatusModal() {
        if (!editingStatusItemId) return;
        const payload = {
            current_odometer: document.getElementById('org-status-odometer').value !== ''
                ? parseInt(document.getElementById('org-status-odometer').value, 10) : null,
            next_service_date: document.getElementById('org-status-next-date').value || null,
            next_service_mileage: document.getElementById('org-status-next-km').value !== ''
                ? parseInt(document.getElementById('org-status-next-km').value, 10) : null,
        };
        try {
            const r = await fetch(`/api/organise/${editingStatusItemId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const res = await r.json();
            if (!res.success) { alert(res.error || 'Failed to save'); return; }
        } catch (_) {
            alert('Network error — please try again.');
            return;
        }
        closeStatusModal();
        loadOrganise();
    }

    window.organiseEdit = function (id) {
        const item = organiseItems.find(i => i.id === id);
        if (item) openModal(item);
    };

    window.organiseDelete = function (id) {
        const item = organiseItems.find(i => i.id === id);
        if (!item) return;
        const kids = childItems(id);
        const extra = kids.length ? ` This will also delete ${kids.length} linked document${kids.length === 1 ? '' : 's'}.` : '';
        if (!confirm(`Delete "${item.title}"?${extra}`)) return;
        fetch(`/api/organise/${id}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(res => {
                if (!res.success) { alert(res.error || 'Failed to delete'); return; }
                loadOrganise();
            })
            .catch(() => alert('Network error'));
    };

    window.organiseTogglePaid = function (id) {
        const item = organiseItems.find(i => i.id === id);
        if (!item) return;

        const payload = { paid: !item.paid };
        if (!item.paid && item.due_date) {
            const nextDue = nextDueDate(item.due_date);
            if (!confirm(`Mark "${item.title}" as paid and set the next due date to ${formatDate(nextDue)}?`)) {
                return;
            }
            payload.paid = false;
            payload.last_date = todayISO();
            payload.due_date = nextDue;
        }

        fetch(`/api/organise/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
            .then(r => r.json())
            .then(res => {
                if (!res.success) { alert(res.error || 'Failed to update'); return; }
                loadOrganise();
            })
            .catch(() => alert('Network error'));
    };

    window.organiseAddRenewal = function (carId) {
        openModal(null, { kind: 'renewal', parentId: carId, category: 'Car' });
    };

    window.organiseAttachToCar = function (id) {
        pickCar('Attach to a car', 'Choose which car this document belongs to.').then(carId => {
            if (!carId) return;
            fetch(`/api/organise/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parent_id: carId }),
            })
                .then(r => r.json())
                .then(res => {
                    if (!res.success) { alert(res.error || 'Failed to attach'); return; }
                    loadOrganise();
                })
                .catch(() => alert('Network error'));
        });
    };

    window.organiseEditService = function (itemId, serviceId) {
        const services = serviceCache[itemId] || [];
        const svc = services.find(s => s.id === serviceId);
        if (svc) openServiceModal(itemId, svc);
    };

    window.organiseDeleteService = function (itemId, serviceId) {
        if (!confirm('Delete this service record?')) return;
        fetch(`/api/organise/${itemId}/services/${serviceId}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(res => {
                if (!res.success) { alert(res.error || 'Failed to delete'); return; }
                if (serviceCache[itemId]) {
                    serviceCache[itemId] = serviceCache[itemId].filter(s => s.id !== serviceId);
                }
                renderServicePanel(itemId);
                renderCarWidgets(itemId);
            })
            .catch(() => alert('Network error'));
    };

    window.openServiceModal = openServiceModal;
    window.toggleServicePanel = toggleServicePanel;

    function checkUrgentRenewals(items) {
        const banner = document.getElementById('urgent-renewal-banner');
        if (!banner) return;
        if (!items || !items.length) {
            banner.style.display = 'none';
            return;
        }

        const urgentItems = items.filter(i => !i.paid && i.due_date && i.days_until_due != null && i.days_until_due <= 7);
        if (!urgentItems.length) {
            banner.style.display = 'none';
            return;
        }

        urgentItems.sort((a, b) => a.days_until_due - b.days_until_due);
        const mostUrgent = urgentItems[0];
        const headingEl = document.getElementById('urgent-renewal-heading');
        const badgeEl = document.getElementById('urgent-renewal-badge');
        const descEl = document.getElementById('urgent-renewal-desc');
        const parent = items.find(i => i.id === mostUrgent.parent_id);
        const scope = parent ? carLabel(parent) : (mostUrgent.category || 'Organise');

        const isOverdue = mostUrgent.days_until_due < 0;
        banner.classList.toggle('is-overdue', isOverdue);

        if (isOverdue) {
            const overdueDays = Math.abs(mostUrgent.days_until_due);
            if (badgeEl) badgeEl.textContent = `Overdue (${overdueDays}d ago)`;
            if (headingEl) headingEl.textContent = mostUrgent.title;
            if (descEl) descEl.textContent = `${scope} was due on ${formatDate(mostUrgent.due_date)} · Tap to view details`;
        } else {
            const dueDays = mostUrgent.days_until_due;
            const dueStr = dueDays === 0 ? 'Today' : `in ${dueDays} day${dueDays === 1 ? '' : 's'}`;
            if (badgeEl) badgeEl.textContent = `Due ${dueStr}`;
            if (headingEl) headingEl.textContent = mostUrgent.title;
            if (descEl) descEl.textContent = `${scope} renewal due on ${formatDate(mostUrgent.due_date)} · Tap to view details`;
        }

        banner.style.display = 'flex';
    }

    function loadOrganise() {
        fetch('/api/organise')
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    organiseItems = res.items;
                    renderOrganise();
                    checkUrgentRenewals(organiseItems);
                    if (typeof loadHeaderNotifications === 'function') loadHeaderNotifications();
                }
            })
            .catch(() => {
                const c = document.getElementById('organise-items-container');
                if (c) c.innerHTML = '<p class="org-empty">Failed to load items.</p>';
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        loadOrganise();

        const section = document.getElementById('organise-section');
        if (section) {
            const toggle = section.querySelector('.section-toggle');
            if (toggle) {
                toggle.addEventListener('click', function () {
                    if (!organiseItems.length) loadOrganise();
                });
            }
        }

        document.getElementById('organise-add-btn')?.addEventListener('click', () => openModal(null));
        document.getElementById('org-modal-close')?.addEventListener('click', closeModal);
        document.getElementById('org-modal-cancel')?.addEventListener('click', closeModal);
        document.getElementById('org-modal-save')?.addEventListener('click', saveItem);

        document.getElementById('svc-modal-close')?.addEventListener('click', closeServiceModal);
        document.getElementById('svc-modal-cancel')?.addEventListener('click', closeServiceModal);
        document.getElementById('svc-modal-save')?.addEventListener('click', saveServiceRecord);

        document.getElementById('org-status-modal-close')?.addEventListener('click', closeStatusModal);
        document.getElementById('org-status-modal-cancel')?.addEventListener('click', closeStatusModal);
        document.getElementById('org-status-modal-save')?.addEventListener('click', saveStatusModal);

        const svcModal = document.getElementById('vehicle-service-modal');
        if (svcModal) {
            svcModal.addEventListener('click', function (e) {
                if (e.target === svcModal) closeServiceModal();
            });
        }
        const statusModal = document.getElementById('org-status-modal');
        if (statusModal) {
            statusModal.addEventListener('click', function (e) {
                if (e.target === statusModal) closeStatusModal();
            });
        }

        document.getElementById('org-kind-toggle')?.addEventListener('click', function (e) {
            const btn = e.target.closest('.org-kind-btn');
            if (!btn) return;
            setItemKind(btn.dataset.kind);
            if (btn.dataset.kind === 'renewal') fillCarSelect(document.getElementById('org-input-parent-id')?.value);
        });

        const catSel = document.getElementById('org-input-category');
        if (catSel) {
            catSel.addEventListener('change', () => {
                if (catSel.value === 'Car' && currentItemKind === 'other') setItemKind('vehicle');
                if (catSel.value !== 'Car' && currentItemKind === 'vehicle') setItemKind('other');
                updateCustomCategoryVisibility();
                updateFormVisibility();
            });
        }

        const modal = document.getElementById('organise-modal');
        if (modal) {
            modal.addEventListener('click', function (e) {
                if (e.target === modal) closeModal();
            });
        }

        document.getElementById('org-car-picker-close')?.addEventListener('click', () => closeCarPicker(null));
        const picker = document.getElementById('org-car-picker');
        if (picker) {
            picker.addEventListener('click', function (e) {
                if (e.target === picker) closeCarPicker(null);
                const btn = e.target.closest('.org-car-picker-item');
                if (btn) closeCarPicker(parseInt(btn.dataset.carId, 10));
            });
        }

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeModal();
                closeServiceModal();
                closeStatusModal();
                closeCarPicker(null);
                const lb = document.getElementById('org-lightbox');
                if (lb) lb.style.display = 'none';
                const popup = document.getElementById('org-emoji-popup');
                if (popup) popup.style.display = 'none';
                const qm = document.getElementById('org-quick-menu');
                if (qm) qm.style.display = 'none';
            }
        });

        document.getElementById('org-emoji-btn')?.addEventListener('click', function (e) {
            e.stopPropagation();
            openEmojiPicker();
        });
        document.getElementById('org-emoji-clear')?.addEventListener('click', clearEmoji);

        const emojiPopup = document.getElementById('org-emoji-popup');
        if (emojiPopup) {
            emojiPopup.addEventListener('click', function (e) {
                const btn = e.target.closest('.org-ep-emoji');
                if (btn) selectEmoji(btn.dataset.emoji);
            });
        }

        document.getElementById('org-input-photo')?.addEventListener('change', function () {
            const file = this.files && this.files[0];
            if (!file) return;
            if (file.size > 5 * 1024 * 1024) {
                alert('Photo is too large (max 5 MB).');
                this.value = '';
                return;
            }
            pendingPhotoFile = file;
            photoRemoved = false;
            const reader = new FileReader();
            reader.onload = function (ev) {
                document.getElementById('org-photo-preview-img').src = ev.target.result;
                document.getElementById('org-photo-preview').style.display = '';
            };
            reader.readAsDataURL(file);
        });

        document.getElementById('org-photo-remove')?.addEventListener('click', function () {
            pendingPhotoFile = null;
            photoRemoved = true;
            document.getElementById('org-input-photo').value = '';
            document.getElementById('org-photo-preview-img').src = '';
            document.getElementById('org-photo-preview').style.display = 'none';
        });

        const quickBtn = document.getElementById('org-quick-btn');
        const quickMenu = document.getElementById('org-quick-menu');
        if (quickBtn && quickMenu) {
            quickBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                quickMenu.style.display = quickMenu.style.display === 'none' ? 'block' : 'none';
            });
            quickMenu.addEventListener('click', function (e) {
                const item = e.target.closest('.org-quick-item');
                if (!item) return;
                quickMenu.style.display = 'none';
                applyCarTemplate(item);
            });
            document.addEventListener('click', function () {
                quickMenu.style.display = 'none';
            });
        }
    });
}());
