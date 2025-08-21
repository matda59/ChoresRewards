// This file will store the session authentication check for the frontend
// It will be imported by auth.js
export function isAuthenticated() {
    // Use localStorage or sessionStorage to persist authentication state
    // Here we use sessionStorage for session-based auth
    return sessionStorage.getItem('authenticated') === 'true';
}

export function setAuthenticated(value) {
    sessionStorage.setItem('authenticated', value ? 'true' : 'false');
}

export function clearAuthenticated() {
    sessionStorage.removeItem('authenticated');
}
