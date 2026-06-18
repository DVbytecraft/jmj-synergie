# TODO - Hydration + DevTools hardening

- [x] Inspect React/Next code paths causing hydration mismatch.
- [x] Create deterministic date formatting utility (`formatDateFr`, UTC-based) to avoid SSR/client locale+timezone mismatches.
- [x] Replace `toLocaleDateString("fr-FR")` in `src/app/(dashboard)/dashboard/page.tsx` with deterministic `formatDateFr`.
- [ ] Replace remaining `toLocaleDateString("fr-FR")` occurrences under `src/app/(dashboard)` with `formatDateFr`.
- [ ] Re-run Next dev build and verify:
  - hydration mismatch is gone/reduced
  - TanStack Query Devtools chunk no longer fails to load
  - runtime error `resolveQueryBoolean` is gone
- [ ] If Devtools still fails, disable Devtools entirely in production/devtools and validate bundle integrity.

