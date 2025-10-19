document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('moderation-form');
    const contentInput = document.getElementById('content-input');
    const imageInput = document.getElementById('image-input');
    const fileNameDisplay = document.getElementById('file-name-display');
    const statusMessage = document.getElementById('status-message');
    const quickResults = document.getElementById('quick-results');
    const actionBanner = document.getElementById('action-banner');
    const toggleDetails = document.getElementById('toggle-details');
    const detailsContent = document.getElementById('details-content');
    const detailsChevron = document.getElementById('details-chevron');
    
    let authToken = null;

    // Initialize authentication on page load
    initializeAuth();

    imageInput.addEventListener('change', function () {
        const file = this.files[0];
        if (file) {
            fileNameDisplay.textContent = file.name;
            fileNameDisplay.classList.remove('text-gray-400');
            fileNameDisplay.classList.add('text-white');
        } else {
            fileNameDisplay.textContent = 'Or upload an image';
            fileNameDisplay.classList.remove('text-white');
            fileNameDisplay.classList.add('text-gray-400');
        }
    });

    // Toggle detailed analysis section
    toggleDetails.addEventListener('click', function() {
        const isHidden = detailsContent.classList.contains('hidden');
        if (isHidden) {
            detailsContent.classList.remove('hidden');
            detailsChevron.classList.add('rotate-180');
        } else {
            detailsContent.classList.add('hidden');
            detailsChevron.classList.remove('rotate-180');
        }
    });

    const ALL_CATEGORIES = [
        'normal', 'violence', 'hate_speech', 'profanity', 'sexual', 'spam', 'threat'
    ];

    async function initializeAuth() {
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify({ 
                    username: 'demo_user', 
                    password: 'demo_pass' 
                })
            });
            
            const data = await response.json();
            if (data.token) {
                authToken = data.token;
                console.log('✅ Authentication successful');
            } else {
                console.warn('⚠️ Authentication failed, proceeding without token');
            }
        } catch (error) {
            console.warn('⚠️ Auth endpoint not available, proceeding without token:', error);
        }
    }

    form.addEventListener('submit', async function (event) {
        event.preventDefault();

        const content = contentInput.value.trim();
        const imageFile = imageInput.files[0];

        if (!content && !imageFile) {
            showStatus('Please enter some text or upload an image to analyze.', 'error');
            return;
        }

        showStatus('Analyzing content for safety issues...', 'loading');

        const formData = new FormData();
        formData.append('content', content);
        if (imageFile) formData.append('image', imageFile);

        try {
            const headers = {};
            if (authToken) {
                headers['Authorization'] = `Bearer ${authToken}`;
            }

            const response = await fetch('/moderate', { 
                method: 'POST', 
                headers: headers,
                body: formData 
            });

            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error('Authentication required. Please refresh the page.');
                }
                throw new Error(`Server error: ${response.status}`);
            }

            const data = await response.json();

            if (data.error) {
                showStatus(`Error: ${data.error}`, 'error');
                return;
            }

            showStatus('Analysis complete! Review results below.', 'success');
            displayResults(data);

        } catch (error) {
            console.error('❌ Fetch/Parsing Error:', error);
            showStatus(`Error: ${error.message}`, 'error');
        }
    });

    function showStatus(message, type = 'info') {
        statusMessage.innerHTML = '';
        
        const icon = {
            loading: '⏳',
            success: '✅',
            error: '❌',
            info: 'ℹ️'
        }[type];

        const colorClass = {
            loading: 'text-blue-400',
            success: 'text-green-400',
            error: 'text-red-400',
            info: 'text-blue-400'
        }[type];

        statusMessage.innerHTML = `
            <div class="flex items-center justify-center ${colorClass}">
                <span class="mr-2">${icon}</span>
                <span>${message}</span>
            </div>
        `;
    }

    function displayResults(data) {
        // Show quick results section
        quickResults.classList.remove('hidden');
        quickResults.classList.add('fade-in');

        const classification = data.classification || {};
        const riskLevel = data.risk_score?.level || 'Low';
        const actions = data.action?.actions || [];
        const riskScore = data.risk_score?.score || 0;

        // Update quick overview
        updateQuickOverview(riskLevel, classification, actions, riskScore);
        
        // Update action banner
        updateActionBanner(riskLevel, actions, data.action?.banner_message);
        
        // Update detailed scores
        updateDetailedScores(classification);
        
        // Update NLP insights
        updateNlpInsights(data.nlp_analysis);
        
        // Update historical context
        updateHistoricalContext(data.historical_context);
    }

    function updateQuickOverview(riskLevel, classification, actions, riskScore) {
        const riskLevelElement = document.getElementById('overview-risk-level');
        const issuesElement = document.getElementById('overview-issues');
        const recommendationElement = document.getElementById('overview-recommendation');

        // Risk level with color coding
        const riskConfig = {
            'High': { color: 'text-red-500', bg: 'risk-high', label: 'Unsafe' },
            'Medium': { color: 'text-yellow-500', bg: 'risk-medium', label: 'Needs Review' },
            'Low': { color: 'text-green-500', bg: 'risk-low', label: 'Safe' }
        }[riskLevel] || { color: 'text-gray-500', bg: '', label: 'Unknown' };

        riskLevelElement.className = `text-2xl font-bold mb-1 ${riskConfig.color}`;
        riskLevelElement.textContent = riskConfig.label;

        // Count issues (scores above 0.3)
        const issueCount = Object.entries(classification).filter(([key, score]) => 
            key !== 'normal' && score > 0.3
        ).length;

        issuesElement.textContent = issueCount === 0 ? 'None' : `${issueCount} issue${issueCount > 1 ? 's' : ''}`;
        issuesElement.className = `text-2xl font-bold mb-1 ${issueCount > 0 ? 'text-yellow-500' : 'text-green-500'}`;

        // Recommendation
        if (riskLevel === 'High') {
            recommendationElement.textContent = 'Do Not Post';
            recommendationElement.className = 'text-2xl font-bold mb-1 text-red-500';
        } else if (riskLevel === 'Medium') {
            recommendationElement.textContent = 'Review';
            recommendationElement.className = 'text-2xl font-bold mb-1 text-yellow-500';
        } else {
            recommendationElement.textContent = 'Post';
            recommendationElement.className = 'text-2xl font-bold mb-1 text-green-500';
        }
    }

    function updateActionBanner(riskLevel, actions, bannerMessage) {
        const bannerTitle = document.getElementById('banner-title');
        const bannerMessageEl = document.getElementById('banner-message');
        const bannerActions = document.getElementById('banner-actions');

        const bannerConfig = {
            'High': {
                bg: 'bg-red-500/20 border-red-500/30',
                title: 'Content Unsafe',
                message: 'This content violates safety guidelines',
                action: 'Remove Content'
            },
            'Medium': {
                bg: 'bg-yellow-500/20 border-yellow-500/30',
                title: 'Review Recommended',
                message: 'Content may need adjustments',
                action: 'Edit & Review'
            },
            'Low': {
                bg: 'bg-green-500/20 border-green-500/30',
                title: 'Content Looks Good',
                message: 'No major safety issues detected',
                action: 'Post Content'
            }
        }[riskLevel] || {
            bg: 'bg-gray-500/20 border-gray-500/30',
            title: 'Analysis Complete',
            message: 'Review results below',
            action: 'Continue'
        };

        actionBanner.className = `hidden p-4 rounded-xl mb-6 fade-in border ${bannerConfig.bg}`;
        bannerTitle.textContent = bannerConfig.title;
        bannerMessageEl.textContent = bannerMessage || bannerConfig.message;
        bannerActions.textContent = bannerConfig.action;

        actionBanner.classList.remove('hidden');
    }

    function updateDetailedScores(classification) {
        ALL_CATEGORIES.forEach(category => {
            const score = classification[category];
            const element = document.getElementById(`score-${category}`);
            
            if (element && score !== undefined) {
                const percentage = (score * 100).toFixed(0);
                element.textContent = `${percentage}%`;
                
                // Color coding based on score
                if (score > 0.7) {
                    element.className = 'text-lg font-semibold text-red-500';
                } else if (score > 0.3) {
                    element.className = 'text-lg font-semibold text-yellow-500';
                } else {
                    element.className = 'text-lg font-semibold text-green-500';
                }
            }
        });
    }

    function updateNlpInsights(nlpData) {
        const entitiesContainer = document.getElementById('nlp-entities');
        
        if (!nlpData || !nlpData.entities || Object.keys(nlpData.entities).length === 0) {
            entitiesContainer.innerHTML = '<p class="text-gray-500 italic">No specific insights detected</p>';
            return;
        }

        let insightsHTML = '';
        const entities = nlpData.entities;

        // People
        if (entities.persons && entities.persons.length > 0) {
            insightsHTML += `
                <div class="mb-3">
                    <div class="text-xs text-gray-400 mb-1">People Mentioned</div>
                    <div class="flex flex-wrap gap-1">
                        ${entities.persons.map(person => 
                            `<span class="px-2 py-1 bg-blue-500/20 text-blue-300 rounded-full text-xs">${person}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
        }

        // Organizations
        if (entities.organizations && entities.organizations.length > 0) {
            insightsHTML += `
                <div class="mb-3">
                    <div class="text-xs text-gray-400 mb-1">Organizations</div>
                    <div class="flex flex-wrap gap-1">
                        ${entities.organizations.map(org => 
                            `<span class="px-2 py-1 bg-purple-500/20 text-purple-300 rounded-full text-xs">${org}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
        }

        // Locations
        if (entities.locations && entities.locations.length > 0) {
            insightsHTML += `
                <div class="mb-3">
                    <div class="text-xs text-gray-400 mb-1">Locations</div>
                    <div class="flex flex-wrap gap-1">
                        ${entities.locations.map(location => 
                            `<span class="px-2 py-1 bg-green-500/20 text-green-300 rounded-full text-xs">${location}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
        }

        // Other entities
        if (entities.other && entities.other.length > 0) {
            insightsHTML += `
                <div class="mb-3">
                    <div class="text-xs text-gray-400 mb-1">Other Details</div>
                    <div class="flex flex-wrap gap-1">
                        ${entities.other.map(other => 
                            `<span class="px-2 py-1 bg-gray-500/20 text-gray-300 rounded-full text-xs">${other}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
        }

        entitiesContainer.innerHTML = insightsHTML || '<p class="text-gray-500 italic">No specific insights detected</p>';
    }

    function updateHistoricalContext(historicalData) {
        const historyContainer = document.getElementById('historical-content');
        
        if (!historicalData || historicalData.similar_cases_found === 0) {
            historyContainer.innerHTML = '<p class="text-gray-500 italic">No similar content found in history</p>';
            return;
        }

        let historyHTML = `
            <div class="text-xs text-green-400 mb-3">
                Found ${historicalData.similar_cases_found} similar case${historicalData.similar_cases_found > 1 ? 's' : ''}
            </div>
        `;

        if (historicalData.previous_decisions && historicalData.previous_decisions.length > 0) {
            historicalData.previous_decisions.forEach((case_, index) => {
                const riskPercent = (case_.risk_score * 100).toFixed(0);
                const riskColor = case_.risk_score > 0.7 ? 'text-red-400' : 
                                case_.risk_score > 0.3 ? 'text-yellow-400' : 'text-green-400';
                
                historyHTML += `
                    <div class="mb-3 p-3 bg-gray-600/30 rounded-lg border-l-4 border-yellow-500/50">
                        <div class="text-xs text-gray-300 mb-1 line-clamp-2">
                            "${case_.content.length > 80 ? case_.content.substring(0, 80) + '...' : case_.content}"
                        </div>
                        <div class="flex justify-between items-center text-xs">
                            <span class="${riskColor} font-semibold">${riskPercent}% risk</span>
                            <span class="text-gray-400">${case_.previous_actions[0] || 'Reviewed'}</span>
                        </div>
                    </div>
                `;
            });
        }

        historyContainer.innerHTML = historyHTML;
    }

    // Add some utility CSS
    const style = document.createElement('style');
    style.textContent = `
        .line-clamp-2 {
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .rotate-180 {
            transform: rotate(180deg);
        }
        .fade-in {
            animation: fadeIn 0.6s ease-out;
        }
        @keyframes fadeIn {
            from { 
                opacity: 0; 
                transform: translateY(20px); 
            }
            to { 
                opacity: 1; 
                transform: translateY(0); 
            }
        }
        .risk-high {
            background: linear-gradient(135deg, rgba(254, 215, 215, 0.2) 0%, rgba(254, 178, 178, 0.2) 100%);
            border: 1px solid rgba(252, 129, 129, 0.3);
        }
        .risk-medium {
            background: linear-gradient(135deg, rgba(254, 235, 200, 0.2) 0%, rgba(251, 211, 141, 0.2) 100%);
            border: 1px solid rgba(246, 173, 85, 0.3);
        }
        .risk-low {
            background: linear-gradient(135deg, rgba(198, 246, 213, 0.2) 0%, rgba(154, 230, 180, 0.2) 100%);
            border: 1px solid rgba(72, 187, 120, 0.3);
        }
    `;
    document.head.appendChild(style);

    // Add example content helper
    const exampleContent = "This is amazing content that should be safe for everyone to enjoy without any issues or concerns about safety.";
    
    // Add click to insert example (optional feature)
    contentInput.addEventListener('focus', function() {
        if (!this.value.trim()) {
            this.placeholder = "Try: 'John from Google wants to hurt people with violence' for demo";
        }
    });
});