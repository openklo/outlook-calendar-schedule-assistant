# tests/test_classify.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))  # co source, not deployed mirror
import calendar_overview as c
def mk(loc="", sub=""): return {"location":{"displayName":loc}, "subject":sub}
# virtual via URL
mt,rt = c._classify_meeting(mk("https://teams.microsoft.com/x/1","Team sync")); assert (mt,rt)==("virtual",False)
# virtual via provider keyword
mt,rt = c._classify_meeting(mk("Zoom","Quick chat")); assert mt=="virtual" and rt is False
mt,rt = c._classify_meeting(mk("Google Meet code: abc","x")); assert mt=="virtual"
mt,rt = c._classify_meeting(mk("Microsoft Teams","y")); assert mt=="virtual"
# in-person via non-URL room name -> needs transport
mt,rt = c._classify_meeting(mk("Room 4B","Standup")); assert (mt,rt)==("in-person",True)
mt,rt = c._classify_meeting(mk("Oslo office, gate 2","Client")); assert rt is True
# in-person via subject even without location
mt,rt = c._classify_meeting(mk("","In-person lunch")); assert (mt,rt)==("in-person",True)
# unknown: no location, no in-person signal
mt,rt = c._classify_meeting(mk("","Random task")); assert (mt,rt)==("unknown",False)
# URL-with-tz / geo coords must NOT be misread as "in person"
mt,rt = c._classify_meeting(mk("51.5074 N, 0.1278 W","Geo note")); assert rt is True   # geo room = physical
print("CLASSIFY-OK")
