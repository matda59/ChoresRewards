document.addEventListener('DOMContentLoaded', function() {
    const pinOverlay = document.getElementById('pin-overlay');
    const siteContent = document.getElementById('site-content');
    const masterPinInput = document.getElementById('master-pin-input');
    const masterPinSubmit = document.getElementById('master-pin-submit');
    const masterPinError = document.getElementById('master-pin-error');

    if (!pinOverlay || !siteContent || !masterPinInput || !masterPinSubmit || !masterPinError) {
        console.error('PIN overlay elements missing');
        if (siteContent) {
            siteContent.style.display = 'block';
        }
        return;
    }

    // Remove localStorage check and use session-based auth
    // Initially hide site content and show pin overlay
    pinOverlay.style.display = 'flex';
    siteContent.style.display = 'none';

    masterPinSubmit.addEventListener('click', function() {
        console.log('Submit button clicked'); // Debug log to verify click event fires
        const enteredPin = masterPinInput.value.trim();
        if (!enteredPin.match(/^\d{4}$/)) {
            masterPinError.textContent = 'Please enter a valid 4-digit PIN.';
            masterPinError.style.display = 'block';
            return;
        }
        // Send the entered PIN to the new login API
        fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ pin: enteredPin })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                masterPinError.style.display = 'none';
                pinOverlay.style.display = 'none';
                siteContent.style.display = 'block';
            } else {
                masterPinError.textContent = data.error || 'Incorrect PIN. Please try again.';
                masterPinError.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error verifying PIN:', error);
            masterPinError.textContent = 'Error verifying PIN. Please try again later.';
            masterPinError.style.display = 'block';
        });
    });

    // Add keydown event listener to submit PIN on Enter key press
    masterPinInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            masterPinSubmit.click();
        }
    });

    // Initialize column colors
    const columns = document.querySelectorAll('.column');
    columns.forEach(column => {
        const colorInput = column.querySelector('.color-input');
        const personId = colorInput.getAttribute('id').replace('color-picker-', '');
        fetch(`/get_column_color/${personId}`, { method: 'GET' })
        .then(response => response.json())
        .then(data => {
            let color = (data.success && data.color) ? data.color : '#cccccc';
            column.style.backgroundColor = color;
            colorInput.value = color;
        })
        .catch(error => {
            column.style.backgroundColor = '#cccccc';
            colorInput.value = '#cccccc';
        });

        // Add event listener to save color on change
        colorInput.addEventListener('change', function() {
            const newColor = colorInput.value;
            fetch('/save_column_color', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    person_id: personId,
                    color: newColor
                })
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    column.style.backgroundColor = newColor;
                } else {
                    console.error('Failed to save color:', result.error);
                }
            })
            .catch(error => {
                console.error('Error saving color:', error);
            });
        });
    });

    // Initialize weekly summary

    // updateWeeklySummary(); // Removed because function is not defined here

    // Set up a MutationObserver to watch for changes to points displays
    const pointsDisplays = document.querySelectorAll('.points-display');
    // const observer = new MutationObserver(updateWeeklySummary); // Removed because function is not defined here
    // const config = { childList: true, characterData: true, subtree: true };

    // pointsDisplays.forEach(display => {
    //     observer.observe(display, config);
    // });
});

(function() {

// Family member management functions for settings page

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

window.confirmDeletePersonLegacy = function(personId, personName, btn) {
    deletePersonId = personId;
    deletePersonCard = btn.closest('.existing-person-card');
    document.getElementById('delete-person-modal').style.display = 'flex';
}


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
};

})();
