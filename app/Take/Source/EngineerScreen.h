#pragma once
#include <JuceHeader.h>

//==============================================================================
class EngineerScreen : public juce::Component
{
public:
    EngineerScreen() { setOpaque (true); }

    void setSessionCode (const juce::String& code) { sessionCode = code; repaint(); }
    void setRecording   (bool rec, int take = 1)   { isRecording = rec; takeNum = take; repaint(); }
    void setLevel       (float l, float r)          { leftDb = l; rightDb = r; repaint(); }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (juce::Colour (0xFF111113));
        drawHeader      (g);
        drawLeftColumn  (g);
        drawRightColumn (g);
        drawStatusBar   (g);
    }

    void resized() override {}

    void mouseDown (const juce::MouseEvent& e) override
    {
        if (e.x < 200)
        {
            auto p = e.getPosition();
            if (recBtn().contains (p))            { isRecording = !isRecording; repaint(); return; }
            for (int i = 0; i < 3; ++i)
                if (syncRow (i).contains (p))     { syncOn[i] = !syncOn[i]; repaint(); return; }
            return;
        }

        // Right column — cue mix knobs (hit inside circle)
        for (int i = 0; i < 7; ++i)
        {
            auto k = knobCenter (i);
            float dx = e.x - k.cx, dy = e.y - k.cy;
            if (dx * dx + dy * dy <= 16.0f * 16.0f)
            {
                dragging = i;  dragStartY = e.y;  dragStartVal = cueMix[i];  return;
            }
        }

        // EQ sliders (expanded hit area ±10px on each side)
        for (int i = 0; i < 4; ++i)
        {
            if (eqSliderBounds (i).expanded (10.0f, 0.0f).contains ((float) e.x, (float) e.y))
            {
                dragging = 7 + i;  dragStartY = e.y;  dragStartVal = eq[i];  return;
            }
        }
    }

    void mouseDrag (const juce::MouseEvent& e) override
    {
        if (dragging < 0) return;
        int val = juce::jlimit (0, 100, dragStartVal + (dragStartY - e.y));
        if (dragging < 7) cueMix[dragging]     = val;
        else              eq[dragging - 7]     = val;
        repaint();
    }

    void mouseUp (const juce::MouseEvent&) override { dragging = -1; }

private:
    // Session / recording state
    juce::String sessionCode { "TAKE-0000" };
    bool  isRecording { false };
    int   takeNum     { 1 };
    float leftDb      { -18.0f };
    float rightDb     { -22.0f };

    // Left column state
    bool syncOn[3] { true, true, false };

    // Right column state
    int cueMix[7] { 60, 30, 50, 20, 55, 40, 75 };
    int eq[4]     { 50, 50, 60, 65 };

    // Drag state
    int dragging     { -1 };
    int dragStartY   {  0 };
    int dragStartVal {  0 };

    //==========================================================================
    // Left column — fixed hit rectangles
    static juce::Rectangle<int> recBtn()           { return juce::Rectangle<int> ( 12, 244, 86, 40); }
    static juce::Rectangle<int> stopBtn()          { return juce::Rectangle<int> (102, 244, 86, 40); }
    static juce::Rectangle<int> rtzBtn()           { return juce::Rectangle<int> ( 12, 288, 86, 40); }
    static juce::Rectangle<int> punchBtn()         { return juce::Rectangle<int> (102, 288, 86, 40); }
    static juce::Rectangle<int> syncRow (int i)    { return juce::Rectangle<int> (0, 348 + i * 22, 200, 22); }

    // Right column — dynamic layout (depends on getWidth())
    struct KnobPos { float cx, cy; };

    KnobPos knobCenter (int index) const
    {
        float rw = (float) (getWidth() - 200);
        if (index < 4)                          // row 1 — four knobs
        {
            float sw = rw / 4.0f;
            return { 200.0f + sw * index + sw * 0.5f, 94.0f };
        }
        float sw = rw / 3.0f;                  // row 2 — three knobs
        return { 200.0f + sw * (index - 4) + sw * 0.5f, 172.0f };
    }

    juce::Rectangle<float> eqSliderBounds (int i) const
    {
        float rw = (float) (getWidth() - 200);
        float sw = rw / 4.0f;
        float cx = 200.0f + sw * i + sw * 0.5f;
        return { cx - 4.0f, 256.0f, 8.0f, 50.0f };
    }

    //==========================================================================
    void sectionLabel (juce::Graphics& g, const juce::String& text, int y)
    {
        g.setFont (TakeUI::monoFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (text, 12, y, 140, 12, juce::Justification::centredLeft);
    }

    void divider (juce::Graphics& g, int y)
    {
        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (y, 0.0f, 200.0f);
    }

    //==========================================================================
    void drawHeader (juce::Graphics& g)
    {
        g.setColour (juce::Colour (0xFF1E1E24));
        g.fillRect (0, 43, getWidth(), 1);

        g.setFont (TakeUI::monoFont (15.0f, true));
        g.setColour (juce::Colour (0xFF185FA5));
        g.drawText ("TAKE", 16, 0, 60, 44, juce::Justification::centredLeft);

        if (isRecording)
        {
            g.setColour (juce::Colour (0xFFFF4F4F));
            g.fillEllipse ((float) (getWidth() - 90), 19.0f, 6.0f, 6.0f);
            g.setFont (TakeUI::monoFont (11.0f));
            g.drawText ("REC T" + juce::String (takeNum),
                        getWidth() - 84, 0, 74, 44, juce::Justification::centredLeft);
        }
        else
        {
            g.setFont (TakeUI::monoFont (11.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (sessionCode, getWidth() - 130, 0, 120, 44,
                        juce::Justification::centredRight);
        }

        drawConnectionDots (g);
    }

    void drawConnectionDots (juce::Graphics& g)
    {
        struct Dot { const char* label; bool on; int approxW; };
        const Dot dots[] = {
            { "Companion", true,  56 },
            { "Server",    true,  40 },
            { "Artist",    true,  38 },
            { "Reaper",    false, 42 },
        };

        constexpr int kD = 5, kGap = 4, kBetween = 12;
        int totalW = 0;
        for (auto& d : dots) totalW += kD + kGap + d.approxW + kBetween;
        totalW -= kBetween;

        int left = 76, right = getWidth() - 120;
        int x    = left + (right - left - totalW) / 2;
        int dotY = (44 - kD) / 2;

        g.setFont (TakeUI::monoFont (9.0f));
        for (auto& d : dots)
        {
            g.setColour (d.on ? juce::Colour (0xFF3DDC84) : juce::Colour (0xFF2E2E3A));
            g.fillEllipse ((float) x, (float) dotY, (float) kD, (float) kD);
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (d.label, x + kD + kGap, 0, d.approxW, 44,
                        juce::Justification::centredLeft);
            x += kD + kGap + d.approxW + kBetween;
        }
    }

    //==========================================================================
    void drawLeftColumn (juce::Graphics& g)
    {
        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawVerticalLine (200, 44.0f, (float) (getHeight() - 28));

        sectionLabel (g, "Artist input", 54);
        drawMeter (g, "L", leftDb,  juce::Rectangle<int> (12, 72,  176, 20));
        drawMeter (g, "R", rightDb, juce::Rectangle<int> (12, 96,  176, 20));

        divider (g, 118);
        sectionLabel (g, "Takes", 122);
        drawTakesPanel (g);

        divider (g, 228);
        sectionLabel (g, "Transport", 232);
        drawTransport (g);

        divider (g, 332);
        sectionLabel (g, "Sync", 336);
        drawSyncSettings (g);
    }

    void drawMeter (juce::Graphics& g, const juce::String& ch,
                    float db, juce::Rectangle<int> b)
    {
        g.setFont (TakeUI::monoFont (10.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (ch, b.removeFromLeft (16), juce::Justification::centred);
        g.drawText (juce::String (juce::roundToInt (db)) + "dB",
                    b.removeFromRight (40), juce::Justification::centred);
        auto bar = b.reduced (4, 5);
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

    void drawTakesPanel (juce::Graphics& g)
    {
        for (int i = 0; i < 3; ++i)
            drawTakeRow (g, juce::Rectangle<int> (0, 136 + i * 22, 200, 22), i + 1, false);
        drawTakeRow (g, juce::Rectangle<int> (0, 202, 200, 22), 4, true);
    }

    void drawTakeRow (juce::Graphics& g, juce::Rectangle<int> row, int num, bool live)
    {
        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (row.getBottom() - 1, 0.0f, 200.0f);

        auto numCol   = row.withWidth (28);
        auto badgeCol = juce::Rectangle<int> (158, row.getY(), 42, row.getHeight());
        auto waveCol  = juce::Rectangle<int> ( 28, row.getY(), 130, row.getHeight());

        auto numColour = live ? juce::Colour (0xFFFF4F4F) : juce::Colour (0xFF1D9E75);
        g.setFont (TakeUI::monoFont (10.0f, true));
        g.setColour (numColour);
        g.drawText ("T" + juce::String (num), numCol, juce::Justification::centred);

        float cy   = (float) row.getCentreY();
        auto waveColour = live ? juce::Colour (0xFFFF4F4F) : juce::Colour (0xFF185FA5);
        for (int px = waveCol.getX(); px < waveCol.getRight(); px += 2)
        {
            float t = (float)(px - waveCol.getX()) / (float) waveCol.getWidth();
            if (live && t > 0.60f) break;
            float amp = (std::sin (t * 21.0f + num * 1.3f) * 0.5f
                       + std::cos (t * 13.0f) * 0.3f
                       + std::sin (t * 37.0f) * 0.2f) * 0.5f + 0.5f;
            g.setColour (waveColour.withAlpha (0.75f));
            g.drawLine ((float) px, cy - juce::jlimit (0.1f, 1.0f, amp) * 5.0f,
                        (float) px, cy + juce::jlimit (0.1f, 1.0f, amp) * 5.0f, 1.0f);
        }

        auto badge = badgeCol.withSizeKeepingCentre (30, 14);
        g.setColour (numColour.withAlpha (0.15f));
        g.fillRoundedRectangle (badge.toFloat(), 3.0f);
        g.setColour (numColour);
        g.setFont (TakeUI::monoFont (8.0f, true));
        g.drawText (live ? "LIVE" : "WAV", badge, juce::Justification::centred);
    }

    void drawTransport (juce::Graphics& g)
    {
        auto recColour = isRecording ? juce::Colour (0xFFFF4F4F) : juce::Colour (0xFF8B2020);
        drawButton (g, recBtn(),   recColour,                 juce::String::fromUTF8 ("\xe2\x97\x8f Rec"));
        drawButton (g, stopBtn(),  juce::Colour (0xFF1A1A1E), juce::String::fromUTF8 ("\xe2\x96\xa0 Stop"));
        drawButton (g, rtzBtn(),   juce::Colour (0xFF1A1A1E), juce::String::fromUTF8 ("\xe2\x86\xa9 RTZ"));
        drawButton (g, punchBtn(), juce::Colour (0xFF5C3A00), juce::String::fromUTF8 ("\xe2\x8a\xa1 Punch"));
    }

    void drawButton (juce::Graphics& g, juce::Rectangle<int> b,
                     juce::Colour bg, const juce::String& label)
    {
        g.setColour (bg);
        g.fillRoundedRectangle (b.toFloat(), 4.0f);
        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFFF0F0F8));
        g.drawText (label, b, juce::Justification::centred);
    }

    void drawSyncSettings (juce::Graphics& g)
    {
        const char* labels[] = { "Auto-sync lossless", "Place on timeline", "Notify on sync" };
        for (int i = 0; i < 3; ++i)
        {
            auto row = syncRow (i);
            g.setFont (TakeUI::monoFont (9.0f));
            g.setColour (juce::Colour (0xFFC0C0D0));
            g.drawText (labels[i], row.getX() + 12, row.getY(), 130, row.getHeight(),
                        juce::Justification::centredLeft);
            drawTogglePill (g, 162, row.getCentreY() - 7, syncOn[i]);
        }
    }

    void drawTogglePill (juce::Graphics& g, int x, int y, bool on)
    {
        auto pill = juce::Rectangle<int> (x, y, 26, 14);
        g.setColour (on ? juce::Colour (0xFF185FA5) : juce::Colour (0xFF2A2A32));
        g.fillRoundedRectangle (pill.toFloat(), 7.0f);
        float cx = on ? (float) (pill.getRight() - 9) : (float) (pill.getX() + 9);
        g.setColour (juce::Colour (0xFFF0F0F8));
        g.fillEllipse (cx - 4.0f, (float) pill.getCentreY() - 4.0f, 8.0f, 8.0f);
    }

    //==========================================================================
    void drawRightColumn (juce::Graphics& g)
    {
        g.setFont (TakeUI::monoFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (juce::String::fromUTF8 ("Cue mix \xe2\x80\x94 artist headphones"),
                    212, 54, getWidth() - 224, 12, juce::Justification::centredLeft);

        drawCueMixKnobs (g);

        g.setFont (TakeUI::monoFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("4-band EQ", 212, 222, 120, 12, juce::Justification::centredLeft);

        drawEQSection (g);
    }

    void drawCueMixKnobs (juce::Graphics& g)
    {
        struct KnobDef { const char* label; int idx; juce::uint32 colour; };
        const KnobDef row1[] = {
            { "Rev size", 0, 0xFFA78BFA },
            { "Rev mix",  1, 0xFFA78BFA },
            { "Dly time", 2, 0xFF2DD4BF },
            { "Dly mix",  3, 0xFF2DD4BF },
        };
        const KnobDef row2[] = {
            { "Comp thr",   4, 0xFFFFB340 },
            { "Comp ratio", 5, 0xFFFFB340 },
            { "Cue vol",    6, 0xFF3DDC84 },
        };

        for (auto& k : row1)
        {
            auto p = knobCenter (k.idx);
            drawKnob (g, p.cx, p.cy, (float) cueMix[k.idx], juce::Colour (k.colour), k.label);
        }
        for (auto& k : row2)
        {
            auto p = knobCenter (k.idx);
            drawKnob (g, p.cx, p.cy, (float) cueMix[k.idx], juce::Colour (k.colour), k.label);
        }
    }

    void drawKnob (juce::Graphics& g, float cx, float cy, float value,
                   juce::Colour colour, const juce::String& label)
    {
        constexpr float r = 16.0f;

        g.setColour (juce::Colour (0xFF0A0A0B));
        g.fillEllipse (cx - r, cy - r, r * 2.0f, r * 2.0f);

        g.setColour (juce::Colour (0xFF2A2A32));
        g.drawEllipse (cx - r + 0.5f, cy - r + 0.5f, (r - 0.5f) * 2.0f, (r - 0.5f) * 2.0f, 1.0f);

        static const float kStart = juce::MathConstants<float>::pi * 1.2f;
        static const float kEnd   = juce::MathConstants<float>::pi * 2.8f;
        float angle = kStart + (value / 100.0f) * (kEnd - kStart);
        g.setColour (colour);
        g.drawLine (cx + std::sin (angle) * 4.0f,  cy - std::cos (angle) * 4.0f,
                    cx + std::sin (angle) * 12.0f, cy - std::cos (angle) * 12.0f, 2.0f);

        g.setFont (TakeUI::monoFont (8.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (label, (int) (cx - 32), (int) (cy + r + 3), 64, 10,
                    juce::Justification::centred);

        g.setColour (colour.withAlpha (0.85f));
        g.drawText (juce::String (juce::roundToInt (value)),
                    (int) (cx - 20), (int) (cy + r + 13), 40, 10,
                    juce::Justification::centred);
    }

    void drawEQSection (juce::Graphics& g)
    {
        const char* freqs[] = { "80Hz", "400Hz", "2kHz", "8kHz" };
        for (int i = 0; i < 4; ++i)
            drawEQSlider (g, i, (float) eq[i], freqs[i]);
    }

    void drawEQSlider (juce::Graphics& g, int i, float value, const juce::String& label)
    {
        auto b = eqSliderBounds (i);

        g.setColour (juce::Colour (0xFF1A1A1E));
        g.fillRoundedRectangle (b, 3.0f);

        float fillH = b.getHeight() * (value / 100.0f);
        g.setColour (juce::Colour (0xFF185FA5));
        g.fillRoundedRectangle (b.withTop (b.getBottom() - fillH), 3.0f);

        g.setFont (TakeUI::monoFont (8.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (label, (int) (b.getCentreX() - 24), (int) (b.getBottom() + 4),
                    48, 10, juce::Justification::centred);
    }

    //==========================================================================
    void drawStatusBar (juce::Graphics& g)
    {
        int barY = getHeight() - 28;
        g.setColour (juce::Colour (0xFF0A0A0B));
        g.fillRect (0, barY, getWidth(), 28);
        g.setColour (juce::Colour (0xFF1A1A20));
        g.drawHorizontalLine (barY, 0.0f, (float) getWidth());
        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("Latency 0ms  |  BW 0 kbps  |  WAV 48k  |  Takes 3  |  Last T3",
                    16, barY, getWidth() - 32, 28, juce::Justification::centredLeft);
    }

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (EngineerScreen)
};
