// Reset points function
function resetPoints(personId) {
    let newPoints = prompt("Enter new points value (default is 0):", "0");
    if (newPoints === null) return;
    newPoints = parseFloat(newPoints);
    if (isNaN(newPoints)) {
        alert("Invalid number entered. Please try again.");
        return;
    }
    fetch("/reset_points", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_id: personId, new_points: newPoints }),
    })
    .then(response => response.json())
    .then(data => { if (data.success) window.location.reload(); else alert(data.message || "Failed to reset points"); })
    .catch(error => console.error("Error resetting points:", error));
}

// Confirm delete person function
function confirmDeletePerson(personId, personName) {
    if (confirm(`Are you sure you want to delete ${personName}? This action cannot be undone.`)) {
        deletePerson(personId);
    }
}

// Delete person function
function deletePerson(personId) {
    fetch('/delete_person', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_id: personId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || 'Failed to delete person');
        }
    })
    .catch(error => {
        console.error('Error deleting person:', error);
        alert('An error occurred while deleting the person.');
    });
}

window.openAddPersonModal = function() {
    document.getElementById('add-person-input').value = '';
    document.getElementById('add-person-modal').style.display = 'flex';
    setTimeout(() => {
        document.getElementById('add-person-input').focus();
    }, 100);
}
window.closeAddPersonModal = function() {
    document.getElementById('add-person-modal').style.display = 'none';
}
window.confirmAddPerson = function() {
    const name = document.getElementById('add-person-input').value.trim();
    if (!name) return;
    fetch('/add_person', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || 'Failed to add person');
        }
    })
    .catch(() => {
        alert('Failed to add person');
    });
    closeAddPersonModal();
}

document.addEventListener('DOMContentLoaded', function() {
    const addBtn = document.getElementById('add-person-btn');
    if (addBtn) addBtn.addEventListener('click', openAddPersonModal);

    // Bonus points mode radio buttons
    const bonusModeRadios = document.querySelectorAll('input[name="bonus_mode"]');
    const bonusStaticInput = document.getElementById('bonus-static-input');
    const bonusMinInput = document.getElementById('bonus-min-input');
    const bonusMaxInput = document.getElementById('bonus-max-input');

    function updateBonusInputs() {
        const selectedMode = document.querySelector('input[name="bonus_mode"]:checked').value;
        if (selectedMode === 'static') {
            bonusStaticInput.style.display = 'inline-block';
            bonusMinInput.style.display = 'none';
            bonusMaxInput.style.display = 'none';
        } else if (selectedMode === 'range') {
            bonusStaticInput.style.display = 'none';
            bonusMinInput.style.display = 'inline-block';
            bonusMaxInput.style.display = 'inline-block';
        }
    }

    bonusModeRadios.forEach(radio => {
        radio.addEventListener('change', updateBonusInputs);
    });

    // Initialize on page load
    updateBonusInputs();
});
