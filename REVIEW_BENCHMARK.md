# Code Review & Benchmark Report

Date: 2026-04-08 (UTC)

## Scope
- Static checks (`eslint`, `tsc --noEmit`)
- Production build benchmark (`npm run build`, 3 runs)

## Code Review Findings

### 1) Lint status: **failing**
`npm run lint` reports **38 problems** (**26 errors**, **12 warnings**).

#### Highest-priority lint errors to address
- `@typescript-eslint/no-explicit-any` appears across multiple files and is the largest source of failures.
- `@typescript-eslint/no-empty-object-type` failures in shared UI components (`command.tsx`, `textarea.tsx`).
- `@typescript-eslint/no-require-imports` in `tailwind.config.ts`.
- `no-useless-escape` in `HandParticleVisualizer.tsx`.

#### Warnings worth triaging
- `react-hooks/exhaustive-deps` missing dependencies in effects.
- `react-refresh/only-export-components` in several UI modules.

### 2) Type-check status: **passing**
`npx tsc --noEmit` completed successfully.

## Benchmark Results

### Build command
- `npm run build` (3 consecutive runs)

### Timing summary
- Run 1: **21.23s**
- Run 2: **22.01s**
- Run 3: **21.14s**
- Average: **21.46s**

### Bundle output (stable across runs)
- `dist/assets/index-*.js`: **~1,117.39 kB** (gzip **~315.39 kB**)
- Vite warning: chunk(s) exceed 500 kB minified threshold.

## Recommendations

1. **Unblock CI first** by reducing `no-explicit-any` violations in core components/pages.
2. Introduce **targeted code-splitting** (`dynamic import()`, route-level splits, or Rollup `manualChunks`) to reduce initial JS size.
3. Update local Browserslist DB (`npx update-browserslist-db@latest`) to remove stale metadata warning.
4. Audit effect dependencies and ensure intentional omissions are documented or refactored.

