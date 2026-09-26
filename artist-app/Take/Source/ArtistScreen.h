#pragma once
#include <JuceHeader.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/select.h>
#include <cerrno>
#include <cmath>
#include <functional>
#include <thread>
#include <string>
#include <vector>

// The artist's main window — built to docs/artist-window.html (400 x 640).
// Positions below are the reference's, measured in the browser; the header
// leaves 80 px on the left for the macOS window buttons (Main.cpp places them).

//==============================================================================
namespace TakeUI
{
    // Colour tokens from the reference (and the engineer app).
    namespace Col
    {
        const juce::Colour bg      { 0xFF0A0A0B };
        const juce::Colour surface { 0xFF111113 };
        const juce::Colour sunken  { 0xFF0D0D0F };
        const juce::Colour line    { 0xFF1C1C1F };
        const juce::Colour line2   { 0xFF2A2A2E };
        const juce::Colour text    { 0xFFE8E8EA };
        const juce::Colour text2   { 0xFFC4C4C8 };
        const juce::Colour text3   { 0xFF9A9AA0 };
        const juce::Colour muted   { 0xFF6B6B70 };
        const juce::Colour faint   { 0xFF4D4D52 };
        const juce::Colour ghost   { 0xFF38383C };
        const juce::Colour teal    { 0xFF2DD4BF };
        const juce::Colour blue    { 0xFF4F8FFF };
        const juce::Colour purple  { 0xFFA78BFA };
        const juce::Colour amber   { 0xFFE7B23E };
        const juce::Colour red     { 0xFFF76464 };
    }

    enum class Weight { regular, medium, semibold, bold };

    // IBM Plex Mono (embedded, BinaryData) at a CSS pixel size; letterSpacing
    // in px, as the reference's CSS gives it.
    inline juce::Font font (float px, Weight weight = Weight::regular, float letterSpacing = 0.0f)
    {
        static const juce::Typeface::Ptr faces[] = {
            juce::Typeface::createSystemTypefaceFor (BinaryData::IBMPlexMonoRegular_ttf,  (size_t) BinaryData::IBMPlexMonoRegular_ttfSize),
            juce::Typeface::createSystemTypefaceFor (BinaryData::IBMPlexMonoMedium_ttf,   (size_t) BinaryData::IBMPlexMonoMedium_ttfSize),
            juce::Typeface::createSystemTypefaceFor (BinaryData::IBMPlexMonoSemiBold_ttf, (size_t) BinaryData::IBMPlexMonoSemiBold_ttfSize),
            juce::Typeface::createSystemTypefaceFor (BinaryData::IBMPlexMonoBold_ttf,     (size_t) BinaryData::IBMPlexMonoBold_ttfSize),
        };
        juce::Font f (juce::FontOptions (faces[(int) weight]).withPointHeight (px));
        if (letterSpacing != 0.0f)
            f.setExtraKerningFactor (letterSpacing / f.getHeight());  // JUCE tracking is a fraction of height
        return f;
    }

    inline float textWidth (const juce::Font& f, const juce::String& s)
    {
        return juce::GlyphArrangement::getStringWidth (f, s);
    }

    inline void text (juce::Graphics& g, const juce::String& s, const juce::Font& f, juce::Colour c,
                      juce::Rectangle<float> r, juce::Justification j = juce::Justification::centredLeft)
    {
        g.setFont (f);
        g.setColour (c);
        g.drawText (s, r, j, false);
    }

    // Read the relay host from the session file written by start_artist.py.
    // Falls back to 127.0.0.1 for single-machine dev.
    inline juce::String readRelayHost()
    {
        auto f = juce::File ("/tmp/take_session.json");
        if (! f.existsAsFile()) return "127.0.0.1";
        auto json = juce::JSON::parse (f.loadFileAsString());
        auto ip = json["engineer_ip"].toString();
        if (ip.isEmpty() || ip.startsWith ("127.") || ip == "localhost")
            return "127.0.0.1";
        return ip;
    }

    // M:SS
    inline juce::String formatMinSec (float seconds)
    {
        int s = juce::jmax (0, juce::roundToInt (seconds));
        return juce::String (s / 60) + ":" + juce::String (s % 60).paddedLeft ('0', 2);
    }

    // Plain POSIX HTTP/1.0 request (juce::URL asserts on connection failures).
    // Returns the status code, or 0 if the server couldn't be reached.
    inline int http (const juce::String& host, int port, const char* method, const juce::String& path,
                     int timeoutMs, juce::String* responseBody = nullptr, const juce::String& jsonBody = {})
    {
        int fd = ::socket (AF_INET, SOCK_STREAM, 0);
        if (fd < 0) return 0;

        struct timeval tv { timeoutMs / 1000, (timeoutMs % 1000) * 1000 };
        ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));
        ::setsockopt (fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof (tv));

        struct sockaddr_in addr {};
        addr.sin_family = AF_INET;
        addr.sin_port   = htons ((uint16_t) port);
        ::inet_pton (AF_INET, host.toRawUTF8(), &addr.sin_addr);

        // connect() ignores the socket timeouts and can block for a minute on
        // an unreachable host: connect non-blocking and wait at most timeoutMs.
        const int flags = ::fcntl (fd, F_GETFL, 0);
        ::fcntl (fd, F_SETFL, flags | O_NONBLOCK);
        if (::connect (fd, (struct sockaddr*) &addr, sizeof (addr)) < 0)
        {
            fd_set w;
            FD_ZERO (&w);
            FD_SET (fd, &w);
            struct timeval ct { timeoutMs / 1000, (timeoutMs % 1000) * 1000 };
            int err = 0;
            socklen_t len = sizeof (err);
            if (errno != EINPROGRESS || ::select (fd + 1, nullptr, &w, nullptr, &ct) != 1
                || ::getsockopt (fd, SOL_SOCKET, SO_ERROR, &err, &len) < 0 || err != 0)
            {
                ::close (fd);
                return 0;
            }
        }
        ::fcntl (fd, F_SETFL, flags);

        const auto body = jsonBody.toStdString();
        const auto req = juce::String (method) + " " + path + " HTTP/1.0\r\nHost: " + host
                         + "\r\nContent-Type: application/json\r\nContent-Length: "
                         + juce::String ((int) body.size()) + "\r\nConnection: close\r\n\r\n";
        ::send (fd, req.toRawUTF8(), req.getNumBytesAsUTF8(), 0);
        if (! body.empty())
            ::send (fd, body.data(), body.size(), 0);

        juce::MemoryBlock buf;
        char tmp[1024];
        ssize_t n;
        while ((n = ::recv (fd, tmp, sizeof (tmp), 0)) > 0)
            buf.append (tmp, (size_t) n);
        ::close (fd);

        const auto full = juce::String::fromUTF8 (static_cast<const char*> (buf.getData()), (int) buf.getSize());
        if (! full.startsWith ("HTTP/")) return 0;
        const int status = full.fromFirstOccurrenceOf (" ", false, false)
                               .upToFirstOccurrenceOf (" ", false, false).getIntValue();
        if (responseBody != nullptr)
        {
            const int sep = full.indexOf ("\r\n\r\n");
            *responseBody = sep >= 0 ? full.substring (sep + 4).trim() : juce::String();
        }
        return status;
    }

    inline juce::var getJson (const juce::String& host, int port, const juce::String& path, int timeoutMs)
    {
        juce::String body;
        if (http (host, port, "GET", path, timeoutMs, &body) / 100 != 2) return {};
        return juce::JSON::parse (body);
    }

    // A background thread running `work` every `intervalMs`.
    class Poller : public juce::Thread
    {
    public:
        Poller (const juce::String& name, int intervalMs, std::function<void()> work)
            : juce::Thread (name), interval (intervalMs), fn (std::move (work)) {}
        ~Poller() override { stopThread (8000); }  // longest cycle: three 2.5 s requests
        void run() override
        {
            while (! threadShouldExit())
            {
                fn();
                wait (interval);
            }
        }
    private:
        int interval;
        std::function<void()> fn;
    };
}

//==============================================================================
class ArtistScreen : public juce::Component
{
    using Col    = juce::Colour;
    using Weight = TakeUI::Weight;

    struct Marker { juce::String name; float position; };  // position in seconds

    //==========================================================================
    // Record ring: READY / 3-2-1 / REC with the take number.
    class RecordRing : public juce::Component
    {
    public:
        static constexpr float kRing = 104.0f, kPad = 16.0f;  // pad = room for the glow
        int  countdown { 0 };      // seconds left, 0 = not counting
        bool recording { false };  // capture running (after the countdown)
        int  take      { 1 };

        void paint (juce::Graphics& g) override
        {
            namespace C = TakeUI::Col;
            const auto c   = getLocalBounds().toFloat().getCentre();
            const float r  = kRing / 2.0f;
            const bool rec = recording && countdown == 0;
            const auto ring = rec ? C::red : C::blue;

            auto disc = [&] (float radius, juce::Colour col)
            {
                g.setColour (col);
                g.fillEllipse (c.x - radius, c.y - radius, radius * 2.0f, radius * 2.0f);
            };
            if (rec)
            {
                disc (r + 14.0f, ring.withAlpha (0.05f));
                disc (r + 10.0f, ring.withAlpha (0.11f));
                disc (r + 5.0f,  ring.withAlpha (0.22f));
            }
            else
            {
                disc (r + 8.0f, ring.withAlpha (0.07f));
            }
            disc (r, C::surface);
            g.setColour (ring);
            g.drawEllipse (c.x - (r - 1.25f), c.y - (r - 1.25f), (r - 1.25f) * 2.0f, (r - 1.25f) * 2.0f, 2.5f);

            const float top = kPad;  // ring's top edge in this component
            if (countdown > 0)
            {
                TakeUI::text (g, juce::String (countdown), TakeUI::font (40.0f, Weight::bold, 0.68f), ring,
                              { 0.0f, c.y - 30.0f, (float) getWidth(), 60.0f }, juce::Justification::centred);
                return;
            }
            // Reference: label box at +34.3 (17 tall, 17px line), take at +55.3 (14.5 tall).
            TakeUI::text (g, rec ? "REC" : "READY", TakeUI::font (17.0f, Weight::bold, 0.68f),
                          Col (0xFFF0F0F8), { 0.0f, top + 34.3f - 2.55f, (float) getWidth(), 22.1f },
                          juce::Justification::centred);
            TakeUI::text (g, "T" + juce::String (take), TakeUI::font (11.0f), ring.withAlpha (0.75f),
                          { 0.0f, top + 55.3f, (float) getWidth(), 14.5f }, juce::Justification::centred);
        }
    };

    //==========================================================================
    // Input meter for the one input being recorded (the backend records a
    // single chosen input, never a mix): teal to -12 dB, amber to -6 dB, red above.
    class LevelMeter : public juce::Component
    {
    public:
        void setLevel (float level)
        {
            if (std::abs (level - db) > 0.05f)
            {
                db = level;
                repaint();
            }
        }

        void paint (juce::Graphics& g) override
        {
            drawRow (g, "IN", db, ((float) getHeight() - 14.0f) / 2.0f);
        }

    private:
        float db { -60.0f };

        void drawRow (juce::Graphics& g, const juce::String& ch, float db, float y)
        {
            namespace C = TakeUI::Col;
            const float w = (float) getWidth();
            TakeUI::text (g, ch, TakeUI::font (10.5f), C::muted, { 0.0f, y, 14.0f, 14.0f },
                          juce::Justification::centred);
            TakeUI::text (g, juce::String::fromUTF8 ("\xE2\x88\x92") + juce::String (juce::roundToInt (-db)) + " dB",
                          TakeUI::font (10.5f), C::muted, { w - 48.0f, y, 48.0f, 14.0f },
                          juce::Justification::centredRight);

            const juce::Rectangle<float> bar (22.0f, y + 4.0f, w - 22.0f - 8.0f - 48.0f, 6.0f);
            juce::Path clip;
            clip.addRoundedRectangle (bar, 2.0f);
            g.setColour (Col (0xFF18181C));
            g.fillPath (clip);

            const float f = juce::jlimit (0.0f, 1.0f, (db + 60.0f) / 60.0f);
            if (f <= 0.0f) return;
            juce::Graphics::ScopedSaveState save (g);
            g.reduceClipRegion (clip);
            constexpr float kAmber = 48.0f / 60.0f, kRed = 54.0f / 60.0f;
            auto seg = [&] (float from, float to, juce::Colour col)
            {
                if (f <= from) return;
                g.setColour (col);
                g.fillRect (bar.getX() + bar.getWidth() * from, bar.getY(),
                            bar.getWidth() * (juce::jmin (f, to) - from), bar.getHeight());
            };
            seg (0.0f, kAmber, C::teal);
            seg (kAmber, kRed, C::amber);
            seg (kRed, 1.0f, C::red);
        }
    };

    //==========================================================================
    // Backing track: header (label, engineer cursor, time), section strip,
    // waveform with markers / engineer cursor / playhead, ruler.
    class TrackView : public juce::Component
    {
    public:
        std::vector<Marker> markers;
        float duration  { 0.0f };   // 0 = no backing track loaded
        float playhead  { 0.0f };   // seconds
        float cursor    { -1.0f };  // engineer's cursor in the DAW, seconds; < 0 = unknown

        void paint (juce::Graphics& g) override
        {
            namespace C = TakeUI::Col;
            const float w = (float) getWidth();

            // Header row (12.5 tall)
            TakeUI::text (g, "BACKING TRACK", TakeUI::font (10.0f, Weight::regular, 1.0f), C::muted,
                          { 0.0f, 0.0f, 200.0f, 12.5f });
            float right = w;
            if (duration > 0.0f)
            {
                const auto t = TakeUI::formatMinSec (playhead) + " / " + TakeUI::formatMinSec (duration);
                const auto f = TakeUI::font (10.0f);
                TakeUI::text (g, t, f, C::faint, { 0.0f, 0.0f, w, 12.5f }, juce::Justification::centredRight);
                right -= TakeUI::textWidth (f, t) + 12.0f;
            }
            if (cursor >= 0.0f)
            {
                const auto t = "Engineer " + TakeUI::formatMinSec (cursor);
                const auto f = TakeUI::font (10.0f);
                const float tw = TakeUI::textWidth (f, t);
                TakeUI::text (g, t, f, C::amber, { right - tw, 0.0f, tw + 1.0f, 12.5f });
                const float dx = right - tw - 5.0f - 3.0f, dy = 6.25f - 1.0f;  // 6 px square turned 45°
                juce::Path d;
                d.addQuadrilateral (dx, dy - 4.24f, dx + 4.24f, dy, dx, dy + 4.24f, dx - 4.24f, dy);
                g.setColour (C::amber);
                g.fillPath (d);
            }

            // Box: 1 px border, radius 6
            const juce::Rectangle<float> box (0.0f, 20.5f, w, 88.0f);
            juce::Path clip;
            clip.addRoundedRectangle (box, 6.0f);
            {
                juce::Graphics::ScopedSaveState save (g);
                g.reduceClipRegion (clip);
                const auto inner = box.reduced (1.0f);
                drawSections (g, inner.withHeight (25.0f));
                g.setColour (C::line);
                g.fillRect (inner.getX(), inner.getY() + 25.0f, inner.getWidth(), 1.0f);
                drawWave  (g, { inner.getX(), inner.getY() + 26.0f, inner.getWidth(), 44.0f });
                drawRuler (g, { inner.getX(), inner.getY() + 70.0f, inner.getWidth(), 16.0f });
            }
            g.setColour (C::line);
            g.drawRoundedRectangle (box.reduced (0.5f), 5.5f, 1.0f);
        }

    private:
        int currentIndex() const
        {
            int cur = -1;
            for (int i = 0; i < (int) markers.size(); ++i)
                if (markers[(size_t) i].position <= playhead + 0.01f
                    && (cur < 0 || markers[(size_t) i].position >= markers[(size_t) cur].position))
                    cur = i;
            return cur;
        }

        void drawSections (juce::Graphics& g, juce::Rectangle<float> b)
        {
            namespace C = TakeUI::Col;
            g.setColour (C::surface);
            g.fillRect (b);
            if (markers.empty())
            {
                TakeUI::text (g, "No markers", TakeUI::font (9.5f), C::faint, b, juce::Justification::centred);
                return;
            }
            const int n = (int) markers.size(), cur = currentIndex();
            const float slot = b.getWidth() / (float) n;
            for (int i = 0; i < n; ++i)
            {
                const juce::Rectangle<float> r (b.getX() + slot * (float) i, b.getY(), slot, b.getHeight());
                if (i > 0)
                {
                    g.setColour (C::line);
                    g.fillRect (r.getX(), r.getY(), 1.0f, r.getHeight());
                }
                if (i == cur)
                {
                    g.setColour (C::blue.withAlpha (0.08f));
                    g.fillRect (r);
                    g.setColour (Col (0xFF24324D));
                    g.drawRect (r, 1.0f);
                    TakeUI::text (g, markers[(size_t) i].name, TakeUI::font (10.5f, Weight::semibold), C::blue,
                                  r.reduced (2.0f, 0.0f), juce::Justification::centred);
                }
                else
                {
                    TakeUI::text (g, markers[(size_t) i].name, TakeUI::font (9.5f), C::faint,
                                  r.reduced (2.0f, 0.0f), juce::Justification::centred);
                }
            }
        }

        void drawWave (juce::Graphics& g, juce::Rectangle<float> b)
        {
            namespace C = TakeUI::Col;
            g.setColour (C::sunken);
            g.fillRect (b);
            if (duration <= 0.0f)
            {
                TakeUI::text (g, juce::String::fromUTF8 ("Waiting for backing track\xE2\x80\xA6"),
                              TakeUI::font (10.0f), C::faint, b, juce::Justification::centred);
                return;
            }
            // Placeholder shape (as in the reference) — not the track's real audio.
            const float cy = b.getCentreY(), maxH = b.getHeight() * 0.4f;
            g.setColour (Col (0xFF34343F));
            for (float px = 1.0f; px < b.getWidth(); px += 3.0f)
            {
                const float t = px / b.getWidth();
                float a = (std::sin (t * 23.4f) * 0.5f + std::cos (t * 11.7f) * 0.3f + std::sin (t * 47.1f) * 0.2f) * 0.5f + 0.5f;
                a = juce::jlimit (0.06f, 1.0f, a) * maxH;
                g.fillRect (b.getX() + px - 0.7f, cy - a, 1.4f, a * 2.0f);
            }
            auto xAt = [&] (float sec) { return b.getX() + b.getWidth() * juce::jlimit (0.0f, 1.0f, sec / duration); };

            g.setColour (C::blue.withAlpha (0.28f));
            for (const auto& m : markers)
                if (m.position > 0.0f)
                    g.fillRect (xAt (m.position) - 0.5f, b.getY(), 1.0f, b.getHeight());

            g.setColour (C::blue);
            g.fillRect (xAt (playhead) - 0.8f, b.getY(), 1.6f, b.getHeight());

            if (cursor >= 0.0f)  // the engineer's cursor in the DAW, live
            {
                const float x = xAt (cursor);
                g.setColour (C::amber);
                g.fillRect (x - 0.75f, b.getY(), 1.5f, b.getHeight());
                juce::Path tri;
                tri.addTriangle (x - 4.25f, b.getY(), x + 4.25f, b.getY(), x, b.getY() + 6.0f);
                g.fillPath (tri);
            }
        }

        void drawRuler (juce::Graphics& g, juce::Rectangle<float> b)
        {
            namespace C = TakeUI::Col;
            g.setColour (C::sunken);
            g.fillRect (b);
            g.setColour (C::line);
            g.fillRect (b.getX(), b.getY(), b.getWidth(), 1.0f);
            if (duration <= 0.0f) return;
            const auto f = TakeUI::font (8.5f);
            for (int i = 0; i <= 4; ++i)
            {
                const auto s = TakeUI::formatMinSec (duration * (float) i / 4.0f);
                const float tw = TakeUI::textWidth (f, s);
                float x = b.getX() + b.getWidth() * (float) i / 4.0f - tw / 2.0f;
                if (i == 0) x = b.getX() + 4.0f;
                if (i == 4) x = b.getRight() - 4.0f - tw;
                TakeUI::text (g, s, f, C::ghost, { x, b.getY() + 4.0f, tw + 1.0f, 11.0f });
            }
        }
    };

    //==========================================================================
    // Now / Next section card.
    class NowCard : public juce::Component
    {
    public:
        std::vector<Marker> markers;
        float playhead { 0.0f };

        void paint (juce::Graphics& g) override
        {
            namespace C = TakeUI::Col;
            const auto b = getLocalBounds().toFloat();
            g.setColour (C::surface);
            g.fillRoundedRectangle (b.reduced (0.5f), 8.0f);
            g.setColour (C::line);
            g.drawRoundedRectangle (b.reduced (0.5f), 8.0f, 1.0f);

            int cur = -1, next = -1;
            for (int i = 0; i < (int) markers.size(); ++i)
            {
                const float p = markers[(size_t) i].position;
                if (p <= playhead + 0.01f) { if (cur < 0 || p >= markers[(size_t) cur].position) cur = i; }
                else if (next < 0 || p < markers[(size_t) next].position) next = i;
            }
            const juce::String now = markers.empty() ? "No markers"
                                   : cur >= 0 ? markers[(size_t) cur].name
                                              : juce::String::fromUTF8 ("\xE2\x80\x94");

            const auto tagF = TakeUI::font (9.0f, Weight::regular, 1.26f);
            TakeUI::text (g, "NOW", tagF, C::muted, { 15.0f, 8.8f, 30.0f, 11.5f });
            TakeUI::text (g, now, TakeUI::font (15.0f, Weight::semibold), markers.empty() ? C::muted : C::blue,
                          { 45.0f, 2.3f, 200.0f, 19.5f });

            if (next < 0) return;
            const auto inF = TakeUI::font (11.0f);
            const auto inS = "~" + juce::String (juce::jmax (0, juce::roundToInt (markers[(size_t) next].position - playhead))) + "s";
            const auto name = markers[(size_t) next].name;
            float x = b.getWidth() - 15.0f - TakeUI::textWidth (inF, inS);
            TakeUI::text (g, inS, inF, C::faint, { x, 4.8f, TakeUI::textWidth (inF, inS) + 1.0f, 14.5f });
            x -= 8.0f + TakeUI::textWidth (inF, name);
            TakeUI::text (g, name, inF, C::text3, { x, 4.8f, TakeUI::textWidth (inF, name) + 1.0f, 14.5f });
            x -= 8.0f + TakeUI::textWidth (tagF, "NEXT");
            TakeUI::text (g, "NEXT", tagF, C::muted, { x, 7.3f, 30.0f, 11.5f });
        }
    };

    //==========================================================================
    // The six cue knobs. Dragging one sets the artist's own cue mix; the
    // engineer's changes arrive through the /cue/params poll.
    class CueMixPanel : public juce::Component
    {
    public:
        CueMixPanel()
        {
            knobs[0] = { "Reverb",  "reverb",      0.0f, TakeUI::Col::teal };
            knobs[1] = { "Rev mix", "reverbMix",   0.0f, TakeUI::Col::teal };
            knobs[2] = { "Delay",   "delay",       0.0f, TakeUI::Col::blue };
            knobs[3] = { "Del mix", "delayMix",    0.0f, TakeUI::Col::blue };
            knobs[4] = { "Comp",    "compression", 0.0f, TakeUI::Col::purple };
            knobs[5] = { "Cue vol", "volume",    100.0f, TakeUI::Col::text };
        }

        void paint (juce::Graphics& g) override
        {
            TakeUI::text (g, "CUE MIX", TakeUI::font (10.0f, Weight::regular, 1.0f), TakeUI::Col::muted,
                          { 0.0f, 0.0f, 200.0f, 12.5f });
            for (int i = 0; i < 6; ++i)
            {
                const float cx = centreX (i);
                const auto& k = knobs[i];
                g.setColour (Col (0xFF0E0E10));
                g.fillEllipse (cx - 21.0f, kKnobY, 42.0f, 42.0f);
                g.setColour (k.colour);
                g.drawEllipse (cx - 20.0f, kKnobY + 1.0f, 40.0f, 40.0f, 2.0f);

                const float a = juce::degreesToRadians (-135.0f + k.value * 2.7f);
                const juce::Point<float> c (cx, kKnobY + 21.0f);
                juce::Path tick;
                tick.addRectangle (-1.0f, -16.0f, 2.0f, 13.0f);
                g.fillPath (tick, juce::AffineTransform::rotation (a).translated (c));

                TakeUI::text (g, k.label, TakeUI::font (9.5f), TakeUI::Col::text3,
                              { cx - 30.0f, 69.5f, 60.0f, 12.0f }, juce::Justification::centred);
            }
        }

        void mouseDown (const juce::MouseEvent& e) override
        {
            drag = -1;
            for (int i = 0; i < 6; ++i)
                if (e.position.getDistanceFrom ({ centreX (i), kKnobY + 21.0f }) <= 21.0f)
                    drag = i;
            if (drag >= 0) { dragY = e.position.y; dragFrom = knobs[drag].value; }
        }

        void mouseDrag (const juce::MouseEvent& e) override
        {
            if (drag < 0) return;
            knobs[drag].value = juce::jlimit (0.0f, 100.0f, dragFrom + (dragY - e.position.y));
            repaint();
        }

        void mouseUp (const juce::MouseEvent&) override
        {
            if (drag < 0) return;
            const auto path = juce::String ("/cue/local/") + knobs[drag].param + "/"
                              + juce::String (juce::roundToInt (knobs[drag].value));
            std::thread ([path] { TakeUI::http ("127.0.0.1", 5004, "POST", path, 1000); }).detach();
            drag = -1;
        }

        // A value from the backend (the engineer's change, or ours read back).
        void setParamValue (const juce::String& param, float value)
        {
            for (int i = 0; i < 6; ++i)
                if (param == knobs[i].param)
                {
                    if (i == drag) return;  // don't fight a live drag
                    value = juce::jlimit (0.0f, 100.0f, value);
                    if (std::abs (knobs[i].value - value) > 0.01f) { knobs[i].value = value; repaint(); }
                    return;
                }
        }

    private:
        struct Knob { const char* label; const char* param; float value; juce::Colour colour; };
        static constexpr float kKnobY = 22.5f;
        Knob  knobs[6];
        int   drag { -1 };
        float dragY { 0.0f }, dragFrom { 0.0f };

        float centreX (int i) const
        {
            const float col = ((float) getWidth() - 5.0f * 4.0f) / 6.0f;  // 6 columns, 4 px gaps
            return (float) i * (col + 4.0f) + col / 2.0f;
        }
    };

    //==========================================================================
    class EndSessionButton : public juce::Component
    {
    public:
        std::function<void()> onClick;
        void paint (juce::Graphics& g) override
        {
            const auto b = getLocalBounds().toFloat().reduced (0.5f);
            if (isMouseOver())
            {
                g.setColour (Col (0xFF161618));
                g.fillRoundedRectangle (b, 8.0f);
            }
            g.setColour (TakeUI::Col::line2);
            g.drawRoundedRectangle (b, 8.0f, 1.0f);
            TakeUI::text (g, "End Session", TakeUI::font (12.0f, Weight::medium), Col (0xFFD4D4D6),
                          getLocalBounds().toFloat(), juce::Justification::centred);
        }
        void mouseEnter (const juce::MouseEvent&) override { repaint(); }
        void mouseExit  (const juce::MouseEvent&) override { repaint(); }
        void mouseUp (const juce::MouseEvent& e) override
        {
            if (getLocalBounds().contains (e.getPosition()) && onClick) onClick();
        }
    };

public:
    //==========================================================================
    std::function<void()> onBack;

    ArtistScreen()
    {
        setOpaque (true);
        for (auto* c : std::initializer_list<juce::Component*> { &ring, &meter, &track, &nowCard, &cueMix, &endButton })
            addAndMakeVisible (c);

        endButton.onClick = [this]
        {
            const auto host = relayHost, code = relayCode;
            if (code.isNotEmpty())
                std::thread ([host, code] { TakeUI::http (host, 5010, "DELETE", "/session/" + code, 2000); }).detach();
            if (onBack) onBack();
        };

        juce::Component::SafePointer<ArtistScreen> safe (this);

        // Local backend (this machine): transport state, engineer cursor, levels.
        localPoller = std::make_unique<TakeUI::Poller> ("TakeLocal", 100, [safe]
        {
            const auto st  = TakeUI::getJson ("127.0.0.1", 5004, "/status", 300);
            const auto lvl = TakeUI::getJson ("127.0.0.1", 5004, "/levels", 300);
            juce::MessageManager::callAsync ([safe, st, lvl]
            {
                if (safe != nullptr) safe->applyLocal (st, lvl);
            });
        });
        cuePoller = std::make_unique<TakeUI::Poller> ("TakeCue", 250, [safe]
        {
            const auto params = TakeUI::getJson ("127.0.0.1", 5004, "/cue/params", 300);
            if (! params.isObject()) return;
            juce::MessageManager::callAsync ([safe, params]
            {
                if (safe == nullptr) return;
                if (auto* obj = params.getDynamicObject())
                    for (auto& p : obj->getProperties())
                        safe->cueMix.setParamValue (p.name.toString(), (float) (double) p.value);
            });
        });
        localPoller->startThread();
        cuePoller->startThread();
    }

    ~ArtistScreen() override
    {
        for (auto* p : { &localPoller, &cuePoller, &timecodePoller, &relayPoller, &markersPoller, &heartbeat })
            p->reset();
    }

    void setSessionCode (const juce::String& code) { sessionCode = code; repaint(); }

    // Called once after joining: starts everything that talks to the relay on
    // the engineer's machine.
    void setEngineerIP (const juce::String& ip, const juce::String& code)
    {
        if (ip.isEmpty() || code.isEmpty()) return;
        relayHost = ip;
        relayCode = code;
        juce::Component::SafePointer<ArtistScreen> safe (this);

        // Session file read by start_artist.py — relay host + code bootstrap
        juce::File ("/tmp/take_session.json")
            .replaceWithText ("{\"engineer_ip\":\"" + ip + "\",\"code\":\"" + code
                              + "\",\"written_at\":" + juce::String (juce::Time::currentTimeMillis()) + "}");

        heartbeat = std::make_unique<TakeUI::Poller> ("TakeHeartbeat", 5000, [ip, code]
        {
            TakeUI::http (ip, 5010, "POST", "/session/" + code + "/heartbeat", 3000, nullptr, "{\"role\":\"artist\"}");
        });
        timecodePoller = std::make_unique<TakeUI::Poller> ("TakeTimecode", 100, [safe, ip]
        {
            const auto tc = TakeUI::getJson (ip, 5010, "/timecode", 300);
            if (! tc.isObject()) return;
            const float pos = (float) (double) tc["pos"];
            const bool playing = (bool) tc["playing"];
            juce::MessageManager::callAsync ([safe, pos, playing]
            {
                if (safe != nullptr) safe->applyTimecode (pos, playing);
            });
        });
        // Engineer heartbeat, the DAW's state and its armed track.
        relayPoller = std::make_unique<TakeUI::Poller> ("TakeRelay", 1000, [safe, ip, code]
        {
            const auto session = TakeUI::getJson (ip, 5010, "/session/" + code + "/status", 1500);
            const auto daw     = TakeUI::getJson (ip, 5010, "/reaper/status", 2500);
            const auto tracks  = TakeUI::getJson (ip, 5010, "/tracks", 2500);
            juce::MessageManager::callAsync ([safe, session, daw, tracks]
            {
                if (safe != nullptr) safe->applyRelay (session, daw, tracks);
            });
        });
        markersPoller = std::make_unique<TakeUI::Poller> ("TakeMarkers", 5000, [safe, ip]
        {
            const auto arr = TakeUI::getJson (ip, 5010, "/markers", 2500);
            if (! arr.isArray()) return;
            std::vector<Marker> m;
            for (const auto& item : *arr.getArray())
                if (item.isObject())
                    m.push_back ({ item["name"].toString(), (float) (double) item["position"] });
            juce::MessageManager::callAsync ([safe, m]
            {
                if (safe == nullptr) return;
                safe->track.markers = m;
                safe->nowCard.markers = m;
                safe->track.repaint();
                safe->nowCard.repaint();
            });
        });
        for (auto* p : { heartbeat.get(), timecodePoller.get(), relayPoller.get(), markersPoller.get() })
            p->startThread();
    }

    void paint (juce::Graphics& g) override
    {
        namespace C = TakeUI::Col;
        const float w = (float) getWidth();
        g.fillAll (C::bg);

        // Header: mark + wordmark, session code
        {
            const float cx = 89.0f, cy = 21.5f, r = 5.4f;
            g.setColour (C::teal.withAlpha (0.15f));
            g.fillEllipse (cx - r, cy - r, r * 2.0f, r * 2.0f);
            g.setColour (C::teal);
            g.drawEllipse (cx - r, cy - r, r * 2.0f, r * 2.0f, 1.62f);
            TakeUI::text (g, "TAKE", TakeUI::font (13.0f, Weight::semibold, 0.39f), C::text, { 106.0f, 13.0f, 60.0f, 17.0f });

            const auto codeF  = TakeUI::font (13.0f, Weight::semibold, 0.65f);
            const auto labelF = TakeUI::font (9.5f, Weight::regular, 1.33f);
            const float codeW = TakeUI::textWidth (codeF, sessionCode);
            TakeUI::text (g, sessionCode, codeF, Col (0xFFF2F2F3), { w - 16.0f - codeW, 13.0f, codeW + 2.0f, 17.0f });
            const float labelW = TakeUI::textWidth (labelF, "SESSION");
            TakeUI::text (g, "SESSION", labelF, C::muted, { w - 16.0f - codeW - 8.0f - labelW, 17.0f, labelW + 2.0f, 12.0f });
        }
        hline (g, 43.0f);

        // Connections
        drawConnRow (g, 56.0f, "Engineer", {}, engineerStatus());
        drawConnRow (g, 84.0f, dawName, dawSub(), dawStatus());
        hline (g, 114.0f);

        hline (g, 295.0f);            // under the meters
        hline (g, 464.0f);            // above the cue mix
        hline (g, (float) getHeight() - 65.0f);  // above the footer
    }

    void resized() override
    {
        const int w = getWidth();
        const auto pad = (int) RecordRing::kPad;
        ring.setBounds (w / 2 - 52 - pad, 129 - pad, 104 + pad * 2, 104 + pad * 2);
        meter.setBounds (20, 247, w - 40, 34);
        track.setBounds (20, 308, w - 40, 109);
        nowCard.setBounds (20, 427, w - 40, 24);
        cueMix.setBounds (20, 478, w - 40, 84);
        endButton.setBounds (20, getHeight() - 52, w - 40, 36);
    }

private:
    //==========================================================================
    struct Status { juce::String text; juce::Colour colour; bool on; };

    // No local backend at all is reported on the Engineer row: without it
    // nothing reaches or leaves this machine.
    Status engineerStatus() const
    {
        namespace C = TakeUI::Col;
        if (! backendUp)     return { "Take backend not running", C::faint, false };
        if (engineerAlive)   return { "Connected", C::blue, true };
        return { "Not connected", C::faint, false };
    }

    Status dawStatus() const
    {
        namespace C = TakeUI::Col;
        if (! dawReachable) return { "Not running", C::faint, false };
        // Recording = the DAW is rolling and this machine is capturing the take.
        if (dawPlaying && capturing) return { "Recording", C::teal, true };
        if (dawPlaying)              return { "Playing", C::teal, true };
        return { "Connected", C::teal, true };
    }

    juce::String dawSub() const
    {
        if (! dawReachable) return {};
        if (armedTracks.isEmpty()) return "no track armed";
        return armedTracks[0] + (armedTracks.size() > 1 ? " +" + juce::String (armedTracks.size() - 1) : juce::String());
    }

    void drawConnRow (juce::Graphics& g, float y, const juce::String& name, const juce::String& sub, const Status& s)
    {
        namespace C = TakeUI::Col;
        const float w = (float) getWidth();
        const auto nameF = TakeUI::font (12.5f);
        const float nameW = TakeUI::textWidth (nameF, name);
        TakeUI::text (g, name, nameF, C::text2, { 20.0f, y + 0.8f, nameW + 2.0f, 16.5f });

        const auto statusF = TakeUI::font (11.0f);
        const float statusW = TakeUI::textWidth (statusF, s.text);
        const float statusX = w - 20.0f - statusW;
        TakeUI::text (g, s.text, statusF, s.colour, { statusX, y + 1.8f, statusW + 2.0f, 14.5f });
        g.setColour (s.on ? s.colour : C::faint);
        g.fillEllipse (statusX - 6.0f - 7.0f, y + 5.5f, 7.0f, 7.0f);

        if (sub.isNotEmpty())
        {
            const float subX = 20.0f + nameW + 8.0f;
            const float maxW = statusX - 13.0f - 12.0f - subX;
            TakeUI::text (g, sub, TakeUI::font (10.5f), C::muted, { subX, y + 2.8f, juce::jmax (0.0f, maxW), 14.0f });
        }
    }

    void hline (juce::Graphics& g, float y)
    {
        g.setColour (TakeUI::Col::line);
        g.fillRect (0.0f, y, (float) getWidth(), 1.0f);
    }

    //==========================================================================
    void applyLocal (const juce::var& st, const juce::var& lvl)
    {
        const bool up = st.isObject();
        bool changed = up != backendUp;
        backendUp = up;
        if (up)
        {
            const bool rec  = (bool) st["recording"];
            const int  cd   = (int) st["countdown"];
            const int  take = (int) st["take"];
            changed = changed || rec != capturing;
            capturing = rec;
            // Before a take: the next take's number; during it: this one's.
            ring.take      = rec ? juce::jmax (1, take) : take + 1;
            ring.countdown = rec ? cd : 0;
            ring.recording = rec;
            ring.repaint();

            const float dur = (float) (double) st["backing_duration"];
            const auto cur  = st["engineer_cursor"];
            const float cursor = cur.isVoid() || cur.isUndefined() ? -1.0f : (float) (double) cur;
            if (dur != track.duration || std::abs (cursor - track.cursor) > 0.0005f)
            {
                track.duration = dur;
                track.cursor   = cursor;
                track.repaint();
            }
        }
        if (lvl.isObject())
            meter.setLevel (juce::jlimit (-60.0f, 0.0f, (float) (double) lvl["level"]));
        if (changed) repaint (0, 44, getWidth(), 71);
    }

    void applyTimecode (float pos, bool playing)
    {
        if (playing != dawPlaying)
        {
            dawPlaying = playing;
            repaint (0, 44, getWidth(), 71);
        }
        if (std::abs (pos - track.playhead) > 0.001f)
        {
            track.playhead = pos;
            nowCard.playhead = pos;
            track.repaint();
            nowCard.repaint();
        }
    }

    void applyRelay (const juce::var& session, const juce::var& daw, const juce::var& tracks)
    {
        engineerAlive = session.isObject() && (bool) session["engineer"];
        dawReachable  = daw.isObject() && (bool) daw["reachable"];
        if (daw.isObject() && daw["name"].toString().isNotEmpty())
            dawName = daw["name"].toString();
        if (tracks.isArray())
        {
            armedTracks.clear();
            for (const auto& t : *tracks.getArray())
                if ((bool) t["armed"])
                    armedTracks.add (t["name"].toString());
        }
        repaint (0, 44, getWidth(), 71);
    }

    //==========================================================================
    juce::String sessionCode;
    juce::String relayHost { "127.0.0.1" }, relayCode;

    bool backendUp { false }, capturing { false };
    bool engineerAlive { false }, dawReachable { false }, dawPlaying { false };
    juce::String dawName { "Pro Tools" };
    juce::StringArray armedTracks;

    RecordRing       ring;
    LevelMeter       meter;
    TrackView        track;
    NowCard          nowCard;
    CueMixPanel      cueMix;
    EndSessionButton endButton;

    std::unique_ptr<TakeUI::Poller> localPoller, cuePoller, timecodePoller, relayPoller, markersPoller, heartbeat;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ArtistScreen)
};
