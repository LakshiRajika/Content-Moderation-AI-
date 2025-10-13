// static/script.js

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('moderation-form');
    const contentInput = document.getElementById('content-input');
    const imageInput = document.getElementById('image-input');
    const fileNameDisplay = document.getElementById('file-name-display');
    const statusMessage = document.getElementById('status-message');

    imageInput.addEventListener('change', function () {
        if (this.files.length > 0) {
            fileNameDisplay.textContent = this.files[0].name;
        } else {
            fileNameDisplay.textContent = 'Choose Image (Optional)';
        }
    });

    const ALL_CATEGORIES = [
        'normal',
        'violence',
        'hate_speech',
        'profanity',
        'sexual',
        'spam',
        'threat'
    ];

    form.addEventListener('submit', function (event) {
        event.preventDefault();

        const content = contentInput.value.trim();
        const imageFile = imageInput.files[0];

        if (!content && !imageFile) {
            statusMessage.textContent = 'Please enter text or select an image to classify.';
            return;
        }

        statusMessage.textContent = 'Processing content...';

        const formData = new FormData();
        formData.append('content', content);
        if (imageFile) {
            formData.append('image', imageFile);
        }

        fetch('/moderate', {
            method: 'POST',
            body: formData
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    statusMessage.textContent = `Server Error: ${data.error}`;
                    return;
                }

                statusMessage.textContent = '✅ Classification complete. Results below.';

                const classification = data.classification || {};
                ALL_CATEGORIES.forEach(category => {
                    const score = classification[category];
                    const el = document.getElementById(`score-${category}`);
                    if (el && score !== undefined) {
                        const pct = (score * 100).toFixed(2);
                        el.textContent = `${pct}%`;
                        if (category === 'normal') {
                            el.style.color = score > 0.9 ? 'limegreen' : (score > 0.7 ? 'orange' : 'red');
                        } else {
                            el.style.color = score > 0.5 ? 'red' : (score > 0.2 ? 'orange' : 'green');
                        }
                    }
                });

                // ✅ Update Risk and Action Info
                document.getElementById('risk-level').textContent =
                    data.risk_score?.level || '--';
                document.getElementById('action-actions').textContent =
                    (data.action?.actions || []).join(', ') || '--';
                document.getElementById('audit-id').textContent =
                    data.audit_id || '--';
            })
            .catch(error => {
                console.error('❌ Fetch/Parsing Error:', error);
                statusMessage.textContent = `Network or server error: ${error.message}`;
            });
    });
});
