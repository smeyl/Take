-- Take: all-in-one session script — auto-started by Reaper via __startup.lua
-- (installed by setup.sh; replaces take_reaper_poll.lua + take_export_tracks.lua
--  + take_export_markers.lua, which required manual runs every session)
--
-- What it does, continuously:
--   * polls /tmp/take_reaper_cmd for commands from the Python backend:
--       record            — arm the Take Session track, save cursor pos, record
--       stop              — stop the transport
--       rtz               — return to zero (project start)
--       swap\n{filepath}\n{track_idx}\n{start_time}
--                         — replace the streamed item with the lossless file
--   * exports the track list to /tmp/take_tracks.json whenever it changes
--   * exports markers to /tmp/take_markers.json whenever they change
--   * guarantees a "Take Session" track exists, with its input set to
--     BlackHole and record-armed — created automatically if missing

local CMD_FILE     = "/tmp/take_reaper_cmd"
local START_FILE   = "/tmp/take_record_start"
local TRACKS_FILE  = "/tmp/take_tracks.json"
local MARKERS_FILE = "/tmp/take_markers.json"
local TRACK_NAME   = "Take Session"

local last_tracks_json  = nil
local last_markers_json = nil
local tick = 0

--------------------------------------------------------------------------------
-- Take Session track

local function find_session_track()
  for i = 0, reaper.CountTracks(0) - 1 do
    local tr = reaper.GetTrack(0, i)
    local _, name = reaper.GetTrackName(tr, "", 256)
    if name == TRACK_NAME then return tr, i end
  end
  return nil, -1
end

-- I_RECINPUT value for BlackHole: stereo pair (1024 + first channel) when two
-- consecutive BlackHole channels exist, otherwise mono channel index.
local function find_blackhole_input()
  local n = reaper.GetNumAudioInputs()
  for i = 0, n - 1 do
    local name = reaper.GetInputChannelName(i) or ""
    if name:find("BlackHole") then
      local nxt = (i + 1 < n) and (reaper.GetInputChannelName(i + 1) or "") or ""
      if nxt:find("BlackHole") then
        return 1024 + i
      end
      return i
    end
  end
  return nil
end

local function ensure_session_track()
  local tr, idx = find_session_track()
  if tr then return tr, idx end

  reaper.Undo_BeginBlock()
  idx = reaper.CountTracks(0)
  reaper.InsertTrackAtIndex(idx, true)
  tr = reaper.GetTrack(0, idx)
  reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", TRACK_NAME, true)

  local input = find_blackhole_input()
  if input then
    reaper.SetMediaTrackInfo_Value(tr, "I_RECINPUT", input)
  end
  reaper.SetMediaTrackInfo_Value(tr, "I_RECARM", 1)
  -- Monitoring off: the Take backend already plays the live stream to the
  -- engineer's output; monitoring here would double it.
  reaper.SetMediaTrackInfo_Value(tr, "I_RECMON", 0)
  reaper.Undo_EndBlock("Take: create session track", -1)
  reaper.UpdateArrange()
  return tr, idx
end

--------------------------------------------------------------------------------
-- Exports (only written when content changes)

local function build_tracks_json()
  local parts = {}
  for i = 0, reaper.CountTracks(0) - 1 do
    local tr = reaper.GetTrack(0, i)
    local _, name = reaper.GetTrackName(tr, "", 256)
    name = name:gsub('\\', '\\\\'):gsub('"', '\\"')
    parts[#parts + 1] = string.format('{"index":%d,"name":"%s"}', i, name)
  end
  return "[" .. table.concat(parts, ",") .. "]"
end

local function build_markers_json()
  local parts = {}
  local i = 0
  repeat
    local retval, isrgn, pos, _, name = reaper.EnumProjectMarkers(i)
    if retval > 0 and not isrgn then
      name = (name or ""):gsub('\\', '\\\\'):gsub('"', '\\"')
      parts[#parts + 1] = string.format('{"name":"%s","position":%.3f}', name, pos)
    end
    i = i + 1
  until retval == 0
  return "[" .. table.concat(parts, ",") .. "]"
end

local function export_if_changed()
  local tj = build_tracks_json()
  if tj ~= last_tracks_json then
    local f = io.open(TRACKS_FILE, "w")
    if f then f:write(tj) f:close() last_tracks_json = tj end
  end
  local mj = build_markers_json()
  if mj ~= last_markers_json then
    local f = io.open(MARKERS_FILE, "w")
    if f then f:write(mj) f:close() last_markers_json = mj end
  end
end

--------------------------------------------------------------------------------
-- Command handlers

local function handle_record()
  local tr, idx = ensure_session_track()
  reaper.SetMediaTrackInfo_Value(tr, "I_RECARM", 1)
  -- Save cursor position + actual track index so Python can request the swap
  local pos = reaper.GetCursorPosition()
  local f = io.open(START_FILE, "w")
  if f then
    f:write(string.format("%.6f\n%d\n", pos, idx))
    f:close()
  end
  reaper.Main_OnCommand(1013, 0)  -- Transport: Record
end

local function handle_stop()
  reaper.Main_OnCommand(1016, 0)  -- Transport: Stop
end

local function handle_rtz()
  reaper.SetEditCurPos(0, true, false)
  reaper.Main_OnCommand(40042, 0)  -- Transport: Go to start of project
end

local function handle_swap(filepath, track_idx, start_time)
  -- Prefer the Take Session track by name; the stored index is only a
  -- fallback in case the track was renamed between record and swap.
  local track = find_session_track()
  if not track then
    track = reaper.GetTrack(0, track_idx)
  end
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

--------------------------------------------------------------------------------
-- Main loop

local function poll_commands()
  local f = io.open(CMD_FILE, "r")
  if not f then return end
  local cmd   = f:read("*l") or ""
  local line2 = f:read("*l") or ""
  local line3 = f:read("*l") or ""
  local line4 = f:read("*l") or ""
  f:close()
  os.remove(CMD_FILE)

  if cmd == "record" then
    handle_record()  -- always targets the Take Session track
  elseif cmd == "stop" then
    handle_stop()
  elseif cmd == "rtz" then
    handle_rtz()
  elseif cmd == "swap" then
    -- line2 = filepath, line3 = track_idx, line4 = start_time
    handle_swap(line2, tonumber(line3) or 0, tonumber(line4) or 0)
  end
end

local function main()
  poll_commands()
  tick = tick + 1
  if tick % 30 == 0 then  -- roughly once per second
    ensure_session_track()
    export_if_changed()
  end
  reaper.defer(main)
end

ensure_session_track()
export_if_changed()
reaper.ShowConsoleMsg("Take: session script running — '" .. TRACK_NAME
                      .. "' track ready, listening on " .. CMD_FILE .. "\n")
main()
