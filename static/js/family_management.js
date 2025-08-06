let deletePersonId = null;
let deletePersonCard = null;

window.openAddPersonModal = function() {
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

window.confirmDeletePerson = function(personId, personName, btn) {
    deletePersonId = personId;
    deletePersonCard = btn.closest('.existing-person-card');
    document.getElementById('delete-person-modal').style.display = 'flex';
}

document.getElementById('cancel-delete-btn').onclick = function() {
    document.getElementById('delete-person-modal').style.display = 'none';
    deletePersonId = null;
    deletePersonCard = null;
};

document.getElementById('confirm-delete-btn').onclick = function() {
    if (!deletePersonId) return;
    fetch('/delete_person', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_id: deletePersonId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (deletePersonCard) deletePersonCard.remove();
            document.getElementById('delete-person-modal').style.display = 'none';
        } else {
            alert(data.error || 'Failed to delete person');
        }
        deletePersonId = null;
        deletePersonCard = null;
    })
    .catch(() => {
        alert('Failed to delete person');
        deletePersonId = null;
        deletePersonCard = null;
        document.getElementById('delete-person-modal').style.display = 'none';
    });
};

window.renamePerson = function(spanElem, personId) {
    const newName = spanElem.textContent.trim();
    if (!newName) {
        alert("Name cannot be empty.");
        // Reset to previous name by reloading page
        window.location.reload();
        return;
    }
    fetch('/update_name', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_id: personId, new_name: newName })
    })
    .then(res => res.json())
    .then(data => {
        if (!data.success) {
            alert(data.error || 'Failed to update name');
            window.location.reload();
        }
    })
    .catch(() => {
        alert('Failed to update name');
        window.location.reload();
    });
}
