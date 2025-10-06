// static/script.js

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('moderation-form');
    const contentInput = document.getElementById('content-input');
    const imageInput = document.getElementById('image-input');
    const fileNameDisplay = document.getElementById('file-name-display'); // NEW
    const statusMessage = document.getElementById('status-message');

    // --- NEW: Event listener to display the selected file name ---
    imageInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            fileNameDisplay.textContent = this.files[0].name;
        } else {
            fileNameDisplay.textContent = 'Choose Image (Optional)';
        }
    });
    // -----------------------------------------------------------

    // Define all 7 categories (must match the keys returned by main.py)
    const ALL_CATEGORIES = [
        'normal', 
        'violence', 
        'hate_speech', 
        'profanity', 
        'sexual', 
        'spam', 
        'threat'
    ];

    form.addEventListener('submit', function(event) {
        event.preventDefault(); 
        
        const content = contentInput.value.trim();
        const imageFile = imageInput.files[0];

        if (!content && !imageFile) {
            statusMessage.textContent = 'Please enter text or select an image to classify.';
            return;
        }

        statusMessage.textContent = 'Processing content...';
        
        // --- Prepare FormData for Multimodal Upload ---
        const formData = new FormData();
        
        // Append text content
        formData.append('content', content);
        
        // Append image file if one is selected
        if (imageFile) {
            formData.append('image', imageFile);
        }

        fetch('/moderate', {
            method: 'POST',
            // Do NOT set Content-Type; the browser handles it for FormData.
            body: formData 
        })
        .then(response => {
            if (!response.ok) {
                statusMessage.textContent = `Error: HTTP status ${response.status}`;
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json(); 
        })
        .then(data => {
            if (data.error) {
                statusMessage.textContent = `Server Error: ${data.error}`;
                return;
            }

            statusMessage.textContent = 'Classification complete. Results displayed below.';
            
            const classification = data.classification || {};
            
            // 1. Update All 7 Classification Scores
            ALL_CATEGORIES.forEach(category => {
                const score = classification[category];
                const displayElement = document.getElementById(`score-${category}`);
                
                if (displayElement && score !== undefined) {
                    const percentage = (score * 100).toFixed(2);
                    displayElement.textContent = `${percentage}%`;
                    
                    // Apply color coding
                    if (category === 'normal') {
                        // High 'normal' is GOOD
                        displayElement.style.color = score > 0.95 ? 'green' : (score > 0.8 ? 'orange' : 'red');
                    } else {
                        // High harmful score is BAD
                        displayElement.style.color = score > 0.5 ? 'red' : (score > 0.2 ? 'orange' : 'green');
                    }
                }
            });

            // 2. Update Risk and Action Info
            document.getElementById('risk-level').textContent = data.risk_score.level;
            document.getElementById('action-actions').textContent = data.action.actions.join(', ');
            document.getElementById('audit-id').textContent = data.audit_id;

        })
        .catch(error => {
            console.error('Fetch failed or network/parsing error:', error);
            statusMessage.textContent = 'An unknown network or parsing error occurred. Check the console.';
        });
    });
});