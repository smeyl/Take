-- Take: all-in-one session script — auto-started by Reaper via __startup.lua
-- (installed by setup.sh)
--
-- What it does, continuously:
--   * polls /tmp/take_reaper_cmd for commands from the Python backend:
--       record\n{track_idx}
--                         — arm the track, save cursor pos, start recording.
--                           If Reaper is already recording (the engineer hit
--                           Record in Reaper and Take followed), only save the
--                           current position and recording track for the swap.
--       stop              — stop the transport (if recording)
--       rtz               — return to zero (project start)
--       swap\n{filepath}\n{track_idx}\n{start_time}
--                         — replace the streamed item with the lossless file
--       insert\n{filepath}\n{track_idx}
--                         — place a file on a track at the edit cursor (used
--                           when no swap position is known for a take)
--       bounce\n{tracks}  — render the master mix (entire project) to a unique
--                           MP3 in /tmp, then write the output path into
--                           /tmp/take_bounce_done so bounce.py can send it.
--                           {tracks} = comma-separated track indices to include
--                           (others are muted for the render); empty = all
--   * exports the track list to /tmp/take_tracks.json whenever it changes
--   * exports markers to /tmp/take_markers.json whenever they change
--   * exports transport state (position, playing, recording) to
--     /tmp/take_transport.json continuously — record_watcher.py follows the
--     recording flag, and a fresh mtime is also the liveness signal that this
--     script is running
--     (the Reaper web API 404s on this setup, so everything is file-based)
--
-- Deliberately minimal: Take never changes track inputs or routing, and only
-- touches arm state at record time. The engineer owns the Reaper setup.

local CMD_FILE      = "/tmp/take_reaper_cmd"
local START_FILE    = "/tmp/take_record_start"
local TRACKS_FILE   = "/tmp/take_tracks.json"
local MARKERS_FILE  = "/tmp/take_markers.json"
local TRANSPORT_FILE = "/tmp/take_transport.json"
local BOUNCE_DONE_FILE = "/tmp/take_bounce_done"  -- written when a render finishes

local last_tracks_json    = nil
local last_markers_json   = nil
local last_transport_json = nil
local tick = 0
local take_armed_idx = nil  -- track Take armed itself; nil = arm state is the engineer's

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

-- Transport state for timecode.py (which forwards it to the artist over UDP).
-- Written atomically (tmp + rename) so Python can never read a partial file,
-- on every change plus at least once a second — the mtime doubles as the
-- "take_session.lua is alive" heartbeat checked by reaper.script_alive().
local function export_transport(force)
  local state   = reaper.GetPlayState()          -- bitmask: 1=play, 2=pause, 4=rec
  -- Paused counts as NOT playing — the artist's backing player must pause too.
  local playing = (state & 1) == 1 and (state & 2) == 0
  local recording = (state & 4) == 4
  local pos     = playing and reaper.GetPlayPosition() or reaper.GetCursorPosition()
  local tj = string.format('{"pos":%.3f,"playing":%s,"recording":%s}', pos,
                           playing and "true" or "false", recording and "true" or "false")
  if tj == last_transport_json and not force then return end
  local tmp = TRANSPORT_FILE .. ".tmp"
  local f = io.open(tmp, "w")
  if f then
    f:write(tj)
    f:close()
    os.rename(tmp, TRANSPORT_FILE)
    last_transport_json = tj
  end
end

--------------------------------------------------------------------------------
-- Transport commands

local function is_recording()
  return (reaper.GetPlayState() & 4) == 4
end

local function first_armed_track()
  for i = 0, reaper.CountTracks(0) - 1 do
    if reaper.GetMediaTrackInfo_Value(reaper.GetTrack(0, i), "I_RECARM") == 1 then
      return i
    end
  end
  return nil
end

-- Save timeline position + track index so Python can request the swap later
local function write_start(pos, track_idx)
  local f = io.open(START_FILE, "w")
  if f then
    f:write(string.format("%.6f\n%d\n", pos, track_idx))
    f:close()
  end
end

local function handle_record(track_idx)
  if is_recording() then
    -- The engineer started recording from Reaper's own transport and Take is
    -- only now (after the artist's countdown) starting the lossless capture.
    -- Save where on the timeline that capture begins, on the track Reaper is
    -- actually recording, so the swap lands in sync. Arm state and the
    -- transport are the engineer's — don't touch them.
    write_start(reaper.GetPlayPosition(), first_armed_track() or track_idx)
    return
  end
  -- Arm only the target track, only now — inputs and other tracks are
  -- the engineer's business.
  local track = reaper.GetTrack(0, track_idx)
  if track then
    reaper.SetMediaTrackInfo_Value(track, "I_RECARM", 1)
    take_armed_idx = track_idx
  end
  write_start(reaper.GetCursorPosition(), track_idx)
  reaper.Main_OnCommand(1013, 0)  -- Transport: Record
end

local function handle_stop()
  -- Only stop an active recording: when the engineer stopped Reaper first,
  -- this arrives afterwards and must not stop playback they've since started.
  if is_recording() then
    reaper.Main_OnCommand(1016, 0)  -- Transport: Stop
  end
  -- Disarm only a track Take armed itself — leave Reaper as we found it.
  -- START_FILE stays: the upcoming file swap still needs it.
  if take_armed_idx then
    local track = reaper.GetTrack(0, take_armed_idx)
    if track then
      reaper.SetMediaTrackInfo_Value(track, "I_RECARM", 0)
    end
    take_armed_idx = nil
  end
end

local function handle_rtz()
  reaper.SetEditCurPos(0, true, false)
  reaper.Main_OnCommand(40042, 0)  -- Transport: Go to start of project
end

local function handle_swap(filepath, track_idx, start_time)
  local track = reaper.GetTrack(0, track_idx)
  if not track then return end
  -- Find the BlackHole-recorded item this take belongs to and remove it. The
  -- lossless capture can start inside that item rather than at its start
  -- (Reaper-initiated recording rolls through the artist's countdown), so
  -- match an item that spans start_time, with 2 s of slack before it.
  for i = reaper.GetTrackNumMediaItems(track) - 1, 0, -1 do
    local item     = reaper.GetTrackMediaItem(track, i)
    local item_pos = reaper.GetMediaItemInfo_Value(item, "D_POSITION")
    local item_len = reaper.GetMediaItemInfo_Value(item, "D_LENGTH")
    if start_time > item_pos - 2.0 and start_time < item_pos + item_len then
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

local function handle_insert(filepath, track_idx)
  -- Place a file on a track at the edit cursor — the fallback when no swap
  -- position is known (first take of a session, or manual re-sync).
  local track = reaper.GetTrack(0, track_idx)
  if track then
    reaper.SetOnlyTrackSelected(track)
  end
  reaper.InsertMedia(filepath, 0)
  reaper.UpdateArrange()
end

local function handle_bounce(tracks_csv)
  os.remove(BOUNCE_DONE_FILE)  -- clear any prior signal before this render
  -- Track selection: mute every track not in the list for the duration of the
  -- render, then restore. Empty list = include all tracks.
  local selected = {}
  local any_selected = false
  for s in string.gmatch(tracks_csv or "", "[^,]+") do
    local idx = tonumber(s)
    if idx then
      selected[idx] = true
      any_selected = true
    end
  end
  local saved_mutes = {}  -- track_idx -> original B_MUTE, only for tracks we mute
  if any_selected then
    for i = 0, reaper.CountTracks(0) - 1 do
      local tr = reaper.GetTrack(0, i)
      if not selected[i] and reaper.GetMediaTrackInfo_Value(tr, "B_MUTE") == 0 then
        saved_mutes[i] = 0
        reaper.SetMediaTrackInfo_Value(tr, "B_MUTE", 1)
      end
    end
  end
  -- Render to a unique file in /tmp: a fresh name every bounce means Reaper can
  -- never raise its "file already exists" overwrite prompt (nothing watches for
  -- that dialog, so it would wedge the automated flow). Point the render at the
  -- master mix of the entire project as MP3 — don't rely on whatever the
  -- project's last manual render settings happened to be.
  local name   = os.date("session_BT_%Y%m%d_%H%M%S")
  local output = "/tmp/" .. name .. ".mp3"
  local _, prev_dir = reaper.GetSetProjectInfo_String(0, "RENDER_FILE", "", false)
  local _, prev_pat = reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", "", false)
  local _, prev_fmt = reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", "", false)
  local prev_src    = reaper.GetSetProjectInfo(0, "RENDER_SETTINGS", 0, false)
  local prev_bounds = reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 0, false)
  reaper.GetSetProjectInfo_String(0, "RENDER_FILE", "/tmp", true)
  reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", name, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", "l3pm", true)  -- MP3 (LAME)
  reaper.GetSetProjectInfo(0, "RENDER_SETTINGS", 0, true)    -- master mix
  reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 1, true)  -- entire project
  -- Main_OnCommand blocks until the render finishes, so the output file is
  -- complete once it returns.
  reaper.Main_OnCommand(42230, 0)
  -- Restore the project's own render settings — the engineer owns the setup.
  reaper.GetSetProjectInfo_String(0, "RENDER_FILE", prev_dir, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", prev_pat, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", prev_fmt, true)
  reaper.GetSetProjectInfo(0, "RENDER_SETTINGS", prev_src, true)
  reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", prev_bounds, true)
  -- Unmute the tracks we muted for the selection — leave Reaper as we found it.
  for i in pairs(saved_mutes) do
    local tr = reaper.GetTrack(0, i)
    if tr then
      reaper.SetMediaTrackInfo_Value(tr, "B_MUTE", 0)
    end
  end
  -- Signal completion with the actual output path. bounce.py reads the path
  -- from this file, then verifies + sends it.
  local f = io.open(BOUNCE_DONE_FILE, "w")
  if f then
    f:write(output .. "\n")
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
  elseif cmd == "insert" then
    -- line2 = filepath, line3 = track_idx
    handle_insert(line2, tonumber(line3) or 0)
  elseif cmd == "bounce" then
    -- line2 = comma-separated track indices (empty = all)
    handle_bounce(line2)
  end
end

local function main()
  poll_commands()
  tick = tick + 1
  export_transport(tick % 30 == 0)  -- forced write ~1/s = liveness heartbeat
  if tick % 30 == 0 then  -- roughly once per second
    export_if_changed()
  end
  reaper.defer(main)
end

export_if_changed()
export_transport(true)
reaper.ShowConsoleMsg("Take: session script running — listening on " .. CMD_FILE .. "\n")
main()
