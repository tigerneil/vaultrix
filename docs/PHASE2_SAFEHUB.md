# Phase 2: VaultHub - Audited Skill Registry

## Overview

VaultHub is the trusted registry for Vaultrix skills - community-contributed capabilities that extend agent functionality while maintaining security guarantees.

**Timeline**: Weeks 5-8
**Status**: Planning

## Problem Statement

Autonomous agents need to execute diverse tasks, but allowing arbitrary code execution creates severe security risks:

- **Unvetted Code**: Community skills may contain malicious code
- **Supply Chain Attacks**: Dependencies can be compromised
- **Permission Escalation**: Skills might abuse granted permissions
- **Data Exfiltration**: Skills could leak sensitive data

## Solution Architecture

VaultHub provides a multi-layered vetting process:

```
Skill Submission
    ↓
Automated Scanning ──→ REJECT (if critical issues found)
    ↓ PASS
Manual Review ──→ REVISE (if concerns found)
    ↓ APPROVED
Cryptographic Signing
    ↓
Registry Publication
    ↓
Agent Installation (verified)
```

## Components

### 1. Skill Definition Format

Skills are defined using a standardized manifest:

```yaml
# skill.yaml
name: "file-organizer"
version: "1.0.0"
description: "Organize files by type and date"
author: "username"
license: "MIT"

permissions:
  required:
    - resource: filesystem
      level: write
      paths: ["/workspace"]
    - resource: system
      level: read

risk_level: medium

dependencies:
  - python: ">=3.10"
  - packages:
      - pathlib: "^1.0"

entry_point: "organize.py"
tests: "tests/"

metadata:
  tags: ["filesystem", "organization", "productivity"]
  categories: ["utilities"]
  documentation: "README.md"
```

### 2. Automated Scanner

Static analysis pipeline that checks:

#### Security Checks
- No network access without declaration
- No subprocess spawning outside sandbox
- No file access outside declared paths
- No use of dangerous functions (`eval`, `exec`, `__import__`)
- No obfuscated code patterns

#### Code Quality Checks
- Syntax validation
- Import verification
- Type checking (if type hints present)
- Linting (PEP 8 compliance)
- Dependency security (CVE scanning)

#### License Compliance
- Valid SPDX license identifier
- No copyleft conflicts
- Attribution requirements met

**Implementation**: `vaultrix/safehub/scanner/`

```python
class SkillScanner:
    """Automated security and quality scanner for skills."""

    def scan(self, skill_path: Path) -> ScanResult:
        """
        Scan a skill for security issues.

        Returns:
            ScanResult with findings categorized by severity
        """
        findings = []

        # Parse skill manifest
        manifest = self._load_manifest(skill_path)

        # Security scans
        findings.extend(self._scan_dangerous_imports(skill_path))
        findings.extend(self._scan_subprocess_usage(skill_path))
        findings.extend(self._scan_network_access(skill_path))
        findings.extend(self._scan_file_operations(skill_path, manifest))

        # Dependency scans
        findings.extend(self._scan_dependencies(manifest))

        # Code quality scans
        findings.extend(self._scan_code_quality(skill_path))

        return ScanResult(
            skill_name=manifest.name,
            findings=findings,
            passed=self._evaluate_findings(findings),
        )
```

### 3. Manual Review Dashboard

Web-based interface for human reviewers to:

- View automated scan results
- Inspect skill source code
- Test skills in isolated environment
- Request revisions from authors
- Approve or reject submissions
- Add reviewer notes

**Tech Stack**:
- Frontend: React + TailwindCSS
- Backend: FastAPI
- Database: PostgreSQL

**Workflow States**:
```
submitted → scanning → pending_review → approved/rejected/revision_requested
```

### 4. Registry Backend

**API Endpoints**:

```python
# Submission
POST /api/v1/skills/submit
POST /api/v1/skills/{skill_id}/revise

# Discovery
GET /api/v1/skills/search?q={query}&category={cat}
GET /api/v1/skills/{skill_id}
GET /api/v1/skills/popular
GET /api/v1/skills/recent

# Installation
GET /api/v1/skills/{skill_id}/download
GET /api/v1/skills/{skill_id}/signature

# Reviews & Ratings
POST /api/v1/skills/{skill_id}/reviews
GET /api/v1/skills/{skill_id}/reviews
```

**Database Schema**:

```sql
CREATE TABLE skills (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    version VARCHAR(50) NOT NULL,
    description TEXT,
    author_id UUID REFERENCES users(id),
    manifest JSONB NOT NULL,
    source_hash VARCHAR(64) NOT NULL,
    signature TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    approved_at TIMESTAMP,
    UNIQUE(name, version)
);

CREATE TABLE scan_results (
    id UUID PRIMARY KEY,
    skill_id UUID REFERENCES skills(id),
    scanner_version VARCHAR(50),
    findings JSONB,
    passed BOOLEAN,
    scanned_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE reviews (
    id UUID PRIMARY KEY,
    skill_id UUID REFERENCES skills(id),
    reviewer_id UUID REFERENCES users(id),
    status VARCHAR(50),
    notes TEXT,
    reviewed_at TIMESTAMP DEFAULT NOW()
);
```

### 5. Cryptographic Signing

Each approved skill is signed using Ed25519:

```python
from cryptography.hazmat.primitives.asymmetric import ed25519

class SkillSigner:
    """Sign and verify skills cryptographically."""

    def __init__(self, private_key: ed25519.Ed25519PrivateKey):
        self.private_key = private_key
        self.public_key = private_key.public_key()

    def sign_skill(self, skill_path: Path) -> bytes:
        """
        Sign a skill package.

        Returns:
            Signature bytes
        """
        # Create tarball of skill
        tarball = self._create_tarball(skill_path)

        # Compute hash
        skill_hash = hashlib.sha256(tarball).digest()

        # Sign hash
        signature = self.private_key.sign(skill_hash)

        return signature

    def verify_skill(self, skill_path: Path, signature: bytes) -> bool:
        """Verify skill signature."""
        tarball = self._create_tarball(skill_path)
        skill_hash = hashlib.sha256(tarball).digest()

        try:
            self.public_key.verify(signature, skill_hash)
            return True
        except Exception:
            return False
```

### 6. Client Integration

Agents can discover and install skills:

```python
# In vaultrix CLI
vaultrix skill search "file organization"
vaultrix skill info file-organizer
vaultrix skill install file-organizer
vaultrix skill list
vaultrix skill remove file-organizer
```

**Verification Flow**:
```
1. Download skill package + signature
2. Verify signature against VaultHub public key
3. Check hash matches manifest
4. Verify permissions are acceptable
5. Install to ~/.vaultrix/skills/
6. Make available to agent
```

## Security Considerations

### Supply Chain Security

1. **Dependency Pinning**: All dependencies must specify exact versions
2. **Dependency Scanning**: Automated CVE checking for all dependencies
3. **Reproducible Builds**: Deterministic packaging for verification
4. **Signature Chain**: Skills sign their dependencies

### Isolation

1. **Skill Sandbox**: Skills run in separate container from agent core
2. **Permission Boundaries**: Skills cannot exceed declared permissions
3. **Resource Limits**: CPU/memory quotas per skill
4. **Network Isolation**: Skills with network access are further restricted

### Audit Trail

1. **Immutable Logs**: All skill installations logged
2. **Version Tracking**: Agent tracks which skill versions are used
3. **Execution Logs**: Skill actions are logged separately
4. **Incident Response**: Ability to revoke compromised skills

## Implementation Roadmap

### Week 5: Foundation
- [ ] Database schema and migrations
- [ ] Basic API endpoints (submit, search, download)
- [ ] Skill manifest parser
- [ ] Automated scanner framework

### Week 6: Scanning & Review
- [ ] Security scan implementations
- [ ] Dependency vulnerability scanner
- [ ] Review dashboard frontend
- [ ] Approval workflow backend

### Week 7: Signing & Distribution
- [ ] Cryptographic signing system
- [ ] Public key infrastructure
- [ ] Client-side verification
- [ ] CLI integration (`vaultrix skill` commands)

### Week 8: Testing & Documentation
- [ ] End-to-end testing
- [ ] Security audit of VaultHub itself
- [ ] Author documentation
- [ ] User documentation
- [ ] Seed skills (5-10 high-quality examples)

## Example Skills

To seed the registry, we'll create reference implementations:

1. **File Organizer**: Sort files by type, date, size
2. **Data Analyzer**: Basic CSV/JSON analysis
3. **Web Scraper**: Safe web scraping with rate limits
4. **Code Formatter**: Format Python/JS/etc code
5. **Image Processor**: Resize, compress images
6. **PDF Generator**: Create PDFs from markdown
7. **Git Helper**: Common git operations
8. **API Tester**: Test REST APIs
9. **Log Analyzer**: Parse and analyze logs
10. **Backup Manager**: Automated backup routines

## Metrics & Monitoring

Track VaultHub health:

- **Submission Rate**: Skills submitted per week
- **Approval Rate**: % of skills approved
- **Scan Effectiveness**: Issues caught by automated scanning
- **Review Time**: Average time from submission to decision
- **Download Stats**: Most popular skills
- **Security Incidents**: Compromised skills detected

## Open Questions

1. **Monetization**: Should skill authors be able to charge? If so, how?
2. **Reputation System**: How to build author reputation?
3. **Appeals Process**: What if an author disagrees with rejection?
4. **Version Conflicts**: How to handle breaking changes?
5. **Skill Composition**: Can skills depend on other skills?

## Success Criteria

Phase 2 is successful when:

- ✅ VaultHub can accept and process skill submissions
- ✅ Automated scanner catches ≥90% of obvious security issues
- ✅ Manual review workflow is functional and efficient
- ✅ Skills are cryptographically signed and verifiable
- ✅ Agents can discover, install, and execute skills safely
- ✅ At least 10 high-quality seed skills are available
- ✅ Documentation is complete for authors and users

## Next Steps

After Phase 2, Phase 3 (HITL) will add:
- Skill-level approval prompts
- User ratings and reviews
- Skill marketplace features
- Automated skill updates
