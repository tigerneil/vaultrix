# Changelog

All notable changes to Vaultrix will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 1 (Weeks 1-4) - In Progress

#### Added
- Core project structure and build configuration
- Docker-based sandbox manager with resource limits
- Granular permission system with risk classification
- Vaultrix agent with permission-aware execution
- CLI interface with interactive mode
- Comprehensive test suite for permissions and sandbox
- Documentation (README, Architecture, QuickStart, Contributing)
- Example scripts demonstrating usage patterns
- Initialization scripts for sandbox setup

#### Security
- Sandboxed execution environment with container isolation
- Permission matrix implementation (filesystem, network, process, system)
- Risk-based action classification (Low, Medium, High, Critical)
- Access logging and audit trail
- Capability dropping and security hardening

### Phase 2 (Weeks 5-8) - Planned

#### Planned
- VaultHub registry backend infrastructure
- Automated skill scanning pipeline
- Manual review workflow and dashboard
- Cryptographic signing for skills
- Skill dependency management

### Phase 3 (Weeks 9-12) - Planned

#### Planned
- Human-in-the-Loop approval UI
- Action classification engine
- Timeout and fallback logic
- Notification system (CLI, web, integrations)
- Multi-factor approval for critical actions

### Phase 4 (Weeks 13-16) - Planned

#### Planned
- Local key management system
- Data-at-rest encryption (AES-256)
- Secure memory handling
- Encrypted communication channels
- Zero-knowledge architecture

### Phase 5 (Weeks 17-20) - Planned

#### Planned
- Penetration testing results
- Closed beta program
- Third-party security audit
- Performance optimizations
- Bug fixes from beta testing

### Phase 6 (Weeks 21-24) - Planned

#### Planned
- Official 1.0 release
- Complete documentation
- Community onboarding materials
- VaultHub bounty program launch

## [0.1.0] - 2026-03-07

### Added
- Initial alpha release
- Basic sandbox and permission system
- CLI interface
- Core agent implementation

[Unreleased]: https://github.com/yourusername/vaultrix/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/vaultrix/releases/tag/v0.1.0
