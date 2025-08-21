document.addEventListener('DOMContentLoaded', () => {
    const chores = document.querySelectorAll('.chore');
    chores.forEach(chore => {
        chore.addEventListener('dragstart', dragStart);
    });

    const columns = document.querySelectorAll('.column');
    columns.forEach(column => {
        column.addEventListener('dragover', dragOver);
        column.addEventListener('drop', drop);
    });
});

function dragStart(event) {
    event.dataTransfer.setData('text/plain', event.target.dataset.choreId);
}

function dragOver(event) {
    event.preventDefault();
}

function drop(event) {
    event.preventDefault();
    const choreId = event.dataTransfer.getData('text/plain');
    // Instead of newStatus, just complete the chore
    fetch('/complete_chore', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ chore_id: choreId }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update the points/cash badge for the person
            const personName = data.assigned_to;
            const column = document.querySelector(`.column[data-person='${personName}']`);
            if (column) {
                const badgeElem = column.querySelector('.points-display .chore-points-badge');
                if (badgeElem) {
                    let icon, label, value;
                    if (window.REWARD_SYSTEM === 'cash') {
                        icon = '<i class="fas fa-money-bill-wave" style="color:#4CAF50; margin-right:4px;"></i>';
                        value = `$${data.new_points}`;
                        label = 'cash';
                    } else {
                        icon = '<i class="fas fa-award" style="color:#fbbf24; margin-right:4px;"></i>';
                        value = data.new_points;
                        label = 'points';
                    }
                    badgeElem.innerHTML = `
                        ${icon}
                        <span class="chore-points-value">${value}</span>
                        <span style="color:#fff; font-size:1em; font-weight:500; margin-left:4px;">${label}</span>
                    `;
                }
            }
            // Show toast notification for completion or overdue
            if (window.showToast) {
                if (data.overdue) {
                    showToast('Chore was overdue. No points awarded.', 'warning');
                } else {
                    showToast('Chore completed!', 'success');
                }
            }
            // Always reload the page after a short delay to ensure all UI is up to date
            setTimeout(() => { window.location.reload(); }, 900);
        }
    });
}