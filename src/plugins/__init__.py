"""
Plugins package: Contains all plugin implementations.

Each module in this package should define one or more classes
that inherit from BasePlugin and implement the execute() method.
"""

# Import all plugin submodules so PluginLoader can discover them
from src.plugins import (
    audio_summarizer,
    audio_transcriber,
    calculator,
    language_tutor,
    calendar_sync,
    code_interpreter,
    code_reviewer,
    currency_converter,
    daily_standup,
    diagram_generator,
    discord_bot,
    email_sender,
    file_manager,
    finance_analyzer,
    github_integration,
    google_search,
    image_generator,
    interview_mock,
    meeting_minutes,
    mermaid_renderer,
    mindmap_generator,
    ocr_extractor,
    okr_tracker,
    research_writer,
    slack_bot,
    smart_notes,
    table_parser,
    telegram_bot,
    terminal_runner,
    url_summarizer,
    web_search,
    web_crawler,
    weather,
    wikipedia_lookup,
    writing_assistant,
    youtube_summarizer,
    zalo_bot,
)

