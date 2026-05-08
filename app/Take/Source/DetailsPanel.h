#pragma once
#include <JuceHeader.h>

//==============================================================================
class DetailsPanel : public juce::Component
{
public:
    std::function<void()> onClose;

    DetailsPanel() {}

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
        const Conn conns[] = {
            { "Plugin link",   true  },
            { "Relay server",  true  },
            { "Artist app",    true  },
            { "Engineer app",  true  },
            { "Reaper API",    false },
            { "BlackHole 2ch", true  },
        };

        for (int i = 0; i < 6; ++i)
        {
            int rowY = 70 + i * 18;
            g.setColour (conns[i].ok ? juce::Colour (0xFF3DDC84) : juce::Colour (0xFF2E2E3A));
            g.fillEllipse (16.0f, (float) rowY + 4.0f, 6.0f, 6.0f);
            g.setFont (dpFont (10.0f));
            g.setColour (juce::Colour (0xFFC0C0D0));
            g.drawText (conns[i].name, 28, rowY, 180, 14, juce::Justification::centredLeft);
            g.setFont (dpFont (9.0f));
            g.setColour (conns[i].ok ? juce::Colour (0xFF3DDC84) : juce::Colour (0xFF5C5C6E));
            g.drawText (conns[i].ok ? "OK" : "OFF", getWidth() - 52, rowY, 36, 14,
                        juce::Justification::centredRight);
        }

        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (182, 0.0f, (float) getWidth());
    }

    void drawActivityLog (juce::Graphics& g)
    {
        g.setFont (dpFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("ACTIVITY", 16, 190, getWidth() - 32, 12, juce::Justification::centredLeft);

        const char* const entries[] = {
            "14:51:03  Session started",
            "14:51:09  Artist connected",
            "14:53:22  Backing track sent",
            "14:55:41  T4 recording started",
            "14:55:58  T4 sync - 0.4s",
        };

        for (int i = 0; i < 5; ++i)
        {
            g.setFont (dpFont (9.0f));
            g.setColour (juce::Colour (0xFF7A7A8E));
            g.drawText (entries[i], 16, 206 + i * 16, getWidth() - 32, 14,
                        juce::Justification::centredLeft);
        }

        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (294, 0.0f, (float) getWidth());
    }

    void drawBandwidth (juce::Graphics& g)
    {
        g.setFont (dpFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("BANDWIDTH", 16, 302, getWidth() - 32, 12, juce::Justification::centredLeft);

        struct Card { const char* label; const char* value; };
        const Card cards[] = {
            { "Stream UP", "0.8 Mbps" },
            { "Stream DN", "0.4 Mbps" },
            { "Total",     "214 MB"   },
        };

        constexpr int kCardY = 320, kCardH = 52, kGap = 8, kPad = 16;
        int cardW = (getWidth() - kPad * 2 - kGap * 2) / 3;

        for (int i = 0; i < 3; ++i)
        {
            int cx = kPad + i * (cardW + kGap);
            auto r = juce::Rectangle<int> (cx, kCardY, cardW, kCardH);

            g.setColour (juce::Colour (0xFF18181C));
            g.fillRoundedRectangle (r.toFloat(), 4.0f);
            g.setColour (juce::Colour (0xFF222228));
            g.drawRoundedRectangle (r.toFloat(), 4.0f, 1.0f);

            g.setFont (dpFont (8.0f));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (cards[i].label, cx + 4, kCardY + 6, cardW - 8, 12,
                        juce::Justification::centred);

            g.setFont (dpFont (11.0f, true));
            g.setColour (juce::Colour (0xFFF0F0F8));
            g.drawText (cards[i].value, cx + 4, kCardY + 22, cardW - 8, 16,
                        juce::Justification::centred);
        }
    }

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (DetailsPanel)
};
