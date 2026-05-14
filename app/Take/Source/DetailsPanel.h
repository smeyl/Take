#pragma once
#include <JuceHeader.h>

//==============================================================================
class DetailsPanel : public juce::Component
{
public:
    std::function<void()> onClose;

    DetailsPanel() {}

    void setEngineerConnected (bool v) { engineerOk = v; repaint(); }

    void paint (juce::Graphics& g) override
    {
        g.setColour (juce::Colour (0xFF0D0D0F));
        g.fillRect (getLocalBounds());
        g.setColour (juce::Colour (0xFF222228));
        g.drawVerticalLine (0, 0.0f, (float) getHeight());

        drawPanelHeader (g);
        drawConnections (g);
        drawActivityLog (g);
        drawBandwidth   (g);
    }

    void mouseDown (const juce::MouseEvent& e) override
    {
        if (closeBtnBounds().contains (e.getPosition()))
            if (onClose) onClose();
    }

private:
    bool engineerOk { false };

    //-- layout ----------------------------------------------------------------
    static constexpr int kConnStartY = 70;
    static constexpr int kConnRowH   = 18;
    static constexpr int kConnCount  = 3;
    static constexpr int kConnSepY   = kConnStartY + kConnCount * kConnRowH + 4;

    static constexpr int kLogLabelY  = kConnSepY + 10;
    static constexpr int kLogStartY  = kLogLabelY + 18;
    static constexpr int kLogSepY    = kLogStartY + 80;

    static constexpr int kBwLabelY   = kLogSepY + 10;
    static constexpr int kBwCardY    = kBwLabelY + 18;
    static constexpr int kBwCardH    = 52;

    //-- drawing helpers -------------------------------------------------------
    static juce::Font dpFont (float size, bool bold = false)
    {
        int style = bold ? juce::Font::bold : juce::Font::plain;
        return juce::Font (juce::Font::getDefaultMonospacedFontName(), size, style);
    }

    juce::Rectangle<int> closeBtnBounds() const { return { getWidth() - 32, 10, 22, 22 }; }

    void drawPanelHeader (juce::Graphics& g)
    {
        g.setFont (dpFont (13.0f, true));
        g.setColour (juce::Colour (0xFFF0F0F8));
        g.drawText ("Details", 16, 0, 160, 44, juce::Justification::centredLeft);

        auto cb = closeBtnBounds();
        g.setColour (juce::Colour (0xFF2A2A32));
        g.fillRoundedRectangle (cb.toFloat(), 4.0f);
        g.setFont (dpFont (13.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("x", cb, juce::Justification::centred);

        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (44, 0.0f, (float) getWidth());
    }

    void drawConnections (juce::Graphics& g)
    {
        g.setFont (dpFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("CONNECTIONS", 16, 54, getWidth() - 32, 12, juce::Justification::centredLeft);

        struct Conn { const char* name; bool ok; };
        const Conn conns[kConnCount] = {
            { "Companion", false      },
            { "Server",    false      },
            { "Engineer",  engineerOk },
        };

        for (int i = 0; i < kConnCount; ++i)
        {
            const int  rowY = kConnStartY + i * kConnRowH;
            const auto dot  = conns[i].ok ? juce::Colour (0xFF3DDC84) : juce::Colour (0xFF2E2E3A);

            g.setColour (dot);
            g.fillEllipse (16.0f, (float) rowY + 4.0f, 6.0f, 6.0f);

            g.setFont (dpFont (10.0f));
            g.setColour (juce::Colour (0xFFC0C0D0));
            g.drawText (conns[i].name, 28, rowY, 180, 14, juce::Justification::centredLeft);

            g.setFont (dpFont (9.0f));
            g.setColour (conns[i].ok ? juce::Colour (0xFF3DDC84) : juce::Colour (0xFF5C5C6E));
            g.drawText (conns[i].ok ? "OK" : "--",
                        getWidth() - 52, rowY, 36, 14, juce::Justification::centredRight);
        }

        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (kConnSepY, 0.0f, (float) getWidth());
    }

    void drawActivityLog (juce::Graphics& g)
    {
        g.setFont (dpFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("ACTIVITY", 16, kLogLabelY, getWidth() - 32, 12, juce::Justification::centredLeft);

        g.setFont (dpFont (9.0f));
        g.setColour (juce::Colour (0xFF3A3A48));
        g.drawText ("No activity yet", 16, kLogStartY, getWidth() - 32, 14,
                    juce::Justification::centredLeft);

        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (kLogSepY, 0.0f, (float) getWidth());
    }

    void drawBandwidth (juce::Graphics& g)
    {
        g.setFont (dpFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("BANDWIDTH", 16, kBwLabelY, getWidth() - 32, 12, juce::Justification::centredLeft);

        const char* labels[] = { "Stream UP", "Stream DN", "Total sent" };

        constexpr int kGap = 8, kPad = 16;
        const int cardW = (getWidth() - kPad * 2 - kGap * 2) / 3;

        for (int i = 0; i < 3; ++i)
        {
            const int cx = kPad + i * (cardW + kGap);
            auto r = juce::Rectangle<int> (cx, kBwCardY, cardW, kBwCardH);

            g.setColour (juce::Colour (0xFF18181C));
            g.fillRoundedRectangle (r.toFloat(), 4.0f);
            g.setColour (juce::Colour (0xFF222228));
            g.drawRoundedRectangle (r.toFloat(), 4.0f, 1.0f);

            g.setFont (dpFont (8.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (labels[i], cx + 4, kBwCardY + 6, cardW - 8, 12,
                        juce::Justification::centred);

            g.setFont (dpFont (11.0f, true));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText ("--", cx + 4, kBwCardY + 22, cardW - 8, 16,
                        juce::Justification::centred);
        }
    }

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (DetailsPanel)
};
