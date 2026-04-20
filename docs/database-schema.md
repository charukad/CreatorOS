# Database Schema

## Main Tables
### users
- id (uuid, pk)
- email
- name
- created_at

Note:
- v1 local development may bootstrap a single default user record from environment configuration until a fuller auth/session layer is added

### brand_profiles
- id
- user_id
- channel_name
- niche
- target_audience
- tone
- hook_style
- cta_style
- visual_style
- posting_preferences_json
- created_at
- updated_at

Note:
- `posting_preferences_json.platforms` stores preferred platform keys for generation defaults
- `posting_preferences_json.default_platform` stores the profile-level default platform when supplied
- `posting_preferences_json.output_defaults` stores reusable output defaults such as aspect ratio, duration, and caption style

### projects
- id
- user_id
- brand_profile_id
- title
- target_platform
- status
- objective
- notes
- created_at
- updated_at

### content_ideas
- id
- user_id
- project_id
- suggested_title
- hook
- angle
- rationale
- score
- source_feedback_notes nullable
- status
- feedback_notes
- created_at
- updated_at

### scripts
- id
- user_id
- project_id
- content_idea_id
- version_number
- hook
- body
- cta
- full_script
- caption
- title_options
- hashtags
- estimated_duration_seconds
- status
- source_feedback_notes
- created_at
- updated_at

### scenes
- id
- script_id
- scene_order
- title
- narration_text
- overlay_text
- image_prompt
- video_prompt
- estimated_duration_seconds
- notes
- created_at
- updated_at

### generation_attempts
- id
- user_id
- project_id
- script_id
- background_job_id
- scene_id nullable
- provider_name
- input_payload_json
- status
- created_at
- updated_at
- started_at
- finished_at
- error_message

### assets
- id
- user_id
- project_id
- script_id
- scene_id nullable
- generation_attempt_id nullable
- asset_type
- provider_name nullable
- file_path
- mime_type
- duration_seconds nullable
- width nullable
- height nullable
- checksum
- status
- created_at
- updated_at

Note:
- browser-generated asset paths include the generation attempt id segment so regenerated files do not overwrite older artifacts
- checksum is populated when the worker materializes a downloaded file into canonical project storage

### approvals
- id
- user_id
- project_id
- target_type
- target_id
- stage
- decision
- feedback_notes
- created_at

### publish_jobs
- id
- user_id
- project_id
- script_id
- final_asset_id
- platform
- title
- description
- hashtags_json
- scheduled_for
- status
- idempotency_key nullable
- external_post_id nullable
- manual_publish_notes nullable
- error_message nullable
- metadata_json
- created_at
- updated_at

### analytics_snapshots
- id
- user_id
- project_id
- publish_job_id
- views
- likes
- comments
- shares
- saves nullable
- watch_time_seconds nullable
- ctr nullable
- avg_view_duration nullable
- retention_json nullable
- fetched_at

### insights
- id
- user_id
- project_id
- publish_job_id
- analytics_snapshot_id
- insight_type
- summary
- evidence_json
- confidence_score
- created_at

### background_jobs
- id
- user_id
- project_id
- script_id nullable for project-level jobs before a script exists
- job_type
- provider_name nullable
- payload_json
- status
- attempts
- progress_percent
- created_at
- updated_at
- started_at
- finished_at
- error_message

### project_events
- id
- user_id
- project_id
- event_type
- title
- description nullable
- level
- metadata_json
- created_at
- updated_at

Note:
- project events record project creation, settings updates, guarded status transitions, manual overrides, archive decisions, publish milestones, and demo seeding
- project events are operator-facing audit records and are included in project activity and export bundles

### job_logs
- id
- user_id
- project_id
- script_id nullable for project-level jobs before a script exists
- background_job_id
- generation_attempt_id nullable
- level
- event_type
- message
- metadata_json
- created_at
- updated_at

Note:
- job logs persist operator-visible lifecycle events such as queue, claim, progress, attempt start/completion, debug artifact capture, failure, cancellation, retry, and manual intervention required
- download mismatch and duplicate checksum events are logged as `downloads_quarantined` and `duplicate_asset_detected`
- every log remains traceable to the owning project, script, and background job, with optional generation-attempt linkage

## Important Enums
### project.status
- draft
- idea_pending_approval
- script_pending_approval
- asset_generation
- asset_pending_approval
- rough_cut_ready
- final_pending_approval
- ready_to_publish
- scheduled
- published
- failed
- archived

### content_ideas.status
- proposed
- approved
- rejected

### scripts.status
- draft
- approved
- rejected
- superseded

### asset.asset_type
- script_doc
- narration_audio
- scene_image
- scene_video
- rough_cut
- final_video
- subtitle_file
- thumbnail

### asset.status
- planned
- generating
- ready
- failed
- rejected

### approval.stage
- idea
- script
- assets
- final_video
- publish

### approval.decision
- approved
- rejected

### approval.target_type
- content_idea
- script
- asset
- publish_job

### background_jobs.job_type
- generate_ideas
- generate_script
- generate_audio_browser
- generate_visuals_browser
- compose_rough_cut

### background_jobs.state
- queued
- running
- waiting_external
- completed
- failed
- cancelled

### publish_jobs.status
- pending_approval
- approved
- scheduled
- published
- failed
- cancelled

### provider_name
- elevenlabs_web
- flow_web
- local_media
