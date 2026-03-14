# Contributing to Vaultrix

Thank you for your interest in contributing to Vaultrix! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/vaultrix.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate the environment: `source venv/bin/activate` (Unix) or `venv\Scripts\activate` (Windows)
5. Install dependencies: `pip install -r requirements.txt`
6. Install development dependencies: `pip install -e ".[dev]"`

## Development Workflow

1. Create a new branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run tests: `pytest`
4. Run linters: `black vaultrix && ruff check vaultrix`
5. Commit your changes: `git commit -m "Description of changes"`
6. Push to your fork: `git push origin feature/your-feature-name`
7. Open a Pull Request

## Code Style

- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Write docstrings for all public functions and classes
- Keep line length to 100 characters
- Use Black for code formatting
- Use Ruff for linting

## Testing

- Write tests for all new features
- Maintain or improve code coverage
- Run the full test suite before submitting PRs
- Include both unit tests and integration tests where appropriate

## Security Contributions

Security is paramount in Vaultrix. When contributing security-related changes:

1. **Do NOT** open public issues for security vulnerabilities
2. Email security concerns to: security@vaultrix.dev
3. Include detailed reproduction steps
4. Allow time for the maintainers to address the issue before public disclosure

## Documentation

- Update documentation for any user-facing changes
- Add docstrings for all new functions and classes
- Update the README if adding major features
- Include examples where appropriate

## Pull Request Process

1. Ensure your PR description clearly explains the changes
2. Link any related issues
3. Update the CHANGELOG.md with your changes
4. Ensure all CI checks pass
5. Request review from maintainers
6. Address review feedback promptly

## Areas for Contribution

We welcome contributions in the following areas:

### Phase 1 (Current)
- Sandbox isolation improvements
- Permission system enhancements
- Platform-specific adaptations (Windows, Linux, macOS)
- Performance optimizations

### Phase 2
- VaultHub registry implementation
- Automated security scanning tools
- Manual review workflow UI
- Skill signing and verification

### Phase 3
- Human-in-the-Loop UI/UX
- Action classification engine
- Notification systems
- Approval workflow logic

### Phase 4
- Encryption implementations
- Key management systems
- Secure memory handling
- Data security audits

### General
- Documentation improvements
- Bug fixes
- Test coverage improvements
- Example skills and use cases

## Questions?

If you have questions about contributing, please:
- Open a discussion on GitHub
- Join our Discord community
- Email the team at team@vaultrix.dev

Thank you for contributing to Vaultrix! 🔐
