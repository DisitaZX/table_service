function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('click', function(e) {
        if (e.target.closest('.delete-row-btn')) {
            const btn = e.target.closest('.delete-row-btn');
            const rowId = btn.dataset.rowId;
            const tableId = btn.dataset.tableId;

            if (confirm('Вы уверены, что хотите удалить эту строку?')) {
                fetch(`/${tableId}/delete_row/${rowId}/`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        window.location.href = data.redirect_url;
                    } else {
                        alert(data.message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Произошла ошибка при удалении');
                });
            }
        }
        if (e.target.closest('.add-row-btn')) {
            const btn = e.target.closest('.add-row-btn');
            const tableId = btn.dataset.tableId;

            const modal = new bootstrap.Modal(document.getElementById('addRowModal'));
            modal.show();
            modal._element.addEventListener('shown.bs.modal', function onShown() {
                modal._element.removeEventListener('shown.bs.modal', onShown);
                // Загрузка формы
                fetch(`/${tableId}/add_row/`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            document.getElementById('addRowModalContent').innerHTML = data.html;
                        } else if (data.status === 'error') {
                            alert(data.message);
                            modal.hide();
                        } else {
                            alert('Ошибка загрузки формы');
                            modal.hide();
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        modal.hide();
                    });
            })
        }
        if (e.target.closest('.edit-row-btn')) {
            const btn = e.target.closest('.edit-row-btn');
            const rowId = btn.dataset.rowId;
            const tableId = btn.dataset.tableId;

            const modal = new bootstrap.Modal(document.getElementById('rowEditModal'));
            let isModalInitialized = false;

            // Обработчик закрытия модалки
            const handleModalClose = () => {
                if (!document.getElementById('rowEditForm')?.dataset.submitted) {
                    fetch(`/api/unlock_row/${rowId}/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken'),
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({})
                    });
                }
                modal._element.removeEventListener('hidden.bs.modal', handleModalClose);
            };

            // Ждем полной инициализации модалки
            modal._element.addEventListener('shown.bs.modal', function onShown() {
                if (isModalInitialized) return;
                isModalInitialized = true;

                // Удаляем обработчик shown после первого срабатывания
                modal._element.removeEventListener('shown.bs.modal', onShown);

                // Добавляем обработчик закрытия
                modal._element.addEventListener('hidden.bs.modal', handleModalClose);

                // Загрузка формы только после инициализации модалки
                fetch(`/${tableId}/edit_row/${rowId}/`)
                    .then(response => {
                        if (response.status === 423) {
                            return response.json().then(data => {
                                alert(data.message);
                                modal.hide();
                                return Promise.reject('Row locked');
                            });
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.status === 'success') {
                            document.getElementById('modalContent').innerHTML = data.html;
                        } else if (data.status === 'error'){
                            alert(data.message);
                            modal.hide();
                        } else {
                            alert('Ошибка загрузки формы');
                            modal.hide();
                        }
                    })
                    .catch(error => {
                        if (error !== 'Row locked') {
                            console.error('Error:', error);
                            modal.hide();
                        }
                    });
            });

            modal.show();
        }
    });

    // Обработка отправки формы
    document.addEventListener('submit', function(e) {
    if (e.target && e.target.id === 'addRowForm') {
        e.preventDefault();
        const form = e.target;
        const submitBtn = form.querySelector('button[type="submit"]');

        // Блокируем кнопку на время отправки
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Сохранение...';

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if(data.status === 'success') {
                bootstrap.Modal.getInstance(document.getElementById('addRowModal')).hide();
                window.location.reload(); // Обновляем таблицу
            } else {
                alert('Ошибка сохранения: ' + (data.message || 'Неизвестная ошибка'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Ошибка соединения');
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Сохранить';
            });
        }

    if (e.target && e.target.id === 'rowEditForm') {
        e.preventDefault();
        const form = e.target;
        const submitBtn = form.querySelector('button[type="submit"]');

        // Блокируем кнопку на время отправки
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Сохранение...';

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if(data.status === 'success') {
                bootstrap.Modal.getInstance(document.getElementById('rowEditModal')).hide();
                window.location.reload(); // Или обновление только строки
            } else {
                alert('Ошибка сохранения: ' + (data.message || 'Неизвестная ошибка'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Ошибка соединения');
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Сохранить';
            });
        }
    });
});