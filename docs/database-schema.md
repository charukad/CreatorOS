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
- project_id
- title
- angle
- topic
- rationale
- score
- status
- created_at

### scripts
- id
- project_id
- version
- hook
- full_script
- estimated_duration_seconds
- status
- created_at

### scenes
- id
- script_id
- order_index
- narration_text
- duration_seconds
- overlay_text
- image_prompt
- video_prompt
- notes

### generation_attempts
- id
- project_id
- scene_id nullable
- provider_type
- provider_name
- input_payload_json
- status
- started_at
- finished_at
- error_message

### assets
- id
- project_id
- scene_id nullable
- generation_attempt_id nullable
- asset_type
- file_path
- mime_type
- duration_seconds nullable
- width nullable
- height nullable
- checksum
- status
- created_at

### approvals
- id
- project_id
- target_type
- target_id
- stage
- decision
- feedback
- approved_by
- created_at

### publish_jobs
- id
- project_id
- platform
- title
- description
- hashtags_json
- scheduled_for
- status
- external_post_id nullable
- created_at

### analytics_snapshots
- id
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
- insight_type
- summary
- evidence_json
- confidence_score
- created_at

### background_jobs
- id
- job_type
- payload_json
- status
- attempts
- started_at
- finished_at
- error_message

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

### asset.asset_type
- script_doc
- narration_audio
- scene_image
- scene_video
- rough_cut
- final_video
- subtitle_file
- thumbnail

### approval.stage
- idea
- script
- assets
- final_video
- publish
