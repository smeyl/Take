-- Take: fallback insert action, triggered by engineer.py via the Reaper web API.
-- Places an incoming file on the "Take Session" track (created automatically by
-- take_session.lua). Used when no swap position is known for the take.
-- Registered in Reaper as an action — its command ID is what engineer.py calls.

local TRACK_NAME = "Take Session"

local file = io.open("/tmp/take_incoming.txt", "r")
if file then
    local filepath = file:read("*l")
    file:close()
    if filepath and filepath ~= "" then
        local target
        for i = 0, reaper.CountTracks(0) - 1 do
            local tr = reaper.GetTrack(0, i)
            local _, name = reaper.GetTrackName(tr, "", 256)
            if name == TRACK_NAME then
                target = tr
                break
            end
        end
        if target then
            reaper.SetOnlyTrackSelected(target)
        end
        reaper.InsertMedia(filepath, 0)
        os.remove("/tmp/take_incoming.txt")
    end
end
