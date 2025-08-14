document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('search-input');
    const suggestionBox = document.getElementById('suggestion-box');

    input.addEventListener('input', function() {
        const query = input.value.trim();
        if (query.length === 0) {
            suggestionBox.style.display = 'none';
            return;
        }

        fetch(`/autocomplete/?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                suggestionBox.innerHTML = '';
                if (data.length > 0) {
                    data.forEach(item => {
                        const div = document.createElement('div');
                        div.textContent = item;
                        div.addEventListener('mousedown', function(e) {
                            e.preventDefault(); // جلوگیری از از دست رفتن فوکوس
                            input.value = item;
                            suggestionBox.style.display = 'none';
                        });
                        suggestionBox.appendChild(div);
                    });
                    suggestionBox.style.display = 'block';
                } else {
                    suggestionBox.style.display = 'none';
                }
            })
            .catch(() => {
                suggestionBox.style.display = 'none';
            });
    });

    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !suggestionBox.contains(e.target)) {
            suggestionBox.style.display = 'none';
        }
    });
});
