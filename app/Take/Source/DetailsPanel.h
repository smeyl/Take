#pragma once
#include <JuceHeader.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <thread>

//==============================================================================
class DetailsPanel : public juce::Component,
                     public juce::Timer
{
public:
    std::function<void()> onClose;

    DetailsPanel()
    {
        startTimer (10000);
    }

    ~DetailsPanel() override
    {
        stopTimer();
    }

    void setEngineerConnected (bool v) { engineerOk = v; repaint(); }

    void timerCallback() override
    {
        juce::Component::SafePointer<DetailsPanel> safeThis (this);

        std::thread ([safeThis]()
        {
            bool compOk = false, srvOk = false;
            juce::String dummy, takesJson;

            compOk = rawHttpGet ("127.0.0.1", 5010, "/session/active", dummy);
            srvOk  = rawHttpGet ("127.0.0.1", 5001, "/",               dummy);
            rawHttpGet ("127.0.0.1", 5001, "/takes", takesJson);

            juce::StringArray rows;
            juce::int64 bytes = 0;
            parseTakes (takesJson, rows, bytes);

            juce::MessageManager::callAsync ([safeThis, compOk, srvOk, rows, bytes]() mutable
            {
                if (safeThis == nullptr) return;
                safeThis->companionOk = compOk;
                safeThis->serverOk    = srvOk;
                safeThis->takeRows    = std::move (rows);
                safeThis->totalBytes  = bytes;
                safeThis->repaint();
            });
        }).detach();
    }

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
    bool              engineerOk  { false };
    bool              companionOk { false };
    bool              serverOk    { false };
    juce::StringArray takeRows;
    juce::int64       totalBytes  { 0 };

    //-- layout ----------------------------------------------------------------
    static constexpr int kConnStartY = 70;
    static constexpr int kConnRowH   = 18;
    static constexpr int kConnCount  = 3;
    static constexpr int kConnSepY   = kConnStartY + kConnCount * kConnRowH + 4;

    static constexpr int kLogLabelY  = kConnSepY + 10;
    static constexpr int kLogStartY  = kLogLabelY + 18;
    static constexpr int kLogRowH    = 13;
    static constexpr int kLogRows    = 6;
    static constexpr int kLogSepY    = kLogStartY + kLogRows * kLogRowH + 4;

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
            { "Companion", companionOk },
            { "Server",    serverOk   },
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

        if (takeRows.isEmpty())
        {
            g.setColour (juce::Colour (0xFF3A3A48));
            g.drawText ("No activity yet", 16, kLogStartY, getWidth() - 32, kLogRowH,
                        juce::Justification::centredLeft);
        }
        else
        {
            g.setFont (dpFont (9.0f));
            for (int i = 0; i < juce::jmin (takeRows.size(), kLogRows); ++i)
            {
                g.setColour (juce::Colour (0xFFA0A0B4));
                g.drawText (takeRows[i], 16, kLogStartY + i * kLogRowH,
                            getWidth() - 32, kLogRowH, juce::Justification::centredLeft);
            }
        }

        g.setColour (juce::Colour (0xFF1E1E24));
        g.drawHorizontalLine (kLogSepY, 0.0f, (float) getWidth());
    }

    void drawBandwidth (juce::Graphics& g)
    {
        g.setFont (dpFont (9.0f));
        g.setColour (juce::Colour (0xFF5C5C6E));
        g.drawText ("BANDWIDTH", 16, kBwLabelY, getWidth() - 32, 12, juce::Justification::centredLeft);

        const char* labels[] = { "Stream UP", "Stream DN", "Total rcvd" };

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

            juce::String val = "--";
            if (i == 2 && totalBytes > 0)
            {
                double mb = (double) totalBytes / (1024.0 * 1024.0);
                val = juce::String (mb, 1) + " MB";
            }

            g.setFont (dpFont (11.0f, true));
            g.setColour (juce::Colour (0xFF5C5C6E));
            g.drawText (val, cx + 4, kBwCardY + 22, cardW - 8, 16,
                        juce::Justification::centred);
        }
    }

    //-- network ---------------------------------------------------------------
    static void parseTakes (const juce::String& json,
                            juce::StringArray& rows, juce::int64& totalBytes)
    {
        rows.clear();
        totalBytes = 0;

        auto arr = juce::JSON::parse (json);
        if (!arr.isArray()) return;

        auto* a = arr.getArray();
        for (int i = a->size() - 1; i >= 0 && rows.size() < 10; --i)
        {
            const auto& t = (*a)[i];
            if (!t.isObject()) continue;

            const juce::int64 sz = (juce::int64)(double) t["size"];
            totalBytes += sz;

            juce::String name = t["name"].toString();
            juce::String ts   = t["timestamp"].toString();

            // Normalise to HH:MM:SS — strip ISO date prefix if present
            const int tIdx = ts.indexOf ("T");
            if (tIdx >= 0) ts = ts.substring (tIdx + 1);
            if (ts.length() > 8) ts = ts.substring (0, 8);

            juce::String sizeStr;
            if (sz >= 1024 * 1024)
                sizeStr = juce::String (sz / (1024 * 1024)) + "MB";
            else
                sizeStr = juce::String (juce::jmax ((juce::int64) 1, sz / 1024)) + "KB";

            rows.add (ts + "  " + name + "  " + sizeStr);
        }
    }

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

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (DetailsPanel)
};
