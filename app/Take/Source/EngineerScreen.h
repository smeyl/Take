#pragma once
#include <JuceHeader.h>
#include "DetailsPanel.h"

//==============================================================================
class EngineerScreen : public juce::Component
{
public:
    EngineerScreen()
    {
        setOpaque (true);
        addChildComponent (detailsPanel);
        detailsPanel.onClose = [this] {
            detailsVisible = false;
            detailsPanel.setVisible (false);
            applyWindowSize (false);
            repaint();
        };
    }

    void setSessionCode (const juce::String& code) { sessionCode = code; repaint(); }
    void setRecording   (bool rec, int take = 1)   { isRecording = rec; takeNum = take; repaint(); }
    void setLevel       (float l, float r)          { leftDb = l; rightDb = r; repaint(); }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (juce::Colour (0xFF111113));
        drawHeader      (g);
        drawLeftColumn  (g);
        drawRightColumn (g);
        drawRightPanel  (g);
        drawStatusBar   (g);
    }

    void resized() override
    {
        detailsPanel.setBounds (kBaseWidth, 0, 300, getHeight());
    }

    void mouseDown (const juce::MouseEvent& e) override
    {
        if (detailsBtn().contains (e.getPosition()))
        {
            detailsVisible = !detailsVisible;
            detailsPanel.setVisible (detailsVisible);
            if (detailsVisible) detailsPanel.toFront (false);
            applyWindowSize (detailsVisible);
            repaint();
            return;
        }

        // Left column
        if (e.x < 200)
        {
            auto p = e.getPosition();
            if (recBtn().contains (p))           { isRecording = !isRecording; repaint(); return; }
            for (int i = 0; i < 3; ++i)
                if (syncRow (i).contains (p))    { syncOn[i] = !syncOn[i]; repaint(); return; }
            return;
        }

        // Right panel
        if (e.x >= rightPanelX())
        {
            for (int i = 0; i < 3; ++i)
                if (panelPillBounds (i, kStreamPillY).contains (e.getPosition()))
                    { streamQuality = i; repaint(); return; }

            for (int i = 0; i < 3; ++i)
                if (panelPillBounds (i, kSyncPillY).contains (e.getPosition()))
                    { syncFormat = i; repaint(); return; }

            for (int i = 0; i < 3; ++i)
                if (backingRowBounds (i).contains (e.getPosition()))
                    { backingTrack[i] = !backingTrack[i]; repaint(); return; }

            for (int i = 0; i < 3; ++i)
                if (panelPillBounds (i, kBackingQualPillY).contains (e.getPosition()))
                    { backingQuality = i; repaint(); return; }
            return;
        }

        // Cue mix knobs (200 <= x < rightPanelX())
        // Large Cue vol knob (index 6, r=20) — checked first, it's in a different position
        {
            auto cv = cueVolCenter();
            float dx = e.x - cv.x, dy = e.y - cv.y;
            if (dx * dx + dy * dy <= 20.0f * 20.0f)
                { dragging = 6; dragStartY = e.y; dragStartVal = cueMix[6]; return; }
        }
        // Small knobs — indices 0-5
        for (int i = 0; i < 6; ++i)
        {
            auto k = knobCenter (i);
            float dx = e.x - k.cx, dy = e.y - k.cy;
            if (dx * dx + dy * dy <= 16.0f * 16.0f)
                { dragging = i; dragStartY = e.y; dragStartVal = cueMix[i]; return; }
        }

        // EQ sliders
        for (int i = 0; i < 4; ++i)
            if (eqSliderBounds (i).expanded (10.0f, 0.0f).contains ((float) e.x, (float) e.y))
                { dragging = 7 + i; dragStartY = e.y; dragStartVal = eq[i]; return; }
    }

    void mouseDrag (const juce::MouseEvent& e) override
    {
        if (dragging < 0) return;
        int val = juce::jlimit (0, 100, dragStartVal + (dragStartY - e.y));
        if (dragging < 7) cueMix[dragging]  = val;
        else              eq[dragging - 7]  = val;
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

    // Cue mix state
    int cueMix[7] { 60, 30, 50, 20, 55, 40, 75 };
    int eq[4]     { 50, 50, 60, 65 };

    // Right panel state
    int  streamQuality   { 1 };          // 0=AAC 128, 1=AAC 256, 2=FLAC
    int  syncFormat      { 1 };          // 0=FLAC,    1=WAV 24,  2=WAV 32f
    bool backingTrack[3] { true, true, true };
    int  backingQuality  { 1 };          // 0=MP3 128, 1=MP3 256, 2=WAV

    // Drag state (cue mix / EQ)
    int dragging     { -1 };
    int dragStartY   {  0 };
    int dragStartVal {  0 };

    bool         detailsVisible { false };
    DetailsPanel detailsPanel;

    //==========================================================================
    // Layout
    static constexpr int kBaseWidth        = 820;
    static constexpr int kBaseHeight       = 700;
    static constexpr int kRightPanelW      = 180;
    static constexpr int kStreamPillY      =  70;
    static constexpr int kSyncPillY        = 122;
    static constexpr int kBackingRowBase   = 174;
    static constexpr int kBackingQualPillY = 252;

    int contentWidth() const { return juce::jmin (getWidth(), kBaseWidth); }
    int rightPanelX()  const { return contentWidth() - kRightPanelW; }
    juce::Rectangle<int> detailsBtn() const { return { contentWidth() - 62, 9, 50, 26 }; }

    //==========================================================================
    // Left column — static hit rects
    static juce::Rectangle<int> recBtn()        { return {  12, 318, 86, 52 }; }
    static juce::Rectangle<int> stopBtn()       { return { 102, 318, 86, 52 }; }
    static juce::Rectangle<int> rtzBtn()        { return {  12, 378, 86, 52 }; }
    static juce::Rectangle<int> punchBtn()      { return { 102, 378, 86, 52 }; }
    static juce::Rectangle<int> syncRow (int i) { return {   0, 484 + i*22, 200, 22 }; }
    static juce::Rectangle<int> syncNowBtn()    { return {  12, 568, 176, 36 }; }


    // Cue mix — dynamic (depends on getWidth())
    struct KnobPos { float cx, cy; };

    KnobPos knobCenter (int index) const
    {
        float rw = (float) (rightPanelX() - 200);
        if (index < 4)
        {
            float sw = rw / 4.0f;
            return { 200.0f + sw * index + sw * 0.5f, 94.0f };
        }
        float sw = rw / 2.0f;   // row 2 now has 2 knobs (Comp thr, Comp ratio)
        return { 200.0f + sw * (index - 4) + sw * 0.5f, 172.0f };
    }

    juce::Point<float> cueVolCenter() const
    {
        float midX = 200.0f + (float) (rightPanelX() - 200) * 0.5f;
        return { midX, 368.0f };
    }

    juce::Rectangle<float> eqSliderBounds (int i) const
    {
        float rw = (float) (rightPanelX() - 200);
        float sw = rw / 4.0f;
        float cx = 200.0f + sw * i + sw * 0.5f;
        return { cx - 4.0f, 256.0f, 8.0f, 50.0f };
    }

    // Right panel — hit rects
    int panelPillW() const { return (kRightPanelW - 20 - 8) / 3; }  // 50px for 3 pills with 4px gaps

    juce::Rectangle<int> panelPillBounds (int col, int y) const
    {
        int pw = panelPillW();
        return { rightPanelX() + 10 + col * (pw + 4), y, pw, 20 };
    }

    juce::Rectangle<int> backingRowBounds (int i) const
    {
        return { rightPanelX() + 10, kBackingRowBase + i * 22, kRightPanelW - 20, 22 };
    }

    juce::Rectangle<int> sendBtnBounds() const
    {
        return { rightPanelX() + 10, 282, kRightPanelW - 20, 28 };
    }

    void applyWindowSize (bool withPanel)
    {
        int w = kBaseWidth + (withPanel ? 300 : 0);
        if (auto* rw = dynamic_cast<juce::ResizableWindow*> (getTopLevelComponent()))
            rw->setContentComponentSize (w, kBaseHeight);
    }

    //==========================================================================
    // Shared drawing helpers
    void sectionLabel (juce::Graphics& g, const juce::String& text, int y)
    {
        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (text, 12, y, 140, 14, juce::Justification::centredLeft);
    }

    void divider (juce::Graphics& g, int y)
    {
        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (y, 0.0f, 200.0f);
    }

    void rightSectionLabel (juce::Graphics& g, const juce::String& text, int y)
    {
        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (text, rightPanelX() + 10, y, kRightPanelW - 20, 14,
                    juce::Justification::centredLeft);
    }

    void rightDivider (juce::Graphics& g, int y)
    {
        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (y, (float) rightPanelX(), (float) getWidth());
    }

    void drawPills (juce::Graphics& g, int x, int y, int totalW,
                    const char* const* labels, int count, int selected)
    {
        int gap = 4;
        int pw  = (totalW - (count - 1) * gap) / count;
        for (int i = 0; i < count; ++i)
        {
            auto r   = juce::Rectangle<int> (x + i * (pw + gap), y, pw, 20);
            bool sel = (i == selected);
            g.setColour (sel ? juce::Colour (0xFF185FA5) : juce::Colour (0xFF1A1A1E));
            g.fillRoundedRectangle (r.toFloat(), 4.0f);
            g.setFont (TakeUI::monoFont (8.0f, sel));
            g.setColour (sel ? juce::Colour (0xFFF0F0F8) : juce::Colour (0xFF5C5C6E));
            g.drawText (labels[i], r, juce::Justification::centred);
        }
    }

    void drawCheckRow (juce::Graphics& g, int x, int y, const char* label, bool checked)
    {
        auto box = juce::Rectangle<int> (x, y + 5, 12, 12);
        g.setColour (checked ? juce::Colour (0xFF185FA5) : juce::Colour (0xFF2A2A32));
        g.fillRoundedRectangle (box.toFloat(), 2.0f);
        if (checked)
        {
            g.setColour (juce::Colour (0xFFF0F0F8));
            float bx = (float) box.getX(), by = (float) box.getY();
            float bw = (float) box.getWidth(), bh = (float) box.getHeight();
            g.drawLine (bx + 2.0f,      by + bh * 0.55f, bx + bw * 0.42f, by + bh * 0.85f, 1.5f);
            g.drawLine (bx + bw * 0.42f, by + bh * 0.85f, bx + bw - 2.0f, by + bh * 0.15f, 1.5f);
        }
        g.setFont (TakeUI::monoFont (9.0f));
        g.setColour (juce::Colour (0xFFC0C0D0));
        g.drawText (label, x + 18, y, kRightPanelW - 30, 22, juce::Justification::centredLeft);
    }

    //==========================================================================
    void drawHeader (juce::Graphics& g)
    {
        g.setColour (juce::Colour (0xFF1E1E24));
        g.fillRect (0, 43, getWidth(), 1);

        g.setFont (TakeUI::monoFont (15.0f, true));
        g.setColour (juce::Colour (0xFF185FA5));
        g.drawText ("TAKE", 16, 0, 60, 44, juce::Justification::centredLeft);

        // Details button
        {
            auto db = detailsBtn();
            g.setColour (juce::Colour (detailsVisible ? 0xFF185FA5 : 0xFF1A1A1E));
            g.fillRoundedRectangle (db.toFloat(), 4.0f);
            g.setFont (TakeUI::monoFont (10.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText ("Details", db, juce::Justification::centred);
        }

        if (isRecording)
        {
            g.setColour (juce::Colour (0xFFFF4F4F));
            g.fillEllipse ((float) (contentWidth() - 152), 19.0f, 6.0f, 6.0f);
            g.setFont (TakeUI::monoFont (11.0f));
            g.drawText ("REC T" + juce::String (takeNum),
                        contentWidth() - 146, 0, 80, 44, juce::Justification::centredLeft);
        }
        else
        {
            g.setFont (TakeUI::monoFont (11.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (sessionCode, contentWidth() - 192, 0, 120, 44,
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

        int left = 76, right = contentWidth() - 196;
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

        sectionLabel (g, "Artist input", 64);
        drawMeter (g, "L", leftDb,  { 12, 78,  176, 20 });
        drawMeter (g, "R", rightDb, { 12, 102, 176, 20 });

        divider (g, 140);
        sectionLabel (g, "Takes", 162);
        drawTakesPanel (g);

        divider (g, 282);
        sectionLabel (g, "Transport", 304);
        drawTransport (g);

        divider (g, 448);
        sectionLabel (g, "Sync", 470);
        drawSyncSettings (g);
        drawSyncNowBtn (g);

        divider (g, 622);
        const char* const fmtNames[] = { "FLAC", "WAV 24", "WAV 32f" };
        g.setFont (TakeUI::monoFont (9.0f));
        g.setColour (juce::Colour (0xFF3A3A48));
        g.drawText (juce::String ("Format: ") + fmtNames[syncFormat],
                    12, 636, 176, 14, juce::Justification::centredLeft);
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
            drawTakeRow (g, { 0, 176 + i * 22, 200, 22 }, i + 1, false);
        drawTakeRow (g, { 0, 242, 200, 22 }, 4, true);
    }

    void drawTakeRow (juce::Graphics& g, juce::Rectangle<int> row, int num, bool live)
    {
        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (row.getBottom() - 1, 0.0f, 200.0f);

        auto numCol   = row.withWidth (28);
        auto badgeCol = juce::Rectangle<int> (158, row.getY(), 42, row.getHeight());
        auto waveCol  = juce::Rectangle<int> ( 28, row.getY(), 130, row.getHeight());

        auto numColour = live ? juce::Colour (0xFFFF4F4F) : juce::Colour (0xFF1D9E75);
        g.setFont (TakeUI::monoFont (12.0f, true));
        g.setColour (numColour);
        g.drawText ("T" + juce::String (num), numCol, juce::Justification::centred);

        float cy        = (float) row.getCentreY();
        auto  waveColour = live ? juce::Colour (0xFFFF4F4F) : juce::Colour (0xFF185FA5);
        for (int px = waveCol.getX(); px < waveCol.getRight(); px += 2)
        {
            float t = (float) (px - waveCol.getX()) / (float) waveCol.getWidth();
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
        g.setFont (TakeUI::monoFont (10.0f, true));
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
        g.setFont (TakeUI::monoFont (13.0f, true));
        g.setColour (juce::Colour (0xFFF0F0F8));
        g.drawText (label, b, juce::Justification::centred);
    }

    void drawSyncSettings (juce::Graphics& g)
    {
        const char* labels[] = { "Auto-sync lossless", "Place on timeline", "Notify on sync" };
        for (int i = 0; i < 3; ++i)
        {
            auto row = syncRow (i);
            g.setFont (TakeUI::monoFont (12.0f));
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

    void drawSyncNowBtn (juce::Graphics& g)
    {
        auto b = syncNowBtn();
        g.setColour (juce::Colour (0xFF0D0D10));
        g.fillRoundedRectangle (b.toFloat(), 4.0f);
        g.setColour (juce::Colour (0xFF185FA5));
        g.drawRoundedRectangle (b.toFloat().reduced (0.5f), 4.0f, 1.0f);
        g.setFont (TakeUI::monoFont (12.0f));
        g.drawText (juce::String::fromUTF8 ("Sync now \xe2\x80\x94 T4"),
                    b, juce::Justification::centred);
    }


    //==========================================================================
    void drawRightColumn (juce::Graphics& g)
    {
        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText (juce::String::fromUTF8 ("Cue mix \xe2\x80\x94 artist headphones"),
                    212, 54, rightPanelX() - 224, 14, juce::Justification::centredLeft);

        drawCueMixKnobs (g);

        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("4-band EQ", 212, 222, 120, 14, juce::Justification::centredLeft);

        drawEQSection (g);
        drawCueVolSection (g);

        // Divider between cue mix and right panel
        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawVerticalLine (rightPanelX(), 44.0f, (float) (getHeight() - 28));
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

    void drawCueVolSection (juce::Graphics& g)
    {
        // Section label
        g.setFont (TakeUI::monoFont (11.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("Cue volume", 212, 334, rightPanelX() - 224, 14,
                    juce::Justification::centredLeft);

        // Large knob (r=20, diameter=40)
        auto cv   = cueVolCenter();
        float cx  = cv.x, cy = cv.y;
        constexpr float r = 20.0f;

        g.setColour (juce::Colour (0xFF0A0A0B));
        g.fillEllipse (cx - r, cy - r, r * 2.0f, r * 2.0f);

        g.setColour (juce::Colour (0xFF2A2A32));
        g.drawEllipse (cx - r + 0.5f, cy - r + 0.5f, (r - 0.5f) * 2.0f, (r - 0.5f) * 2.0f, 1.0f);

        static const float kStart = juce::MathConstants<float>::pi * 1.2f;
        static const float kEnd   = juce::MathConstants<float>::pi * 2.8f;
        float angle = kStart + ((float) cueMix[6] / 100.0f) * (kEnd - kStart);
        g.setColour (juce::Colour (0xFF3DDC84));
        g.drawLine (cx + std::sin (angle) * 6.0f,  cy - std::cos (angle) * 6.0f,
                    cx + std::sin (angle) * 15.0f, cy - std::cos (angle) * 15.0f, 2.5f);

        // Value below knob
        g.setFont (TakeUI::monoFont (10.0f, true));
        g.setColour (juce::Colour (0xFF3DDC84).withAlpha (0.85f));
        g.drawText (juce::String (cueMix[6]),
                    (int) (cx - 20), (int) (cy + r + 4), 40, 12,
                    juce::Justification::centred);

        // Thin divider
        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (408, 212.0f, (float) (rightPanelX() - 12));

        // Info notes
        g.setFont (TakeUI::monoFont (9.0f));
        g.setColour (juce::Colour (0xFF3A3A48));
        int noteW = rightPanelX() - 224;
        g.drawText ("Parameters sync to artist in real time",
                    212, 420, noteW, 12, juce::Justification::centred);
        g.drawText ("Zero monitoring latency",
                    212, 434, noteW, 12, juce::Justification::centred);
    }

    //==========================================================================
    void drawRightPanel (juce::Graphics& g)
    {
        int cx = rightPanelX() + 10;
        int cw = kRightPanelW - 20;

        // STREAM QUALITY -------------------------------------------------------
        rightSectionLabel (g, "Stream quality", 54);
        {
            const char* labels[] = { "AAC 128", "AAC 256", "FLAC" };
            drawPills (g, cx, kStreamPillY, cw, labels, 3, streamQuality);
        }
        rightDivider (g, 100);

        // SYNC FORMAT ----------------------------------------------------------
        rightSectionLabel (g, "Sync format", 106);
        {
            const char* labels[] = { "FLAC", "WAV 24", "WAV 32f" };
            drawPills (g, cx, kSyncPillY, cw, labels, 3, syncFormat);
        }
        rightDivider (g, 152);

        // BACKING TRACK --------------------------------------------------------
        rightSectionLabel (g, "Backing track", 158);
        {
            const char* tracks[] = { "01 - Drums", "02 - Bass", "03 - Keys" };
            for (int i = 0; i < 3; ++i)
                drawCheckRow (g, cx, kBackingRowBase + i * 22, tracks[i], backingTrack[i]);
        }
        rightDivider (g, 244);

        {
            const char* labels[] = { "MP3 128", "MP3 256", "WAV" };
            drawPills (g, cx, kBackingQualPillY, cw, labels, 3, backingQuality);
        }

        // Send to artist button
        auto sb = sendBtnBounds();
        g.setColour (juce::Colour (0xFF185FA5));
        g.fillRoundedRectangle (sb.toFloat(), 4.0f);
        g.setFont (TakeUI::monoFont (11.0f, true));
        g.setColour (juce::Colour (0xFFF0F0F8));
        g.drawText ("Send to artist", sb, juce::Justification::centred);

        // Status line
        g.setFont (TakeUI::monoFont (9.0f));
        g.setColour (juce::Colour (0xFF3DDC84));
        g.drawText ("Sent - artist confirmed", cx, 316, cw, 14,
                    juce::Justification::centred);

        rightDivider (g, 338);

        // LAST FILE SWAP -------------------------------------------------------
        rightSectionLabel (g, "Last file swap", 344);

        auto card = juce::Rectangle<int> (cx, 360, cw, 68);
        g.setColour (juce::Colour (0xFF18181C));
        g.fillRoundedRectangle (card.toFloat(), 4.0f);
        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawRoundedRectangle (card.toFloat(), 4.0f, 1.0f);

        g.setFont (TakeUI::monoFont (10.0f, true));
        g.setColour (juce::Colour (0xFFF0F0F8));
        g.drawText ("T4 - 14:55:58", cx + 8, 368, cw - 16, 14,
                    juce::Justification::centredLeft);

        g.setFont (TakeUI::monoFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("0.4s - WAV 24", cx + 8, 384, cw - 16, 14,
                    juce::Justification::centredLeft);

        // Programmatic checkmark + "Timeline updated"
        g.setColour (juce::Colour (0xFF1D9E75));
        float ckx = (float) (cx + 8), cky = 400.0f;
        g.drawLine (ckx,        cky + 5.0f, ckx + 4.0f,  cky + 9.0f, 1.5f);
        g.drawLine (ckx + 4.0f, cky + 9.0f, ckx + 10.0f, cky + 2.0f, 1.5f);
        g.setFont (TakeUI::monoFont (9.0f));
        g.drawText ("Timeline updated", cx + 20, 398, cw - 28, 14,
                    juce::Justification::centredLeft);
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
                    16, barY, contentWidth() - 32, 28, juce::Justification::centredLeft);
    }

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (EngineerScreen)
};
