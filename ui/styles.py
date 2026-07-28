"""
Custom CSS styles for the Streamlit UI.

Exported as CUSTOM_CSS constant (a <style> tag string).
Moved from app.py to keep the entry point lean (~400 lines saved).
"""

CUSTOM_CSS = """
<style>
    /* ── Global ── */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        max-width: 900px;
    }

    /* ── Chat header ── */
    .chat-header {
        text-align: center;
        padding: 1rem 0 0.5rem 0;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 1rem;
    }
    .chat-header h1 {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .chat-header p {
        font-size: 0.85rem;
        color: #888;
        margin-top: 0;
    }

    /* ── Chat messages container (scrollable) ── */
    .chat-messages {
        max-height: 60vh;
        overflow-y: auto;
        padding: 0.5rem 1rem;
        margin-bottom: 0.5rem;
        border-radius: 12px;
        background: rgba(128, 128, 128, 0.02);
        scroll-behavior: smooth;
    }

    /* ── Message bubbles ── */
    .message-bubble {
        max-width: 80%;
        padding: 0.75rem 1rem;
        border-radius: 18px;
        position: relative;
        line-height: 1.5;
        font-size: 0.95rem;
        word-wrap: break-word;
    }
    .message-bubble.user {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-bottom-right-radius: 4px;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }
    .message-bubble.assistant {
        background: #2d2d3f;
        color: #e0e0e0;
        border-bottom-left-radius: 4px;
        border: 1px solid rgba(128, 128, 128, 0.15);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }

    /* ── Image in message bubble ── */
    .message-image-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 0.5rem;
    }
    .message-image-grid img {
        max-width: 100%;
        max-height: 250px;
        border-radius: 10px;
        object-fit: contain;
        cursor: zoom-in;
        transition: transform 0.2s;
    }
    .message-image-grid img:hover {
        transform: scale(1.02);
    }
    .message-image-grid .img-single {
        max-height: 300px;
    }
    .message-image-grid .img-multi {
        width: calc(50% - 3px);
        max-height: 200px;
    }
    .image-count-badge {
        display: inline-block;
        padding: 0.1rem 0.4rem;
        border-radius: 8px;
        font-size: 0.65rem;
        font-weight: 700;
        background: rgba(128, 128, 128, 0.12);
        color: #aaa;
        border: 1px solid rgba(128, 128, 128, 0.2);
        margin-left: 0.3rem;
    }

    /* ── Provider badge ── */
    .provider-badge {
        display: inline-block;
        padding: 0.15rem 0.5rem;
        border-radius: 10px;
        font-size: 0.7rem;
        font-weight: 600;
        margin-left: 0.5rem;
    }
    .provider-badge.mock {
        background: #ff6b6b22;
        color: #ff6b6b;
        border: 1px solid #ff6b6b44;
    }
    .provider-badge.ollama {
        background: #4ecdc422;
        color: #4ecdc4;
        border: 1px solid #4ecdc444;
    }
    .provider-badge.openai {
        background: #45b7d122;
        color: #45b7d1;
        border: 1px solid #45b7d144;
    }
    .provider-badge.gemini {
        background: #4caf5022;
        color: #4caf50;
        border: 1px solid #4caf5044;
    }

    /* ── Input area ── */
    .input-container {
        border-top: 1px solid rgba(128, 128, 128, 0.15);
        padding-top: 0.75rem;
        margin-top: 0.5rem;
    }

    /* ── Drag-and-drop zone ── */
    .drop-zone {
        border: 2px dashed rgba(102, 126, 234, 0.3);
        border-radius: 12px;
        padding: 1.5rem 1rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s ease;
        background: rgba(102, 126, 234, 0.02);
        margin-bottom: 0.5rem;
    }
    .drop-zone:hover, .drop-zone:focus-within {
        border-color: #667eea;
        background: rgba(102, 126, 234, 0.06);
    }
    .drop-zone .dz-icon { font-size: 2rem; margin-bottom: 0.3rem; }
    .drop-zone .dz-text { font-size: 0.85rem; color: #888; }
    .drop-zone .dz-hint { font-size: 0.7rem; color: #666; margin-top: 0.2rem; }

    /* ── Image preview thumbnails ── */
    .preview-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 0.5rem;
        margin-bottom: 0.5rem;
        background: rgba(102, 126, 234, 0.03);
        border-radius: 10px;
        border: 1px solid rgba(102, 126, 234, 0.1);
    }
    .preview-item {
        position: relative;
        width: 80px;
        height: 80px;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid rgba(128, 128, 128, 0.15);
    }
    .preview-item img { width: 100%; height: 100%; object-fit: cover; }
    .preview-item .preview-remove {
        position: absolute; top: -4px; right: -4px;
        width: 18px; height: 18px; border-radius: 50%;
        background: rgba(255, 107, 107, 0.9); color: white; border: none;
        font-size: 0.6rem; cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        opacity: 0; transition: opacity 0.15s;
    }
    .preview-item:hover .preview-remove { opacity: 1; }
    .preview-item .preview-name {
        position: absolute; bottom: 0; left: 0; right: 0;
        background: rgba(0, 0, 0, 0.6); color: white;
        font-size: 0.55rem; padding: 1px 4px;
        text-overflow: ellipsis; overflow: hidden; white-space: nowrap;
    }

    /* ── Sidebar sections ── */
    .sidebar-section { margin-bottom: 1.5rem; }
    .sidebar-section h3 {
        font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;
        color: #888; margin-bottom: 0.75rem;
        border-bottom: 1px solid rgba(128, 128, 128, 0.1); padding-bottom: 0.4rem;
    }

    /* ── Session button styling ── */
    div[data-testid="stButton"] button.session-btn {
        text-align: left; font-size: 0.85rem; padding: 0.4rem 0.7rem;
        background: transparent; border: 1px solid transparent;
        border-radius: 8px; transition: all 0.2s; justify-content: flex-start;
    }
    div[data-testid="stButton"] button.session-btn:hover {
        background: rgba(102, 126, 234, 0.1); border-color: rgba(102, 126, 234, 0.2);
    }
    div[data-testid="stButton"] button.session-btn.active {
        background: rgba(102, 126, 234, 0.15); border-color: rgba(102, 126, 234, 0.3);
        color: #667eea; font-weight: 600;
    }

    /* ── Stat card ── */
    .stat-card {
        background: rgba(128, 128, 128, 0.05); border-radius: 10px;
        padding: 0.75rem; text-align: center;
        border: 1px solid rgba(128, 128, 128, 0.1);
    }
    .stat-card .stat-value { font-size: 1.5rem; font-weight: 700; color: #667eea; }
    .stat-card .stat-label {
        font-size: 0.7rem; color: #888;
        text-transform: uppercase; letter-spacing: 0.5px;
    }

    /* ── Toast notifications ── */
    .toast-container { margin-bottom: 0.75rem; }
    .toast-error {
        background: rgba(255, 107, 107, 0.1); border: 1px solid rgba(255, 107, 107, 0.3);
        border-radius: 10px; padding: 0.75rem 1rem;
        color: #ff6b6b; font-size: 0.9rem; margin-bottom: 0.5rem;
    }
    .toast-success {
        background: rgba(78, 205, 196, 0.1); border: 1px solid rgba(78, 205, 196, 0.3);
        border-radius: 10px; padding: 0.75rem 1rem;
        color: #4ecdc4; font-size: 0.9rem; margin-bottom: 0.5rem;
    }

    /* ── Model response markdown ── */
    .message-bubble.assistant p { margin-bottom: 0.4rem; }
    .message-bubble.assistant code {
        background: rgba(128, 128, 128, 0.15);
        padding: 0.15rem 0.35rem; border-radius: 4px; font-size: 0.85em;
    }
    .message-bubble.assistant pre {
        background: rgba(0, 0, 0, 0.3);
        padding: 0.75rem; border-radius: 8px; overflow-x: auto;
    }

    /* ── Welcome message ── */
    .welcome-msg { text-align: center; padding: 3rem 1rem; color: #666; }
    .welcome-msg .emoji { font-size: 4rem; margin-bottom: 1rem; }
    .welcome-msg .title { font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem; color: #e0e0e0; }
    .welcome-msg .subtitle { font-size: 0.9rem; }

    /* ── Auto-scroll anchor ── */
    #scroll-anchor { height: 1px; }

    /* ── Inline edit area ── */
    .edit-container {
        background: rgba(102, 126, 234, 0.05);
        border: 1px solid rgba(102, 126, 234, 0.2);
        border-radius: 12px; padding: 0.5rem; margin-bottom: 0.3rem;
    }
    .edit-container textarea {
        width: 100%; min-height: 60px;
        background: rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(102, 126, 234, 0.3); border-radius: 8px;
        color: #e0e0e0; font-size: 0.9rem; padding: 0.5rem;
        resize: vertical; font-family: inherit;
    }
    .edit-container textarea:focus {
        outline: none; border-color: #667eea;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
    }
    .edit-actions { display: flex; gap: 0.5rem; margin-top: 0.5rem; justify-content: flex-end; }
    .edit-actions button {
        padding: 0.3rem 0.8rem; border-radius: 8px; border: none;
        font-size: 0.8rem; cursor: pointer; font-weight: 600; transition: all 0.15s;
    }
    .edit-actions .save-btn {
        background: linear-gradient(135deg, #667eea, #764ba2); color: white;
    }
    .edit-actions .save-btn:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4); }
    .edit-actions .cancel-btn { background: rgba(128, 128, 128, 0.15); color: #888; }
    .edit-actions .cancel-btn:hover { background: rgba(128, 128, 128, 0.25); }

    /* ── Undo toast ── */
    .undo-toast {
        display: flex; align-items: center; justify-content: space-between;
        background: rgba(78, 205, 196, 0.12);
        border: 1px solid rgba(78, 205, 196, 0.25);
        border-radius: 10px; padding: 0.6rem 1rem;
        margin-bottom: 0.75rem; animation: slideIn 0.3s ease-out;
    }
    @keyframes slideIn { from { transform: translateY(-10px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    .undo-toast .msg { font-size: 0.85rem; color: #4ecdc4; }
    .undo-btn {
        background: rgba(78, 205, 196, 0.2); border: 1px solid rgba(78, 205, 196, 0.3);
        border-radius: 8px; padding: 0.3rem 0.8rem;
        color: #4ecdc4; font-size: 0.8rem; font-weight: 600;
        cursor: pointer; transition: all 0.15s;
    }
    .undo-btn:hover { background: rgba(78, 205, 196, 0.3); transform: scale(1.05); }

    /* ── Health Check ── */
    .health-row { display: flex; align-items: center; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid rgba(128, 128, 128, 0.06); }
    .health-row:last-child { border-bottom: none; }
    .health-info { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; }
    .health-latency { font-size: 0.7rem; color: #888; font-family: monospace; }
    .health-badge { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 8px; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.3px; }
    .health-badge.health-ok { background: rgba(78, 205, 196, 0.12); color: #4ecdc4; border: 1px solid rgba(78, 205, 196, 0.2); }
    .health-badge.health-fail { background: rgba(255, 107, 107, 0.12); color: #ff6b6b; border: 1px solid rgba(255, 107, 107, 0.2); }
    .health-error { font-size: 0.7rem; color: #ff6b6b; padding: 0.1rem 0 0.3rem 1.5rem; font-style: italic; word-break: break-word; }

    /* ── Pinned Messages ── */
    .pinned-section {
        margin-bottom: 1rem; padding: 0.5rem 1rem;
        background: rgba(255, 215, 0, 0.05);
        border: 1px solid rgba(255, 215, 0, 0.15); border-radius: 12px;
    }
    .pinned-header { font-size: 0.75rem; color: #ffd700; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; padding-bottom: 0.4rem; border-bottom: 1px solid rgba(255, 215, 0, 0.1); margin-bottom: 0.5rem; }
    .pinned-badge { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 6px; font-size: 0.65rem; font-weight: 700; background: rgba(255, 215, 0, 0.12); color: #ffd700; border: 1px solid rgba(255, 215, 0, 0.2); margin-left: 0.4rem; vertical-align: middle; }
    .message-bubble.pinned { border-left: 3px solid #ffd700 !important; position: relative; }
    .message-bubble.pinned.user { border-left-color: #ffd700 !important; }
    .message-bubble.pinned.assistant { border-left-color: #ffd700 !important; }
    .pin-btn { cursor: pointer; opacity: 0.4; transition: opacity 0.15s; border: none; background: transparent; padding: 0.1rem; font-size: 0.85rem; }
    .pin-btn:hover { opacity: 1; }
    .pin-btn.active { opacity: 1; color: #ffd700; }

    /* ── Voice Input Button ── */
    .voice-btn { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 50%; border: 1px solid rgba(128, 128, 128, 0.2); background: rgba(128, 128, 128, 0.05); font-size: 1rem; cursor: pointer; transition: all 0.2s ease; color: #888; flex-shrink: 0; }
    .voice-btn:hover { background: rgba(102, 126, 234, 0.1); border-color: rgba(102, 126, 234, 0.3); color: #667eea; }
    .voice-btn.recording { background: rgba(255, 107, 107, 0.15); border-color: #ff6b6b; color: #ff6b6b; animation: pulse 1s ease infinite; }
    @keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(255, 107, 107, 0.4); } 50% { box-shadow: 0 0 0 8px rgba(255, 107, 107, 0); } }

    /* ── TTS Play Button ── */
    .tts-btn { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; border: none; background: rgba(128, 128, 128, 0.08); font-size: 0.75rem; cursor: pointer; transition: all 0.15s; color: #888; margin-left: 0.3rem; flex-shrink: 0; }
    .tts-btn:hover { background: rgba(102, 126, 234, 0.15); color: #667eea; }
    .tts-btn.speaking { background: rgba(78, 205, 196, 0.2); color: #4ecdc4; animation: ttsPulse 0.8s ease infinite; }
    @keyframes ttsPulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.7; transform: scale(0.9); } }

    /* ── Mobile-responsive (Feature 45) ── */
    @media (max-width: 768px) {
        .main .block-container { max-width: 100% !important; padding: 0.5rem !important; }
        .message-bubble { max-width: 90% !important; font-size: 0.9rem !important; }
        .chat-header h1 { font-size: 1.3rem !important; }
        .chat-messages { max-height: 50vh !important; }
        section[data-testid="stSidebar"] > div:first-child { padding: 0.5rem !important; }
    }
    @media (max-width: 480px) {
        .message-bubble { max-width: 95% !important; font-size: 0.85rem !important; padding: 0.5rem !important; }
        .chat-header h1 { font-size: 1.1rem !important; }
        .chat-header { padding: 0.5rem 0 !important; }
        .stat-card .stat-value { font-size: 1.2rem !important; }
    }

    /* ── Voice Input Row ── */
    .voice-input-row { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.3rem; }
    .voice-transcript { flex: 1; font-size: 0.85rem; color: #888; padding: 0.3rem 0.6rem; background: rgba(128, 128, 128, 0.05); border-radius: 8px; border: 1px solid rgba(128, 128, 128, 0.1); min-height: 1.5rem; }
    .voice-transcript.listening { color: #ff6b6b; border-color: rgba(255, 107, 107, 0.2); }

    /* ── Copy Code Button (Feature 46) ── */
    .copy-btn-container { position: relative; }
    .copy-code-btn { position: absolute; top: 4px; right: 4px; padding: 2px 8px; font-size: 0.7rem; border-radius: 6px; border: 1px solid rgba(128,128,128,0.2); background: rgba(128,128,128,0.1); color: #888; cursor: pointer; transition: all 0.2s; z-index: 10; opacity: 0; }
    pre:hover .copy-code-btn { opacity: 1; }
    .copy-code-btn:hover { background: rgba(102,126,234,0.2); color: #667eea; border-color: rgba(102,126,234,0.3); }
    .copy-code-btn.copied { background: rgba(78,205,196,0.2); color: #4ecdc4; border-color: rgba(78,205,196,0.3); }

    /* ── Session Tags (Feature 16) ── */
    .session-tag { display: inline-block; padding: 0.05rem 0.4rem; border-radius: 6px; font-size: 0.6rem; font-weight: 600; margin: 0.1rem 0.15rem; letter-spacing: 0.3px; }
    .session-tag.tag-coding { background: rgba(78,205,196,0.12); color: #4ecdc4; border: 1px solid rgba(78,205,196,0.15); }
    .session-tag.tag-question { background: rgba(102,126,234,0.12); color: #667eea; border: 1px solid rgba(102,126,234,0.15); }
    .session-tag.tag-creative { background: rgba(255,215,0,0.12); color: #ffd700; border: 1px solid rgba(255,215,0,0.15); }
    .session-tag.tag-general { background: rgba(128,128,128,0.12); color: #aaa; border: 1px solid rgba(128,128,128,0.15); }
    .session-tag.tag-learning { background: rgba(78,164,78,0.12); color: #4ea44e; border: 1px solid rgba(78,164,78,0.15); }

    /* ── Avatar row (Feature 58) ── */
    .avatar-row { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0; }
    .avatar-icon { font-size: 1.5rem; line-height: 1; }

    /* ── LaTeX Math (Feature 47) ── */
    .math-inline { display: inline; padding: 0.1rem 0.2rem; }
    .math-block { display: block; text-align: center; padding: 0.75rem; margin: 0.5rem 0; background: rgba(0, 0, 0, 0.15); border-radius: 8px; overflow-x: auto; }

    /* ── Chat History Search (Feature 50) ── */
    .search-result-item { padding: 0.3rem 0.5rem; border-radius: 6px; cursor: pointer; transition: background 0.15s; font-size: 0.8rem; border-left: 2px solid transparent; }
    .search-result-item:hover { background: rgba(102, 126, 234, 0.08); border-left-color: #667eea; }
    .search-result-item .search-title { font-weight: 600; color: #e0e0e0; }
    .search-result-item .search-meta { font-size: 0.65rem; color: #888; }
    .search-highlight { background: rgba(255, 215, 0, 0.25); padding: 0 2px; border-radius: 2px; }

    /* ── Export Buttons (Feature 59) ── */
    .export-btn-group { display: flex; gap: 0.4rem; margin-top: 0.3rem; }

    /* ── Code Diff Viewer (Feature 55) ── */
    .diff-container { display: flex; gap: 1px; border-radius: 8px; overflow: hidden; margin: 0.5rem 0; font-size: 0.8rem; }
    .diff-panel { flex: 1; min-width: 0; overflow-x: auto; }
    .diff-panel-header { padding: 0.3rem 0.6rem; font-weight: 600; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .diff-panel-header.diff-old { background: rgba(255, 107, 107, 0.15); color: #ff6b6b; }
    .diff-panel-header.diff-new { background: rgba(78, 205, 196, 0.15); color: #4ecdc4; }
    .diff-line { padding: 0.1rem 0.6rem; white-space: pre; font-family: monospace; font-size: 0.75rem; line-height: 1.4; }
    .diff-line.diff-added { background: rgba(78, 205, 196, 0.08); }
    .diff-line.diff-removed { background: rgba(255, 107, 107, 0.08); }
    .diff-line.diff-unchanged { background: transparent; color: #888; }

    /* ── Data Visualization Plotter (Feature 57) ── */
    .viz-container { background: rgba(0, 0, 0, 0.1); border-radius: 10px; padding: 1rem; margin: 0.5rem 0; border: 1px solid rgba(128, 128, 128, 0.1); }
    .viz-container .viz-title { font-size: 0.85rem; font-weight: 600; color: #e0e0e0; margin-bottom: 0.5rem; }
    .viz-container .viz-hint { font-size: 0.7rem; color: #888; font-style: italic; }
</style>
"""
