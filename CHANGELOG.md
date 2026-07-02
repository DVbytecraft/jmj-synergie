# Changelog

## Unreleased

- Finished the single-tenant conversion: removed the unmounted cross-org
  `/admin` router (create/list/delete organizations, cross-org user list) —
  it relied on a `super_admin` role that `normalize_single_tenant_user` now
  collapses into `admin` on every request, so it was already unreachable.
  Dropped the same dead `super_admin` branches from `payments`/`documents`
  endpoints and the frontend role type/labels.
- Finished the JMJ Synergie rebrand: remaining "Biloz" defaults, container/DB
  names, PWA manifest/icons, emails, and monitoring dashboards updated; app
  now ships a generated logo instead of a missing icon reference.
- Removed the OHADA sales-journal export module (backend endpoint, frontend
  page, nav entry) — no longer part of the product.
- Fixed a duplicated PDF preview render on the quote detail page and a
  preview button missing its loading/disabled state on the documents page.
- Sidebar and public order-portal pages now read the organization name/logo
  dynamically instead of a hardcoded brand string.
- Project separated from Biloz SaaS codebase; rebranded as JMJ Synergie.
- Removed unused AI OCR SDK references (google-generativeai, anthropic) from
  render.yaml; OCR is handled locally via Tesseract/OpenCV.
- Added repository governance files: LICENSE, SECURITY.md, CONTRIBUTING.md.
