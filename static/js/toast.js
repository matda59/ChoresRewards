// Toast notification system for ChoresRewards with Action / Undo support
// Usage:
//   showToast('Message', 'success', 3000)
//   showToast({ message: 'Chore marked done.', type: 'success', duration: 5000, actionText: 'Undo', onAction: () => ... })

function showToast(messageOrOptions, type = 'info', duration = 3500, actionText = null, onAction = null) {
    let message = messageOrOptions;
    if (typeof messageOrOptions === 'object' && messageOrOptions !== null) {
        message = messageOrOptions.message || '';
        type = messageOrOptions.type || 'info';
        duration = messageOrOptions.duration !== undefined ? messageOrOptions.duration : 3500;
        actionText = messageOrOptions.actionText || null;
        onAction = messageOrOptions.onAction || null;
    }

    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.style.position = 'fixed';
        toastContainer.style.top = '24px';
        toastContainer.style.right = '24px';
        toastContainer.style.zIndex = '99999';
        toastContainer.style.display = 'flex';
        toastContainer.style.flexDirection = 'column';
        toastContainer.style.gap = '10px';
        toastContainer.style.pointerEvents = 'none';
        document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.pointerEvents = 'auto';
    toast.style.minWidth = '220px';
    toast.style.maxWidth = '400px';
    toast.style.padding = '12px 18px';
    toast.style.borderRadius = '10px';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.justifyContent = 'space-between';
    toast.style.gap = '14px';

    const bgMap = {
        success: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
        error: 'linear-gradient(135deg, #dc2626 0%, #ef4444 100%)',
        warning: 'linear-gradient(135deg, #d97706 0%, #f59e0b 100%)',
        info: 'linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)'
    };

    const iconMap = {
        success: '<i class="fas fa-check-circle" style="font-size:1.15em;"></i>',
        error: '<i class="fas fa-exclamation-circle" style="font-size:1.15em;"></i>',
        warning: '<i class="fas fa-triangle-exclamation" style="font-size:1.15em;"></i>',
        info: '<i class="fas fa-info-circle" style="font-size:1.15em;"></i>'
    };

    toast.style.background = bgMap[type] || bgMap.info;
    toast.style.color = '#ffffff';
    toast.style.fontWeight = '600';
    toast.style.fontSize = '0.92rem';
    toast.style.boxShadow = '0 6px 20px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.2)';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-16px) scale(0.96)';
    toast.style.transition = 'opacity 0.25s ease, transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)';

    const contentDiv = document.createElement('div');
    contentDiv.style.display = 'flex';
    contentDiv.style.alignItems = 'center';
    contentDiv.style.gap = '10px';
    contentDiv.innerHTML = `${iconMap[type] || iconMap.info} <span>${message}</span>`;
    toast.appendChild(contentDiv);

    let dismissTimer = null;
    const dismiss = () => {
        if (dismissTimer) clearTimeout(dismissTimer);
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-16px) scale(0.96)';
        setTimeout(() => toast.remove(), 250);
    };

    if (actionText && typeof onAction === 'function') {
        const actionBtn = document.createElement('button');
        actionBtn.type = 'button';
        actionBtn.textContent = actionText;
        actionBtn.style.background = 'rgba(255, 255, 255, 0.22)';
        actionBtn.style.color = '#ffffff';
        actionBtn.style.border = '1px solid rgba(255, 255, 255, 0.4)';
        actionBtn.style.padding = '4px 12px';
        actionBtn.style.borderRadius = '6px';
        actionBtn.style.fontWeight = '700';
        actionBtn.style.fontSize = '0.85rem';
        actionBtn.style.cursor = 'pointer';
        actionBtn.style.flexShrink = '0';
        actionBtn.style.transition = 'background 0.15s ease, transform 0.15s ease';
        actionBtn.onmouseenter = () => { actionBtn.style.background = 'rgba(255, 255, 255, 0.35)'; actionBtn.style.transform = 'scale(1.05)'; };
        actionBtn.onmouseleave = () => { actionBtn.style.background = 'rgba(255, 255, 255, 0.22)'; actionBtn.style.transform = 'scale(1)'; };
        actionBtn.onclick = (e) => {
            e.stopPropagation();
            dismiss();
            onAction();
        };
        toast.appendChild(actionBtn);
    }

    toastContainer.appendChild(toast);

    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0) scale(1)';
    });

    if (duration > 0) {
        dismissTimer = setTimeout(dismiss, duration);
    }

    return { dismiss };
}

window.showToast = showToast;
