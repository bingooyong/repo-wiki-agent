# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do NOT** create a public GitHub issue for security vulnerabilities
2. Email the maintainers directly at [security@example.com] with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (if applicable)

### What to Expect

- **Acknowledgment**: Within 48 hours, you will receive acknowledgment of your report
- **Initial Assessment**: We will assess the severity and impact
- **Fix Development**: For valid issues, we will develop a fix
- **Disclosure**: We will coordinate disclosure with you on a timeline

### Scope

Security boundaries:
- `repo-wiki` CLI processes user-provided repository paths
- LLM API calls with user-provided API keys
- File system access to generated wiki output directories

### Security Best Practices

When using repo-wiki:
- Do not store API keys in configuration files committed to version control
- Use environment variables for sensitive credentials
- Run in isolated environments when processing untrusted repositories

## Security Updates

Security updates will be released as patch versions (e.g., 0.1.1) and announced through GitHub Releases.