# Build Plan

## Milestone 1 — Foundation
- initialize monorepo
- create backend/frontend/worker skeletons
- configure PostgreSQL, Redis, local storage
- define shared enums and schemas
- set up linting, formatting, test runners

## Milestone 2 — Core Domain
- brand profile models
- content project model
- project status/state machine
- idea, script, scene, asset, approval, publish job models
- CRUD endpoints and UI scaffolding

## Milestone 3 — Idea + Script Pipeline
- generate ideas from brand profile
- approve/reject ideas
- generate script and scene breakdown
- persist prompt packs and variants
- approve/reject/regenerate script

## Milestone 4 — Browser Automation: ElevenLabs
- session profile handling
- navigation + selector abstraction
- text input, voice config, generation trigger
- download detection and asset registration
- retry/resume + error capture

## Milestone 5 — Browser Automation: Flow
- session handling
- prompt submission workflow
- clip generation monitoring
- download handling
- map clips to scenes and attempts

## Milestone 6 — Download Manager
- file watcher for download directory
- hash/rename/store files
- attach to project + generation attempt
- mark generation task complete

## Milestone 7 — Media Composer
- consume scene order, durations, audio, overlays
- generate subtitles/captions
- build rough cut timeline
- export preview and final short-form assets

## Milestone 8 — Approval Center
- idea/script/asset/final/publish approval screens
- revision notes and regenerate actions
- immutable approval history

## Milestone 9 — Publishing Center
- metadata editor
- scheduling calendar
- upload workflows and safe state transitions
- manual publish fallback

## Milestone 10 — Analytics + Learning
- analytics snapshot model
- performance summaries
- pattern detection by hook, duration, posting time, voice, content type
- recommendation engine

## Recommended Order of Execution
1. schema contracts
2. DB models/migrations
3. API routes
4. web UI for core project lifecycle
5. background jobs/queue integration
6. browser workers
7. media worker
8. publish + analytics

## Definition of MVP
A single user can:
- set up a brand profile
- create a project
- approve an idea
- approve a script
- generate/download narration and scene clips through browser automation
- assemble a rough cut automatically
- approve final export
- prepare metadata and publish manually if needed
