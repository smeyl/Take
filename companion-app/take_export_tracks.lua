local path = "/tmp/take_tracks.json"
local file = io.open(path, "w")
file:write("[")
local count = reaper.CountTracks(0)
for i = 0, count - 1 do
  local track = reaper.GetTrack(0, i)
  local _, name = reaper.GetTrackName(track, "", 256)
  name = name:gsub('"', '\\"')
  if i > 0 then file:write(",") end
  file:write(string.format('{"index":%d,"name":"%s"}', i, name))
end
file:write("]")
file:close()
reaper.ShowMessageBox("Tracks exported: " .. path, "Take", 0)
