# apps/web/AGENTS.md

## Purpose
Build the CreatorOS dashboard UI.

## Responsibilities
- onboarding and brand profile forms
- project list/detail pages
- idea/script approvals
- asset previews
- rough cut/final approval flows
- publishing calendar and metadata editor
- analytics dashboards

## UI Rules
- use TypeScript everywhere
- use Tailwind and shadcn/ui
- keep components small and reusable
- prefer server-safe patterns for data loading
- no hidden side effects in UI actions

## Verification
- `pnpm --filter web lint`
- `pnpm --filter web typecheck`
