#pragma once
#include <JuceHeader.h>

//==============================================================================
namespace TakeUI
{
    inline juce::Font monoFont (float size, bool bold = false)
    {
        int style = bold ? juce::Font::bold : juce::Font::plain;
        return juce::Font (juce::Font::getDefaultMonospacedFontName(), size, style);
    }
}

//==============================================================================
class ArtistScreen : public juce::Component
{
    //==========================================================================
    class RecordRing : public juce::Component
    {
    public:
        std::function<void()> onClick;
        bool isRecording { false };
        int  takeNumber  { 1 };

        void paint (juce::Graphics& g) override
        {
            auto body       = getLocalBounds().toFloat().reduced (3.0f);
            auto ringColour = isRecording ? juce::Colour (0xFFFF4F4F)
                                          : juce::Colour (0xFF185FA5);

            // subtle outer glow
            g.setColour (ringColour.withAlpha (0.10f));
            g.fillEllipse (body.expanded (10.0f));

            // circle fill
            g.setColour (juce::Colour (0xFF111113));
            g.fillEllipse (body);

            // ring border
            g.setColour (ringColour);
            g.drawEllipse (body, 2.5f);

            // main state label
            g.setFont (TakeUI::monoFont (17.0f, true));
            g.setColour (juce::Colour (0xFFF0F0F8));
            g.drawText (isRecording ? "REC" : "READY",
                        getLocalBounds().translated (0, -8),
                        juce::Justification::centred);

            // take number inside ring
            g.setFont (TakeUI::monoFont (11.0f));
            g.setColour (ringColour.withAlpha (0.75f));
            g.drawText ("T" + juce::String (takeNumber),
                        getLocalBounds().translated (0, 16),
                        juce::Justification::centred);
        }

        void mouseUp (const juce::MouseEvent&) override
        {
            if (onClick) onClick();
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

            // channel label
            auto labelR = bounds.removeFromLeft (20);
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (ch, labelR, juce::Justification::centred);

            // dB readout
            auto dbR = bounds.removeFromRight (52);
            g.drawText (juce::String (juce::roundToInt (db)) + " dB",
                        dbR, juce::Justification::centred);

            // thin bar — 6 px tall, vertically centred in the row
            auto area = bounds.reduced (6, 0);
            auto bar  = juce::Rectangle<int> (area.getX(),
                                              area.getCentreY() - 3,
                                              area.getWidth(), 6);

            g.setColour (juce::Colour (0xFF1A1A1E));
            g.fillRoundedRectangle (bar.toFloat(), 2.0f);

            float frac = juce::jlimit (0.0f, 1.0f, (db + 60.0f) / 60.0f);
            if (frac > 0.0f)
            {
                auto fill = bar.toFloat().withWidth (bar.getWidth() * frac);
                auto col  = juce::Colour (0xFF1D9E75);
                if (frac > 0.80f) col = juce::Colour (0xFFFFAA00);
                if (frac > 0.95f) col = juce::Colour (0xFFFF4F4F);
                g.setColour (col);
                g.fillRoundedRectangle (fill, 2.0f);
            }
        }
    };

    //==========================================================================
    class TrackWindow : public juce::Component
    {
    public:
        void paint (juce::Graphics& g) override
        {
            constexpr int kSectH = 24, kWaveH = 48;
            auto b = getLocalBounds();
            drawSections (g, b.removeFromTop (kSectH));
            drawWaveform (g, b.removeFromTop (kWaveH));
            drawRuler    (g, b);
        }

        void resized() override {}

    private:
        void drawSections (juce::Graphics& g, juce::Rectangle<int> b)
        {
            struct Sec { const char* name; bool current; };
            const Sec secs[] = {
                { "Verse 1", false },
                { "Chorus",  true  },
                { "Verse 2", false },
            };

            int sw = b.getWidth() / 3;

            for (int i = 0; i < 3; ++i)
            {
                int secX = b.getX() + i * sw;
                int secW = (i == 2) ? (b.getWidth() - 2 * sw) : sw;
                auto r   = juce::Rectangle<int> (secX, b.getY(), secW, b.getHeight());

                g.setColour (juce::Colour (0xFF18181C));
                g.fillRect (r);

                if (secs[i].current)
                {
                    g.setColour (juce::Colour (0xFF4F8FFF).withAlpha (0.10f));
                    g.fillRect (r);
                }

                if (i > 0)
                {
                    g.setColour (juce::Colour (0xFF1E1E24));
                    g.drawVerticalLine (secX, (float) b.getY(), (float) b.getBottom());
                }

                g.setFont (TakeUI::monoFont (10.0f));
                g.setColour (secs[i].current ? juce::Colour (0xFF4F8FFF)
                                             : juce::Colour (0xFF5C5C6E));
                g.drawText (secs[i].name, r, juce::Justification::centred);
            }

            g.setColour (juce::Colour (0xFF1E1E24));
            g.drawHorizontalLine (b.getBottom() - 1, (float) b.getX(), (float) b.getRight());
        }

        void drawWaveform (juce::Graphics& g, juce::Rectangle<int> b)
        {
            g.setColour (juce::Colour (0xFF0D0D0F));
            g.fillRect (b);

            float bx   = (float) b.getX();
            float bw   = (float) b.getWidth();
            float cy   = (float) b.getCentreY();
            float maxH = b.getHeight() * 0.40f;

            // punch zone: 20 %–50 % of width, red tint
            float punchX1 = bx + bw * 0.20f;
            float punchX2 = bx + bw * 0.50f;
            g.setColour (juce::Colour (0xFFFF4F4F).withAlpha (0.10f));
            g.fillRect (punchX1, (float) b.getY(), punchX2 - punchX1, (float) b.getHeight());

            // waveform bars — deterministic trig, no random state needed
            for (int px = b.getX(); px < b.getRight(); px += 3)
            {
                float t   = (float)(px - b.getX()) / bw;
                float amp = (std::sin (t * 23.4f) * 0.5f
                           + std::cos (t * 11.7f) * 0.3f
                           + std::sin (t * 47.1f) * 0.2f) * 0.5f + 0.5f;
                amp = juce::jlimit (0.05f, 1.0f, amp);
                float hh = amp * maxH;

                bool inPunch = ((float) px >= punchX1 && (float) px < punchX2);
                g.setColour (inPunch ? juce::Colour (0xFF4A4A5E) : juce::Colour (0xFF353542));
                g.drawLine ((float) px, cy - hh, (float) px, cy + hh, 1.0f);
            }

            // playhead at 45 %
            float phX = bx + bw * 0.45f;
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

                // three minor ticks between each pair of majors
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

public:
    //==========================================================================
    ArtistScreen()
    {
        setOpaque (true);

        addAndMakeVisible (recordRing);
        recordRing.onClick = [this]
        {
            recordRing.isRecording = !recordRing.isRecording;
            if (!recordRing.isRecording)   // stopped — advance to next take
                recordRing.takeNumber++;
            recordRing.repaint();
            repaint();                     // refresh status bar + take label
        };

        addAndMakeVisible (levelMeter);
        levelMeter.setLevel (-18.0f, -22.0f);

        addAndMakeVisible (trackWindow);
    }

    void setSessionCode (const juce::String& code) { sessionCode = code; repaint(); }
    void setLevel       (float l, float r)          { levelMeter.setLevel (l, r); }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (juce::Colour (0xFF111113));
        drawHeader (g);
        drawTakeLabel (g);
        drawStatusBar (g);
    }

    void resized() override
    {
        constexpr int kHeader  = 44, kStatus = 32, kTrack = 90;
        constexpr int kRing    = 130;
        constexpr int kLabelH  = 20, kLabelGap = 8;
        constexpr int kMeterH  = 64, kMeterGap = 18;
        constexpr int kBlock   = kRing + kLabelGap + kLabelH + kMeterGap + kMeterH;

        int usable = getHeight() - kHeader - kStatus - kTrack;
        int top    = kHeader + (usable - kBlock) / 2;
        int cx     = (getWidth() - kRing) / 2;

        recordRing.setBounds (cx, top, kRing, kRing);

        int meterY = top + kRing + kLabelGap + kLabelH + kMeterGap;
        levelMeter.setBounds (28, meterY, getWidth() - 56, kMeterH);

        trackWindow.setBounds (0, getHeight() - kStatus - kTrack, getWidth(), kTrack);
    }

private:
    //==========================================================================
    void drawHeader (juce::Graphics& g)
    {
        // separator
        g.setColour (juce::Colour (0xFF1E1E24));
        g.fillRect (0, 43, getWidth(), 1);

        // TAKE logo
        g.setFont (TakeUI::monoFont (15.0f, true));
        g.setColour (juce::Colour (0xFF1D9E75));
        g.drawText ("TAKE", 16, 0, 60, 44, juce::Justification::centredLeft);

        // session code
        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (sessionCode, getWidth() - 120, 0, 108, 44,
                    juce::Justification::centredRight);

        drawConnectionDots (g);
    }

    void drawConnectionDots (juce::Graphics& g)
    {
        struct Dot { const char* label; bool on; int approxW; };
        const Dot dots[] = {
            { "Companion", true,  64 },
            { "Server",    true,  44 },
            { "Engineer",  false, 58 },
        };

        constexpr int kDot = 6, kGap = 5, kBetween = 16;
        int totalW = 0;
        for (auto& d : dots) totalW += kDot + kGap + d.approxW + kBetween;
        totalW -= kBetween;

        // centre the cluster in the space between logo and session code
        int left  = 76;
        int right = getWidth() - 120;
        int x     = left + (right - left - totalW) / 2;
        int dotY  = (44 - kDot) / 2;

        g.setFont (TakeUI::monoFont (10.0f));

        for (auto& d : dots)
        {
            g.setColour (d.on ? juce::Colour (0xFF3DDC84) : juce::Colour (0xFF2E2E3A));
            g.fillEllipse ((float) x, (float) dotY, (float) kDot, (float) kDot);

            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (d.label, x + kDot + kGap, 0, d.approxW, 44,
                        juce::Justification::centredLeft);

            x += kDot + kGap + d.approxW + kBetween;
        }
    }

    void drawTakeLabel (juce::Graphics& g)
    {
        int y = recordRing.getBottom() + 8;
        g.setFont (TakeUI::monoFont (12.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("T" + juce::String (recordRing.takeNumber),
                    0, y, getWidth(), 20, juce::Justification::centred);
    }

    void drawStatusBar (juce::Graphics& g)
    {
        int barY = getHeight() - 32;
        g.setColour (juce::Colour (0xFF0A0A0B));
        g.fillRect (0, barY, getWidth(), 32);
        g.setColour (juce::Colour (0xFF1A1A20));
        g.drawHorizontalLine (barY, 0.0f, (float) getWidth());

        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));

        auto text = juce::String ("Latency 0ms  |  Take T")
                    + juce::String (recordRing.takeNumber)
                    + "  |  Stream AAC 256";
        g.drawText (text, 16, barY, getWidth() - 32, 32,
                    juce::Justification::centredLeft);
    }

    juce::String sessionCode { "TAKE-0000" };
    RecordRing   recordRing;
    LevelMeter   levelMeter;
    TrackWindow  trackWindow;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ArtistScreen)
};
