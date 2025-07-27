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

        // Results management
        document.getElementById('clear-results').addEventListener('click', () => this.clearResults());

        // Enter key support for inputs
        document.getElementById('search-query').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.testSearchEnterprises();
        });
        document.getElementById('details-siren').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.testEnterpriseDetails();
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

    addResult(title, data, type = 'info') {
        const container = document.getElementById('results-container');
        
        // Clear placeholder if it exists
        if (container.children.length === 1 && container.children[0].classList.contains('text-center')) {
            container.innerHTML = '';
        }

        const resultDiv = document.createElement('div');
        resultDiv.className = `border rounded-lg p-4 ${this.getResultClass(type)}`;
        
        const timestamp = new Date().toLocaleTimeString();
        
        resultDiv.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <h4 class="font-semibold flex items-center">
                    <i class="fas ${this.getResultIcon(type)} mr-2"></i>
                    ${title}
                </h4>
                <span class="text-sm text-gray-500">${timestamp}</span>
            </div>
            <pre class="bg-gray-50 p-3 rounded text-sm overflow-x-auto"><code>${JSON.stringify(data, null, 2)}</code></pre>
        `;
        
        container.insertBefore(resultDiv, container.firstChild);
        
        // Limit to 10 results
        while (container.children.length > 10) {
            container.removeChild(container.lastChild);
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