"""calendar-overview plugin — registers fetch_calendar_overview + find_free_slot."""
import logging
import pathlib
import sys

logger = logging.getLogger(__name__)
_PLUGIN_DIR = pathlib.Path(__file__).resolve().parent

def register(ctx):
    from . import schemas, tools
    ctx.register_tool(name="fetch_calendar_overview", toolset="calendar_overview",
                      schema=schemas.FETCH_CALENDAR_OVERVIEW, handler=tools.fetch_calendar_overview)
    ctx.register_tool(name="find_free_slot", toolset="calendar_overview",
                      schema=schemas.FIND_FREE_SLOT, handler=tools.find_free_slot)

    def _setup(sub) -> None:
        sub.add_argument("wizard", nargs="?", choices=["status", "login", "consume", "verify"],
                         default="status", help="wizard step (default: status)")
        sub.add_argument("--url", default=None,
                         help="FULL callback URL (required for the consume step)")
        sub.add_argument("--env-file", default=None,
                         help="override .env path for status/verify checks")

    def _cmd_calendar_setup(args) -> None:
        """hermes calendar-setup <step> -> scripts/setup_wizard.py (thin shim, house pattern)."""
        import subprocess
        cmd = [sys.executable, str(_PLUGIN_DIR / "scripts" / "setup_wizard.py"), args.wizard]
        if args.wizard == "consume":
            if not args.url:
                print("error: consume requires --url '<FULL_CALLBACK_URL>'", file=sys.stderr)
                sys.exit(2)
            cmd.append(args.url)
        if args.env_file:
            cmd += ["--env-file", args.env_file]
        sys.exit(subprocess.run(cmd).returncode)

    ctx.register_cli_command(
        name="calendar-setup",
        help="calendar-overview first-time setup wizard (status/login/consume/verify)",
        setup_fn=_setup, handler_fn=_cmd_calendar_setup)
    logger.info("calendar-overview: registered 2 tools + calendar-setup CLI wizard")
