# Firmia

French Company Intelligence MCP Server - Democratizing access to French business data.

## 🚀 Overview

Firmia is a production-grade MCP (Model Context Protocol) server that provides comprehensive French company and association intelligence by orchestrating 8+ public APIs and static datasets. It offers a unified interface to French business data that is currently locked behind expensive proprietary solutions.

## 🛠️ Tech Stack

- **Python 3.12**: Modern async Python with full type hints
- **FastMCP**: MCP protocol implementation
- **Redis**: High-performance caching layer
- **DuckDB**: Analytics and static data processing
- **HTTPx**: Async HTTP client with HTTP/2 support
- **Pydantic**: Data validation and serialization
- **OpenTelemetry**: Distributed tracing and monitoring

## ✨ Features

- ✅ **Multi-Source Company Search**: Search across 8+ government APIs
- ✅ **Unified Company Profiles**: Complete data fusion from multiple sources
- ✅ **Official Document Downloads**: Access to bilans, actes, statuts
- ✅ **Business Events Timeline**: BODACC integration for lifecycle tracking
- ✅ **RGPD Compliance**: Privacy filters and audit logging
- ✅ **Multi-Provider Authentication**: Support for 7 auth mechanisms
- 🔧 **Association Search**: RNA API integration
- 🔧 **RGE Certification Check**: Environmental certification verification
- 🔧 **Bank Account Verification**: FICOBA integration (requires auth)
- 📋 **Company Health Scoring**: Analytics based on public data

## 🏃‍♂️ Quick Start

### Prerequisites

- Python 3.12+
- Redis server
- Docker (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/bacoco/Firmia.git
cd Firmia

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env with your API credentials

# Run the server
python -m firmia.server
```

### Available Scripts

```bash
# Development server with auto-reload
uvicorn firmia.server:app --reload --port 8789

# Run tests
pytest

# Run tests with coverage
pytest --cov=src

# Type checking
mypy src

# Linting
ruff check src

# Format code
black src tests
```

## 📁 Project Structure

```
firmia/
├── src/              # Source code
│   ├── api/         # External API clients
│   ├── auth/        # Authentication managers
│   ├── cache/       # Caching layer
│   ├── models/      # Pydantic models
│   ├── tools/       # MCP tools
│   ├── privacy/     # RGPD compliance
│   ├── resilience/  # Circuit breakers
│   └── monitoring/  # Observability
├── tests/           # Test suite
├── deployment/      # Docker & K8s configs
└── docs/           # Documentation
```

## 🧪 Testing

This project includes comprehensive test coverage:

```bash
# Run all tests
pytest

# Run specific test module
pytest tests/unit/test_auth.py

# Run integration tests
pytest tests/integration/

# Generate coverage report
pytest --cov=src --cov-report=html
```

## 🔧 Configuration

Key configuration files:

- `.env` - Environment variables and API credentials
- `pyproject.toml` - Project metadata and tool configuration
- `deployment/docker-compose.yml` - Docker development setup
- `deployment/k8s/` - Kubernetes manifests

## 📝 Development Workflow

This project was set up with Pantheon's automated workflow:

- ✅ Automatic Git commits after each development phase
- ✅ Continuous GitHub integration
- ✅ Test files generated for all components
- ✅ Docker and Kubernetes deployment configs
- ✅ Pre-commit test execution

## 🐳 Docker

Build and run with Docker:

```bash
# Build image
docker build -t firmia .

# Run container
docker run -p 8789:8789 --env-file .env firmia

# Use docker-compose for development
docker-compose -f deployment/docker-compose.dev.yml up
```

## 📊 API Documentation

Once running, the MCP server exposes the following tools:

- `search_companies` - Search for companies and associations
- `get_company_profile` - Get detailed company information
- `download_official_document` - Download official documents
- `get_business_events` - Get business event timeline

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 👥 Author

Loic

---

*Generated with ❤️ by [Pantheon](https://github.com/godsco/pantheon) on 2025-01-20*