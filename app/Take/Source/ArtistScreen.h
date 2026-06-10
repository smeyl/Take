#pragma once
#include <JuceHeader.h>
#include "DetailsPanel.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <thread>
#include <string>
#include <vector>

//==============================================================================
namespace TakeUI
{
    inline juce::Font monoFont (float size, bool bold = false)
    {
        int style = bold ? juce::Font::bold : juce::Font::plain;
        return juce::Font (juce::Font::getDefaultMonospacedFontName(), size, style);
    }

    inline juce::String generateSessionCode()
    {
        juce::Random rng;
        auto pair = [&]() {
            return juce::String::charToString ((juce::juce_wchar) ('A' + rng.nextInt (26)))
                   + juce::String (rng.nextInt (10));
        };
        return pair() + " - " + pair() + " - " + pair();
    }
}

//==============================================================================
class ArtistScreen : public juce::Component,
                     public juce::Timer
{
    //==========================================================================
    struct Marker { juce::String name; float position; };  // position in seconds

    //==========================================================================
    class RecordRing : public juce::Component
    {
    public:
        bool isRecording   { false };
        int  takeNumber    { 1 };
        int  countdownValue { -1 };   // -1 = no countdown, 3/2/1 = counting

        void paint (juce::Graphics& g) override
        {
            auto body     = getLocalBounds().toFloat().reduced (3.0f);
            bool counting = countdownValue > 0;

            auto ringColour = (isRecording && !counting) ? juce::Colour (0xFFFF4F4F)
                                                         : juce::Colour (0xFF185FA5);

            if (isRecording && !counting)
            {
                g.setColour (ringColour.withAlpha (0.05f));
                g.fillEllipse (body.expanded (26.0f));
                g.setColour (ringColour.withAlpha (0.11f));
                g.fillEllipse (body.expanded (15.0f));
                g.setColour (ringColour.withAlpha (0.22f));
                g.fillEllipse (body.expanded (6.0f));
            }
            else
            {
                g.setColour (ringColour.withAlpha (0.07f));
                g.fillEllipse (body.expanded (8.0f));
            }

            g.setColour (juce::Colour (0xFF111113));
            g.fillEllipse (body);

            g.setColour (ringColour);
            g.drawEllipse (body, 2.5f);

            if (counting)
            {
                g.setFont (TakeUI::monoFont (40.0f, true));
                g.setColour (ringColour);
                g.drawText (juce::String (countdownValue),
                            getLocalBounds().translated (0, -8),
                            juce::Justification::centred);
            }
            else
            {
                g.setFont (TakeUI::monoFont (17.0f, true));
                g.setColour (juce::Colour (0xFFF0F0F8));
                g.drawText (isRecording ? "REC" : "READY",
                            getLocalBounds().translated (0, -8),
                            juce::Justification::centred);
            }

            g.setFont (TakeUI::monoFont (11.0f));
            g.setColour (ringColour.withAlpha (0.75f));
            g.drawText ("T" + juce::String (takeNumber),
                        getLocalBounds().translated (0, 16),
                        juce::Justification::centred);
        }

        bool hitTest (int x, int y) override
        {
            auto c  = getLocalBounds().getCentre();
            float r = getWidth() / 2.0f;
            float dx = x - c.x, dy = y - c.y;
            return (dx * dx + dy * dy) <= (r * r);
        }
    };

    //==========================================================================
    class LevelMeter : public juce::Component
    {
    public:
        void setLevel (float l, float r) { leftDb = l; rightDb = r; repaint(); }

        void paint (juce::Graphics& g) override
        {
            int rowH = getHeight() / 2;
            drawChannel (g, "L", leftDb,  getLocalBounds().removeFromTop    (rowH));
            drawChannel (g, "R", rightDb, getLocalBounds().removeFromBottom (rowH));
        }

    private:
        float leftDb  { -60.0f };
        float rightDb { -60.0f };

        void drawChannel (juce::Graphics& g, const juce::String& ch,
                          float db, juce::Rectangle<int> bounds)
        {
            g.setFont (TakeUI::monoFont (11.0f));

            auto labelR = bounds.removeFromLeft (20);
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (ch, labelR, juce::Justification::centred);

            auto dbR = bounds.removeFromRight (52);
            g.setColour (db >= -6.0f  ? juce::Colour (0xFFFF4F4F)
                       : db >= -12.0f ? juce::Colour (0xFFFFAA00)
                                      : juce::Colour (0xFF5C5C6E));
            g.drawText (juce::String (juce::roundToInt (db)) + " dB",
                        dbR, juce::Justification::centred);

            auto area = bounds.reduced (6, 0);
            auto bar  = juce::Rectangle<int> (area.getX(),
                                              area.getCentreY() - 3,
                                              area.getWidth(), 6);

            g.setColour (juce::Colour (0xFF18181C));
            g.fillRoundedRectangle (bar.toFloat(), 2.0f);

            float frac = juce::jlimit (0.0f, 1.0f, (db + 60.0f) / 60.0f);
            if (frac > 0.0f)
            {
                // Three discrete zones: green (-60 to -12), amber (-12 to -6), red (-6 to 0)
                constexpr float kGreenEnd = 48.0f / 60.0f;   // -12 dB
                constexpr float kAmberEnd = 54.0f / 60.0f;   // -6 dB

                struct Seg { float start; float end; juce::uint32 colour; };
                const Seg segs[] = {
                    { 0.0f,      kGreenEnd, 0xFF1D9E75 },
                    { kGreenEnd, kAmberEnd, 0xFFFFAA00 },
                    { kAmberEnd, 1.0f,      0xFFFF4F4F },
                };

                for (auto& s : segs)
                {
                    if (frac <= s.start) break;
                    float segX = bar.getX() + bar.getWidth() * s.start;
                    float segW = bar.getWidth() * (juce::jmin (frac, s.end) - s.start);
                    g.setColour (juce::Colour (s.colour));
                    g.fillRect (segX, (float) bar.getY(), segW, (float) bar.getHeight());
                }
            }
        }
    };

    //==========================================================================
    class TrackWindow : public juce::Component
    {
    public:
        float playheadPct   { 0.0f };
        bool  backingLoaded { false };
        float totalDuration { 64.0f };
        std::vector<Marker> markers;
        float punchIn     { 0.0f };
        float punchOut    { 0.0f };
        bool  punchActive { false };

        void setMarkers (const std::vector<Marker>& m) { markers = m; repaint(); }
        void setPunch   (float in, float out, bool active) { punchIn = in; punchOut = out; punchActive = active; repaint(); }

        void paint (juce::Graphics& g) override
        {
            constexpr int kSectH = 28, kWaveH = 48;
            auto b = getLocalBounds();
            drawSections (g, b.removeFromTop (kSectH));
            drawWaveform (g, b.removeFromTop (kWaveH));
            drawRuler    (g, b);
        }

        void resized() override {}

    private:
        void drawSections (juce::Graphics& g, juce::Rectangle<int> b)
        {
            g.setColour (juce::Colour (0xFF18181C));
            g.fillRect (b);

            if (markers.empty())
            {
                g.setFont (TakeUI::monoFont (10.0f));
                g.setColour (juce::Colour (0xFF3A3A48));
                g.drawText ("No markers", b, juce::Justification::centred);
                g.setColour (juce::Colour (0xFF1E1E24));
                g.drawHorizontalLine (b.getBottom() - 1, (float) b.getX(), (float) b.getRight());
                return;
            }

            const int   n           = (int) markers.size();
            const float slotW       = (float) b.getWidth() / (float) n;
            const float playheadSec = playheadPct * totalDuration;

            // current = last marker whose start position <= playhead
            int currentIdx = 0;
            for (int i = 0; i < n; ++i)
                if (markers[i].position <= playheadSec)
                    currentIdx = i;

            for (int i = 0; i < n; ++i)
            {
                int secX = b.getX() + (int) (slotW * (float) i);
                int secW = (i == n - 1) ? (b.getWidth() - (int) (slotW * (float) i)) : (int) slotW;
                auto r   = juce::Rectangle<int> (secX, b.getY(), secW, b.getHeight());

                g.setColour (juce::Colour (0xFF18181C));
                g.fillRect (r);

                if (i == currentIdx)
                {
                    g.setColour (juce::Colour (0xFF4F8FFF).withAlpha (0.08f));
                    g.fillRect (r);

                    auto cardR = r.reduced (1, 1);
                    g.setColour (juce::Colour (0xFF2A2A38));
                    g.drawRoundedRectangle (cardR.toFloat(), 3.0f, 1.0f);

                    g.setFont (TakeUI::monoFont (13.0f, true));
                    g.setColour (juce::Colour (0xFF4F8FFF));
                    g.drawText (markers[i].name, r, juce::Justification::centred);
                }
                else
                {
                    if (i > 0)
                    {
                        g.setColour (juce::Colour (0xFF1E1E24));
                        g.drawVerticalLine (secX, (float) b.getY(), (float) b.getBottom());
                    }

                    g.setFont (TakeUI::monoFont (10.0f));
                    g.setColour (juce::Colour (0xFF5C5C6E));
                    g.drawText (markers[i].name, r, juce::Justification::centred);
                }
            }

            g.setColour (juce::Colour (0xFF1E1E24));
            g.drawHorizontalLine (b.getBottom() - 1, (float) b.getX(), (float) b.getRight());
        }

        void drawWaveform (juce::Graphics& g, juce::Rectangle<int> b)
        {
            g.setColour (juce::Colour (0xFF0D0D0F));
            g.fillRect (b);

            if (!backingLoaded)
            {
                g.setFont (TakeUI::monoFont (10.0f));
                g.setColour (juce::Colour (0xFF3A3A48));
                g.drawText ("Waiting for backing track...", b, juce::Justification::centred);
                g.setColour (juce::Colour (0xFF1E1E24));
                g.drawHorizontalLine (b.getY(), (float) b.getX(), (float) b.getRight());
                return;
            }

            float bx   = (float) b.getX();
            float bw   = (float) b.getWidth();
            float cy   = (float) b.getCentreY();
            float maxH = b.getHeight() * 0.40f;

            if (punchActive && punchOut > punchIn)
            {
                float px1 = bx + bw * juce::jlimit (0.0f, 1.0f, punchIn  / totalDuration);
                float px2 = bx + bw * juce::jlimit (0.0f, 1.0f, punchOut / totalDuration);
                g.setColour (juce::Colour (0xFFFFAA00).withAlpha (0.12f));
                g.fillRect (px1, (float) b.getY(), px2 - px1, (float) b.getHeight());
                g.setColour (juce::Colour (0xFFFFB340).withAlpha (0.75f));
                g.drawLine (px1, (float) b.getY(), px1, (float) b.getBottom(), 1.5f);
                g.drawLine (px2, (float) b.getY(), px2, (float) b.getBottom(), 1.5f);
            }

            float pxZoneL = (punchActive && punchOut > punchIn)
                                ? bx + bw * juce::jlimit (0.0f, 1.0f, punchIn  / totalDuration) : -1.0f;
            float pxZoneR = (punchActive && punchOut > punchIn)
                                ? bx + bw * juce::jlimit (0.0f, 1.0f, punchOut / totalDuration) : -1.0f;

            for (int px = b.getX(); px < b.getRight(); px += 3)
            {
                float t   = (float)(px - b.getX()) / bw;
                float amp = (std::sin (t * 23.4f) * 0.5f
                           + std::cos (t * 11.7f) * 0.3f
                           + std::sin (t * 47.1f) * 0.2f) * 0.5f + 0.5f;
                amp = juce::jlimit (0.05f, 1.0f, amp);
                float hh = amp * maxH;

                bool inPunch = (pxZoneL >= 0.0f && (float) px >= pxZoneL && (float) px < pxZoneR);
                g.setColour (inPunch ? juce::Colour (0xFF4A4A5E) : juce::Colour (0xFF353542));
                g.drawLine ((float) px, cy - hh, (float) px, cy + hh, 1.0f);
            }

            // Marker lines — drawn before playhead so playhead stays on top
            g.setFont (TakeUI::monoFont (8.0f));
            for (const auto& m : markers)
            {
                float mxF = bx + bw * juce::jlimit (0.0f, 1.0f, m.position / totalDuration);
                g.setColour (juce::Colour (0xFF6A7ABE).withAlpha (0.7f));
                g.drawLine (mxF, (float) b.getY(), mxF, (float) b.getBottom(), 1.0f);
                g.setColour (juce::Colour (0xFF7A8ACE));
                g.drawText (m.name, (int) mxF + 2, b.getY() + 1, 48, 10,
                            juce::Justification::centredLeft);
            }

            float phX = bx + bw * juce::jlimit (0.0f, 1.0f, playheadPct);
            g.setColour (juce::Colour (0xFF4F8FFF));
            g.drawLine (phX, (float) b.getY(), phX, (float) b.getBottom(), 1.5f);

            g.setColour (juce::Colour (0xFF1E1E24));
            g.drawHorizontalLine (b.getY(), bx, bx + bw);
        }

        void drawRuler (juce::Graphics& g, juce::Rectangle<int> b)
        {
            g.setColour (juce::Colour (0xFF0D0D0F));
            g.fillRect (b);

            g.setFont (TakeUI::monoFont (9.0f));
            const char* labels[] = { "0:00", "0:16", "0:32", "0:48", "1:04" };

            for (int i = 0; i <= 4; ++i)
            {
                float frac = i / 4.0f;
                int   tx   = b.getX() + (int) (b.getWidth() * frac);

                g.setColour (juce::Colour (0xFF3A3A48));
                g.drawLine ((float) tx, (float) b.getY(),
                            (float) tx, (float) (b.getY() + 4), 1.0f);

                if (i < 4)
                {
                    for (int m = 1; m <= 3; ++m)
                    {
                        float mf = frac + (m / 4.0f) * 0.25f;
                        int   mx = b.getX() + (int) (b.getWidth() * mf);
                        g.setColour (juce::Colour (0xFF252530));
                        g.drawLine ((float) mx, (float) b.getY(),
                                    (float) mx, (float) (b.getY() + 2), 1.0f);
                    }
                }

                g.setColour (juce::Colour (0xFF3A3A48));
                g.drawText (labels[i], tx - 16, b.getY() + 5, 32,
                            b.getHeight() - 5, juce::Justification::centred);
            }

            g.setColour (juce::Colour (0xFF1E1E24));
            g.drawHorizontalLine (b.getY(), (float) b.getX(), (float) b.getRight());
        }
    };

    //==========================================================================
    class CueMixPanel : public juce::Component
    {
    public:
        struct KnobDef
        {
            const char*  label;
            const char*  param;
            float        value;
            juce::uint32 colour;
        };

        CueMixPanel()
        {
            knobs[0] = { "Reverb",  "reverb",        0.0f, 0xFFA78BFA };
            knobs[1] = { "Rev mix", "reverbMix",    0.0f, 0xFFA78BFA };
            knobs[2] = { "Delay",   "delay",         0.0f, 0xFF2DD4BF };
            knobs[3] = { "Del mix", "delayMix",      0.0f, 0xFF2DD4BF };
            knobs[4] = { "Comp",    "compression",   0.0f, 0xFFFFB340 };
            knobs[5] = { "Cue vol", "volume",      100.0f, 0xFF3DDC84 };
        }

        void paint (juce::Graphics& g) override
        {
            g.setColour (juce::Colour (0xFF18181C));
            g.fillAll();

            g.setColour (juce::Colour (0xFF222228));
            g.drawHorizontalLine (0, 0.0f, (float) getWidth());

            g.setFont (TakeUI::monoFont (9.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText ("Cue mix", 12, 6, 60, 12, juce::Justification::centredLeft);

            float slotW = (float) getWidth() / 6.0f;
            constexpr float kCy = 37.0f;

            for (int i = 0; i < 6; ++i)
            {
                float cx = slotW * i + slotW * 0.5f;
                drawKnob (g, cx, kCy, knobs[i].value,
                          juce::Colour (knobs[i].colour), knobs[i].label,
                          i == dragKnobIndex);
            }
        }

        void resized() override {}

        void mouseDown (const juce::MouseEvent& e) override
        {
            dragKnobIndex = knobIndexAt (e.x, e.y);
            if (dragKnobIndex >= 0)
            {
                dragStartY     = e.y;
                dragStartValue = knobs[dragKnobIndex].value;
            }
        }

        void mouseDrag (const juce::MouseEvent& e) override
        {
            if (dragKnobIndex < 0) return;
            float delta = (float)(dragStartY - e.y);
            knobs[dragKnobIndex].value = juce::jlimit (0.0f, 100.0f, dragStartValue + delta);
            repaint();
        }

        void mouseUp (const juce::MouseEvent&) override
        {
            if (dragKnobIndex < 0) return;
            int val = juce::roundToInt (knobs[dragKnobIndex].value);
            std::string path = std::string ("/cue/local/") + knobs[dragKnobIndex].param
                               + "/" + std::to_string (val);
            std::thread ([path]() { rawHttpPost ("127.0.0.1", 5004, path.c_str()); }).detach();
            dragKnobIndex = -1;
            repaint();
        }

    private:
        KnobDef knobs[6];
        int     dragKnobIndex  { -1 };
        int     dragStartY     { 0 };
        float   dragStartValue { 0.0f };

        int knobIndexAt (int mx, int my) const
        {
            float slotW = (float) getWidth() / 6.0f;
            constexpr float kCy = 37.0f, kR = 16.0f;
            for (int i = 0; i < 6; ++i)
            {
                float cx = slotW * i + slotW * 0.5f;
                float dx = (float) mx - cx, dy = (float) my - kCy;
                if (dx * dx + dy * dy <= kR * kR)
                    return i;
            }
            return -1;
        }

        static void rawHttpPost (const char* host, int port, const char* path)
        {
            int fd = ::socket (AF_INET, SOCK_STREAM, 0);
            if (fd < 0) return;

            struct timeval tv { 1, 0 };
            ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));
            ::setsockopt (fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof (tv));

            struct sockaddr_in addr {};
            addr.sin_family = AF_INET;
            addr.sin_port   = htons ((uint16_t) port);
            ::inet_pton (AF_INET, host, &addr.sin_addr);

            if (::connect (fd, (struct sockaddr*) &addr, sizeof (addr)) < 0)
            {
                ::close (fd);
                return;
            }

            char header[512];
            ::snprintf (header, sizeof (header),
                        "POST %s HTTP/1.0\r\n"
                        "Host: %s\r\n"
                        "Content-Length: 0\r\n"
                        "Connection: close\r\n"
                        "\r\n",
                        path, host);
            ::send (fd, header, ::strlen (header), 0);

            char tmp[64];
            while (::recv (fd, tmp, sizeof (tmp), 0) > 0) {}
            ::close (fd);
        }

        void drawKnob (juce::Graphics& g, float cx, float cy, float value,
                       juce::Colour colour, const juce::String& label, bool active)
        {
            constexpr float r = 16.0f;

            g.setColour (juce::Colour (0xFF0A0A0B));
            g.fillEllipse (cx - r, cy - r, r * 2.0f, r * 2.0f);

            g.setColour (active ? colour.withAlpha (0.4f) : juce::Colour (0xFF2A2A32));
            g.drawEllipse (cx - r + 0.5f, cy - r + 0.5f,
                           (r - 0.5f) * 2.0f, (r - 0.5f) * 2.0f, 1.0f);

            static const float kStart = juce::MathConstants<float>::pi * 1.2f;
            static const float kEnd   = juce::MathConstants<float>::pi * 2.8f;
            float angle = kStart + (value / 100.0f) * (kEnd - kStart);

            g.setColour (colour);
            g.drawLine (cx + std::sin (angle) * 3.0f, cy - std::cos (angle) * 3.0f,
                        cx + std::sin (angle) * 12.0f, cy - std::cos (angle) * 12.0f,
                        2.0f);

            g.setFont (TakeUI::monoFont (9.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (label, (int) (cx - 28.0f), (int) (cy + r + 3.0f),
                        56, 10, juce::Justification::centred);

            g.setColour (colour.withAlpha (0.85f));
            g.drawText (juce::String (juce::roundToInt (value)),
                        (int) (cx - 20.0f), (int) (cy + r + 13.0f),
                        40, 10, juce::Justification::centred);
        }
    };

    //==========================================================================
    class SectionNowCard : public juce::Component
    {
    public:
        void paint (juce::Graphics& g) override
        {
            auto b = getLocalBounds();

            g.setColour (juce::Colour (0xFF18181C));
            g.fillAll();

            g.setColour (juce::Colour (0xFF222228));
            g.drawHorizontalLine (0, 0.0f, (float) getWidth());

            int leftW = b.getWidth() / 2;
            g.setFont (TakeUI::monoFont (14.0f, true));
            g.setColour (juce::Colour (0xFF4F8FFF));
            g.drawText ("Chorus", b.getX() + 12, b.getY(), leftW - 12, b.getHeight(),
                        juce::Justification::centredLeft);

            g.setFont (TakeUI::monoFont (10.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText ("Next: Verse 2  ~14s", b.getX() + leftW, b.getY(), leftW - 12, b.getHeight(),
                        juce::Justification::centredRight);
        }

        void resized() override {}
    };

    //==========================================================================
    class HeartbeatThread : public juce::Thread
    {
    public:
        HeartbeatThread() : juce::Thread ("TakeHeartbeat") {}

        void setParams (const juce::String& host, const juce::String& code)
        {
            relayHost = host;
            sessionCode = code;
        }

        void run() override
        {
            while (!threadShouldExit())
            {
                if (relayHost.isNotEmpty() && sessionCode.isNotEmpty())
                {
                    juce::String path = "/session/" + sessionCode + "/heartbeat";
                    sendPost (relayHost.toRawUTF8(), 5010, path.toRawUTF8());
                }
                wait (5000);
            }
        }

    private:
        juce::String relayHost;
        juce::String sessionCode;

        static void sendPost (const char* host, int port, const char* path)
        {
            int fd = ::socket (AF_INET, SOCK_STREAM, 0);
            if (fd < 0) return;

            struct timeval tv { 3, 0 };
            ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));
            ::setsockopt (fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof (tv));

            struct sockaddr_in addr {};
            addr.sin_family = AF_INET;
            addr.sin_port   = htons ((uint16_t) port);
            ::inet_pton (AF_INET, host, &addr.sin_addr);

            if (::connect (fd, (struct sockaddr*) &addr, sizeof (addr)) < 0)
            {
                ::close (fd);
                return;
            }

            const char* body    = "{\"role\":\"artist\"}";
            const int   bodyLen = (int) ::strlen (body);

            char header[512];
            ::snprintf (header, sizeof (header),
                        "POST %s HTTP/1.0\r\n"
                        "Host: %s\r\n"
                        "Content-Type: application/json\r\n"
                        "Content-Length: %d\r\n"
                        "Connection: close\r\n"
                        "\r\n",
                        path, host, bodyLen);
            ::send (fd, header, ::strlen (header), 0);
            ::send (fd, body, (size_t) bodyLen, 0);

            char tmp[64];
            while (::recv (fd, tmp, sizeof (tmp), 0) > 0) {}
            ::close (fd);
        }
    };

    //==========================================================================
    class TimecodePoller : public juce::Thread
    {
    public:
        std::function<void(float, bool)> onResult;  // (pos, playing)

        TimecodePoller() : juce::Thread ("TakeTimecodePoller") {}

        void run() override
        {
            while (!threadShouldExit())
            {
                juce::String body;
                if (rawHttpGet ("127.0.0.1", 5010, "/timecode", body))
                {
                    auto json = juce::JSON::parse (body);
                    if (json.isObject())
                    {
                        const float pos     = (float)(double) json["pos"];
                        const bool  playing = (bool)          json["playing"];
                        auto cb = onResult;
                        if (cb)
                            juce::MessageManager::callAsync ([cb, pos, playing]() mutable
                            {
                                cb (pos, playing);
                            });
                    }
                }
                wait (100);
            }
        }

    private:
        static bool rawHttpGet (const char* host, int port, const char* path, juce::String& body)
        {
            int fd = ::socket (AF_INET, SOCK_STREAM, 0);
            if (fd < 0) return false;

            struct timeval tv { 0, 200000 };  // 200ms — short timeout for fast local polling
            ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));
            ::setsockopt (fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof (tv));

            struct sockaddr_in addr {};
            addr.sin_family = AF_INET;
            addr.sin_port   = htons ((uint16_t) port);
            ::inet_pton (AF_INET, host, &addr.sin_addr);

            if (::connect (fd, (struct sockaddr*) &addr, sizeof (addr)) < 0)
            {
                ::close (fd);
                return false;
            }

            char req[256];
            ::snprintf (req, sizeof (req),
                        "GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n",
                        path, host);
            ::send (fd, req, ::strlen (req), 0);

            juce::MemoryBlock buf;
            char    tmp[512];
            ssize_t n;
            while ((n = ::recv (fd, tmp, sizeof (tmp), 0)) > 0)
                buf.append (tmp, (size_t) n);
            ::close (fd);

            if (buf.getSize() == 0) return false;

            juce::String full = juce::String::fromUTF8 (
                static_cast<const char*> (buf.getData()), (int) buf.getSize());
            const int sep = full.indexOf ("\r\n\r\n");
            if (sep < 0) return false;

            body = full.substring (sep + 4).trim();
            return body.isNotEmpty();
        }
    };

    //==========================================================================
    class StatusPoller : public juce::Thread
    {
    public:
        std::function<void(bool, bool, int, int)> onResult;  // (connected, recording, take, latencyMs)

        StatusPoller() : juce::Thread ("TakeStatusPoller") {}

        void run() override
        {
            while (!threadShouldExit())
            {
                bool connected = false;
                bool recording = false;
                int  take      = 1;
                int  latencyMs = 0;

                juce::String body;
                auto t0 = juce::Time::getMillisecondCounter();
                if (rawHttpGet ("127.0.0.1", 5004, "/status", body))
                {
                    latencyMs = (int)(juce::Time::getMillisecondCounter() - t0);
                    connected = true;
                    auto json = juce::JSON::parse (body);
                    if (json.isObject())
                    {
                        recording = (bool) json["recording"];
                        take      = (int)  json["take"];
                    }
                }

                // Copy callback by value so the lambda doesn't reference this thread object
                auto cb = onResult;
                if (cb)
                    juce::MessageManager::callAsync ([cb, connected, recording, take, latencyMs]() mutable
                    {
                        cb (connected, recording, take, latencyMs);
                    });

                wait (2000);
            }
        }

    private:
        // Plain POSIX TCP request - avoids juce::URL which fires assertions on connection failure
        static bool rawHttpGet (const char* host, int port, const char* path, juce::String& body)
        {
            DBG ("rawHttpGet called: " + juce::String (host) + ":" + juce::String (port));

            int fd = ::socket (AF_INET, SOCK_STREAM, 0);
            if (fd < 0) return false;

            struct timeval tv { 2, 0 };
            ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));
            ::setsockopt (fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof (tv));

            struct sockaddr_in addr {};
            addr.sin_family = AF_INET;
            addr.sin_port   = htons ((uint16_t) port);
            ::inet_pton (AF_INET, host, &addr.sin_addr);

            if (::connect (fd, (struct sockaddr*) &addr, sizeof (addr)) < 0)
            {
                ::close (fd);
                return false;
            }

            char req[256];
            ::snprintf (req, sizeof (req),
                        "GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n",
                        path, host);
            ::send (fd, req, ::strlen (req), 0);

            juce::MemoryBlock buf;
            char tmp[512];
            ssize_t n;
            while ((n = ::recv (fd, tmp, sizeof (tmp), 0)) > 0)
                buf.append (tmp, (size_t) n);
            ::close (fd);

            DBG ("rawHttpGet: recv loop done, buf.getSize()=" + juce::String ((int) buf.getSize()));
            if (buf.getSize() == 0) return false;

            DBG ("rawHttpGet: constructing juce::String from buf");
            juce::String full = juce::String::fromUTF8 (static_cast<const char*> (buf.getData()), (int) buf.getSize());

            int sep = full.indexOf ("\r\n\r\n");
            DBG ("rawHttpGet: header sep=" + juce::String (sep));
            if (sep < 0) return false;

            DBG ("rawHttpGet: constructing body substring");
            body = full.substring (sep + 4).trim();
            DBG ("rawHttpGet: body=" + body);
            return body.isNotEmpty();
        }
    };

    //==========================================================================
    class MeterPoller : public juce::Thread
    {
    public:
        std::function<void(float, float)> onResult;  // (levelL, levelR) in dB

        MeterPoller() : juce::Thread ("TakeMeterPoller") {}

        void run() override
        {
            while (!threadShouldExit())
            {
                juce::String body;
                if (rawHttpGet ("127.0.0.1", 5004, "/levels", body))
                {
                    auto json = juce::JSON::parse (body);
                    if (json.isObject())
                    {
                        float l = juce::jlimit (-60.0f, 0.0f, (float)(double) json["l"]);
                        float r = juce::jlimit (-60.0f, 0.0f, (float)(double) json["r"]);
                        auto cb = onResult;
                        if (cb)
                            juce::MessageManager::callAsync ([cb, l, r]() mutable
                            {
                                cb (l, r);
                            });
                    }
                }
                wait (100);
            }
        }

    private:
        static bool rawHttpGet (const char* host, int port, const char* path, juce::String& body)
        {
            int fd = ::socket (AF_INET, SOCK_STREAM, 0);
            if (fd < 0) return false;

            struct timeval tv { 0, 200000 };  // 200ms timeout — fast local poll
            ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));
            ::setsockopt (fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof (tv));

            struct sockaddr_in addr {};
            addr.sin_family = AF_INET;
            addr.sin_port   = htons ((uint16_t) port);
            ::inet_pton (AF_INET, host, &addr.sin_addr);

            if (::connect (fd, (struct sockaddr*) &addr, sizeof (addr)) < 0)
            {
                ::close (fd);
                return false;
            }

            char req[256];
            ::snprintf (req, sizeof (req),
                        "GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n",
                        path, host);
            ::send (fd, req, ::strlen (req), 0);

            juce::MemoryBlock buf;
            char    tmp[512];
            ssize_t n;
            while ((n = ::recv (fd, tmp, sizeof (tmp), 0)) > 0)
                buf.append (tmp, (size_t) n);
            ::close (fd);

            if (buf.getSize() == 0) return false;

            juce::String full = juce::String::fromUTF8 (
                static_cast<const char*> (buf.getData()), (int) buf.getSize());
            const int sep = full.indexOf ("\r\n\r\n");
            if (sep < 0) return false;

            body = full.substring (sep + 4).trim();
            return body.isNotEmpty();
        }
    };

    //==========================================================================
    class MarkersPoller : public juce::Thread
    {
    public:
        std::function<void(std::vector<Marker>)> onResult;

        MarkersPoller() : juce::Thread ("TakeMarkersPoller") {}

        void run() override
        {
            while (!threadShouldExit())
            {
                juce::String body;
                if (rawHttpGet ("127.0.0.1", 5010, "/markers", body))
                {
                    auto arr = juce::JSON::parse (body);
                    if (arr.isArray())
                    {
                        std::vector<Marker> result;
                        for (const auto& item : *arr.getArray())
                        {
                            if (item.isObject())
                                result.push_back ({ item["name"].toString(),
                                                   (float)(double) item["position"] });
                        }
                        auto cb = onResult;
                        if (cb)
                            juce::MessageManager::callAsync ([cb, result]() mutable
                            {
                                cb (result);
                            });
                    }
                }
                wait (5000);
            }
        }

    private:
        static bool rawHttpGet (const char* host, int port, const char* path, juce::String& body)
        {
            int fd = ::socket (AF_INET, SOCK_STREAM, 0);
            if (fd < 0) return false;

            struct timeval tv { 2, 0 };
            ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));
            ::setsockopt (fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof (tv));

            struct sockaddr_in addr {};
            addr.sin_family = AF_INET;
            addr.sin_port   = htons ((uint16_t) port);
            ::inet_pton (AF_INET, host, &addr.sin_addr);

            if (::connect (fd, (struct sockaddr*) &addr, sizeof (addr)) < 0)
            {
                ::close (fd);
                return false;
            }

            char req[256];
            ::snprintf (req, sizeof (req),
                        "GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n",
                        path, host);
            ::send (fd, req, ::strlen (req), 0);

            juce::MemoryBlock buf;
            char    tmp[512];
            ssize_t n;
            while ((n = ::recv (fd, tmp, sizeof (tmp), 0)) > 0)
                buf.append (tmp, (size_t) n);
            ::close (fd);

            if (buf.getSize() == 0) return false;

            juce::String full = juce::String::fromUTF8 (
                static_cast<const char*> (buf.getData()), (int) buf.getSize());
            const int sep = full.indexOf ("\r\n\r\n");
            if (sep < 0) return false;

            body = full.substring (sep + 4).trim();
            return body.isNotEmpty();
        }
    };

    //==========================================================================
    class PunchPoller : public juce::Thread
    {
    public:
        std::function<void(float, float, bool)> onResult;  // (in, out, active)

        PunchPoller() : juce::Thread ("TakePunchPoller") {}

        void run() override
        {
            while (!threadShouldExit())
            {
                juce::String body;
                if (rawHttpGet ("127.0.0.1", 5010, "/punch", body))
                {
                    auto json = juce::JSON::parse (body);
                    if (json.isObject())
                    {
                        float pIn    = (float)(double) json["in"];
                        float pOut   = (float)(double) json["out"];
                        bool  active = (bool)          json["active"];
                        auto cb = onResult;
                        if (cb)
                            juce::MessageManager::callAsync ([cb, pIn, pOut, active]() mutable
                            {
                                cb (pIn, pOut, active);
                            });
                    }
                }
                wait (2000);
            }
        }

    private:
        static bool rawHttpGet (const char* host, int port, const char* path, juce::String& body)
        {
            int fd = ::socket (AF_INET, SOCK_STREAM, 0);
            if (fd < 0) return false;

            struct timeval tv { 2, 0 };
            ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));
            ::setsockopt (fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof (tv));

            struct sockaddr_in addr {};
            addr.sin_family = AF_INET;
            addr.sin_port   = htons ((uint16_t) port);
            ::inet_pton (AF_INET, host, &addr.sin_addr);

            if (::connect (fd, (struct sockaddr*) &addr, sizeof (addr)) < 0)
            {
                ::close (fd);
                return false;
            }

            char req[256];
            ::snprintf (req, sizeof (req),
                        "GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n",
                        path, host);
            ::send (fd, req, ::strlen (req), 0);

            juce::MemoryBlock buf;
            char    tmp[512];
            ssize_t n;
            while ((n = ::recv (fd, tmp, sizeof (tmp), 0)) > 0)
                buf.append (tmp, (size_t) n);
            ::close (fd);

            if (buf.getSize() == 0) return false;

            juce::String full = juce::String::fromUTF8 (
                static_cast<const char*> (buf.getData()), (int) buf.getSize());
            const int sep = full.indexOf ("\r\n\r\n");
            if (sep < 0) return false;

            body = full.substring (sep + 4).trim();
            return body.isNotEmpty();
        }
    };

    //==========================================================================
    class CountdownTimer : public juce::Timer
    {
    public:
        std::function<void()> onTick;
        void timerCallback() override { if (onTick) onTick(); }
    };

public:
    //==========================================================================
    std::function<void()> onBack;

    ArtistScreen()
    {
        setOpaque (true);

        addChildComponent (detailsPanel);
        detailsPanel.onClose = [this] {
            detailsVisible = false;
            detailsPanel.setVisible (false);
            applyWindowSize (false);
            repaint();
        };

        addAndMakeVisible (recordRing);
        addAndMakeVisible (levelMeter);
        levelMeter.setLevel (-18.0f, -22.0f);

        addAndMakeVisible (trackWindow);
        addAndMakeVisible (sectionNow);
        addAndMakeVisible (cueMixPanel);

        // Wire status poll results back to UI components via SafePointer
        juce::Component::SafePointer<ArtistScreen> safeThis (this);

        countdownTimer.onTick = [safeThis]() mutable
        {
            if (safeThis == nullptr) return;
            safeThis->recordRing.countdownValue--;
            if (safeThis->recordRing.countdownValue <= 0)
            {
                safeThis->countdownTimer.stopTimer();
                safeThis->recordRing.countdownValue = -1;
                safeThis->recordRing.isRecording    = true;
            }
            safeThis->recordRing.repaint();
            safeThis->repaint();
        };

        statusPoller.onResult = [safeThis] (bool connected, bool recording, int take, int latencyMs)
        {
            if (safeThis == nullptr) return;
            safeThis->serverConnected           = connected;
            safeThis->recordRing.takeNumber     = take;
            safeThis->latencyMs                 = latencyMs;

            bool wasRecording = safeThis->lastBackendRecording;
            safeThis->lastBackendRecording = recording;

            if (recording && !wasRecording)
            {
                // false→true: kick off 3-2-1 countdown
                safeThis->recordRing.countdownValue = 3;
                safeThis->recordRing.isRecording    = false;
                safeThis->countdownTimer.startTimer (1000);
            }
            else if (!recording)
            {
                // stopped or still not recording — cancel any running countdown
                safeThis->countdownTimer.stopTimer();
                safeThis->recordRing.countdownValue = -1;
                safeThis->recordRing.isRecording    = false;
            }
            // true→true while counting: leave countdown running, don't reset

            safeThis->recordRing.repaint();
            safeThis->repaint();
        };
        statusPoller.startThread();

        timecodePoller.onResult = [safeThis] (float pos, bool /*playing*/)
        {
            if (safeThis == nullptr) return;
            constexpr float kTotalDuration = 64.0f;
            safeThis->trackWindow.playheadPct = pos / kTotalDuration;
            safeThis->trackWindow.repaint();
        };
        timecodePoller.startThread();

        meterPoller.onResult = [safeThis] (float l, float r)
        {
            if (safeThis == nullptr) return;
            safeThis->levelMeter.setLevel (l, r);
        };

        markersPoller.onResult = [safeThis] (std::vector<Marker> m)
        {
            if (safeThis == nullptr) return;
            safeThis->trackWindow.setMarkers (m);
        };
        markersPoller.startThread();

        punchPoller.onResult = [safeThis] (float in, float out, bool active)
        {
            if (safeThis == nullptr) return;
            safeThis->trackWindow.setPunch (in, out, active);
        };
        punchPoller.startThread();

        startTimer (2000);   // backing track file check
    }

    ~ArtistScreen() override
    {
        stopTimer();
        punchPoller.stopThread (500);
        markersPoller.stopThread (500);
        meterPoller.stopThread (500);
        timecodePoller.stopThread (500);
        heartbeatThread.stopThread (3000);
        statusPoller.stopThread (3000);
    }

    void setSessionCode (const juce::String& code) { sessionCode = code; repaint(); }
    void setLevel       (float l, float r)          { levelMeter.setLevel (l, r); }

    void setEngineerIP (const juce::String& ip, const juce::String& code)
    {
        companionConnected = ip.isNotEmpty();
        engineerConnected  = ip.isNotEmpty();
        detailsPanel.setEngineerConnected (engineerConnected);

        if (ip.isNotEmpty() && code.isNotEmpty())
        {
            relayCode = code;
            heartbeatThread.setParams ("127.0.0.1", code);
            heartbeatThread.startThread();

            if (!meterPoller.isThreadRunning())
                meterPoller.startThread();

            juce::File ("/tmp/take_session.json")
                .replaceWithText ("{\"engineer_ip\":\"" + ip + "\",\"code\":\"" + code
                                  + "\",\"written_at\":" + juce::String (juce::Time::currentTimeMillis()) + "}");
        }

        repaint();
    }

    void timerCallback() override
    {
        auto f = juce::File::getSpecialLocation (juce::File::userHomeDirectory)
                             .getChildFile ("Desktop/Take/companion-app/incoming/take_backing_track.mp3");
        const bool found = f.existsAsFile();
        if (found != trackWindow.backingLoaded)
        {
            trackWindow.backingLoaded = found;
            trackWindow.repaint();
        }
    }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (juce::Colour (0xFF111113));
        drawHeader (g);
        drawConnectionDots (g, 44, kDotsRowH);
        drawTakeLabel (g);
        drawStatusBar (g);
    }

    void resized() override
    {
        constexpr int kHeader     = 44;
        constexpr int kStatus     = 32;
        constexpr int kTrack      = 110;
        constexpr int kSectionNow = 48;
        constexpr int kCueMix     = 80;
        constexpr int kPad        = 14;
        constexpr int kRing       = 110;
        constexpr int kLabelH     = 20, kLabelGap = 12;
        constexpr int kMeterH     = 56, kMeterGap = 12;
        constexpr int kBlock      = kRing + kLabelGap + kLabelH + kMeterGap + kMeterH;

        int cw     = contentWidth();
        int usable = getHeight() - kHeader - kDotsRowH - kStatus - kTrack - kSectionNow - kCueMix;
        int top    = kHeader + kDotsRowH + juce::jmax (12, (usable - kBlock) / 2);
        int cx     = (cw - kRing) / 2;

        recordRing.setBounds (cx, top, kRing, kRing);

        int meterY = top + kRing + kLabelGap + kLabelH + kMeterGap;
        levelMeter.setBounds (kPad, meterY, cw - kPad * 2, kMeterH);

        int bottomStack = getHeight() - kStatus;
        cueMixPanel.setBounds (kPad, bottomStack - kCueMix,                        cw - kPad * 2, kCueMix);
        sectionNow.setBounds  (kPad, bottomStack - kCueMix - kSectionNow,          cw - kPad * 2, kSectionNow);
        trackWindow.setBounds (kPad, bottomStack - kCueMix - kSectionNow - kTrack, cw - kPad * 2, kTrack);

        detailsPanel.setBounds (kBaseWidth, 0, 300, getHeight());
    }

    void mouseDown (const juce::MouseEvent& e) override
    {
        if (backBtnBounds().expanded (4).contains (e.getPosition()))
        {
            if (onBack) onBack();
            return;
        }

        if (endSessionBtnBounds().expanded (4).contains (e.getPosition()))
        {
            auto code = relayCode.toStdString();
            if (!code.empty())
                std::thread ([code]() {
                    std::string path = "/session/" + code;
                    rawHttpDelete ("127.0.0.1", 5010, path.c_str());
                }).detach();
            if (onBack) onBack();
            return;
        }

        if (detailsBtnBounds().expanded (4).contains (e.getPosition()))
        {
            detailsVisible = !detailsVisible;
            detailsPanel.setVisible (detailsVisible);
            if (detailsVisible) detailsPanel.toFront (false);
            applyWindowSize (detailsVisible);
            repaint();
        }
    }

private:
    //==========================================================================
    static constexpr int kBaseWidth  = 400;
    static constexpr int kBaseHeight = 620;
    static constexpr int kDotsRowH   = 32;

    int contentWidth() const { return juce::jmin (getWidth(), kBaseWidth); }

    void applyWindowSize (bool withPanel)
    {
        int w = kBaseWidth + (withPanel ? 300 : 0);
        if (auto* rw = dynamic_cast<juce::ResizableWindow*> (getTopLevelComponent()))
            rw->setContentComponentSize (w, kBaseHeight);
    }

    juce::Rectangle<int> backBtnBounds() const
    {
        return { 12, getHeight() - 28, 44, 20 };
    }

    juce::Rectangle<int> endSessionBtnBounds() const
    {
        return { 62, getHeight() - 29, 72, 26 };
    }

    juce::Rectangle<int> detailsBtnBounds() const
    {
        return { contentWidth() - 58, getHeight() - 29, 44, 26 };
    }

    static void rawHttpDelete (const char* host, int port, const char* path)
    {
        int fd = ::socket (AF_INET, SOCK_STREAM, 0);
        if (fd < 0) return;

        struct timeval tv { 2, 0 };
        ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));
        ::setsockopt (fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof (tv));

        struct sockaddr_in addr {};
        addr.sin_family = AF_INET;
        addr.sin_port   = htons ((uint16_t) port);
        ::inet_pton (AF_INET, host, &addr.sin_addr);

        if (::connect (fd, (struct sockaddr*) &addr, sizeof (addr)) < 0)
        {
            ::close (fd);
            return;
        }

        char req[256];
        ::snprintf (req, sizeof (req),
                    "DELETE %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n",
                    path, host);
        ::send (fd, req, ::strlen (req), 0);

        char tmp[64];
        while (::recv (fd, tmp, sizeof (tmp), 0) > 0) {}
        ::close (fd);
    }

    void drawHeader (juce::Graphics& g)
    {
        g.setColour (juce::Colour (0xFF1E1E24));
        g.fillRect (0, 43, getWidth(), 1);

        g.setFont (TakeUI::monoFont (16.0f, true));
        {
            const char* const  kL[] = { "T", "A", "K", "E", nullptr };
            const juce::uint32 kC[] = { 0xFFF0F0F8, 0xFF3DDC84, 0xFF3DDC84, 0xFF3DDC84 };
            constexpr float kSlot = 11.0f, kGap = 1.5f;
            float lx = 12.0f;
            for (int i = 0; kL[i]; ++i, lx += kSlot + kGap)
            {
                g.setColour (juce::Colour (kC[i]));
                g.drawText (kL[i], (int) lx, 0, (int) kSlot + 1, 44, juce::Justification::centredLeft);
            }
        }

        {
            auto pill = juce::Rectangle<int> (contentWidth() - 102, 11, 90, 22);
            g.setColour (juce::Colour (0xFF18181C));
            g.fillRoundedRectangle (pill.toFloat(), 4.0f);
            g.setColour (juce::Colour (0xFF222228));
            g.drawRoundedRectangle (pill.toFloat(), 4.0f, 1.0f);
            g.setFont (TakeUI::monoFont (9.0f));
            g.setColour (juce::Colour (0xFF7A7A8E));
            g.drawText (sessionCode, pill, juce::Justification::centred);
        }
    }

    void drawConnectionDots (juce::Graphics& g, int rowY, int rowH)
    {
        struct Dot { const char* label; bool on; int approxW; };
        const Dot dots[] = {
            { "Companion", companionConnected, 64 },
            { "Server",    serverConnected,    44 },
            { "Engineer",  engineerConnected,  58 },
        };

        constexpr int kPad = 14, kDot = 6, kGap = 5, kBetween = 16;
        int totalW = 0;
        for (auto& d : dots) totalW += kDot + kGap + d.approxW + kBetween;
        totalW -= kBetween;

        int cw   = contentWidth();
        int x    = kPad + (cw - kPad * 2 - totalW) / 2;
        int dotY = rowY + (rowH - kDot) / 2;

        g.setFont (TakeUI::monoFont (10.0f));

        for (auto& d : dots)
        {
            auto dotColour = d.on ? juce::Colour (0xFF3DDC84) : juce::Colour (0xFF2E2E3A);
            if (d.on)
            {
                g.setColour (dotColour.withAlpha (0.11f));
                g.fillEllipse ((float)(x - 5), (float)(dotY - 5), (float)(kDot + 10), (float)(kDot + 10));
                g.setColour (dotColour.withAlpha (0.24f));
                g.fillEllipse ((float)(x - 2), (float)(dotY - 2), (float)(kDot + 4), (float)(kDot + 4));
            }
            g.setColour (dotColour);
            g.fillEllipse ((float) x, (float) dotY, (float) kDot, (float) kDot);

            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (d.label, x + kDot + kGap, rowY, d.approxW, rowH,
                        juce::Justification::centredLeft);

            x += kDot + kGap + d.approxW + kBetween;
        }
    }

    void drawTakeLabel (juce::Graphics& g)
    {
        int y = recordRing.getBottom() + 12;
        g.setFont (TakeUI::monoFont (12.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("T" + juce::String (recordRing.takeNumber),
                    0, y, contentWidth(), 20, juce::Justification::centred);
    }

    void drawStatusBar (juce::Graphics& g)
    {
        int barY = getHeight() - 32;
        g.setColour (juce::Colour (0xFF0A0A0B));
        g.fillRect (0, barY, getWidth(), 32);
        g.setColour (juce::Colour (0xFF1A1A20));
        g.drawHorizontalLine (barY, 0.0f, (float) getWidth());

        g.setFont (TakeUI::monoFont (10.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("<- Back", 12, barY, 44, 32, juce::Justification::centredLeft);

        {
            auto eb = endSessionBtnBounds();
            g.setColour (juce::Colour (0xFF1A0808));
            g.fillRoundedRectangle (eb.toFloat(), 4.0f);
            g.setColour (juce::Colour (0xFF5C1A1A));
            g.drawRoundedRectangle (eb.toFloat(), 4.0f, 1.0f);
            g.setFont (TakeUI::monoFont (9.0f));
            g.setColour (juce::Colour (0xFFFF4F4F));
            g.drawText ("End session", eb, juce::Justification::centred);
        }

        {
            auto db = detailsBtnBounds();
            g.setColour (juce::Colour (detailsVisible ? 0xFF185FA5 : 0xFF1A1A1E));
            g.fillRoundedRectangle (db.toFloat(), 4.0f);
            g.setFont (TakeUI::monoFont (10.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText ("Details", db, juce::Justification::centred);
        }

        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        auto text = juce::String ("Latency ") + juce::String (latencyMs) + "ms"
                    + "  |  Take T" + juce::String (recordRing.takeNumber)
                    + "  |  Stream AAC 256";
        g.drawText (text, 140, barY, contentWidth() - 198, 32,
                    juce::Justification::centredLeft);
    }

    bool            detailsVisible        { false };
    bool            companionConnected    { false };
    bool            serverConnected       { false };
    bool            engineerConnected     { false };
    int             latencyMs             { 0 };
    bool            lastBackendRecording  { false };
    DetailsPanel    detailsPanel;
    juce::String    sessionCode { TakeUI::generateSessionCode() };
    juce::String    relayCode;
    RecordRing      recordRing;
    LevelMeter      levelMeter;
    TrackWindow     trackWindow;
    SectionNowCard  sectionNow;
    CueMixPanel     cueMixPanel;
    HeartbeatThread heartbeatThread;
    TimecodePoller  timecodePoller;
    StatusPoller    statusPoller;
    MeterPoller     meterPoller;
    MarkersPoller   markersPoller;
    PunchPoller     punchPoller;
    CountdownTimer  countdownTimer;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ArtistScreen)
};
