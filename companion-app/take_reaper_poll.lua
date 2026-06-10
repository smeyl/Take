-- Take: persistent transport control polling script
-- Run via Reaper: Actions > Run script... (stays running via reaper.defer)
-- Copy to: ~/Library/Application Support/REAPER/Scripts/take_reaper_poll.lua
--
-- Handles three commands written to /tmp/take_reaper_cmd by Python:
--   record\n{track_idx}          — arm track, save cursor pos, start recording
--   stop                          — stop recording
--   swap\n{filepath}\n{track_idx}\n{start_time}  — replace streamed item with lossless file

local CMD_FILE   = "/tmp/take_reaper_cmd"
local START_FILE = "/tmp/take_record_start"

local function handle_record(track_idx)
  local track = reaper.GetTrack(0, track_idx)
  if track then
    reaper.SetMediaTrackInfo_Value(track, "I_RECARM", 1)
  end
  -- Write Reaper project cursor position so Python can use it for the later swap
  local pos = reaper.GetCursorPosition()
  local f = io.open(START_FILE, "w")
  if f then
    f:write(string.format("%.6f\n%d\n", pos, track_idx))
    f:close()
  end
  reaper.Main_OnCommand(1013, 0)  -- Transport: Record
end

local function handle_stop()
  reaper.Main_OnCommand(1016, 0)  -- Transport: Stop
end

local function handle_swap(filepath, track_idx, start_time)
  local track = reaper.GetTrack(0, track_idx)
  if not track then return end
  -- Find the BlackHole-recorded item near start_time and remove it
  for i = reaper.GetTrackNumMediaItems(track) - 1, 0, -1 do
    local item     = reaper.GetTrackMediaItem(track, i)
    local item_pos = reaper.GetMediaItemInfo_Value(item, "D_POSITION")
    if math.abs(item_pos - start_time) < 2.0 then
      reaper.DeleteTrackMediaItem(track, item)
      break
    end
  end
  -- Insert lossless file at the same timeline position
  reaper.SetOnlyTrackSelected(track)
  reaper.SetEditCurPos(start_time, false, false)
  reaper.InsertMedia(filepath, 0)
  reaper.UpdateArrange()
end

local function main()
  local f = io.open(CMD_FILE, "r")
  if f then
    local cmd   = f:read("*l") or ""
    local line2 = f:read("*l") or ""
    local line3 = f:read("*l") or ""
    local line4 = f:read("*l") or ""
    f:close()
    os.remove(CMD_FILE)

    if cmd == "record" then
      handle_record(tonumber(line2) or 0)
    elseif cmd == "stop" then
      handle_stop()
    elseif cmd == "swap" then
      -- line2 = filepath, line3 = track_idx, line4 = start_time
      handle_swap(line2, tonumber(line3) or 0, tonumber(line4) or 0)
    end
  end
  reaper.defer(main)
end

main()
