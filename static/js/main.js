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
    
        // --- Reward Image Edit Modal Logic ---
        let currentRewardId = null;
    
        window.openEditRewardImageModal = function(rewardId, imageUrl) {
            currentRewardId = rewardId;
            const modal = document.getElementById('edit-reward-image-modal');
            modal.style.display = 'flex';
            document.getElementById('reward-image-upload').value = '';
            document.getElementById('reward-image-url').value = imageUrl || '';
        };
    
        window.closeEditRewardImageModal = function() {
            const modal = document.getElementById('edit-reward-image-modal');
            modal.style.display = 'none';
            currentRewardId = null;
        };
    
        window.saveRewardImage = function() {
            const fileInput = document.getElementById('reward-image-upload');
            const urlInput = document.getElementById('reward-image-url');
            const formData = new FormData();
            formData.append('reward_id', currentRewardId);
            if (fileInput.files && fileInput.files[0]) {
                formData.append('image', fileInput.files[0]);
            } else if (urlInput.value) {
                formData.append('image_url', urlInput.value);
            } else {
                alert('Please select an image or enter a URL.');
                return;
            }
            fetch('/edit_reward_image', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.reload();
                } else {
                    alert(data.error || 'Failed to update image.');
                }
            })
            .catch(() => alert('Failed to update image.'));
            closeEditRewardImageModal();
        };
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