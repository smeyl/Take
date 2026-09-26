#pragma once

#include <JuceHeader.h>
#include <thread>
#include "ArtistScreen.h"

//==============================================================================
class TakeLookAndFeel : public juce::LookAndFeel_V4
{
public:
    void drawButtonBackground (juce::Graphics& g, juce::Button& button,
                               const juce::Colour& backgroundColour,
                               bool isMouseOverButton, bool isButtonDown) override
    {
        auto bounds = button.getLocalBounds().toFloat().reduced (0.5f);
        auto colour = backgroundColour;

        if (isButtonDown)
            colour = colour.darker (0.15f);
        else if (isMouseOverButton)
            colour = colour.brighter (0.08f);

        g.setColour (colour);
        g.fillRoundedRectangle (bounds, 8.0f);
    }

    juce::Font getTextButtonFont (juce::TextButton&, int) override
    {
        return juce::Font (juce::FontOptions (14.0f).withStyle ("Bold"));
    }

    void fillTextEditorBackground (juce::Graphics& g, int width, int height,
                                   juce::TextEditor& editor) override
    {
        g.setColour (editor.findColour (juce::TextEditor::backgroundColourId));
        g.fillRoundedRectangle (0.0f, 0.0f, (float) width, (float) height, 8.0f);
    }

    void drawTextEditorOutline (juce::Graphics& g, int width, int height,
                                juce::TextEditor& editor) override
    {
        auto colour = editor.hasKeyboardFocus (true)
                          ? editor.findColour (juce::TextEditor::focusedOutlineColourId)
                          : editor.findColour (juce::TextEditor::outlineColourId);
        g.setColour (colour);
        g.drawRoundedRectangle (0.5f, 0.5f, width - 1.0f, height - 1.0f, 8.0f, 1.0f);
    }
};

//==============================================================================
// The primary action, in the design's selected-blue style (as the engineer
// app's Start session button).
class TakePrimaryButton : public juce::Component
{
public:
    std::function<void()> onClick;
    void setText (const juce::String& t) { text = t; repaint(); }

    void paint (juce::Graphics& g) override
    {
        const auto b = getLocalBounds().toFloat().reduced (0.5f);
        const bool on = isEnabled();
        if (on)
        {
            g.setColour (juce::Colour (isMouseOver() ? 0xFF15284D : 0xFF10203F));
            g.fillRoundedRectangle (b, 8.0f);
        }
        g.setColour (on ? TakeUI::Col::blue : TakeUI::Col::line2);
        g.drawRoundedRectangle (b, 8.0f, 1.0f);
        TakeUI::text (g, text, TakeUI::font (12.0f, TakeUI::Weight::medium), on ? TakeUI::Col::blue : TakeUI::Col::faint,
                      getLocalBounds().toFloat(), juce::Justification::centred);
    }
    void mouseEnter (const juce::MouseEvent&) override { repaint(); }
    void mouseExit  (const juce::MouseEvent&) override { repaint(); }
    void enablementChanged() override { repaint(); }
    void mouseUp (const juce::MouseEvent& e) override
    {
        if (isEnabled() && getLocalBounds().contains (e.getPosition()) && onClick) onClick();
    }

private:
    juce::String text;
};

//==============================================================================
// The artist's join screen: enter the engineer's session code (found on the
// LAN by discovery), or the engineer's address if discovery can't find them.
class RoleSelectScreen : public juce::Component,
                         public juce::TextEditor::Listener,
                         private juce::Timer
{
public:
    std::function<void(const juce::String&, const juce::String&)> onJoin;  // (engineerIP, rawCode)

    RoleSelectScreen()
    {
        setLookAndFeel (&laf);

        auto styleEditor = [] (juce::TextEditor& ed, const juce::String& placeholder, const juce::Font& f)
        {
            namespace C = TakeUI::Col;
            ed.setTextToShowWhenEmpty (placeholder, C::ghost);
            ed.setColour (juce::TextEditor::backgroundColourId,     C::surface);
            ed.setColour (juce::TextEditor::textColourId,           juce::Colour (0xFFF2F2F3));
            ed.setColour (juce::TextEditor::outlineColourId,        C::line2);
            ed.setColour (juce::TextEditor::focusedOutlineColourId, C::blue);
            ed.setColour (juce::TextEditor::highlightColourId,      C::blue.withAlpha (0.3f));
            ed.setColour (juce::CaretComponent::caretColourId,      C::blue);
            ed.setCaretVisible (true);
            ed.setFont (f);
            ed.setJustification (juce::Justification::centred);
        };

        styleEditor (sessionCodeEditor, juce::String::fromUTF8 ("A7 \xC2\xB7 F2 \xC2\xB7 K9"),
                     TakeUI::font (21.0f, TakeUI::Weight::semibold, 1.05f));
        sessionCodeEditor.addListener (this);
        addAndMakeVisible (sessionCodeEditor);

        // Manual address entry — a fallback only. The primary flow is LAN
        // discovery (the artist enters just the code); this field appears if
        // discovery fails or the artist opts into it via the link below.
        styleEditor (relayHostEditor, "e.g. 192.168.1.20", TakeUI::font (13.0f));
        // Pre-fill from the session file written by start_artist.py, if present
        // (only exists after a prior successful join) — a convenience for the
        // manual path; discovery is tried first regardless.
        {
            auto known = TakeUI::readRelayHost();
            if (known != "127.0.0.1")
                relayHostEditor.setText (known, juce::dontSendNotification);
        }
        addAndMakeVisible (relayHostEditor);
        startTimer (1000);  // keep the manual field pre-filled if a file appears

        joinButton.setText ("Join session");
        joinButton.onClick = [this] { doJoinSession(); };
        addAndMakeVisible (joinButton);

        setManualMode (false);  // discovery-first: hide the IP field by default
    }

    ~RoleSelectScreen() override
    {
        stopTimer();
        setLookAndFeel (nullptr);
    }

    // juce::Timer — auto-fill the engineer IP once start_artist.py has
    // discovered it. Never overwrite something the user typed.
    void timerCallback() override
    {
        if (relayHostEditor.getText().isNotEmpty())
        {
            stopTimer();
            return;
        }
        auto known = TakeUI::readRelayHost();
        if (known != "127.0.0.1")
        {
            relayHostEditor.setText (known, juce::dontSendNotification);
            stopTimer();
        }
    }

    void paint (juce::Graphics& g) override
    {
        namespace C = TakeUI::Col;
        const float w = (float) getWidth();
        g.fillAll (C::bg);

        // Header, as on the session screen: mark + wordmark, role on the right
        const float cx = 89.0f, cy = 21.5f, r = 5.4f;
        g.setColour (C::teal.withAlpha (0.15f));
        g.fillEllipse (cx - r, cy - r, r * 2.0f, r * 2.0f);
        g.setColour (C::teal);
        g.drawEllipse (cx - r, cy - r, r * 2.0f, r * 2.0f, 1.62f);
        TakeUI::text (g, "TAKE", TakeUI::font (13.0f, TakeUI::Weight::semibold, 0.39f), C::text, { 106.0f, 13.0f, 60.0f, 17.0f });
        TakeUI::text (g, "ARTIST", TakeUI::font (9.5f, TakeUI::Weight::regular, 1.33f), C::muted,
                      { 0.0f, 16.0f, w - 16.0f, 12.0f }, juce::Justification::centredRight);
        g.setColour (C::line);
        g.fillRect (0.0f, 43.0f, w, 1.0f);

        const auto labelF = TakeUI::font (9.5f, TakeUI::Weight::regular, 1.33f);
        const auto hintF  = TakeUI::font (10.5f);
        const auto code   = sessionCodeEditor.getBounds().toFloat();
        TakeUI::text (g, "SESSION CODE", labelF, C::muted, { 0.0f, code.getY() - 20.0f, w, 12.0f },
                      juce::Justification::centred);
        TakeUI::text (g, "From the engineer's Take app", hintF, C::faint, { 0.0f, code.getBottom() + 8.0f, w, 14.0f },
                      juce::Justification::centred);

        if (manualMode)
        {
            const auto ip = relayHostEditor.getBounds().toFloat();
            TakeUI::text (g, "ENGINEER'S ADDRESS", labelF, C::muted, { 0.0f, ip.getY() - 20.0f, w, 12.0f },
                          juce::Justification::centred);
            TakeUI::text (g, "Shown under the code on the engineer's start screen", hintF, C::faint,
                          { 0.0f, ip.getBottom() + 8.0f, w, 14.0f }, juce::Justification::centred);
        }
        else
        {
            TakeUI::text (g, "Can't connect? Enter the engineer's address", hintF, C::blue, manualLinkBounds(),
                          juce::Justification::centred);
        }

        if (errorText.isNotEmpty())
            TakeUI::text (g, errorText, TakeUI::font (11.0f), C::red,
                          { 0.0f, (float) joinButton.getBottom() + 12.0f, w, 16.0f }, juce::Justification::centred);
    }

    void resized() override
    {
        const int w = getWidth(), bw = 320, x = (w - bw) / 2;
        // The block sits a little above centre; the address field adds a row.
        const int top = manualMode ? 188 : 224;
        sessionCodeEditor.setBounds (x, top, bw, 52);
        int y = top + 52 + 30;
        if (manualMode)
        {
            relayHostEditor.setBounds (x, y + 24, bw, 40);
            y += 24 + 40 + 30;
        }
        joinButton.setBounds (x, y + 12, bw, 40);
    }

    juce::Rectangle<float> manualLinkBounds() const
    {
        return { 0.0f, (float) joinButton.getBottom() + 40.0f, (float) getWidth(), 16.0f };
    }

    // Reveal (or hide) the manual address field. Discovery is the default;
    // this is the "Can't connect?" escape hatch, also shown when discovery fails.
    void setManualMode (bool on)
    {
        manualMode = on;
        relayHostEditor.setVisible (on);
        resized();
        repaint();
        if (on)
            relayHostEditor.grabKeyboardFocus();
    }

    void setError (const juce::String& e) { errorText = e; repaint(); }

    void setConnecting (bool connecting)
    {
        joinButton.setEnabled (! connecting);
        joinButton.setText (connecting ? juce::String::fromUTF8 ("Connecting\xE2\x80\xA6") : "Join session");
        if (connecting) setError ({});
    }

    void mouseDown (const juce::MouseEvent& e) override
    {
        if (! manualMode && manualLinkBounds().contains (e.position))
            setManualMode (true);
       #if JUCE_MAC
        else if (e.getPosition().y < 44)   // where the title bar would be: move the window
            takeDragWindowFrom (*this);
       #endif
    }

    // juce::TextEditor::Listener
    void textEditorTextChanged (juce::TextEditor& editor) override
    {
        if (isFormattingCode) return;
        isFormattingCode = true;

        // Middle dot (U+00B7) — matches the engineer app's XX · XX · XX format
        const juce::String sep = " " + juce::String::fromUTF8 ("\xC2\xB7") + " ";

        juce::String raw;
        for (auto c : editor.getText().toUpperCase())
            if (juce::CharacterFunctions::isLetterOrDigit (c) && raw.length() < 6)
                raw += c;

        juce::String formatted;
        const int len = raw.length();
        if (len <= 2)
            formatted = raw;
        else if (len <= 4)
            formatted = raw.substring (0, 2) + sep + raw.substring (2);
        else
            formatted = raw.substring (0, 2) + sep + raw.substring (2, 4) + sep + raw.substring (4);

        editor.setText (formatted, juce::dontSendNotification);
        editor.moveCaretToEnd();

        isFormattingCode = false;
    }

    void textEditorReturnKeyPressed (juce::TextEditor&) override { doJoinSession(); }

private:
    void doJoinSession()
    {
        // Strip separators to get raw 6-char code
        juce::String raw;
        for (auto c : sessionCodeEditor.getText().toUpperCase())
            if (juce::CharacterFunctions::isLetterOrDigit (c) && raw.length() < 6)
                raw += c;

        if (raw.length() < 6)
        {
            setError ("Enter the 6-character code");
            return;
        }

        // Pick first LAN address
        juce::String localIP = "127.0.0.1";
        for (auto& addr : juce::IPAddress::getAllAddresses())
        {
            auto s = addr.toString();
            if (s.startsWith ("192.168.") || s.startsWith ("10.") || s.startsWith ("172."))
            {
                localIP = s;
                break;
            }
        }

        setConnecting (true);

        // Capture value types, the onJoin callback, and a SafePointer for error
        // feedback. onJoin is owned by MainComponent which outlives the request.
        juce::String code = raw;
        juce::String ip   = localIP;
        auto cb = onJoin;
        juce::Component::SafePointer<RoleSelectScreen> safeThis (this);

        // If the user opened the manual field and typed an IP, honour it and
        // skip discovery. Otherwise discovery is the primary path — a stale
        // pre-fill in the hidden field must NOT pre-empt it.
        juce::String typedHost = manualMode ? relayHostEditor.getText().trim()
                                            : juce::String();

        std::thread ([code, ip, typedHost, cb, safeThis]() mutable
        {
            juce::String relayHost = typedHost;

            // 1. Primary path: find the relay by broadcasting the code on the LAN.
            if (relayHost.isEmpty())
            {
                juce::String found;
                if (discoverRelay (code, ip, found))
                    relayHost = found;
            }

            // 2. No IP at all — reveal the manual field (pre-filled from a prior
            //    session if available) and let the artist enter it.
            if (relayHost.isEmpty())
            {
                juce::MessageManager::callAsync ([safeThis]() mutable
                {
                    if (safeThis == nullptr) return;
                    safeThis->setConnecting (false);
                    safeThis->setManualMode (true);
                    safeThis->setError ("Couldn't find the engineer on this network");
                });
                return;
            }

            // 3. Normal HTTP join to the resolved relay host.
            juce::String body = "{\"code\":\"" + code + "\",\"ip\":\"" + ip + "\"}";
            juce::String engineerIP;
            int statusCode = 0;
            const bool ok = rawHttpPost (relayHost.toRawUTF8(), 5010, "/session/join",
                                         body, engineerIP, statusCode);

            juce::MessageManager::callAsync ([cb, safeThis, ok, statusCode,
                                              engineerIP, code]() mutable
            {
                if (ok)
                {
                    if (cb) cb (engineerIP, code);
                    return;
                }
                if (safeThis == nullptr) return;
                safeThis->setConnecting (false);
                safeThis->setManualMode (true);  // let them try a manual address
                safeThis->setError (statusCode == 404 ? "No session with that code — check it with the engineer"
                                                      : "Could not reach the engineer");
            });
        }).detach();
    }

    // LAN discovery: broadcast the session code on UDP 5011 and wait up to 2s
    // for the relay's reply carrying its IP. Returns true and sets relayIpOut on
    // success. Sends to both the limited broadcast and the /24 subnet-directed
    // broadcast (the reliable path on most home/office LANs). Returns false if
    // nothing answers — the caller then falls back to manual IP entry.
    static bool discoverRelay (const juce::String& code, const juce::String& localIP,
                               juce::String& relayIpOut)
    {
        int fd = ::socket (AF_INET, SOCK_DGRAM, 0);
        if (fd < 0) return false;

        int one = 1;
        ::setsockopt (fd, SOL_SOCKET, SO_BROADCAST, &one, sizeof (one));

        struct timeval tv { 2, 0 };  // 2s reply window
        ::setsockopt (fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof (tv));

        // Bind an ephemeral port so the relay's unicast reply comes back to us.
        struct sockaddr_in local {};
        local.sin_family      = AF_INET;
        local.sin_addr.s_addr = INADDR_ANY;
        local.sin_port        = 0;
        if (::bind (fd, (struct sockaddr*) &local, sizeof (local)) < 0)
        {
            ::close (fd);
            return false;
        }

        const juce::String payload = juce::String ("TAKE_DISCOVER_V1:") + code;

        auto sendTo = [&] (const juce::String& ipStr)
        {
            struct sockaddr_in dst {};
            dst.sin_family = AF_INET;
            dst.sin_port   = htons (5011);
            if (::inet_pton (AF_INET, ipStr.toRawUTF8(), &dst.sin_addr) == 1)
                ::sendto (fd, payload.toRawUTF8(), payload.getNumBytesAsUTF8(), 0,
                          (struct sockaddr*) &dst, sizeof (dst));
        };

        sendTo ("255.255.255.255");
        // /24 subnet-directed broadcast — common home/office layout
        auto octets = juce::StringArray::fromTokens (localIP, ".", "");
        if (octets.size() == 4)
            sendTo (octets[0] + "." + octets[1] + "." + octets[2] + ".255");

        // Await a valid reply (may need to skip a stray packet within the window).
        for (int attempt = 0; attempt < 4; ++attempt)
        {
            char buf[512];
            struct sockaddr_in from {};
            socklen_t fromLen = sizeof (from);
            ssize_t n = ::recvfrom (fd, buf, sizeof (buf) - 1, 0,
                                    (struct sockaddr*) &from, &fromLen);
            if (n <= 0) break;  // timeout or error
            buf[n] = 0;

            auto json = juce::JSON::parse (juce::String::fromUTF8 (buf, (int) n));
            if (json.isObject()
                && json["magic"].toString() == "TAKE_DISCOVER_V1"
                && json["code"].toString()  == code)
            {
                auto foundIp = json["relay_ip"].toString();
                if (foundIp.isNotEmpty())
                {
                    relayIpOut = foundIp;
                    ::close (fd);
                    return true;
                }
            }
        }

        ::close (fd);
        return false;
    }

    // POSIX HTTP POST - avoids juce::URL which fires internal assertions on connection failure.
    static bool rawHttpPost (const char* host, int port, const char* path,
                             const juce::String& jsonBody, juce::String& responseIP,
                             int& statusCode)
    {
        statusCode = 0;

        int fd = ::socket (AF_INET, SOCK_STREAM, 0);
        if (fd < 0) return false;

        struct timeval tv { 5, 0 };
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

        const char* bodyPtr = jsonBody.toRawUTF8();
        const int   bodyLen = (int) ::strlen (bodyPtr);

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
        ::send (fd, bodyPtr, (size_t) bodyLen, 0);

        juce::MemoryBlock buf;
        char    tmp[512];
        ssize_t n;
        while ((n = ::recv (fd, tmp, sizeof (tmp), 0)) > 0)
            buf.append (tmp, (size_t) n);
        ::close (fd);

        if (buf.getSize() == 0) return false;

        juce::String full = juce::String::fromUTF8 (static_cast<const char*> (buf.getData()), (int) buf.getSize());

        // Status line: "HTTP/1.0 200 OK"
        if (full.startsWith ("HTTP/"))
            statusCode = full.fromFirstOccurrenceOf (" ", false, false)
                             .upToFirstOccurrenceOf (" ", false, false).getIntValue();

        int sep = full.indexOf ("\r\n\r\n");
        if (sep < 0) return false;

        juce::String body = full.substring (sep + 4).trim();
        if (body.isEmpty()) return false;

        auto json = juce::JSON::parse (body);
        responseIP = json["engineer_ip"].toString();
        return responseIP.isNotEmpty();
    }

    TakeLookAndFeel  laf;
    juce::TextEditor  sessionCodeEditor;
    juce::TextEditor  relayHostEditor;
    TakePrimaryButton joinButton;
    juce::String      errorText;
    bool             isFormattingCode { false };
    bool             manualMode       { false };
};

//==============================================================================
class MainComponent : public juce::Component
{
public:
    enum class Screen { ROLE_SELECT, ARTIST };

    MainComponent();
    ~MainComponent() override;

    void paint (juce::Graphics&) override;
    void resized() override;
    void showScreen (Screen screen);

private:
    Screen      currentScreen { Screen::ROLE_SELECT };
    juce::String engineerIP;
    juce::String rawCode;
    std::unique_ptr<juce::Component> screenComponent;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainComponent)
};
