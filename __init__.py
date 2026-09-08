"""calendar-overview plugin — registers fetch_calendar_overview + find_free_slot."""
import logging
logger = logging.getLogger(__name__)

def register(ctx):
    from . import schemas, tools
    ctx.register_tool(name="fetch_calendar_overview", toolset="calendar_overview",
                      schema=schemas.FETCH_CALENDAR_OVERVIEW, handler=tools.fetch_calendar_overview)
    ctx.register_tool(name="find_free_slot", toolset="calendar_overview",
                      schema=schemas.FIND_FREE_SLOT, handler=tools.find_free_slot)
    logger.info("calendar-overview: registered 2 tools")
