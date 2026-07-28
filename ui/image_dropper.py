"""
Image Dropper (Feature 172: Kéo thả Ảnh vào Ô Chat)

Adds drag-and-drop functionality for images directly onto the chat area.
When dragging an image file over the window, a dark overlay appears
with "Kéo thả ảnh vào đây". Dropped images are processed into
session state for the AI to analyze.

Usage:
    from ui.image_dropper import get_drag_drop_html
    st.markdown(get_drag_drop_html(), unsafe_allow_html=True)
"""

import random

# ── JavaScript + HTML overlay ──

_DRAG_DROP_JS_TEMPLATE = """
<style>
#dd-overlay {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    z-index: 999999;
    justify-content: center;
    align-items: center;
    font-size: 2rem;
    color: white;
    font-weight: 700;
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
}}
#dd-overlay.show {{
    display: flex;
}}
#dd-overlay .dd-box {{
    border: 3px dashed rgba(102, 126, 234, 0.6);
    border-radius: 24px;
    padding: 3rem 5rem;
    text-align: center;
    background: rgba(102, 126, 234, 0.1);
}}
#dd-overlay .dd-icon {{
    font-size: 4rem;
    margin-bottom: 1rem;
}}
#dd-overlay .dd-text {{
    font-size: 1.5rem;
}}
#dd-overlay .dd-hint {{
    font-size: 0.9rem;
    color: rgba(255,255,255,0.6);
    margin-top: 0.5rem;
}}
</style>
<div id="dd-overlay">
    <div class="dd-box">
        <div class="dd-icon">🖼️</div>
        <div class="dd-text">Kéo thả ảnh vào đây</div>
        <div class="dd-hint">Hỗ trợ PNG, JPG, GIF, WEBP</div>
    </div>
</div>
<script>
(function() {{
    'use strict';
    if (window.__ddInitialized_{uid}) return;
    window.__ddInitialized_{uid} = true;

    var overlay = document.getElementById('dd-overlay');
    if (!overlay) return;

    var dragCounter = 0;
    var allowedTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'];

    function showOverlay() {{
        overlay.classList.add('show');
    }}
    function hideOverlay() {{
        overlay.classList.remove('show');
    }}

    document.addEventListener('dragenter', function(e) {{
        e.preventDefault();
        e.stopPropagation();
        dragCounter++;
        if (dragCounter === 1) {{
            showOverlay();
        }}
    }});

    document.addEventListener('dragleave', function(e) {{
        e.preventDefault();
        e.stopPropagation();
        dragCounter--;
        if (dragCounter <= 0) {{
            dragCounter = 0;
            hideOverlay();
        }}
    }});

    document.addEventListener('dragover', function(e) {{
        e.preventDefault();
        e.stopPropagation();
    }});

    document.addEventListener('drop', function(e) {{
        e.preventDefault();
        e.stopPropagation();
        dragCounter = 0;
        hideOverlay();

        var files = e.dataTransfer.files;
        if (!files || files.length === 0) return;

        var imageFiles = [];
        for (var i = 0; i < files.length; i++) {{
            if (allowedTypes.indexOf(files[i].type) !== -1) {{
                imageFiles.push(files[i]);
            }}
        }}

        if (imageFiles.length === 0) return;

        // Visual-only: show a brief toast notification
        // Actual upload goes through Streamlit's st.file_uploader
        var count = imageFiles.length;
        var notif = document.createElement('div');
        notif.style.cssText = 'position:fixed;bottom:1rem;left:50%;transform:translateX(-50%);' +
            'background:#667eea;color:#fff;padding:0.5rem 1.5rem;border-radius:8px;' +
            'z-index:999999;font-size:0.9rem;box-shadow:0 2px 10px rgba(0,0,0,0.3);';
        notif.textContent = '📷 ' + count + ' ảnh được kéo thả! Dùng "📷 Upload ảnh" để gửi.';
        document.body.appendChild(notif);
        setTimeout(function() {{
            notif.style.opacity = '0';
            notif.style.transition = 'opacity 0.5s';
            setTimeout(function() {{ notif.remove(); }}, 500);
        }}, 3000);
    }});
}})();
</script>
"""


def get_drag_drop_html() -> str:
    """
    Get the HTML/JS/CSS for the drag-and-drop overlay.

    Returns:
        HTML string to inject via st.markdown(..., unsafe_allow_html=True)

    The overlay appears when an image file is dragged over the window.
    This is a VISUAL-ONLY enhancement. Dropped files show a notification
    telling the user to use the "📷 Upload ảnh" button to actually send them.
    """
    uid = random.randint(100000, 999999)
    return _DRAG_DROP_JS_TEMPLATE.format(uid=uid)


# (Dead code removed: _parse_dropped_images was used for JS-to-Streamlit bridge
#  that was not technically feasible with st.markdown injection alone.
#  Drag-drop is now visual-only; images go through st.file_uploader.)
