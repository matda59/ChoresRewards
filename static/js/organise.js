/**

 * organise.js — Life Organisation Tracker

 * Handles CRUD for the Organise section (vehicles, insurance, bills, etc.)

 */

(function () {

    'use strict';



    // ── State ──────────────────────────────────────────────────────────────

    let organiseItems = [];

    let editingItemId = null;

    let pendingPhotoFile = null;

    let photoRemoved = false;

    // Service history state

    const serviceCache = {};      // itemId → array of service records

    let editingServiceId = null;

    let editingServiceItemId = null;



    const CATEGORY_ICONS = {

        'Car': '🚗',

        'Property': '🏠',

        'Finance': '💰',

        'Health': '🏥',

        'Insurance': '🛡️',

        'General': '📋',

    };



    // ── Emoji Picker Data ──────────────────────────────────────────────────

    const EMOJI_DATA = [

        { label: 'Vehicles', emojis: ['🚗','🚕','🚙','🏎','🚓','🚑','🚒','🛻','🚐','🚌','🏍','🛵','🚲','🚜','✈️','🚁','🚢','⛵','🚂'] },

        { label: 'Places', emojis: ['🏠','🏡','🏢','🏥','🏦','⛽','🏪','🏫','🏨','🏗','🏛'] },

        { label: 'Finance', emojis: ['💰','💵','💳','💎','📈','💹','💸','🪙','🏦'] },

        { label: 'Health', emojis: ['💊','🩺','🩻','💉','🦷','❤️','🧬','🏃'] },

        { label: 'Time', emojis: ['📅','📆','🗓','⏰','⏱','⌚','🕐'] },

        { label: 'Tools', emojis: ['🔧','🔨','⚙️','🔩','🪛','🛠️','🔋','🧰','🪜'] },

        { label: 'Docs', emojis: ['📋','📄','📃','📑','🗂','📁','📂','🗃','🔖'] },

        { label: 'Symbols', emojis: ['⚡','🔑','🛡️','⭐','🎯','🔔','✅','⚠️','🚨','🔥','💡','🌟','🎉','🏆','🪪','🔐'] },

    ];



    // ── Helpers ────────────────────────────────────────────────────────────

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



    // ── Emoji Picker ───────────────────────────────────────────────────────

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



    // ── Render ─────────────────────────────────────────────────────────────

    function renderOrganise() {

        const container = document.getElementById('organise-items-container');

        if (!container) return;



        if (!organiseItems.length) {

            container.innerHTML = '<p class="org-empty">No items yet. Click <b>+ Add Item</b> to get started.</p>';

            return;

        }



        const cars = organiseItems.filter(i => i.category === 'Car');

        const others = organiseItems.filter(i => i.category !== 'Car');



        let html = '';



        // ── Car section ────────────────────────────────────────────────────

        if (cars.length) {

            html += `<div class="org-category-group">

                <h3 class="org-category-heading">🚗 Cars</h3>

                <div class="org-car-list">

                    ${cars.map(renderCarCard).join('')}

                </div>

            </div>`;

        }



        // ── Other categories ───────────────────────────────────────────────

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



        container.innerHTML = html;



        // Re-expand any car service panels that were open

        Object.keys(serviceCache).forEach(id => {

            const panel = document.getElementById(`svc-panel-${id}`);

            if (panel) {

                panel.style.display = '';

                renderServicePanel(parseInt(id));

            }

        });

        // Eagerly load service data for all car cards so the summary is always up to date

        cars.forEach(c => {

            if (!serviceCache[c.id]) {

                fetchServiceSummary(c.id);

            } else {

                updateCarSummaryStrip(c.id);

            }

        });

    }



    // ── Car card (with service history) ────────────────────────────────────

    function renderCarCard(item) {

        const photoStr = item.photo_url

            ? `<div class="org-card-photo"><img src="${escapeHtml(item.photo_url)}" alt="Photo" class="org-card-photo-img org-photo-zoomable" loading="lazy" onclick="orgOpenLightbox(this.src,this.alt)"></div>`

            : '';



        const parts = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean);

        const vehicleName = parts.length ? escapeHtml(parts.join(' ')) : escapeHtml(item.title);

        const regoStr = item.vehicle_rego

            ? `<span class="org-rego-badge">${escapeHtml(item.vehicle_rego)}</span>` : '';

        const notesStr = item.notes

            ? `<div class="org-card-notes"><i class="fas fa-sticky-note"></i> ${escapeHtml(item.notes)}</div>` : '';



        // Due date summary strip entries (from the item's own due_date / last_date)

        const duePills = buildCarDuePills(item);



        return `

        <div class="org-car-card" data-id="${item.id}">

            <div class="org-car-header">

                ${photoStr}

                <div class="org-car-info">

                    <div class="org-car-title">

                        <span class="org-card-icon">${item.icon || '🚗'}</span>

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

            <div class="org-car-summary-strip" id="car-summary-${item.id}">${duePills}</div>

            <div class="org-svc-toggle-bar">

                <button class="org-svc-toggle-btn" onclick="toggleServicePanel(${item.id})">

                    <i class="fas fa-wrench"></i> Service History

                    <i class="fas fa-chevron-down org-svc-chevron" id="svc-chevron-${item.id}"></i>

                </button>

                <button class="org-svc-add-btn admin-only" onclick="openServiceModal(${item.id}, null)" title="Add service record">

                    <i class="fas fa-plus"></i> Add Service

                </button>

            </div>

            <div class="org-svc-panel" id="svc-panel-${item.id}" style="display:none;">

                <div class="org-svc-list" id="svc-list-${item.id}">

                    <span class="org-svc-loading">Loading…</span>

                </div>

            </div>

        </div>`;

    }



    function buildCarDuePills(item) {

        const pills = [];



        if (item.due_date) {

            const sc = statusClass(item.status);

            const dl = daysLabel(item.days_until_due);

            pills.push(`<span class="org-car-pill org-car-pill--${item.status || 'ok'}">

                <i class="fas fa-id-card"></i> Rego/Renewal: ${formatDate(item.due_date)}

                <span class="org-car-pill-badge">${dl}</span>

            </span>`);

        }



        if (item.last_date) {

            pills.push(`<span class="org-car-pill org-car-pill--neutral">

                <i class="fas fa-history"></i> Last renewed: ${formatDate(item.last_date)}

            </span>`);

        }



        return pills.join('');

    }



    function fetchServiceSummary(itemId) {

        fetch(`/api/organise/${itemId}/services`)

            .then(r => r.json())

            .then(res => {

                if (res.success) {

                    serviceCache[itemId] = res.services;

                    updateCarSummaryStrip(itemId);

                    // Also re-render the panel if it's already open

                    const panel = document.getElementById(`svc-panel-${itemId}`);

                    if (panel && panel.style.display !== 'none') renderServicePanel(itemId);

                }

            })

            .catch(() => {});

    }



    function updateCarSummaryStrip(itemId) {

        const strip = document.getElementById(`car-summary-${itemId}`);

        if (!strip) return;

        const item = organiseItems.find(i => i.id === itemId);

        if (!item) return;

        const services = serviceCache[itemId] || [];

        const pills = buildCarDuePills(item);



        // Odometer pill — latest recorded mileage across all service records

        let odomPill = '';

        const withMileage = services.filter(s => s.mileage != null);

        if (withMileage.length) {

            const maxMileage = Math.max(...withMileage.map(s => s.mileage));

            odomPill = `<span class="org-car-pill org-car-pill--neutral"><i class="fas fa-tachometer-alt"></i> ${maxMileage.toLocaleString()} km</span>`;

        }



        // Next service due pill — find the soonest next_service_date across all records

        let nextSvcPill = '';

        const withNextDate = services.filter(s => s.next_service_date);

        if (withNextDate.length) {

            withNextDate.sort((a, b) => a.next_service_date.localeCompare(b.next_service_date));

            const next = withNextDate[0];

            const today = new Date(); today.setHours(0, 0, 0, 0);

            const nextDate = new Date(next.next_service_date);

            const diffDays = Math.round((nextDate - today) / 86400000);

            let cls = 'org-car-pill--ok';

            if (diffDays < 0) cls = 'org-car-pill--overdue';

            else if (diffDays <= 30) cls = 'org-car-pill--due_soon';

            const mileStr = next.next_service_mileage != null ? ` · ${next.next_service_mileage.toLocaleString()} km` : '';

            nextSvcPill = `<span class="org-car-pill ${cls}"><i class="fas fa-calendar-check"></i> Next service: ${formatDate(next.next_service_date)}${mileStr}</span>`;

        }



        // Last service pill

        let lastSvcPill = '';

        if (services.length) {

            const last = services[0]; // already sorted desc

            const dateStr = last.service_date ? formatDate(last.service_date) : '';

            lastSvcPill = `<span class="org-car-pill org-car-pill--neutral">

                <i class="fas fa-wrench"></i> Last service: ${escapeHtml(last.service_type)}${dateStr ? ' — ' + dateStr : ''}

            </span>`;

        }



        const allPills = pills + odomPill + nextSvcPill + lastSvcPill;

        strip.innerHTML = allPills || '<span class="org-car-pill org-car-pill--neutral" style="opacity:.5;">No due dates set</span>';

    }



    function toggleServicePanel(itemId) {

        const panel = document.getElementById(`svc-panel-${itemId}`);

        const chevron = document.getElementById(`svc-chevron-${itemId}`);

        if (!panel) return;

        const isOpen = panel.style.display !== 'none';

        panel.style.display = isOpen ? 'none' : '';

        if (chevron) chevron.style.transform = isOpen ? '' : 'rotate(180deg)';

        if (!isOpen) {

            loadServicePanel(itemId);

        }

    }



    function loadServicePanel(itemId) {

        fetch(`/api/organise/${itemId}/services`)

            .then(r => r.json())

            .then(res => {

                if (res.success) {

                    serviceCache[itemId] = res.services;

                    renderServicePanel(itemId);

                    updateCarSummaryStrip(itemId);

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



        // Vehicle info badge

        let vehicleStr = '';

        if (item.category === 'Car') {

            const parts = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean);

            if (parts.length || item.vehicle_rego) {

                vehicleStr = `<div class="org-card-vehicle">`;

                if (parts.length) vehicleStr += `<i class="fas fa-car" style="opacity:.6; margin-right:4px;"></i>${escapeHtml(parts.join(' '))}`;

                if (item.vehicle_rego) vehicleStr += ` <span class="org-rego-badge">${escapeHtml(item.vehicle_rego)}</span>`;

                vehicleStr += `</div>`;

            }

        }



        // Photo

        const photoStr = item.photo_url

            ? `<div class="org-card-photo"><img src="${escapeHtml(item.photo_url)}" alt="Photo" class="org-card-photo-img org-photo-zoomable" loading="lazy" onclick="orgOpenLightbox(this.src,this.alt)"></div>`

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

                <button class="org-btn-edit" onclick="organiseEdit(${item.id})" title="Edit"><i class="fas fa-pencil-alt"></i></button>

                <button class="org-btn-toggle-paid" onclick="organiseTogglePaid(${item.id})" title="${item.paid ? 'Mark unpaid' : 'Mark paid'}">

                    ${item.paid ? '<i class="fas fa-times-circle"></i>' : '<i class="fas fa-check-circle"></i>'}

                </button>

                <button class="org-btn-delete" onclick="organiseDelete(${item.id})" title="Delete"><i class="fas fa-trash"></i></button>

            </div>

        </div>`;

    }



    // ── Modal ──────────────────────────────────────────────────────────────

    function openModal(item) {

        editingItemId = item ? item.id : null;

        pendingPhotoFile = null;

        photoRemoved = false;



        const modal = document.getElementById('organise-modal');

        if (!modal) return;



        document.getElementById('org-modal-title').textContent = item ? 'Edit Item' : 'Add Item';

        document.getElementById('org-input-title').value = item ? item.title : '';

        document.getElementById('org-input-category').value = item ? item.category : 'Car';

        document.getElementById('org-input-custom-category').value =

            (item && !['Car', 'Property', 'Finance', 'Health', 'Insurance', 'General'].includes(item.category)) ? item.category : '';

        document.getElementById('org-input-provider').value = item ? (item.provider || '') : '';

        document.getElementById('org-input-due-date').value = item ? (item.due_date || '') : '';

        document.getElementById('org-input-last-date').value = item ? (item.last_date || '') : '';

        document.getElementById('org-input-cost').value = item ? (item.cost != null ? item.cost : '') : '';

        document.getElementById('org-input-reminder').value = item ? (item.reminder_days || 30) : 30;

        document.getElementById('org-input-paid').checked = item ? Boolean(item.paid) : false;

        document.getElementById('org-input-notes').value = item ? (item.notes || '') : '';



        // Icon / emoji

        const icon = item ? (item.icon || '') : '';

        document.getElementById('org-input-icon').value = icon;

        document.getElementById('org-emoji-display').textContent = icon || '☺';

        const popup = document.getElementById('org-emoji-popup');

        if (popup) popup.style.display = 'none';



        // Vehicle fields

        document.getElementById('org-input-vehicle-make').value = item ? (item.vehicle_make || '') : '';

        document.getElementById('org-input-vehicle-model').value = item ? (item.vehicle_model || '') : '';

        document.getElementById('org-input-vehicle-year').value = item ? (item.vehicle_year || '') : '';

        document.getElementById('org-input-vehicle-rego').value = item ? (item.vehicle_rego || '') : '';



        // Photo

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



        updateCustomCategoryVisibility();

        updateVehicleFieldsVisibility();

        modal.style.display = 'flex';

        setTimeout(() => document.getElementById('org-input-title').focus(), 80);

    }



    function closeModal() {

        const modal = document.getElementById('organise-modal');

        if (modal) modal.style.display = 'none';

        editingItemId = null;

        pendingPhotoFile = null;

        photoRemoved = false;

    }



    function updateCustomCategoryVisibility() {

        const sel = document.getElementById('org-input-category');

        const customWrap = document.getElementById('org-custom-category-wrap');

        if (sel && customWrap) {

            customWrap.style.display = sel.value === '__custom__' ? '' : 'none';

        }

    }



    function updateVehicleFieldsVisibility() {

        const cat = document.getElementById('org-input-category');

        const vf = document.getElementById('org-vehicle-fields');

        if (cat && vf) {

            vf.style.display = cat.value === 'Car' ? '' : 'none';

        }

    }



    function getFormData() {

        const categorySel = document.getElementById('org-input-category').value;

        const customCat = document.getElementById('org-input-custom-category').value.trim();

        const category = categorySel === '__custom__' ? (customCat || 'General') : categorySel;



        return {

            title: document.getElementById('org-input-title').value.trim(),

            category,

            provider: document.getElementById('org-input-provider').value.trim(),

            due_date: document.getElementById('org-input-due-date').value || null,

            last_date: document.getElementById('org-input-last-date').value || null,

            cost: document.getElementById('org-input-cost').value !== ''

                ? parseFloat(document.getElementById('org-input-cost').value) : null,

            reminder_days: parseInt(document.getElementById('org-input-reminder').value) || 30,

            paid: document.getElementById('org-input-paid').checked,

            notes: document.getElementById('org-input-notes').value.trim(),

            icon: document.getElementById('org-input-icon').value,

            vehicle_make: document.getElementById('org-input-vehicle-make').value.trim(),

            vehicle_model: document.getElementById('org-input-vehicle-model').value.trim(),

            vehicle_year: document.getElementById('org-input-vehicle-year').value

                ? parseInt(document.getElementById('org-input-vehicle-year').value) : null,

            vehicle_rego: document.getElementById('org-input-vehicle-rego').value.trim(),

        };

    }



    async function saveItem() {

        const data = getFormData();

        if (!data.title) {

            alert('Please enter a title.');

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



    // ── Service Modal ──────────────────────────────────────────────────────

    function openServiceModal(itemId, service) {

        editingServiceItemId = itemId;

        editingServiceId = service ? service.id : null;



        const modal = document.getElementById('vehicle-service-modal');

        if (!modal) return;

        document.getElementById('svc-modal-title').textContent = service ? 'Edit Service Record' : 'Add Service Record';

        document.getElementById('svc-input-type').value = service ? service.service_type : '';

        document.getElementById('svc-input-date').value = service ? (service.service_date || '') : '';

        document.getElementById('svc-input-mileage').value = service ? (service.mileage != null ? service.mileage : '') : '';

        document.getElementById('svc-input-provider').value = service ? (service.provider || '') : '';

        document.getElementById('svc-input-cost').value = service ? (service.cost != null ? service.cost : '') : '';

        document.getElementById('svc-input-notes').value = service ? (service.notes || '') : '';

        document.getElementById('svc-input-next-date').value = service ? (service.next_service_date || '') : '';

        document.getElementById('svc-input-next-mileage').value = service ? (service.next_service_mileage != null ? service.next_service_mileage : '') : '';

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

            mileage: document.getElementById('svc-input-mileage').value !== '' ? parseInt(document.getElementById('svc-input-mileage').value) : null,

            provider: document.getElementById('svc-input-provider').value.trim() || null,

            cost: document.getElementById('svc-input-cost').value !== '' ? parseFloat(document.getElementById('svc-input-cost').value) : null,

            notes: document.getElementById('svc-input-notes').value.trim() || null,

            next_service_date: document.getElementById('svc-input-next-date').value || null,

            next_service_mileage: document.getElementById('svc-input-next-mileage').value !== '' ? parseInt(document.getElementById('svc-input-next-mileage').value) : null,

        };

        const url = editingServiceId

            ? `/api/organise/${editingServiceItemId}/services/${editingServiceId}`

            : `/api/organise/${editingServiceItemId}/services`;

        const method = editingServiceId ? 'PUT' : 'POST';

        try {

            const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });

            const res = await r.json();

            if (!res.success) { alert(res.error || 'Failed to save'); return; }

        } catch (_) { alert('Network error — please try again.'); return; }

        const savedItemId = editingServiceItemId;

        closeServiceModal();

        loadServicePanel(savedItemId);

        // ensure panel stays open

        const panel = document.getElementById(`svc-panel-${savedItemId}`);

        if (panel) panel.style.display = '';

        const chevron = document.getElementById(`svc-chevron-${savedItemId}`);

        if (chevron) chevron.style.transform = 'rotate(180deg)';

    }



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

            })

            .catch(() => alert('Network error'));

    };



    window.openServiceModal = openServiceModal;

    window.toggleServicePanel = toggleServicePanel;



    // ── Photo lightbox ─────────────────────────────────────────────────────

    window.orgOpenLightbox = function (src, alt) {

        const lb  = document.getElementById('org-lightbox');

        const img = document.getElementById('org-lightbox-img');

        if (!lb || !img) return;

        img.src = src;

        img.alt = alt || '';

        lb.style.display = 'flex';

    };



    // ── Actions ────────────────────────────────────────────────────────────

    window.organiseEdit = function (id) {

        const item = organiseItems.find(i => i.id === id);

        if (item) openModal(item);

    };



    window.organiseDelete = function (id) {

        const item = organiseItems.find(i => i.id === id);

        if (!item) return;

        if (!confirm(`Delete "${item.title}"?`)) return;

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

        fetch(`/api/organise/${id}`, {

            method: 'PUT',

            headers: { 'Content-Type': 'application/json' },

            body: JSON.stringify({ paid: !item.paid }),

        })

            .then(r => r.json())

            .then(res => {

                if (!res.success) { alert(res.error || 'Failed to update'); return; }

                loadOrganise();

            })

            .catch(() => alert('Network error'));

    };



    // ── Load ───────────────────────────────────────────────────────────────

    function loadOrganise() {

        fetch('/api/organise')

            .then(r => r.json())

            .then(res => {

                if (res.success) {

                    organiseItems = res.items;

                    renderOrganise();

                }

            })

            .catch(() => {

                const c = document.getElementById('organise-items-container');

                if (c) c.innerHTML = '<p class="org-empty">Failed to load items.</p>';

            });

    }



    // ── Init ───────────────────────────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', function () {

        const section = document.getElementById('organise-section');

        if (section) {

            const toggle = section.querySelector('.section-toggle');

            if (toggle) {

                toggle.addEventListener('click', function () {

                    if (!organiseItems.length) loadOrganise();

                }, { once: true });

            }

            if (!section.classList.contains('collapsed')) {

                loadOrganise();

            }

        }



        document.getElementById('organise-add-btn')?.addEventListener('click', () => openModal(null));

        document.getElementById('org-modal-close')?.addEventListener('click', closeModal);

        document.getElementById('org-modal-cancel')?.addEventListener('click', closeModal);

        document.getElementById('org-modal-save')?.addEventListener('click', saveItem);



        // Service modal

        document.getElementById('svc-modal-close')?.addEventListener('click', closeServiceModal);

        document.getElementById('svc-modal-cancel')?.addEventListener('click', closeServiceModal);

        document.getElementById('svc-modal-save')?.addEventListener('click', saveServiceRecord);



        const svcModal = document.getElementById('vehicle-service-modal');

        if (svcModal) {

            svcModal.addEventListener('click', function (e) {

                if (e.target === svcModal) closeServiceModal();

            });

        }



        const catSel = document.getElementById('org-input-category');

        if (catSel) {

            catSel.addEventListener('change', () => {

                updateCustomCategoryVisibility();

                updateVehicleFieldsVisibility();

            });

        }



        const modal = document.getElementById('organise-modal');

        if (modal) {

            modal.addEventListener('click', function (e) {

                if (e.target === modal) closeModal();

            });

        }



        document.addEventListener('keydown', function (e) {

            if (e.key === 'Escape') {

                closeModal();

                closeServiceModal();

                const lb = document.getElementById('org-lightbox');

                if (lb) lb.style.display = 'none';

                const popup = document.getElementById('org-emoji-popup');

                if (popup) popup.style.display = 'none';

                const qm = document.getElementById('org-quick-menu');

                if (qm) qm.style.display = 'none';

            }

        });



        // ── Emoji picker ─────────────────────────────────────────────────

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



        document.addEventListener('click', function (e) {

            const popup = document.getElementById('org-emoji-popup');

            const btn = document.getElementById('org-emoji-btn');

            if (popup && btn && !btn.contains(e.target) && !popup.contains(e.target)) {

                popup.style.display = 'none';

            }

        });



        // ── Photo upload ──────────────────────────────────────────────────

        const photoInput = document.getElementById('org-input-photo');

        if (photoInput) {

            photoInput.addEventListener('change', function () {

                const file = this.files[0];

                if (!file) return;

                if (file.size > 5 * 1024 * 1024) {

                    alert('Photo must be under 5 MB.');

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

        }



        document.getElementById('org-photo-remove')?.addEventListener('click', function () {

            pendingPhotoFile = null;

            photoRemoved = true;

            document.getElementById('org-input-photo').value = '';

            document.getElementById('org-photo-preview-img').src = '';

            document.getElementById('org-photo-preview').style.display = 'none';

        });



        // ── Quick-add car templates ───────────────────────────────────────

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

                // Service-type items open the service modal for the first Car if one exists

                if (item.dataset.type === 'service') {

                    const cars = organiseItems.filter(i => i.category === 'Car');

                    if (!cars.length) {

                        alert('Add a Car item first, then you can log service records.');

                        return;

                    }

                    // If multiple cars, pick the first (most common case)

                    openServiceModal(cars[0].id, null);

                    document.getElementById('svc-input-type').value = item.dataset.title || '';

                    return;

                }

                openModal(null);

                document.getElementById('org-input-title').value = item.dataset.title;

                const iconVal = item.dataset.icon || '';

                document.getElementById('org-input-icon').value = iconVal;

                document.getElementById('org-emoji-display').textContent = iconVal || '☺';

                document.getElementById('org-input-category').value = 'Car';

                updateCustomCategoryVisibility();

                updateVehicleFieldsVisibility();

            });

            document.addEventListener('click', function () {

                quickMenu.style.display = 'none';

            });

        }

    });

}());



