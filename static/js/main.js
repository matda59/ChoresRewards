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
    
        // --- Reward Edit Modal Logic ---
        let currentRewardId = null;

        window.openEditRewardModal = function(card) {
            currentRewardId = card.dataset.rewardId;
            document.getElementById('er-title').value = card.dataset.title || '';
            document.getElementById('er-points').value = card.dataset.points || '';
            document.getElementById('er-description').value = card.dataset.description || '';
            const sel = document.getElementById('er-assigned-to');
            if (sel) {
                for (let i = 0; i < sel.options.length; i++) {
                    if (sel.options[i].value === card.dataset.assignedTo) { sel.selectedIndex = i; break; }
                }
            }
            document.getElementById('er-image-upload').value = '';
            document.getElementById('er-image-url').value = card.dataset.imageUrl || '';
            document.getElementById('edit-reward-modal').style.display = 'flex';
        };

        window.closeEditRewardModal = function() {
            document.getElementById('edit-reward-modal').style.display = 'none';
            currentRewardId = null;
        };

        window.saveEditReward = function() {
            const title = document.getElementById('er-title').value.trim();
            const points = document.getElementById('er-points').value;
            const description = document.getElementById('er-description').value.trim();
            const assignedTo = document.getElementById('er-assigned-to').value;
            const fileInput = document.getElementById('er-image-upload');
            const imageUrl = document.getElementById('er-image-url').value.trim();

            if (!title) { alert('Title is required.'); return; }
            if (!points || isNaN(parseFloat(points))) { alert('A valid amount is required.'); return; }

            // Step 1: save text fields
            fetch('/edit_reward', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reward_id: currentRewardId, title, points_required: parseFloat(points), description, assigned_to: assignedTo })
            })
            .then(r => r.json())
            .then(d => {
                if (!d.success) { alert(d.error || 'Failed to save reward.'); return; }
                // Step 2: if an image was provided, upload it too
                const hasFile = fileInput.files && fileInput.files[0];
                if (hasFile || imageUrl) {
                    const fd = new FormData();
                    fd.append('reward_id', currentRewardId);
                    if (hasFile) fd.append('image', fileInput.files[0]);
                    else fd.append('image_url', imageUrl);
                    return fetch('/edit_reward_image', { method: 'POST', body: fd })
                        .then(r => r.json())
                        .then(d2 => { if (!d2.success) alert(d2.error || 'Saved but image failed.'); });
                }
            })
            .then(() => { closeEditRewardModal(); window.location.reload(); })
            .catch(() => alert('Failed to save reward.'));
        };

        // Keep old name as alias in case any stray references exist
        window.openEditRewardImageModal = window.openEditRewardModal;
        window.closeEditRewardImageModal = window.closeEditRewardModal;
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
                    let icon, value;
                    if (window.REWARD_SYSTEM === 'cash') {
                        icon = '<i class="fas fa-money-bill-wave" style="color:#4CAF50; margin-right:4px;"></i>';
                        value = `$${data.new_points}`;
                    } else {
                        icon = '<i class="fas fa-award" style="color:#fbbf24; margin-right:4px;"></i>';
                        value = data.new_points;
                    }
                    badgeElem.innerHTML = `
                        ${icon}
                        <span class="chore-points-value">${value}</span>
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
            // Fetch the updated completed chores HTML fragment and update the DOM
            fetch('/completed_chores_fragment')
                .then(resp => resp.text())
                .then(html => {
                    const completedList = document.querySelector('.completed-chores-list');
                    if (completedList) {
                        completedList.innerHTML = html;
                        completedList.style.display = '';
                    }
                });
        }
    });
}