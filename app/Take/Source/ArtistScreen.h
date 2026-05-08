#pragma once
#include <JuceHeader.h>
#include "DetailsPanel.h"

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

            // layered glow — multi-ring emanation, stronger when recording
            if (isRecording)
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

            g.setColour (juce::Colour (0xFF18181C));
            g.fillRoundedRectangle (bar.toFloat(), 2.0f);

            float frac = juce::jlimit (0.0f, 1.0f, (db + 60.0f) / 60.0f);
            if (frac > 0.0f)
            {
                auto fill = bar.toFloat().withWidth (bar.getWidth() * frac);
                juce::ColourGradient grad (juce::Colour (0xFF1D9E75), (float) bar.getX(), 0.0f,
                                           juce::Colour (0xFFFF4F4F), (float) bar.getRight(), 0.0f, false);
                grad.addColour (0.72, juce::Colour (0xFF1D9E75));
                grad.addColour (0.88, juce::Colour (0xFFFFAA00));
                g.setGradientFill (grad);
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

    //==========================================================================
    class CueMixPanel : public juce::Component
    {
    public:
        void paint (juce::Graphics& g) override
        {
            g.setColour (juce::Colour (0xFF18181C));
            g.fillAll();

            g.setColour (juce::Colour (0xFF222228));
            g.drawHorizontalLine (0, 0.0f, (float) getWidth());

            g.setFont (TakeUI::monoFont (9.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText ("Cue mix", 12, 6, 60, 12, juce::Justification::centredLeft);

            struct Knob { const char* label; float value; juce::uint32 colour; };
            const Knob knobs[] = {
                { "Reverb",  60.0f, 0xFFA78BFA },
                { "Rev mix", 30.0f, 0xFFA78BFA },
                { "Delay",   40.0f, 0xFF2DD4BF },
                { "Del mix", 20.0f, 0xFF2DD4BF },
                { "Comp",    50.0f, 0xFFFFB340 },
                { "Cue vol", 75.0f, 0xFF3DDC84 },
            };

            float slotW = (float) getWidth() / 6.0f;
            constexpr float kCy = 37.0f;

            for (int i = 0; i < 6; ++i)
            {
                float cx = slotW * i + slotW * 0.5f;
                drawKnob (g, cx, kCy, knobs[i].value,
                          juce::Colour (knobs[i].colour), knobs[i].label);
            }
        }

        void resized() override {}

    private:
        void drawKnob (juce::Graphics& g, float cx, float cy, float value,
                       juce::Colour colour, const juce::String& label)
        {
            constexpr float r = 14.0f;

            // circle body
            g.setColour (juce::Colour (0xFF0A0A0B));
            g.fillEllipse (cx - r, cy - r, r * 2.0f, r * 2.0f);

            // subtle border ring
            g.setColour (juce::Colour (0xFF2A2A32));
            g.drawEllipse (cx - r + 0.5f, cy - r + 0.5f,
                           (r - 0.5f) * 2.0f, (r - 0.5f) * 2.0f, 1.0f);

            // tick — angle=0 at 12 o'clock, CW positive (JUCE rotary convention)
            static const float kStart = juce::MathConstants<float>::pi * 1.2f;
            static const float kEnd   = juce::MathConstants<float>::pi * 2.8f;
            float angle = kStart + (value / 100.0f) * (kEnd - kStart);

            g.setColour (colour);
            g.drawLine (cx + std::sin (angle) * 3.0f, cy - std::cos (angle) * 3.0f,
                        cx + std::sin (angle) * 10.0f, cy - std::cos (angle) * 10.0f,
                        2.0f);

            // label
            g.setFont (TakeUI::monoFont (8.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (label, (int) (cx - 28.0f), (int) (cy + r + 3.0f),
                        56, 10, juce::Justification::centred);

            // value
            g.setColour (colour.withAlpha (0.85f));
            g.drawText (juce::String (juce::roundToInt (value)),
                        (int) (cx - 20.0f), (int) (cy + r + 13.0f),
                        40, 10, juce::Justification::centred);
        }
    };

public:
    //==========================================================================
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
        addAndMakeVisible (cueMixPanel);
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
        constexpr int kHeader   = 44, kStatus = 32;
        constexpr int kTrack    = 90, kCueMix = 80;
        constexpr int kRing     = 130;
        constexpr int kLabelH   = 20, kLabelGap = 8;
        constexpr int kMeterH   = 56, kMeterGap = 12;
        constexpr int kBlock    = kRing + kLabelGap + kLabelH + kMeterGap + kMeterH;

        int cw     = contentWidth();
        int usable = getHeight() - kHeader - kStatus - kTrack - kCueMix;
        int top    = kHeader + juce::jmax (8, (usable - kBlock) / 2);
        int cx     = (cw - kRing) / 2;

        recordRing.setBounds (cx, top, kRing, kRing);

        int meterY = top + kRing + kLabelGap + kLabelH + kMeterGap;
        levelMeter.setBounds (28, meterY, cw - 56, kMeterH);

        int bottomStack = getHeight() - kStatus;
        cueMixPanel.setBounds  (0, bottomStack - kCueMix,          cw, kCueMix);
        trackWindow.setBounds  (0, bottomStack - kCueMix - kTrack, cw, kTrack);

        detailsPanel.setBounds (kBaseWidth, 0, 300, getHeight());
    }

    void mouseDown (const juce::MouseEvent& e) override
    {
        // Expand hit area slightly for the small Details button
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
    static constexpr int kBaseHeight = 500;

    int contentWidth() const { return juce::jmin (getWidth(), kBaseWidth); }

    void applyWindowSize (bool withPanel)
    {
        int w = kBaseWidth + (withPanel ? 300 : 0);
        if (auto* rw = dynamic_cast<juce::ResizableWindow*> (getTopLevelComponent()))
            rw->setContentComponentSize (w, kBaseHeight);
    }

    juce::Rectangle<int> detailsBtnBounds() const { return { contentWidth() - 54, 9, 44, 26 }; }

    void drawHeader (juce::Graphics& g)
    {
        // separator
        g.setColour (juce::Colour (0xFF1E1E24));
        g.fillRect (0, 43, getWidth(), 1);

        // TAKE wordmark — 16px bold with subtle letter spacing
        g.setFont (TakeUI::monoFont (16.0f, true));
        g.setColour (juce::Colour (0xFF1D9E75));
        {
            const char* const kL[] = { "T", "A", "K", "E", nullptr };
            constexpr float kSlot = 11.0f, kGap = 1.5f;
            float lx = 12.0f;
            for (int i = 0; kL[i]; ++i, lx += kSlot + kGap)
                g.drawText (kL[i], (int) lx, 0, (int) kSlot + 1, 44, juce::Justification::centredLeft);
        }

        // Details button — right-aligned at getWidth()-10
        {
            auto db = detailsBtnBounds();
            g.setColour (juce::Colour (detailsVisible ? 0xFF185FA5 : 0xFF1A1A1E));
            g.fillRoundedRectangle (db.toFloat(), 4.0f);
            g.setFont (TakeUI::monoFont (10.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText ("Details", db, juce::Justification::centred);
        }

        // Session code — right-aligned at getWidth()-70 (left of Details button)
        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (sessionCode, contentWidth() - 170, 0, 100, 44,
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

        // centre the cluster between x=80 and getWidth()-140
        int left  = 80;
        int right = contentWidth() - 140;
        int x     = left + (right - left - totalW) / 2;
        int dotY  = (44 - kDot) / 2;

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
                    0, y, contentWidth(), 20, juce::Justification::centred);
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
        g.drawText (text, 16, barY, contentWidth() - 32, 32,
                    juce::Justification::centredLeft);
    }

    bool         detailsVisible { false };
    DetailsPanel detailsPanel;
    juce::String sessionCode { "TAKE-0000" };
    RecordRing   recordRing;
    LevelMeter   levelMeter;
    TrackWindow  trackWindow;
    CueMixPanel  cueMixPanel;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ArtistScreen)
};
