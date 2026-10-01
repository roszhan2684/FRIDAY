-- Migration 002 — Update routines with personalized apps and job sites

-- Coding Mode: Cursor + Terminal + Apple Music (not Spotify)
UPDATE routines SET
    steps = '[
        {"tool": "open_app", "args": {"name": "Cursor"}, "spoken_before": "Opening Cursor.", "delay_seconds": 0},
        {"tool": "open_app", "args": {"name": "Terminal"}, "spoken_before": "And your terminal.", "delay_seconds": 1},
        {"tool": "open_app", "args": {"name": "Music"}, "spoken_before": "Getting your music going.", "delay_seconds": 1}
    ]',
    updated_at = datetime('now')
WHERE LOWER(name) = 'coding mode';

-- Job Hunt Mode: open jobright.ai, glassdoor, linkedin, resume
UPDATE routines SET
    trigger_phrases = '["job hunt mode", "job hunting", "job search mode", "let s apply jobs", "lets apply jobs", "apply jobs", "apply for jobs", "job apply mode"]',
    steps = '[
        {"tool": "open_url", "args": {"url": "https://jobright.ai"}, "spoken_before": "Opening JobRight.", "delay_seconds": 0},
        {"tool": "open_url", "args": {"url": "https://www.glassdoor.com/Job/index.htm"}, "spoken_before": "Opening Glassdoor.", "delay_seconds": 1},
        {"tool": "open_url", "args": {"url": "https://www.linkedin.com/jobs"}, "spoken_before": "And LinkedIn Jobs.", "delay_seconds": 1},
        {"tool": "open_file", "args": {"query": "resume", "hint": "pdf"}, "spoken_before": "Pulling up your resume.", "delay_seconds": 1}
    ]',
    updated_at = datetime('now')
WHERE LOWER(name) = 'job hunt mode';
