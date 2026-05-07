"""Wrapper that catches ALL exceptions and writes them to a debug log."""
import sys
import traceback

DEBUG_LOG = "/tmp/douyin_debug.log"

def global_excepthook(exc_type, exc_value, exc_tb):
    """Catch ALL unhandled exceptions."""
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    with open(DEBUG_LOG, "a") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"UNHANDLED EXCEPTION:\n")
        f.writelines(tb_lines)
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = global_excepthook

# Now import and run the app
import app
app.app.launch(server_name="0.0.0.0", server_port=7860, share=False)
