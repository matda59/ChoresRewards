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
    const newStatus = event.target.closest('.column').dataset.status;
    fetch('/update_chore_status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ chore_id: choreId, new_status: newStatus }),
    }).then(response => response.json())
      .then(data => {
          if (data.success) {
              window.location.reload();
          }
      });
}