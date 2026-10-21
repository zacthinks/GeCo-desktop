# Security policy

GeCo Desktop is pre-release software. No production-supported version or security maintenance window has been announced.

## Reporting

If GitHub's **Report a vulnerability** option is available under the repository's Security tab, please use it to report issues privately. Otherwise, open a minimal issue asking for a private reporting channel **without including an exploit, secret, personal data or research files**.

## Security assumptions

GeCo Desktop opens local TeAL projects and launches GeCo on the local machine. Its GeCo browser server must bind to loopback and not enable development debugging by default. Python environments and future executable plugins are **not security sandboxes**; users should install only trusted packages and models.

Never attach private corpora, coding judgments, authentication tokens, signing keys, or local environment details to public bug reports. Please provide a synthetic reproduction when possible.
