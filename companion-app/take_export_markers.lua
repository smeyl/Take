local path = "/tmp/take_markers.json"
local file = io.open(path, "w")
file:write("[")
local first = true
local i = 0
local retval, isrgn, pos, rgnend, name, markrgnindexnumber

repeat
  retval, isrgn, pos, rgnend, name, markrgnindexnumber = reaper.EnumProjectMarkers(i)
  if retval > 0 and not isrgn then
    if not first then file:write(",") end
    file:write(string.format('{"name":"%s","position":%.3f}',
      name:gsub('"', '\\"'), pos))
    first = false
  end
  i = i + 1
until retval == 0

file:write("]")
file:close()
reaper.ShowMessageBox("Markers exported: " .. path, "Take", 0)
