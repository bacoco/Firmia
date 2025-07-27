# Contributing to MCP Firms

Thank you for your interest in contributing to MCP Firms! This document provides guidelines and instructions for contributing to the project.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Adding New API Adapters](#adding-new-api-adapters)
- [Testing Guidelines](#testing-guidelines)
- [Code Style Guidelines](#code-style-guidelines)
- [Documentation Standards](#documentation-standards)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please read and follow our Code of Conduct:

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive criticism
- Respect differing viewpoints and experiences
- Show empathy towards other community members

## Getting Started

### Prerequisites

- Node.js 18.0.0 or higher
- npm 8.0.0 or higher
- Git
- TypeScript knowledge
- Familiarity with MCP (Model Context Protocol)

### First-Time Contributors

1. Look for issues labeled `good first issue` or `help wanted`
2. Comment on the issue to express interest
3. Ask questions if you need clarification
4. Submit a PR when ready

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/yourusername/mcp-firms.git
cd mcp-firms

# Add upstream remote
git remote add upstream https://github.com/originalrepo/mcp-firms.git
```

### 2. Install Dependencies

```bash
# Install project dependencies
npm install

# Install development tools globally (optional)
npm install -g typescript jest eslint
```

### 3. Environment Setup

```bash
# Copy environment example
cp .env.example .env.development

# Configure with test API keys (if available)
# Or use mock mode for development
echo "USE_MOCK_APIS=true" >> .env.development
```

### 4. Verify Setup

```bash
# Run tests
npm test

# Run linting
npm run lint

# Run type checking
npm run typecheck

# Start development server
npm run dev
```

## Project Structure

```
mcp-firms/
├── src/                      # Source code
│   ├── index.ts             # MCP server entry point
│   ├── adapters/            # API adapters
│   │   ├── index.ts         # Adapter factory
│   │   ├── base.ts          # Base adapter class
│   │   ├── insee.ts         # INSEE adapter
│   │   ├── banque-france.ts # Banque de France adapter
│   │   └── inpi.ts          # INPI adapter
│   ├── cache/               # Caching implementation
│   ├── rate-limiter/        # Rate limiting
│   ├── types/               # TypeScript types
│   └── utils/               # Utility functions
├── tests/                   # Test files
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── fixtures/           # Test data
├── docs/                    # Documentation
├── scripts/                 # Build and utility scripts
└── .github/                # GitHub workflows
```

## Development Workflow

### 1. Create a Feature Branch

```bash
# Update main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write code following our style guidelines
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 3. Commit Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat: add support for new API endpoint"

# Follow conventional commits:
# feat: new feature
# fix: bug fix
# docs: documentation changes
# test: test additions/changes
# refactor: code refactoring
# chore: maintenance tasks
```

### 4. Keep Branch Updated

```bash
# Fetch upstream changes
git fetch upstream

# Rebase your branch
git rebase upstream/main
```

## Adding New API Adapters

### Step-by-Step Guide

#### 1. Create Adapter File

Create `src/adapters/your-api.ts`:

```typescript
import { BaseAdapter } from './base.js';
import { 
  SearchOptions, 
  DetailsOptions, 
  SearchResult, 
  EnterpriseDetails,
  AdapterStatus,
  AdapterConfig 
} from '../types/index.js';

export class YourAPIAdapter extends BaseAdapter {
  private readonly apiKey: string;
  private readonly baseUrl: string;

  constructor(config: AdapterConfig) {
    super(config);
    this.apiKey = process.env.YOUR_API_KEY || '';
    this.baseUrl = process.env.YOUR_API_URL || 'https://api.your-api.com';
  }

  async search(query: string, options: SearchOptions): Promise<SearchResult[]> {
    // Implement search logic
    const cacheKey = this.getCacheKey('search', query, options);
    
    // Check cache
    const cached = await this.cache.get(cacheKey);
    if (cached) return cached;

    // Apply rate limiting
    await this.rateLimiter.acquire('your-api');

    try {
      // Make API call
      const response = await this.makeRequest('/search', { q: query });
      
      // Transform response
      const results = this.transformSearchResults(response);
      
      // Cache results
      await this.cache.set(cacheKey, results);
      
      return results;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async getDetails(siren: string, options: DetailsOptions): Promise<EnterpriseDetails> {
    // Implement details retrieval
  }

  async getStatus(): Promise<AdapterStatus> {
    // Implement status check
  }

  private transformSearchResults(data: any): SearchResult[] {
    // Transform API response to standard format
  }
}
```

#### 2. Register Adapter

Update `src/adapters/index.ts`:

```typescript
import { YourAPIAdapter } from './your-api.js';

export function setupAdapters(config: AdapterConfig): Record<string, BaseAdapter> {
  return {
    insee: new INSEEAdapter(config),
    'banque-france': new BanqueFranceAdapter(config),
    inpi: new INPIAdapter(config),
    'your-api': new YourAPIAdapter(config), // Add your adapter
  };
}
```

#### 3. Add Configuration

Update `.env.example`:

```env
# Your API Configuration
YOUR_API_KEY=your_api_key_here
YOUR_API_URL=https://api.your-api.com
RATE_LIMIT_YOUR_API=1000
```

#### 4. Add Types

Update `src/types/index.ts` if needed:

```typescript
export interface YourAPISpecificData {
  // Add any API-specific types
}
```

#### 5. Write Tests

Create `tests/unit/adapters/your-api.test.ts`:

```typescript
import { YourAPIAdapter } from '../../../src/adapters/your-api';
import { createMockConfig } from '../../helpers';

describe('YourAPIAdapter', () => {
  let adapter: YourAPIAdapter;

  beforeEach(() => {
    adapter = new YourAPIAdapter(createMockConfig());
  });

  describe('search', () => {
    it('should search enterprises', async () => {
      // Test implementation
    });
  });

  describe('getDetails', () => {
    it('should get enterprise details', async () => {
      // Test implementation
    });
  });
});
```

#### 6. Document the Adapter

Update `docs/API.md` with:
- Authentication requirements
- Endpoint documentation
- Field mappings
- Rate limits
- Example requests/responses

## Testing Guidelines

### Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── adapters/           # Adapter tests
│   ├── cache/              # Cache tests
│   └── utils/              # Utility tests
├── integration/            # Integration tests
│   ├── api/               # Real API tests (optional)
│   └── mcp/               # MCP protocol tests
├── fixtures/              # Test data
│   ├── insee/            # INSEE response mocks
│   ├── banque-france/    # BdF response mocks
│   └── inpi/             # INPI response mocks
└── helpers/              # Test utilities
```

### Writing Tests

#### Unit Tests

```typescript
describe('ComponentName', () => {
  // Setup
  let component: Component;
  
  beforeEach(() => {
    component = new Component();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // Group related tests
  describe('methodName', () => {
    it('should handle normal case', async () => {
      // Arrange
      const input = 'test';
      const expected = 'result';

      // Act
      const result = await component.method(input);

      // Assert
      expect(result).toBe(expected);
    });

    it('should handle error case', async () => {
      // Test error handling
      await expect(component.method(null))
        .rejects.toThrow('Invalid input');
    });
  });
});
```

#### Integration Tests

```typescript
describe('INSEE API Integration', () => {
  // Skip in CI if no API keys
  const skipIfNoCredentials = process.env.INSEE_API_KEY ? it : it.skip;

  skipIfNoCredentials('should search real enterprises', async () => {
    const adapter = new INSEEAdapter(realConfig);
    const results = await adapter.search('Airbus');
    
    expect(results).toHaveLength(greaterThan(0));
    expect(results[0]).toMatchObject({
      siren: expect.stringMatching(/^\d{9}$/),
      name: expect.any(String)
    });
  });
});
```

### Test Coverage

- Aim for >80% code coverage
- Focus on critical paths
- Test error scenarios
- Mock external dependencies

```bash
# Run tests with coverage
npm run test:coverage

# View coverage report
open coverage/lcov-report/index.html
```

## Code Style Guidelines

### TypeScript Style

- Use TypeScript strict mode
- Prefer interfaces over types for objects
- Use enums for constants
- Explicit return types for public methods

```typescript
// Good
export interface EnterpriseData {
  siren: string;
  name: string;
  address?: Address;
}

export async function searchEnterprises(
  query: string,
  options: SearchOptions = {}
): Promise<EnterpriseData[]> {
  // Implementation
}

// Avoid
export type EnterpriseData = {
  siren: string;
  name: string;
  address?: any;
};

export async function searchEnterprises(query, options = {}) {
  // Implementation
}
```

### Naming Conventions

- **Files**: kebab-case (`rate-limiter.ts`)
- **Classes**: PascalCase (`RateLimiter`)
- **Interfaces**: PascalCase with 'I' prefix optional (`IAdapter` or `Adapter`)
- **Functions**: camelCase (`searchEnterprises`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_RETRIES`)

### Error Handling

```typescript
// Create specific error classes
export class APIError extends Error {
  constructor(
    public code: APIErrorCode,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = 'APIError';
  }
}

// Use try-catch with proper error handling
try {
  const result = await riskyOperation();
  return result;
} catch (error) {
  logger.error('Operation failed', { error, context });
  
  if (error instanceof APIError) {
    throw error;
  }
  
  throw new APIError(
    APIErrorCode.UNKNOWN_ERROR,
    'An unexpected error occurred',
    error
  );
}
```

### Async/Await

Always use async/await instead of promises:

```typescript
// Good
async function getData(): Promise<Data> {
  const result = await fetchData();
  return transformData(result);
}

// Avoid
function getData(): Promise<Data> {
  return fetchData()
    .then(result => transformData(result));
}
```

## Documentation Standards

### Code Comments

```typescript
/**
 * Searches for enterprises matching the given query.
 * 
 * @param query - The search query (name or SIREN/SIRET)
 * @param options - Search options
 * @returns Array of matching enterprises
 * @throws {APIError} If the search fails
 * 
 * @example
 * ```typescript
 * const results = await adapter.search('Airbus', { maxResults: 10 });
 * ```
 */
export async function searchEnterprises(
  query: string,
  options: SearchOptions = {}
): Promise<SearchResult[]> {
  // Implementation
}
```

### README Updates

When adding features, update:
- Feature list
- Configuration section
- Usage examples
- API documentation

### Changelog

Update CHANGELOG.md following [Keep a Changelog](https://keepachangelog.com/):

```markdown
## [Unreleased]

### Added
- Support for new API endpoint

### Fixed
- Rate limiting issue with concurrent requests

### Changed
- Improved error messages
```

## Submitting Changes

### Pull Request Process

1. **Create PR**
   - Use descriptive title
   - Reference related issues
   - Fill out PR template

2. **PR Description**
   ```markdown
   ## Description
   Brief description of changes

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update

   ## Testing
   - [ ] Unit tests pass
   - [ ] Integration tests pass
   - [ ] Manual testing completed

   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] Tests added/updated
   ```

3. **Review Process**
   - Automated checks must pass
   - At least one maintainer review
   - Address feedback promptly
   - Keep PR updated with main

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

Examples:
```
feat(adapters): add support for new INSEE endpoint

- Implement search by activity code
- Add caching for activity searches
- Update tests and documentation

Closes #123
```

## Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Steps

1. **Prepare Release**
   ```bash
   # Update version
   npm version minor

   # Update CHANGELOG.md
   # Move Unreleased items to new version
   ```

2. **Create Release PR**
   - Title: `Release v1.2.0`
   - Include changelog in description
   - Get maintainer approval

3. **Tag and Publish**
   ```bash
   # After PR merge
   git tag v1.2.0
   git push origin v1.2.0

   # Publish to npm (maintainers only)
   npm publish
   ```

## Getting Help

- 💬 **Discord**: Join our [Discord server](https://discord.gg/example)
- 📧 **Email**: dev@example.com
- 🐛 **Issues**: [GitHub Issues](https://github.com/yourusername/mcp-firms/issues)
- 📖 **Wiki**: [Project Wiki](https://github.com/yourusername/mcp-firms/wiki)

## Recognition

Contributors are recognized in:
- [CONTRIBUTORS.md](../CONTRIBUTORS.md)
- Release notes
- Project README

Thank you for contributing to MCP Firms! 🎉