from html import escape


def build_rough_cut_preview_html(manifest: dict[str, object]) -> str:
    scenes = manifest.get("scenes", [])
    if not isinstance(scenes, list):
        scenes = []

    scene_cards = "\n".join(_build_scene_card(scene) for scene in scenes)
    project_title = escape(str(manifest.get("project_title", "CreatorOS Project")))
    duration = escape(str(manifest.get("total_duration_seconds", "unknown")))
    generated_at = escape(str(manifest.get("generated_at", "unknown")))
    narration_asset = manifest.get("narration_asset", {})
    narration_path = ""
    if isinstance(narration_asset, dict):
        narration_path = escape(str(narration_asset.get("file_path", "Not available")))

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>CreatorOS Rough Cut Preview</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #07111f;
        --card: rgba(15, 23, 42, 0.82);
        --line: rgba(148, 163, 184, 0.2);
        --text: #e2e8f0;
        --muted: #94a3b8;
        --cyan: #67e8f9;
        --green: #86efac;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background:
          radial-gradient(circle at top left, rgba(103, 232, 249, 0.18), transparent 30rem),
          radial-gradient(circle at bottom right, rgba(134, 239, 172, 0.14), transparent 28rem),
          var(--bg);
        color: var(--text);
        font-family: "Trebuchet MS", "Gill Sans", Verdana, sans-serif;
      }}
      main {{
        width: min(980px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 48px 0;
      }}
      header, article {{
        border: 1px solid var(--line);
        background: var(--card);
        border-radius: 28px;
        padding: 24px;
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.22);
      }}
      h1, h2, p {{ margin: 0; }}
      h1 {{ font-size: clamp(2rem, 5vw, 4.5rem); line-height: 0.95; }}
      h2 {{ font-size: 1.25rem; }}
      .eyebrow {{
        color: var(--cyan);
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        margin-bottom: 16px;
      }}
      .meta {{
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin-top: 24px;
      }}
      .pill {{
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 14px;
        color: var(--muted);
      }}
      .pill strong {{ color: var(--text); display: block; margin-top: 6px; }}
      .timeline {{ display: grid; gap: 18px; margin-top: 24px; }}
      .scene-grid {{
        display: grid;
        gap: 18px;
        grid-template-columns: minmax(0, 0.34fr) minmax(0, 0.66fr);
      }}
      .time {{
        color: var(--green);
        font-size: 0.8rem;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
      }}
      .copy {{ color: var(--muted); line-height: 1.7; margin-top: 12px; }}
      code {{
        display: block;
        border: 1px solid var(--line);
        border-radius: 16px;
        color: var(--cyan);
        margin-top: 12px;
        overflow-wrap: anywhere;
        padding: 12px;
      }}
      @media (max-width: 720px) {{
        .scene-grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <p class="eyebrow">CreatorOS Rough Cut Preview</p>
        <h1>{project_title}</h1>
        <div class="meta">
          <div class="pill">Total duration<strong>{duration}s</strong></div>
          <div class="pill">Generated<strong>{generated_at}</strong></div>
          <div class="pill">Narration source<strong>{narration_path}</strong></div>
        </div>
      </header>
      <section class="timeline">
        {scene_cards}
      </section>
    </main>
  </body>
</html>
"""


def _build_scene_card(scene: object) -> str:
    if not isinstance(scene, dict):
        return ""

    scene_order = escape(str(scene.get("scene_order", "?")))
    title = escape(str(scene.get("title", "Untitled scene")))
    start_seconds = escape(str(scene.get("start_seconds", "?")))
    end_seconds = escape(str(scene.get("end_seconds", "?")))
    overlay_text = escape(str(scene.get("overlay_text", "")))
    narration_text = escape(str(scene.get("narration_text", "")))
    visual_asset_path = escape(str(scene.get("visual_asset_path", "Not available")))

    return f"""<article>
  <div class="scene-grid">
    <div>
      <p class="time">Scene {scene_order} | {start_seconds}s to {end_seconds}s</p>
      <h2>{title}</h2>
      <code>{visual_asset_path}</code>
    </div>
    <div>
      <p class="copy"><strong>Overlay:</strong> {overlay_text}</p>
      <p class="copy"><strong>Narration:</strong> {narration_text}</p>
    </div>
  </div>
</article>"""
