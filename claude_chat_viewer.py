#!/usr/bin/env python3
"""
Claude Code Chat Viewer
=======================
A tool to view Claude Code conversation history in a beautiful, readable format.

This tool parses the JSONL chat files stored by Claude Code CLI and renders
them as styled HTML pages or serves them via a live web server.

Author: https://github.com/your-username
License: MIT
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from html import escape
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import re

# =============================================================================
# CONFIGURATION - Modify these if your Claude Code installation differs
# =============================================================================

# Default Claude Code data directory (standard location)
CLAUDE_DIR = Path.home() / ".claude"

# Where to output generated HTML files
DEFAULT_OUTPUT_DIR = Path.home() / "claude-chat-history"

# Live server default port
DEFAULT_PORT = 8787

# =============================================================================
# HTML TEMPLATE
# =============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Code Chat - {title}</title>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-user: #0f3460;
            --bg-assistant: #1a1a2e;
            --text-primary: #e8e8e8;
            --text-secondary: #a0a0a0;
            --accent: #e94560;
            --accent-light: #ff6b6b;
            --border: #2a2a4a;
            --code-bg: #0d0d1a;
            --thinking-bg: #1e1e3f;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'SF Pro Text', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 0;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}

        header {{
            background: var(--bg-secondary);
            padding: 20px;
            border-bottom: 2px solid var(--accent);
            margin-bottom: 30px;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        header h1 {{
            font-size: 1.5rem;
            color: var(--accent-light);
            margin-bottom: 10px;
        }}

        .meta {{
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}

        .meta span {{
            margin-right: 20px;
        }}

        .message {{
            margin-bottom: 20px;
            border-radius: 12px;
            overflow: hidden;
        }}

        .message-header {{
            padding: 10px 15px;
            font-weight: 600;
            font-size: 0.85rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .message-content {{
            padding: 15px 20px;
            font-size: 0.95rem;
        }}

        .user {{
            background: var(--bg-user);
            border-left: 4px solid #4fc3f7;
        }}

        .user .message-header {{
            background: rgba(79, 195, 247, 0.1);
            color: #4fc3f7;
        }}

        .assistant {{
            background: var(--bg-assistant);
            border-left: 4px solid var(--accent);
        }}

        .assistant .message-header {{
            background: rgba(233, 69, 96, 0.1);
            color: var(--accent-light);
        }}

        .thinking {{
            background: var(--thinking-bg);
            border-left: 4px solid #9c27b0;
            margin: 10px 0;
            font-size: 0.9rem;
        }}

        .thinking .message-header {{
            background: rgba(156, 39, 176, 0.1);
            color: #ce93d8;
            cursor: pointer;
        }}

        .thinking .message-content {{
            display: none;
            color: var(--text-secondary);
            font-style: italic;
        }}

        .thinking.expanded .message-content {{
            display: block;
        }}

        .tool-call {{
            background: var(--code-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin: 10px 0;
            overflow: hidden;
        }}

        .tool-call-header {{
            background: rgba(76, 175, 80, 0.1);
            padding: 8px 12px;
            font-size: 0.8rem;
            color: #81c784;
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
        }}

        .tool-call-content {{
            padding: 10px 12px;
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 0.8rem;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-word;
        }}

        pre {{
            background: var(--code-bg);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 0.85rem;
            margin: 10px 0;
        }}

        code {{
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.85rem;
        }}

        .timestamp {{
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}

        .session-list {{
            list-style: none;
        }}

        .session-list li {{
            background: var(--bg-secondary);
            margin-bottom: 15px;
            padding: 18px 20px;
            border-radius: 8px;
            border-left: 4px solid var(--accent);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .session-list li:hover {{
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}

        .session-list a {{
            color: var(--accent-light);
            text-decoration: none;
            font-weight: 600;
            font-size: 1.1rem;
            display: block;
            margin-bottom: 10px;
        }}

        .session-list a:hover {{
            text-decoration: underline;
        }}

        .session-list .session-meta {{
            display: flex;
            gap: 16px;
            align-items: center;
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}

        .session-list .session-meta > span {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .session-list .session-time {{
            color: #81c784;
            font-weight: 500;
        }}

        .session-list .session-path {{
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 0.75rem;
        }}

        .session-list .preview {{
            margin-top: 10px;
            font-style: italic;
            color: #888;
            font-size: 0.85rem;
            line-height: 1.4;
        }}

        .tooltip {{
            position: relative;
            cursor: help;
        }}

        .tooltip:hover::after {{
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 0;
            background: var(--code-bg);
            color: var(--text-primary);
            padding: 6px 10px;
            border-radius: 4px;
            white-space: nowrap;
            font-size: 0.75rem;
            z-index: 1000;
            margin-bottom: 5px;
            border: 1px solid var(--border);
        }}

        .live-badge {{
            background: #e94560;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}

        .back-link {{
            color: #4fc3f7;
            text-decoration: none;
            display: inline-block;
            margin-bottom: 20px;
        }}

        .back-link:hover {{
            text-decoration: underline;
        }}

        .info-box {{
            margin-bottom: 20px;
            padding: 12px 16px;
            background: rgba(76, 175, 80, 0.1);
            border-radius: 8px;
            color: #81c784;
            border: 1px solid rgba(76, 175, 80, 0.3);
        }}

        .search-container {{
            margin-bottom: 20px;
            position: relative;
        }}

        .search-box {{
            width: 100%;
            padding: 12px 16px 12px 40px;
            background: var(--bg-secondary);
            border: 2px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 0.95rem;
            transition: border-color 0.3s;
        }}

        .search-box:focus {{
            outline: none;
            border-color: var(--accent);
        }}

        .search-box::placeholder {{
            color: var(--text-secondary);
        }}

        .search-icon {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
            font-size: 1.2rem;
        }}

        .search-stats {{
            margin-top: 10px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}

        .session-list li.hidden {{
            display: none;
        }}

        .text-content {{
            white-space: pre-wrap;
            word-break: break-word;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 10px;
            }}

            header {{
                padding: 15px;
            }}

            .meta span {{
                display: block;
                margin-bottom: 5px;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>{title}</h1>
            <div class="meta">
                {meta}
            </div>
        </div>
    </header>
    <div class="container">
        {content}
    </div>
    <script>
        // Toggle thinking blocks
        document.querySelectorAll('.thinking .message-header').forEach(header => {{
            header.addEventListener('click', () => {{
                header.parentElement.classList.toggle('expanded');
            }});
        }});

        // Search functionality
        const searchBox = document.getElementById('searchBox');
        const sessionList = document.getElementById('sessionList');
        const searchStats = document.getElementById('searchStats');
        const totalSessionsElement = document.getElementById('totalSessions');

        if (searchBox && sessionList) {{
            const allSessions = Array.from(sessionList.querySelectorAll('li'));
            const totalCount = allSessions.length;

            searchBox.addEventListener('input', (e) => {{
                const searchTerm = e.target.value.toLowerCase().trim();

                if (searchTerm === '') {{
                    // Show all sessions
                    allSessions.forEach(item => item.classList.remove('hidden'));
                    searchStats.textContent = '';
                    if (totalSessionsElement) {{
                        totalSessionsElement.textContent = `${{totalCount}} sessions found`;
                    }}
                    return;
                }}

                // Filter sessions
                let visibleCount = 0;
                allSessions.forEach(item => {{
                    const title = item.getAttribute('data-title') || '';
                    const project = item.getAttribute('data-project') || '';
                    const preview = item.getAttribute('data-preview') || '';

                    const matches = title.includes(searchTerm) ||
                                  project.includes(searchTerm) ||
                                  preview.includes(searchTerm);

                    if (matches) {{
                        item.classList.remove('hidden');
                        visibleCount++;
                    }} else {{
                        item.classList.add('hidden');
                    }}
                }});

                // Update search stats
                searchStats.textContent = `Showing ${{visibleCount}} of ${{totalCount}} sessions`;
                if (totalSessionsElement) {{
                    totalSessionsElement.textContent = `${{visibleCount}} of ${{totalCount}} sessions`;
                }}
            }});
        }}
    </script>
</body>
</html>
"""

# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def parse_timestamp(ts):
    """Parse timestamp from various formats."""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except ValueError:
            return None
    return None


def format_timestamp(ts):
    """Format timestamp for display."""
    dt = parse_timestamp(ts)
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return ""


def format_relative_time(timestamp):
    """Format timestamp as relative time (e.g., '2 hours ago')."""
    if isinstance(timestamp, (int, float)):
        dt = datetime.fromtimestamp(timestamp)
    else:
        dt = timestamp

    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days}d ago"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks}w ago"
    else:
        months = int(seconds / 2592000)
        if months < 12:
            return f"{months}mo ago"
        else:
            years = int(months / 12)
            return f"{years}y ago"


def truncate_path(path, max_parts=2):
    """Truncate path to show only the last few directories."""
    parts = path.strip('/').split('/')
    if len(parts) <= max_parts:
        return path
    return '.../' + '/'.join(parts[-max_parts:])


def extract_text_content(content):
    """Extract plain text from message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    texts.append(item.get('text', ''))
                elif item.get('type') == 'thinking':
                    texts.append(f"[THINKING]\n{item.get('thinking', '')}\n[/THINKING]")
                elif item.get('type') == 'tool_use':
                    tool_name = item.get('name', 'Unknown')
                    tool_input = json.dumps(item.get('input', {}), indent=2)
                    texts.append(f"[TOOL: {tool_name}]\n{tool_input}\n[/TOOL]")
            elif isinstance(item, str):
                texts.append(item)
        return '\n'.join(texts)
    return ""


def render_message_content(content):
    """Render message content as HTML."""
    html_parts = []

    if isinstance(content, str):
        text = escape(content)
        text = text.replace('\n', '<br>')
        html_parts.append(f'<div class="text-content">{text}</div>')
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                item_type = item.get('type', '')

                if item_type == 'text':
                    text = item.get('text', '')
                    text = escape(text)
                    # Code blocks
                    text = re.sub(
                        r'```(\w*)\n(.*?)```',
                        r'<pre><code class="\1">\2</code></pre>',
                        text,
                        flags=re.DOTALL
                    )
                    # Inline code
                    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
                    # Line breaks
                    text = text.replace('\n', '<br>')
                    html_parts.append(f'<div class="text-content">{text}</div>')

                elif item_type == 'thinking':
                    thinking = escape(item.get('thinking', ''))[:1000]
                    if len(item.get('thinking', '')) > 1000:
                        thinking += '... (truncated)'
                    html_parts.append(f'''
                        <div class="message thinking">
                            <div class="message-header">
                                <span>💭 Thinking (click to expand)</span>
                            </div>
                            <div class="message-content">{thinking}</div>
                        </div>
                    ''')

                elif item_type == 'tool_use':
                    tool_name = escape(item.get('name', 'Unknown'))
                    tool_input = item.get('input', {})

                    # Format tool input nicely based on tool type
                    if tool_name == 'Bash':
                        cmd = tool_input.get('command', '')
                        desc = tool_input.get('description', '')
                        display = f"$ {cmd}"
                        if desc:
                            display = f"# {desc}\n$ {cmd}"
                    elif tool_name == 'Read':
                        display = f"Reading: {tool_input.get('file_path', '')}"
                    elif tool_name == 'Write':
                        display = f"Writing to: {tool_input.get('file_path', '')}"
                    elif tool_name == 'Edit':
                        display = f"Editing: {tool_input.get('file_path', '')}"
                    elif tool_name in ('Grep', 'Glob'):
                        pattern = tool_input.get('pattern', '')
                        path = tool_input.get('path', '.')
                        display = f"Pattern: {pattern}\nPath: {path}"
                    elif tool_name == 'Task':
                        display = f"Agent: {tool_input.get('subagent_type', 'unknown')}\nTask: {tool_input.get('description', '')}"
                    else:
                        display = json.dumps(tool_input, indent=2)[:500]

                    html_parts.append(f'''
                        <div class="tool-call">
                            <div class="tool-call-header">🔧 {tool_name}</div>
                            <div class="tool-call-content">{escape(display)}</div>
                        </div>
                    ''')

                elif item_type == 'tool_result':
                    result = str(item.get('content', ''))[:1000]
                    if len(str(item.get('content', ''))) > 1000:
                        result += '... (truncated)'
                    html_parts.append(f'''
                        <div class="tool-call">
                            <div class="tool-call-header">📤 Tool Result</div>
                            <div class="tool-call-content">{escape(result)}</div>
                        </div>
                    ''')

    return '\n'.join(html_parts) if html_parts else '<div class="text-content">(empty message)</div>'


def parse_session(session_path):
    """Parse a session JSONL file and extract messages."""
    messages = []
    session_info = {}

    with open(session_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)

                # Handle summary entries
                if data.get('type') == 'summary':
                    session_info['summary'] = data.get('summary', '')
                    continue

                # Skip non-message entries
                if data.get('type') in ('file-history-snapshot',):
                    continue

                msg = data.get('message', {})
                if not msg:
                    continue

                role = msg.get('role', data.get('type', ''))
                content = msg.get('content', '')
                timestamp = data.get('timestamp', '')

                if role in ('user', 'assistant'):
                    messages.append({
                        'role': role,
                        'content': content,
                        'timestamp': timestamp,
                        'uuid': data.get('uuid', ''),
                    })

                    # Capture session metadata from first message
                    if not session_info.get('sessionId'):
                        session_info['sessionId'] = data.get('sessionId', '')
                        session_info['cwd'] = data.get('cwd', '')
                        session_info['version'] = data.get('version', '')

            except json.JSONDecodeError:
                continue

    return messages, session_info


def get_all_sessions(claude_dir=None):
    """Get all available chat sessions."""
    if claude_dir is None:
        claude_dir = CLAUDE_DIR

    claude_dir = Path(claude_dir)
    projects_dir = claude_dir / "projects"
    sessions = []

    if not projects_dir.exists():
        return sessions

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        # Convert directory name back to path
        project_path = project_dir.name.replace('-', '/')

        for session_file in project_dir.glob('*.jsonl'):
            session_id = session_file.stem
            if session_id == 'sessions-index':
                continue

            try:
                stat = session_file.stat()
                messages, info = parse_session(session_file)

                if messages:
                    first_msg = messages[0].get('content', '')
                    if isinstance(first_msg, list):
                        first_msg = extract_text_content(first_msg)
                    preview = first_msg[:150] + '...' if len(first_msg) > 150 else first_msg

                    sessions.append({
                        'id': session_id,
                        'project': project_path,
                        'path': session_file,
                        'modified': stat.st_mtime,
                        'size': stat.st_size,
                        'message_count': len(messages),
                        'preview': preview,
                        'summary': info.get('summary', ''),
                    })
            except Exception:
                continue

    # Sort by modification time, newest first
    sessions.sort(key=lambda x: x['modified'], reverse=True)
    return sessions


# =============================================================================
# RENDERING FUNCTIONS
# =============================================================================

def render_session_html(messages, session_info, session_id, is_live=False):
    """Render a chat session as HTML."""
    content_parts = []

    # Add back link and live indicator for live mode
    if is_live:
        content_parts.append('''
            <a href="/" class="back-link">← Back to all sessions</a>
            <div class="info-box">
                <span class="live-badge">LIVE</span>
                Auto-refreshes every 5 seconds
            </div>
        ''')

    for i, msg in enumerate(messages):
        role = msg['role']
        content = render_message_content(msg['content'])
        timestamp = format_timestamp(msg['timestamp'])

        role_label = "👤 You" if role == 'user' else "🤖 Claude"

        content_parts.append(f'''
            <div class="message {role}" id="msg-{i}">
                <div class="message-header">
                    <span>{role_label}</span>
                    <span class="timestamp">{timestamp}</span>
                </div>
                <div class="message-content">
                    {content}
                </div>
            </div>
        ''')

    # Add auto-refresh script for live mode
    if is_live:
        content_parts.append('''
            <script>
                setTimeout(() => location.reload(), 5000);
            </script>
        ''')

    title = session_info.get('summary', f"Session {session_id[:8]}")
    meta_parts = []
    if session_info.get('cwd'):
        meta_parts.append(f"<span>📁 {escape(session_info['cwd'])}</span>")
    if session_info.get('sessionId'):
        meta_parts.append(f"<span>🔑 {session_info['sessionId'][:8]}...</span>")
    if messages:
        first_ts = format_timestamp(messages[0].get('timestamp'))
        if first_ts:
            meta_parts.append(f"<span>📅 {first_ts}</span>")
    meta_parts.append(f"<span>💬 {len(messages)} messages</span>")
    if is_live:
        meta_parts.append('<span class="live-badge">LIVE</span>')

    return HTML_TEMPLATE.format(
        title=escape(title),
        meta=' '.join(meta_parts),
        content='\n'.join(content_parts)
    )


def render_session_list(sessions, is_live=False, link_prefix=""):
    """Render an index page listing all sessions."""
    items = []

    for i, session in enumerate(sessions):
        mod_time_dt = datetime.fromtimestamp(session['modified'])
        relative_time = format_relative_time(mod_time_dt)
        absolute_time = mod_time_dt.strftime("%Y-%m-%d %H:%M")
        size_kb = session['size'] / 1024

        if is_live:
            html_file = f"/session/{session['id']}"
        else:
            html_file = f"{link_prefix}{session['id']}.html"

        title = session.get('summary') or f"Session {session['id'][:12]}"

        # Truncate path for display
        full_path = session['project']
        display_path = truncate_path(full_path, max_parts=2)

        items.append(f'''
            <li data-index="{i}" data-title="{escape(title.lower())}" data-project="{escape(session['project'].lower())}" data-preview="{escape(session['preview'].lower())}">
                <a href="{html_file}">{escape(title)}</a>
                <div class="session-meta">
                    <span class="session-time" title="{escape(absolute_time)}">🕐 {escape(relative_time)}</span>
                    <span class="session-path tooltip" data-tooltip="{escape(full_path)}">📁 {escape(display_path)}</span>
                    <span>💬 {session['message_count']}</span>
                    <span>📦 {size_kb:.1f}KB</span>
                </div>
                <div class="preview">{escape(session['preview'])}</div>
            </li>
        ''')

    live_indicator = ""
    if is_live:
        live_indicator = '''
            <div class="info-box">
                <span class="live-badge">LIVE</span>
                Auto-refreshes every 10 seconds
            </div>
            <script>
                setTimeout(() => location.reload(), 10000);
            </script>
        '''

    search_box = '''
        <div class="search-container">
            <span class="search-icon">🔍</span>
            <input type="text" id="searchBox" class="search-box" placeholder="Search sessions by title, project, or content...">
            <div class="search-stats" id="searchStats"></div>
        </div>
    '''

    content = f'{live_indicator}{search_box}<ul class="session-list" id="sessionList">{"".join(items)}</ul>'

    meta = f"<span id='totalSessions'>{len(sessions)} sessions found</span>"
    if is_live:
        meta += ' <span class="live-badge">LIVE</span>'

    return HTML_TEMPLATE.format(
        title="Claude Code Chat History",
        meta=meta,
        content=content
    )


# =============================================================================
# LIVE SERVER
# =============================================================================

class LiveChatHandler(BaseHTTPRequestHandler):
    """HTTP handler for live chat viewing."""

    claude_dir = CLAUDE_DIR

    def log_message(self, format, *args):
        # Suppress default request logging for cleaner output
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/' or path == '/index.html':
            self.serve_index()
        elif path.startswith('/session/'):
            session_id = path.replace('/session/', '').replace('.html', '')
            self.serve_session(session_id)
        elif path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def serve_index(self):
        sessions = get_all_sessions(self.claude_dir)
        html = render_session_list(sessions, is_live=True)
        self._send_html(html)

    def serve_session(self, session_id):
        sessions = get_all_sessions(self.claude_dir)
        matching = [s for s in sessions if session_id in s['id']]

        if not matching:
            self.send_error(404, f"Session {session_id} not found")
            return

        session = matching[0]
        messages, info = parse_session(session['path'])
        html = render_session_html(messages, info, session['id'], is_live=True)
        self._send_html(html)

    def _send_html(self, html):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))


def start_live_server(port=DEFAULT_PORT, claude_dir=None, open_browser=True):
    """Start the live web server."""
    if claude_dir:
        LiveChatHandler.claude_dir = Path(claude_dir)

    server = HTTPServer(('localhost', port), LiveChatHandler)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║         Claude Code Chat Viewer - Live Server            ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║   🌐 URL: http://localhost:{port:<24}        ║
║                                                          ║
║   • Session list refreshes every 10 seconds              ║
║   • Individual chats refresh every 5 seconds             ║
║   • Press Ctrl+C to stop the server                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

    if open_browser:
        webbrowser.open(f"http://localhost:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
        server.shutdown()


# =============================================================================
# STATIC GENERATION
# =============================================================================

def generate_static_html(output_dir, claude_dir=None, limit=50, open_browser=False):
    """Generate static HTML files for all sessions."""
    sessions = get_all_sessions(claude_dir)[:limit]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Generating HTML for {len(sessions)} sessions...")

    for session in sessions:
        try:
            messages, info = parse_session(session['path'])
            html = render_session_html(messages, info, session['id'], is_live=False)

            output_file = output_path / f"{session['id']}.html"
            output_file.write_text(html, encoding='utf-8')
        except Exception as e:
            print(f"  ⚠ Error processing {session['id']}: {e}")

    # Generate index
    index_html = render_session_list(sessions, is_live=False)
    index_file = output_path / "index.html"
    index_file.write_text(index_html, encoding='utf-8')

    print(f"\n✅ Generated {len(sessions)} session files")
    print(f"📁 Output directory: {output_path}")
    print(f"🏠 Index: {index_file}")

    if open_browser:
        webbrowser.open(f"file://{index_file}")


def list_sessions(claude_dir=None, limit=50):
    """List all available sessions in terminal."""
    sessions = get_all_sessions(claude_dir)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║              Claude Code Chat Sessions                   ║
╚══════════════════════════════════════════════════════════╝
""")

    for i, session in enumerate(sessions[:limit], 1):
        mod_time = datetime.fromtimestamp(session['modified']).strftime("%Y-%m-%d %H:%M")
        print(f"{i:3}. [{session['id'][:8]}] {mod_time}")
        print(f"     📁 {session['project']}")
        print(f"     💬 {session['message_count']} messages | {session['size']/1024:.1f} KB")
        if session.get('summary'):
            print(f"     📝 {session['summary']}")
        preview = session['preview'][:60].replace('\n', ' ')
        print(f"     Preview: {preview}...")
        print()

    print(f"Total: {len(sessions)} sessions")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="View Claude Code chat history in a beautiful, readable format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --serve              Start live server (auto-updates!)
  %(prog)s --serve -P 9000      Live server on custom port
  %(prog)s                      Generate static HTML files
  %(prog)s --list               List all sessions in terminal
  %(prog)s -s abc123            Generate HTML for specific session
  %(prog)s --open               Open in browser after generating

Configuration:
  The default Claude Code data directory is ~/.claude
  Use --claude-dir to specify a different location
        """
    )

    parser.add_argument(
        '--serve', action='store_true',
        help='Start live web server (recommended)'
    )
    parser.add_argument(
        '-P', '--port', type=int, default=DEFAULT_PORT,
        help=f'Port for live server (default: {DEFAULT_PORT})'
    )
    parser.add_argument(
        '-s', '--session',
        help='View specific session by ID (partial match supported)'
    )
    parser.add_argument(
        '-p', '--project',
        help='Filter sessions by project path'
    )
    parser.add_argument(
        '-o', '--output', default=str(DEFAULT_OUTPUT_DIR),
        help=f'Output directory for static HTML (default: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '--claude-dir', default=str(CLAUDE_DIR),
        help=f'Claude Code data directory (default: {CLAUDE_DIR})'
    )
    parser.add_argument(
        '--list', action='store_true',
        help='List all sessions in terminal'
    )
    parser.add_argument(
        '--open', action='store_true',
        help='Open in browser after generating'
    )
    parser.add_argument(
        '-n', '--limit', type=int, default=50,
        help='Limit number of sessions (default: 50)'
    )

    args = parser.parse_args()

    # Update global CLAUDE_DIR if specified
    claude_dir = Path(args.claude_dir)

    if not claude_dir.exists():
        print(f"❌ Error: Claude Code directory not found: {claude_dir}")
        print(f"   Make sure Claude Code is installed and has been used at least once.")
        sys.exit(1)

    # Live server mode
    if args.serve:
        start_live_server(args.port, claude_dir, open_browser=True)
        return

    # List mode
    if args.list:
        list_sessions(claude_dir, args.limit)
        return

    # Single session mode
    if args.session:
        sessions = get_all_sessions(claude_dir)
        matching = [s for s in sessions if args.session in s['id']]

        if not matching:
            print(f"❌ No session found matching: {args.session}")
            print("   Use --list to see available sessions")
            sys.exit(1)

        session = matching[0]
        messages, info = parse_session(session['path'])
        html = render_session_html(messages, info, session['id'], is_live=False)

        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        output_file = output_path / f"{session['id']}.html"
        output_file.write_text(html, encoding='utf-8')

        print(f"✅ Generated: {output_file}")

        if args.open:
            webbrowser.open(f"file://{output_file}")
        return

    # Default: generate all static HTML
    generate_static_html(args.output, claude_dir, args.limit, args.open)


if __name__ == '__main__':
    main()
