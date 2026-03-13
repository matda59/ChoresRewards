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

    // Always require PIN on settings.html
    const forcePin = window.location.pathname.endsWith('/settings') || window.location.pathname.endsWith('/settings.html');
    if (forcePin) {
        pinOverlay.style.display = 'flex';
        siteContent.style.display = 'none';
        // Attach event listeners for PIN entry
        masterPinSubmit.addEventListener('click', function() {
            const enteredPin = masterPinInput.value.trim();
            if (!enteredPin.match(/^\d{4}$/)) {
                masterPinError.textContent = 'Please enter a valid 4-digit PIN.';
                masterPinError.style.display = 'block';
                return;
            }
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
                    sessionStorage.setItem('authenticated', 'true');
                    masterPinError.style.display = 'none';
                    pinOverlay.style.display = 'none';
                    siteContent.style.display = 'block';
                } else {
                    sessionStorage.setItem('authenticated', 'false');
                    masterPinError.textContent = data.error || 'Incorrect PIN. Please try again.';
                    masterPinError.style.display = 'block';
                }
            })
            .catch(error => {
                sessionStorage.setItem('authenticated', 'false');
                console.error('Error verifying PIN:', error);
                masterPinError.textContent = 'Error verifying PIN. Please try again later.';
                masterPinError.style.display = 'block';
            });
        });
        masterPinInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                masterPinSubmit.click();
            }
        });
    } else {
        // Default: check backend session
        fetch('/api/check_auth')
            .then(response => response.json())
            .then(data => {
                if (data.authenticated) {
                    pinOverlay.style.display = 'none';
                    siteContent.style.display = 'block';
                } else {
                    pinOverlay.style.display = 'flex';
                    siteContent.style.display = 'none';
                    // Attach event listeners only if PIN is needed
                    masterPinSubmit.addEventListener('click', function() {
                        const enteredPin = masterPinInput.value.trim();
                        if (!enteredPin.match(/^\d{4}$/)) {
                            masterPinError.textContent = 'Please enter a valid 4-digit PIN.';
                            masterPinError.style.display = 'block';
                            return;
                        }
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
                                sessionStorage.setItem('authenticated', 'true');
                                masterPinError.style.display = 'none';
                                pinOverlay.style.display = 'none';
                                siteContent.style.display = 'block';
                            } else {
                                sessionStorage.setItem('authenticated', 'false');
                                masterPinError.textContent = data.error || 'Incorrect PIN. Please try again.';
                                masterPinError.style.display = 'block';
                            }
                        })
                        .catch(error => {
                            sessionStorage.setItem('authenticated', 'false');
                            console.error('Error verifying PIN:', error);
                            masterPinError.textContent = 'Error verifying PIN. Please try again later.';
                            masterPinError.style.display = 'block';
                        });
                    });
                    masterPinInput.addEventListener('keydown', function(event) {
                        if (event.key === 'Enter') {
                            event.preventDefault();
                            masterPinSubmit.click();
                        }
                    });
                }
            })
            .catch(() => {
                // On error, default to requiring PIN
                pinOverlay.style.display = 'flex';
                siteContent.style.display = 'none';
            });
    }

            // ...existing code for columns, weekly summary, etc...
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

    // ...existing code for weekly summary, MutationObserver, etc...
    // (unchanged)
});
