document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('search-input');
    const box = document.getElementById('suggestion-box');
    let timer = null;
    input.addEventListener('input', function() {
        clearTimeout(timer);
        const val = input.value.trim();
        if (!val) {
            box.style.display = 'none';
            box.innerHTML = '';
            return;
        }
        timer = setTimeout(function() {
            fetch(`/autocomplete/?q=${encodeURIComponent(val)}`)
                .then(res => res.json())
                .then(data => {
                    if (data.length === 0) {
                        box.style.display = 'none';
                        box.innerHTML = '';
                        return;
                    }
                    box.innerHTML = '';
                    data.forEach(name => {
                        const div = document.createElement('div');
                        div.textContent = name;
                        div.style.cursor = 'pointer';
                        div.onclick = function() {
                            // Instead of searching, go to product detail page
                            window.location.href = `/product/${encodeURIComponent(name)}/`;
                        };
                        box.appendChild(div);
                    });
                    box.style.display = 'block';
                });
        }, 200);
    });
    document.addEventListener('click', function(e) {
        if (!box.contains(e.target) && e.target !== input) {
            box.style.display = 'none';
        }
    });
});
