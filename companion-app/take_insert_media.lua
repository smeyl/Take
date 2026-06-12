-- Take: fallback insert action, triggered by engineer.py via the Reaper web API.
-- Places an incoming file on the engineer's selected destination track. Used
-- when no swap position is known for the take. Registered automatically by
-- take_session.lua on startup (command ID written to /tmp/take_insert_cmd_id).

local file = io.open("/tmp/take_incoming.txt", "r")
if file then
    local filepath    = file:read("*l")
    local track_index = tonumber(file:read("*l")) or 0
    file:close()
    if filepath and filepath ~= "" then
        local track = reaper.GetTrack(0, track_index)
        if track then
            reaper.SetOnlyTrackSelected(track)
        end
        reaper.InsertMedia(filepath, 0)
        os.remove("/tmp/take_incoming.txt")
    end
end
