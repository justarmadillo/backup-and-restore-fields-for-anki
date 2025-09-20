# __init__.py
# Addon: Field State Backup & Restore (Final)
# - Buttons are always visible and grouped together.
# - Provides a helpful message if used on the wrong note type.
# - Silently backs up fields, then clears them on configured note types.
# - Silently restores fields, then clears the cache on configured note types.

import json
import base64
import logging
from aqt import mw, gui_hooks
from aqt.editor import Editor
from aqt.utils import showInfo
from bs4 import BeautifulSoup

# Use logging for silent error reporting instead of pop-up boxes.
# Errors will appear in the Anki debug console (Ctrl+Shift+;).
log = logging.getLogger(__name__)

def get_config() -> dict:
    """Safely reads addon configuration from config.json."""
    return mw.addonManager.getConfig(__name__)

def add_backup_restore_buttons(buttons: list[str], editor: Editor):
    """Adds the Backup and Restore buttons to the editor for all note types."""
    
    # --- 1. CONFIGURATION ---
    config = get_config()
    # Get lists from config, providing empty lists as a fallback.
    enabled_notetypes = config.get("enabled_notetypes", [])
    ignored_fields_config = config.get("ignored_backup_fields", ["image", "cache"])
    # Make the comparison case-insensitive for robustness.
    ignored_fields_lower = [f.lower() for f in ignored_fields_config]

    # --- 2. CORE ADDON LOGIC ---
    def on_backup_fields(_):
        """Wrapper for backup. First checks if the notetype is supported."""
        if not editor.note: return

        current_notetype_name = editor.note.model()['name']
        if current_notetype_name not in enabled_notetypes:
            # Show a helpful message if notetype is wrong
            showInfo(f"This note type ('{current_notetype_name}') is not enabled for backup/restore.\n\n"
                     f"Please use one of the following note types:\n- {', '.join(enabled_notetypes)}")
            return
        
        # If the notetype is correct, proceed with the backup.
        editor.saveNow(lambda: _do_backup(editor))

    def _do_backup(editor: Editor):
        """Backs up field content and clears the original fields."""
        try:
            note = editor.note
            model = note.model()
            field_names = mw.col.models.field_names(model)

            if "Cache" not in field_names:
                log.warning("Backup failed: Note type is missing the 'Cache' field.")
                return

            backup_data, fields_to_clear = [], []
            for i, field_name in enumerate(field_names):
                if i == 0 or field_name.lower() in ignored_fields_lower:
                    continue
                field_content = note[field_name]
                if field_content and field_content.strip():
                    backup_data.append({"field": field_name, "html": field_content})
                    fields_to_clear.append(field_name)

            if not backup_data: return
                
            json_string = json.dumps(backup_data, ensure_ascii=False)
            base64_string = base64.b64encode(json_string.encode('utf-8')).decode('ascii')
            note["Cache"] = f"<div>{base64_string}</div>"
            
            for field_name in fields_to_clear:
                note[field_name] = ""

            if not editor.addMode:
                mw.col.update_note(note)
            editor.loadNote()
        except Exception as e:
            log.error(f"An error occurred during backup: {e}", exc_info=True)

    def on_restore_fields(_):
        """Wrapper for restore. First checks if the notetype is supported."""
        if not editor.note: return

        current_notetype_name = editor.note.model()['name']
        if current_notetype_name not in enabled_notetypes:
            # Show the same helpful message
            showInfo(f"This note type ('{current_notetype_name}') is not enabled for backup/restore.\n\n"
                     f"Please use one of the following note types:\n- {', '.join(enabled_notetypes)}")
            return
        
        # If the notetype is correct, proceed with the restore.
        editor.saveNow(lambda: _do_restore(editor))

    def _do_restore(editor: Editor):
        """Restores field content and clears the cache."""
        try:
            note = editor.note
            model = note.model()
            field_names = mw.col.models.field_names(model)
            if "Cache" not in field_names:
                log.warning("Restore failed: 'Cache' field not found.")
                return

            cache_content = note["Cache"]
            if not cache_content or not cache_content.strip(): return

            soup = BeautifulSoup(cache_content, "html.parser")
            b64_string = soup.get_text().strip()
            if not b64_string: return

            json_string = base64.b64decode(b64_string).decode('utf-8')
            backup_data = json.loads(json_string)

            for item in backup_data:
                field_name, field_html = item.get("field"), item.get("html", "")
                if field_name and field_name in field_names:
                    note[field_name] = field_html
            
            note["Cache"] = ""
            if not editor.addMode:
                mw.col.update_note(note)
            editor.loadNote()
        except Exception as e:
            log.error(f"An error occurred during restore: {e}", exc_info=True)

    # --- 3. BUTTON CREATION ---
    # The buttons are now created unconditionally. The logic check is moved inside their click handlers.

    # First, generate the HTML for each button individually.
    backup_button_html = editor.addButton(
        icon=None,
        cmd="backup_fields_final_cmd", # Use unique cmd strings
        func=on_backup_fields,
        tip="Backup fields and clear them (Ctrl+Alt+B)",
        label="Backup",
        keys="Ctrl+Alt+B"
    )

    restore_button_html = editor.addButton(
        icon=None,
        cmd="restore_fields_final_cmd", # Use unique cmd strings
        func=on_restore_fields,
        tip="Restore fields and clear cache (Ctrl+Alt+R)",
        label="Restore",
        keys="Ctrl+Alt+R"
    )

    # Combine the buttons into a single HTML string to ensure they always appear next to each other.
    # To change the order, just swap the two variables in the f-string below.
    combined_buttons = f"{backup_button_html}{restore_button_html}"

    # Now, add the single combined string to the list of buttons.
    buttons.append(combined_buttons)
    
    return buttons

# Hook into the editor setup process.
gui_hooks.editor_did_init_buttons.append(add_backup_restore_buttons)