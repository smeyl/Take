-- Take: all-in-one session script — auto-started by Reaper via __startup.lua
-- (installed by setup.sh)
--
-- What it does, continuously:
--   * polls /tmp/take_reaper_cmd for commands from the Python backend:
--       record\n{track_idx}
--                         — arm the track, save cursor pos, start recording
--       stop              — stop the transport
--       rtz               — return to zero (project start)
--       swap\n{filepath}\n{track_idx}\n{start_time}
--                         — replace the streamed item with the lossless file
--       bounce            — render with the most recent render settings, then
--                           write /tmp/take_bounce_done so bounce.py can send it
--   * exports the track list to /tmp/take_tracks.json whenever it changes
--   * exports markers to /tmp/take_markers.json whenever they change
--   * registers take_insert_media.lua as an action on startup and writes its
--     command ID to /tmp/take_insert_cmd_id (read by engineer.py) — no manual
--     action registration needed
--
-- Deliberately minimal: Take never changes track inputs or routing, and only
-- touches arm state at record time. The engineer owns the Reaper setup.

local CMD_FILE      = "/tmp/take_reaper_cmd"
local START_FILE    = "/tmp/take_record_start"
local TRACKS_FILE   = "/tmp/take_tracks.json"
local MARKERS_FILE  = "/tmp/take_markers.json"
local INSERT_ID_FILE = "/tmp/take_insert_cmd_id"
local BOUNCE_DONE_FILE = "/tmp/take_bounce_done"  -- written when a render finishes

local last_tracks_json  = nil
local last_markers_json = nil
local tick = 0

--------------------------------------------------------------------------------
-- Insert action self-registration

local function register_insert_action()
  local script = reaper.GetResourcePath() .. "/Scripts/take_insert_media.lua"
  -- Idempotent: re-adding an already-registered script returns its existing ID
  local cmd_id = reaper.AddRemoveReaScript(true, 0, script, true)
  if cmd_id and cmd_id ~= 0 then
    local named = reaper.ReverseNamedCommandLookup(cmd_id)
    if named then
      local f = io.open(INSERT_ID_FILE, "w")
      if f then
        f:write("_" .. named)  -- web API form: /_/_RS<hash>
        f:close()
        return true
      end
    end
  end
  return false
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
-- Transport commands

local function handle_record(track_idx)
  -- Arm only the target track, only now — inputs and other tracks are
  -- the engineer's business.
  local track = reaper.GetTrack(0, track_idx)
  if track then
    reaper.SetMediaTrackInfo_Value(track, "I_RECARM", 1)
  end
  -- Save cursor position + track index so Python can request the swap later
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
  -- Disarm the track we armed at record time — leave Reaper as we found it.
  -- Read (don't delete) START_FILE: the upcoming file swap still needs it.
  local f = io.open(START_FILE, "r")
  if f then
    f:read("*l")  -- skip position line
    local idx = tonumber(f:read("*l") or "") or 0
    f:close()
    local track = reaper.GetTrack(0, idx)
    if track then
      reaper.SetMediaTrackInfo_Value(track, "I_RECARM", 0)
    end
  end
end

local function handle_rtz()
  reaper.SetEditCurPos(0, true, false)
  reaper.Main_OnCommand(40042, 0)  -- Transport: Go to start of project
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

local function handle_bounce()
  os.remove(BOUNCE_DONE_FILE)  -- clear any prior signal before this render
  -- Render with the project's most recent render settings, no dialog. This is
  -- the same action bounce.py used to invoke over the Reaper web API (which
  -- 404s on this setup); run in-process, Main_OnCommand blocks until the
  -- render finishes, so the output file is complete once it returns.
  reaper.Main_OnCommand(42230, 0)
  -- Signal completion. bounce.py waits for this, then verifies + sends the file.
  local f = io.open(BOUNCE_DONE_FILE, "w")
  if f then
    f:write("done\n")
    f:close()
  end
end

--------------------------------------------------------------------------------
-- Main loop

local function poll_commands()
  -- Claim the file by renaming it first: Python writes atomically (tmp file +
  -- rename), so a visible CMD_FILE is always complete, and claiming it means
  -- a new command arriving between our read and delete can't be lost.
  local claimed = CMD_FILE .. ".claimed"
  if not os.rename(CMD_FILE, claimed) then return end
  local f = io.open(claimed, "r")
  if not f then return end
  local cmd   = f:read("*l") or ""
  local line2 = f:read("*l") or ""
  local line3 = f:read("*l") or ""
  local line4 = f:read("*l") or ""
  f:close()
  os.remove(claimed)

  if cmd == "record" then
    handle_record(tonumber(line2) or 0)
  elseif cmd == "stop" then
    handle_stop()
  elseif cmd == "rtz" then
    handle_rtz()
  elseif cmd == "swap" then
    -- line2 = filepath, line3 = track_idx, line4 = start_time
    handle_swap(line2, tonumber(line3) or 0, tonumber(line4) or 0)
  elseif cmd == "bounce" then
    handle_bounce()
  end
end

local function main()
  poll_commands()
  tick = tick + 1
  if tick % 30 == 0 then  -- roughly once per second
    export_if_changed()
  end
  reaper.defer(main)
end

local registered = register_insert_action()
export_if_changed()
reaper.ShowConsoleMsg("Take: session script running — listening on " .. CMD_FILE
                      .. (registered and ", insert action registered\n"
                                      or  ", WARNING: insert action not registered\n"))
main()
