// Firmia MCP Test UI - JavaScript functionality

class FirmiaUI {
    constructor() {
        this.apiBase = '/api';
        this.init();
    }

    init() {
        this.bindEvents();
        this.checkStatus();
        // Auto-refresh status every 10 seconds
        setInterval(() => this.checkStatus(), 10000);
    }

    bindEvents() {
        // Status controls
        document.getElementById('refresh-status').addEventListener('click', () => this.checkStatus());
        document.getElementById('start-mcp').addEventListener('click', () => this.startMCPServer());
        document.getElementById('stop-mcp').addEventListener('click', () => this.stopMCPServer());

        // Tool tests
        document.getElementById('test-search').addEventListener('click', () => this.testSearchEnterprises());
        document.getElementById('test-details').addEventListener('click', () => this.testEnterpriseDetails());
        document.getElementById('test-status').addEventListener('click', () => this.testAPIStatus());
        
        // INPI Advanced Features
        document.getElementById('test-beneficial').addEventListener('click', () => this.testBeneficialOwners());
        document.getElementById('test-publications').addEventListener('click', () => this.testCompanyPublications());
        document.getElementById('test-updates').addEventListener('click', () => this.testDifferentialUpdates());

        // Results management
        document.getElementById('clear-results').addEventListener('click', () => this.clearResults());

        // Enter key support for inputs
        document.getElementById('search-query').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.testSearchEnterprises();
        });
        document.getElementById('details-siren').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.testEnterpriseDetails();
        });
        document.getElementById('beneficial-siren').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.testBeneficialOwners();
        });
        document.getElementById('publications-siren').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.testCompanyPublications();
        });
    }

    async checkStatus() {
        try {
            const response = await fetch(`${this.apiBase}/status`);
            const status = await response.json();
            
            this.updateServerStatus(status);
        } catch (error) {
            console.error('Failed to check status:', error);
            this.updateServerStatus({ webUI: 'running', mcpServer: 'error' });
        }
    }

    updateServerStatus(status) {
        const mcpStatus = document.getElementById('mcp-status');
        const serverStatus = document.getElementById('server-status');

        // Update MCP server status
        if (status.mcpServer === 'running') {
            mcpStatus.textContent = 'Running';
            mcpStatus.className = 'text-green-600 font-medium';
            serverStatus.innerHTML = `
                <div class="w-3 h-3 bg-green-400 rounded-full"></div>
                <span class="text-sm">All systems operational</span>
            `;
        } else if (status.mcpServer === 'stopped') {
            mcpStatus.textContent = 'Stopped';
            mcpStatus.className = 'text-red-600 font-medium';
            serverStatus.innerHTML = `
                <div class="w-3 h-3 bg-red-400 rounded-full"></div>
                <span class="text-sm">MCP server stopped</span>
            `;
        } else {
            mcpStatus.textContent = 'Error';
            mcpStatus.className = 'text-red-600 font-medium';
            serverStatus.innerHTML = `
                <div class="w-3 h-3 bg-red-400 rounded-full animate-pulse"></div>
                <span class="text-sm">Connection error</span>
            `;
        }
    }

    async startMCPServer() {
        try {
            this.showLoading();
            const response = await fetch(`${this.apiBase}/mcp/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            
            this.addResult('MCP Server Start', result, 'info');
            
            // Wait a bit and check status
            setTimeout(() => this.checkStatus(), 2000);
        } catch (error) {
            this.addResult('MCP Server Start', { error: error.message }, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async stopMCPServer() {
        try {
            this.showLoading();
            const response = await fetch(`${this.apiBase}/mcp/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            
            this.addResult('MCP Server Stop', result, 'info');
            this.checkStatus();
        } catch (error) {
            this.addResult('MCP Server Stop', { error: error.message }, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async testSearchEnterprises() {
        const query = document.getElementById('search-query').value.trim();
        if (!query) {
            alert('Please enter a company name or SIREN number');
            return;
        }

        const params = {
            query: query,
            source: document.getElementById('search-source').value,
            maxResults: parseInt(document.getElementById('search-max').value)
        };

        try {
            this.showLoading();
            const response = await fetch(`${this.apiBase}/mcp/test/search_enterprises`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params })
            });
            const result = await response.json();
            
            this.addResult('Search Enterprises', result, result.success ? 'success' : 'error');
        } catch (error) {
            this.addResult('Search Enterprises', { error: error.message }, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async testEnterpriseDetails() {
        const siren = document.getElementById('details-siren').value.trim();
        if (!siren) {
            alert('Please enter a SIREN number (9 digits)');
            return;
        }

        if (!/^\d{9}$/.test(siren)) {
            alert('SIREN must be exactly 9 digits');
            return;
        }

        const params = {
            siren: siren,
            source: document.getElementById('details-source').value,
            includeFinancials: document.getElementById('include-financials').checked,
            includeIntellectualProperty: document.getElementById('include-ip').checked
        };

        try {
            this.showLoading();
            const response = await fetch(`${this.apiBase}/mcp/test/get_enterprise_details`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params })
            });
            const result = await response.json();
            
            this.addResult('Enterprise Details', result, result.success ? 'success' : 'error');
        } catch (error) {
            this.addResult('Enterprise Details', { error: error.message }, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async testAPIStatus() {
        try {
            this.showLoading();
            const response = await fetch(`${this.apiBase}/mcp/test/get_api_status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params: {} })
            });
            const result = await response.json();
            
            this.addResult('API Status', result, result.success ? 'success' : 'error');
            
            // Update API status display
            if (result.success && result.apis) {
                const statusText = Object.keys(result.apis).map(api => 
                    `${api.toUpperCase()}: ${result.apis[api].available ? 'UP' : 'DOWN'}`
                ).join(', ');
                document.getElementById('api-status').textContent = statusText;
            }
        } catch (error) {
            this.addResult('API Status', { error: error.message }, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async testBeneficialOwners() {
        const siren = document.getElementById('beneficial-siren').value.trim();
        if (!siren) {
            alert('Please enter a SIREN number (9 digits)');
            return;
        }

        if (!/^\d{9}$/.test(siren)) {
            alert('SIREN must be exactly 9 digits');
            return;
        }

        const params = { siren };

        try {
            this.showLoading();
            const response = await fetch(`${this.apiBase}/mcp/test/get_beneficial_owners`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params })
            });
            const result = await response.json();
            
            this.addResult('Beneficial Owners', result, result.success ? 'success' : 'error');
        } catch (error) {
            this.addResult('Beneficial Owners', { error: error.message }, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async testCompanyPublications() {
        const siren = document.getElementById('publications-siren').value.trim();
        if (!siren) {
            alert('Please enter a SIREN number (9 digits)');
            return;
        }

        if (!/^\d{9}$/.test(siren)) {
            alert('SIREN must be exactly 9 digits');
            return;
        }

        const params = {
            siren: siren,
            type: document.getElementById('publications-type').value,
            includeConfidential: document.getElementById('include-confidential').checked
        };

        try {
            this.showLoading();
            const response = await fetch(`${this.apiBase}/mcp/test/get_company_publications`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params })
            });
            const result = await response.json();
            
            this.addResult('Company Publications', result, result.success ? 'success' : 'error');
        } catch (error) {
            this.addResult('Company Publications', { error: error.message }, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async testDifferentialUpdates() {
        const fromDate = document.getElementById('updates-from').value;
        if (!fromDate) {
            alert('Please select a start date');
            return;
        }

        const params = {
            from: fromDate,
            pageSize: parseInt(document.getElementById('updates-pagesize').value) || 10
        };

        const toDate = document.getElementById('updates-to').value;
        if (toDate) {
            params.to = toDate;
        }

        try {
            this.showLoading();
            const response = await fetch(`${this.apiBase}/mcp/test/get_differential_updates`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params })
            });
            const result = await response.json();
            
            this.addResult('Differential Updates', result, result.success ? 'success' : 'error');
        } catch (error) {
            this.addResult('Differential Updates', { error: error.message }, 'error');
        } finally {
            this.hideLoading();
        }
    }

    addResult(title, data, type = 'info') {
        const container = document.getElementById('results-container');
        
        // Clear placeholder if it exists
        if (container.children.length === 1 && container.children[0].classList.contains('text-center')) {
            container.innerHTML = '';
        }

        const resultDiv = document.createElement('div');
        resultDiv.className = `border rounded-lg p-4 ${this.getResultClass(type)}`;
        
        const timestamp = new Date().toLocaleTimeString();
        
        // Format content based on data type
        let content = '';
        if (title === 'Search Enterprises' && data.success && data.result && data.result.content) {
            content = this.formatSearchResults(data);
        } else if (title === 'Enterprise Details' && data.success && data.result && data.result.content) {
            content = this.formatEnterpriseDetails(data);
        } else if (title === 'API Status' && data.success && data.result && data.result.content) {
            content = this.formatApiStatus(data);
        } else if (title === 'Beneficial Owners' && data.success && data.result && data.result.content) {
            content = this.formatBeneficialOwners(data);
        } else if (title === 'Company Publications' && data.success && data.result && data.result.content) {
            content = this.formatCompanyPublications(data);
        } else if (title === 'Differential Updates' && data.success && data.result && data.result.content) {
            content = this.formatDifferentialUpdates(data);
        } else {
            // Fallback to JSON display for other types
            content = `<pre class="bg-gray-50 p-3 rounded text-sm overflow-x-auto"><code>${JSON.stringify(data, null, 2)}</code></pre>`;
        }
        
        resultDiv.innerHTML = `
            <div class="flex items-center justify-between mb-4">
                <h4 class="font-semibold flex items-center">
                    <i class="fas ${this.getResultIcon(type)} mr-2"></i>
                    ${title}
                </h4>
                <span class="text-sm text-gray-500">${timestamp}</span>
            </div>
            ${content}
        `;
        
        container.insertBefore(resultDiv, container.firstChild);
        
        // Limit to 10 results
        while (container.children.length > 10) {
            container.removeChild(container.lastChild);
        }
    }

    formatSearchResults(data) {
        try {
            const results = JSON.parse(data.result.content[0].text);
            
            if (!results.success || !results.results) {
                return `<div class="text-red-600">❌ Search failed</div>`;
            }

            let html = '<div class="space-y-4">';
            
            results.results.forEach(sourceResult => {
                const sourceName = sourceResult.source.toUpperCase();
                
                html += `<div class="border-l-4 border-blue-500 pl-4">`;
                html += `<h5 class="font-medium text-lg mb-2 text-blue-700"><i class="fas fa-building mr-2"></i>${sourceName}</h5>`;
                
                if (sourceResult.error) {
                    html += `<div class="text-red-600 text-sm">❌ ${sourceResult.error}</div>`;
                } else if (sourceResult.data && sourceResult.data.length > 0) {
                    html += '<div class="overflow-x-auto">';
                    html += '<table class="min-w-full divide-y divide-gray-200">';
                    html += `
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">SIREN</th>
                                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Activity</th>
                                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                    `;
                    
                    sourceResult.data.forEach(company => {
                        const statusIcon = company.status === 'A' ? '✅' : company.status === 'C' ? '❌' : '❓';
                        const statusText = company.status === 'A' ? 'Active' : company.status === 'C' ? 'Closed' : 'Unknown';
                        
                        html += `
                            <tr class="hover:bg-gray-50">
                                <td class="px-3 py-2">
                                    <div class="font-medium text-gray-900">${company.name || 'N/A'}</div>
                                    <div class="text-sm text-gray-500">Form: ${company.legalForm || 'N/A'}</div>
                                </td>
                                <td class="px-3 py-2">
                                    <div class="text-sm font-mono">${company.siren}</div>
                                    <div class="text-xs text-gray-500">${company.siret || ''}</div>
                                </td>
                                <td class="px-3 py-2 text-sm text-gray-500">${company.activity || 'N/A'}</td>
                                <td class="px-3 py-2">
                                    <span class="text-sm">${statusIcon} ${statusText}</span>
                                </td>
                                <td class="px-3 py-2 text-sm text-gray-500">${company.creationDate || 'N/A'}</td>
                            </tr>
                        `;
                    });
                    
                    html += '</tbody></table></div>';
                } else {
                    html += '<div class="text-gray-500 text-sm">No data available</div>';
                }
                
                html += '</div>';
            });
            
            html += '</div>';
            return html;
            
        } catch (error) {
            return `<div class="text-red-600">❌ Error formatting results: ${error.message}</div>`;
        }
    }

    formatEnterpriseDetails(data) {
        try {
            const results = JSON.parse(data.result.content[0].text);
            
            if (!results.success) {
                return `<div class="text-red-600">❌ Details request failed: ${results.error || 'Unknown error'}</div>`;
            }

            const siren = results.siren;
            const details = results.details;
            
            if (!details || Object.keys(details).length === 0) {
                return `<div class="text-yellow-600">⚠️ No details found for SIREN ${siren}</div>`;
            }

            let html = `<div class="space-y-6">`;
            html += `<div class="text-lg font-semibold text-gray-800 border-b pb-2">Enterprise Details for SIREN: ${siren}</div>`;
            
            // Display details from each source
            Object.entries(details).forEach(([sourceName, sourceData]) => {
                html += `<div class="border-l-4 border-blue-500 pl-4">`;
                html += `<h5 class="font-medium text-lg mb-3 text-blue-700"><i class="fas fa-building mr-2"></i>${sourceName.toUpperCase()}</h5>`;
                
                if (sourceData.error) {
                    html += `<div class="text-red-600 text-sm">❌ ${sourceData.error}</div>`;
                } else if (sourceData.basicInfo) {
                    // Format basic info
                    html += '<div class="bg-gray-50 rounded-lg p-4 mb-4">';
                    html += '<h6 class="font-medium text-gray-800 mb-2">Basic Information</h6>';
                    html += '<div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">';
                    
                    const basicInfo = sourceData.basicInfo;
                    if (basicInfo.name) html += `<div><span class="font-medium">Name:</span> ${basicInfo.name}</div>`;
                    if (basicInfo.legalForm) html += `<div><span class="font-medium">Legal Form:</span> ${basicInfo.legalForm}</div>`;
                    if (basicInfo.address) html += `<div><span class="font-medium">Address:</span> ${basicInfo.address}</div>`;
                    if (basicInfo.activity) html += `<div><span class="font-medium">Activity:</span> ${basicInfo.activity}</div>`;
                    if (basicInfo.creationDate) html += `<div><span class="font-medium">Created:</span> ${basicInfo.creationDate}</div>`;
                    if (basicInfo.status) html += `<div><span class="font-medium">Status:</span> ${basicInfo.status}</div>`;
                    
                    html += '</div></div>';
                    
                    // Format financials if available
                    if (sourceData.financials) {
                        html += '<div class="bg-green-50 rounded-lg p-4 mb-4">';
                        html += '<h6 class="font-medium text-gray-800 mb-2">Financial Information</h6>';
                        html += '<div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">';
                        
                        const financials = sourceData.financials;
                        if (financials.revenue) html += `<div><span class="font-medium">Revenue:</span> ${financials.revenue}</div>`;
                        if (financials.employees) html += `<div><span class="font-medium">Employees:</span> ${financials.employees}</div>`;
                        if (financials.lastUpdate) html += `<div><span class="font-medium">Last Update:</span> ${financials.lastUpdate}</div>`;
                        
                        html += '</div></div>';
                    }
                    
                    // Format intellectual property if available
                    if (sourceData.intellectualProperty) {
                        html += '<div class="bg-purple-50 rounded-lg p-4 mb-4">';
                        html += '<h6 class="font-medium text-gray-800 mb-2">Intellectual Property</h6>';
                        html += '<div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">';
                        
                        const ip = sourceData.intellectualProperty;
                        if (ip.trademarks !== undefined) html += `<div><span class="font-medium">Trademarks:</span> ${ip.trademarks}</div>`;
                        if (ip.patents !== undefined) html += `<div><span class="font-medium">Patents:</span> ${ip.patents}</div>`;
                        if (ip.designs !== undefined) html += `<div><span class="font-medium">Designs:</span> ${ip.designs}</div>`;
                        
                        html += '</div></div>';
                    }
                } else {
                    html += '<div class="text-gray-500 text-sm">No detailed information available</div>';
                }
                
                html += '</div>';
            });
            
            html += '</div>';
            return html;
            
        } catch (error) {
            return `<div class="text-red-600">❌ Error formatting enterprise details: ${error.message}</div>`;
        }
    }

    formatApiStatus(data) {
        try {
            const results = JSON.parse(data.result.content[0].text);
            
            if (!results.success || !results.status) {
                return `<div class="text-red-600">❌ Status check failed</div>`;
            }

            let html = '<div class="grid grid-cols-1 md:grid-cols-3 gap-4">';
            
            Object.entries(results.status).forEach(([apiName, status]) => {
                const isAvailable = status.available;
                const statusColor = isAvailable ? 'green' : 'red';
                const statusIcon = isAvailable ? '✅' : '❌';
                
                html += `
                    <div class="border rounded-lg p-4 bg-${statusColor}-50 border-${statusColor}-200">
                        <h6 class="font-medium text-${statusColor}-800">${statusIcon} ${apiName.toUpperCase()}</h6>
                        <div class="mt-2 text-sm">
                            <div class="text-${statusColor}-700">
                                Status: <span class="font-medium">${isAvailable ? 'Available' : 'Unavailable'}</span>
                            </div>
                `;
                
                if (status.rateLimit) {
                    html += `
                            <div class="text-${statusColor}-600">
                                Rate Limit: ${status.rateLimit.remaining || 'N/A'} remaining
                            </div>
                    `;
                }
                
                if (status.error) {
                    html += `<div class="text-red-600 text-xs mt-1">${status.error}</div>`;
                }
                
                html += `
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            return html;
            
        } catch (error) {
            return `<div class="text-red-600">❌ Error formatting API status: ${error.message}</div>`;
        }
    }

    formatBeneficialOwners(data) {
        try {
            const results = JSON.parse(data.result.content[0].text);
            
            if (!results.success) {
                return `<div class="text-red-600">❌ Beneficial owners request failed: ${results.error || 'Unknown error'}</div>`;
            }

            const beneficialOwners = results.beneficialOwners || [];
            const siren = results.siren;
            
            if (beneficialOwners.length === 0) {
                return `<div class="text-yellow-600">⚠️ No beneficial owners found for SIREN ${siren}</div>`;
            }

            let html = `<div class="space-y-4">`;
            html += `<div class="text-lg font-semibold text-gray-800 border-b pb-2">Beneficial Owners for SIREN: ${siren}</div>`;
            
            html += '<div class="overflow-x-auto">';
            html += '<table class="min-w-full divide-y divide-gray-200">';
            html += `
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Birth Date</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
            `;
            
            beneficialOwners.forEach(owner => {
                const typeIcon = owner.isCompany ? '🏢' : '👤';
                const typeText = owner.isCompany ? 'Company' : 'Individual';
                
                html += `
                    <tr class="hover:bg-gray-50">
                        <td class="px-3 py-2">
                            <div class="font-medium text-gray-900">${owner.name || 'N/A'}</div>
                            ${owner.companySiren ? `<div class="text-xs text-gray-500">SIREN: ${owner.companySiren}</div>` : ''}
                        </td>
                        <td class="px-3 py-2 text-sm text-gray-500">${owner.role || 'N/A'}</td>
                        <td class="px-3 py-2 text-sm">
                            <span>${typeIcon} ${typeText}</span>
                        </td>
                        <td class="px-3 py-2 text-sm text-gray-500">${owner.birthDate || 'N/A'}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table></div></div>';
            return html;
            
        } catch (error) {
            return `<div class="text-red-600">❌ Error formatting beneficial owners: ${error.message}</div>`;
        }
    }

    formatCompanyPublications(data) {
        try {
            const results = JSON.parse(data.result.content[0].text);
            
            if (!results.success) {
                return `<div class="text-red-600">❌ Publications request failed: ${results.error || 'Unknown error'}</div>`;
            }

            const publications = results.publications || [];
            const siren = results.siren;
            
            if (publications.length === 0) {
                return `<div class="text-yellow-600">⚠️ No publications found for SIREN ${siren}</div>`;
            }

            let html = `<div class="space-y-4">`;
            html += `<div class="text-lg font-semibold text-gray-800 border-b pb-2">Company Publications for SIREN: ${siren}</div>`;
            
            html += '<div class="overflow-x-auto">';
            html += '<table class="min-w-full divide-y divide-gray-200">';
            html += `
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Document</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Download</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
            `;
            
            publications.forEach(pub => {
                const confidentialIcon = pub.confidential ? '🔒' : '📄';
                const confidentialText = pub.confidential ? 'Confidential' : 'Public';
                const typeIcon = pub.type === 'BILAN' ? '💰' : pub.type === 'ACTE' ? '📋' : '📄';
                
                html += `
                    <tr class="hover:bg-gray-50">
                        <td class="px-3 py-2">
                            <div class="font-medium text-gray-900">${pub.name || 'N/A'}</div>
                            <div class="text-xs text-gray-500">ID: ${pub.id}</div>
                        </td>
                        <td class="px-3 py-2 text-sm">
                            <span>${typeIcon} ${pub.type}</span>
                        </td>
                        <td class="px-3 py-2 text-sm text-gray-500">${pub.date || 'N/A'}</td>
                        <td class="px-3 py-2 text-sm">
                            <span>${confidentialIcon} ${confidentialText}</span>
                        </td>
                        <td class="px-3 py-2 text-sm">
                            ${pub.downloadUrl ? 
                                `<a href="${pub.downloadUrl}" target="_blank" class="text-blue-600 hover:text-blue-800">📥 Download</a>` : 
                                '<span class="text-gray-400">Not available</span>'
                            }
                        </td>
                    </tr>
                `;
            });
            
            html += '</tbody></table></div></div>';
            return html;
            
        } catch (error) {
            return `<div class="text-red-600">❌ Error formatting company publications: ${error.message}</div>`;
        }
    }

    formatDifferentialUpdates(data) {
        try {
            const results = JSON.parse(data.result.content[0].text);
            
            if (!results.success) {
                return `<div class="text-red-600">❌ Differential updates request failed: ${results.error || 'Unknown error'}</div>`;
            }

            const updates = results.updates || {};
            const companies = updates.companies || [];
            
            if (companies.length === 0) {
                return `<div class="text-yellow-600">⚠️ No company updates found for the specified period</div>`;
            }

            let html = `<div class="space-y-4">`;
            html += `<div class="text-lg font-semibold text-gray-800 border-b pb-2">Recent Company Updates (${companies.length} results)</div>`;
            
            if (updates.nextCursor) {
                html += `<div class="text-sm text-blue-600">Next cursor available: ${updates.nextCursor}</div>`;
            }
            
            html += '<div class="overflow-x-auto">';
            html += '<table class="min-w-full divide-y divide-gray-200">';
            html += `
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">SIREN</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Update Type</th>
                        <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
            `;
            
            companies.forEach(company => {
                const updateIcon = company.updateType === 'CREATION' ? '🆕' : 
                                 company.updateType === 'RADIATION' ? '❌' : '✏️';
                const updateClass = company.updateType === 'CREATION' ? 'text-green-600' : 
                                  company.updateType === 'RADIATION' ? 'text-red-600' : 'text-blue-600';
                
                html += `
                    <tr class="hover:bg-gray-50">
                        <td class="px-3 py-2">
                            <div class="font-medium text-gray-900">${company.name || 'N/A'}</div>
                        </td>
                        <td class="px-3 py-2">
                            <div class="text-sm font-mono">${company.siren}</div>
                        </td>
                        <td class="px-3 py-2">
                            <span class="${updateClass}">${updateIcon} ${company.updateType}</span>
                        </td>
                        <td class="px-3 py-2 text-sm text-gray-500">${company.updateDate || 'N/A'}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table></div></div>';
            return html;
            
        } catch (error) {
            return `<div class="text-red-600">❌ Error formatting differential updates: ${error.message}</div>`;
        }
    }

    getResultClass(type) {
        switch (type) {
            case 'success': return 'border-green-200 bg-green-50';
            case 'error': return 'border-red-200 bg-red-50';
            case 'info': return 'border-blue-200 bg-blue-50';
            default: return 'border-gray-200 bg-gray-50';
        }
    }

    getResultIcon(type) {
        switch (type) {
            case 'success': return 'fa-check-circle text-green-500';
            case 'error': return 'fa-exclamation-circle text-red-500';
            case 'info': return 'fa-info-circle text-blue-500';
            default: return 'fa-circle text-gray-500';
        }
    }

    clearResults() {
        const container = document.getElementById('results-container');
        container.innerHTML = `
            <div class="text-center text-gray-500 py-12">
                <i class="fas fa-clipboard-list text-4xl mb-4"></i>
                <p>Test results will appear here</p>
                <p class="text-sm mt-2">Use the tools on the left to test the MCP server</p>
            </div>
        `;
    }

    showLoading() {
        document.getElementById('loading').classList.remove('hidden');
    }

    hideLoading() {
        document.getElementById('loading').classList.add('hidden');
    }
}

// Initialize the UI when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new FirmiaUI();
});