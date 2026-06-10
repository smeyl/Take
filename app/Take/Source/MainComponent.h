#pragma once

#include <JuceHeader.h>
#include <thread>
#include "ArtistScreen.h"
#include "EngineerScreen.h"

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
        g.fillRoundedRectangle (0.0f, 0.0f, (float) width, (float) height, 6.0f);
    }

    void drawTextEditorOutline (juce::Graphics& g, int width, int height,
                                juce::TextEditor& editor) override
    {
        auto colour = editor.hasKeyboardFocus (true)
                          ? editor.findColour (juce::TextEditor::focusedOutlineColourId)
                          : editor.findColour (juce::TextEditor::outlineColourId);
        g.setColour (colour);
        g.drawRoundedRectangle (0.5f, 0.5f, width - 1.0f, height - 1.0f, 6.0f, 1.0f);
    }
};

//==============================================================================
class RoleSelectScreen : public juce::Component,
                         public juce::TextEditor::Listener
{
public:
    // (engineerIP, rawCode, password)
    std::function<void(const juce::String&, const juce::String&, const juce::String&)> onJoin;

    RoleSelectScreen()
    {
        setLookAndFeel (&laf);

        subtitleLabel.setText ("Artist", juce::dontSendNotification);
        subtitleLabel.setFont (juce::Font (juce::FontOptions (11.0f)));
        subtitleLabel.setColour (juce::Label::textColourId, juce::Colour (0xFF5C5C6E));
        subtitleLabel.setJustificationType (juce::Justification::centred);
        addAndMakeVisible (subtitleLabel);

        sessionCodeEditor.setTextToShowWhenEmpty ("A7 - F2 - K9",
                                                  juce::Colour (0xFF3A3A45));
        sessionCodeEditor.setColour (juce::TextEditor::backgroundColourId,     juce::Colour (0xFF18181C));
        sessionCodeEditor.setColour (juce::TextEditor::textColourId,           juce::Colour (0xFFF0F0F8));
        sessionCodeEditor.setColour (juce::TextEditor::outlineColourId,        juce::Colour (0xFF222228));
        sessionCodeEditor.setColour (juce::TextEditor::focusedOutlineColourId, juce::Colour (0xFF3A3A48));
        sessionCodeEditor.setCaretVisible (true);
        sessionCodeEditor.setFont (juce::Font (juce::FontOptions (15.0f)));
        sessionCodeEditor.setJustification (juce::Justification::centred);
        sessionCodeEditor.addListener (this);
        addAndMakeVisible (sessionCodeEditor);

        auto setupSmallEditor = [] (juce::TextEditor& ed, const juce::String& placeholder)
        {
            ed.setTextToShowWhenEmpty (placeholder, juce::Colour (0xFF3A3A45));
            ed.setColour (juce::TextEditor::backgroundColourId,     juce::Colour (0xFF18181C));
            ed.setColour (juce::TextEditor::textColourId,           juce::Colour (0xFFF0F0F8));
            ed.setColour (juce::TextEditor::outlineColourId,        juce::Colour (0xFF222228));
            ed.setColour (juce::TextEditor::focusedOutlineColourId, juce::Colour (0xFF3A3A48));
            ed.setCaretVisible (true);
            ed.setFont (juce::Font (juce::FontOptions (12.0f)));
            ed.setJustification (juce::Justification::centred);
        };

        setupSmallEditor (passwordEditor, "Password (optional)");
        passwordEditor.setPasswordCharacter (0x2022);  // bullet
        addAndMakeVisible (passwordEditor);

        setupSmallEditor (relayHostEditor, "Engineer IP (auto)");
        // Pre-fill from the session file written by start_artist.py, if present
        {
            auto known = TakeUI::readRelayHost();
            if (known != "127.0.0.1")
                relayHostEditor.setText (known, juce::dontSendNotification);
        }
        addAndMakeVisible (relayHostEditor);

        joinButton.setButtonText ("Join session");
        joinButton.setColour (juce::TextButton::buttonColourId,   juce::Colour (0xFF1D9E75));
        joinButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFF17805E));
        joinButton.setColour (juce::TextButton::textColourOffId,  juce::Colour (0xFFF0F0F8));
        joinButton.setColour (juce::TextButton::textColourOnId,   juce::Colour (0xFFF0F0F8));
        joinButton.onClick = [this] { doJoinSession(); };
        addAndMakeVisible (joinButton);

        errorLabel.setFont (juce::Font (juce::FontOptions (11.0f)));
        errorLabel.setColour (juce::Label::textColourId, juce::Colour (0xFFFF4F4F));
        errorLabel.setJustificationType (juce::Justification::centred);
        errorLabel.setVisible (false);
        addAndMakeVisible (errorLabel);
    }

    ~RoleSelectScreen() override
    {
        setLookAndFeel (nullptr);
    }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (juce::Colour (0xFF0A0A0B));

        auto boldFont = juce::Font (juce::FontOptions (56.0f).withStyle ("Bold"));
        juce::AttributedString logo;
        logo.setJustification (juce::Justification::centred);
        logo.append ("T",   boldFont, juce::Colour (0xFFF0F0F8));
        logo.append ("ake", boldFont, juce::Colour (0xFF4F8FFF));
        logo.draw (g, juce::Rectangle<float> (0.0f, 160.0f, (float) getWidth(), 66.0f));
    }

    void resized() override
    {
        int w  = getWidth();
        int cx = (w - 240) / 2;

        subtitleLabel.setBounds (0,  228, w,   22);
        sessionCodeEditor.setBounds (cx, 266, 240, 46);
        passwordEditor.setBounds    (cx, 320, 240, 34);
        relayHostEditor.setBounds   (cx, 362, 240, 34);
        joinButton.setBounds        (cx, 412, 240, 46);
        errorLabel.setBounds        (0,  466, w,   22);
    }

    // juce::TextEditor::Listener
    void textEditorTextChanged (juce::TextEditor& editor) override
    {
        if (isFormattingCode) return;
        isFormattingCode = true;

        const juce::String sep = " - ";

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
            errorLabel.setText ("Enter a 6-character code", juce::dontSendNotification);
            errorLabel.setVisible (true);
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

        joinButton.setEnabled (false);
        errorLabel.setVisible (false);

        // Capture value types, the onJoin callback, and a SafePointer for error
        // feedback. onJoin is owned by MainComponent which outlives the request.
        juce::String code     = raw;
        juce::String ip       = localIP;
        juce::String password = passwordEditor.getText().trim();
        auto cb = onJoin;
        juce::Component::SafePointer<RoleSelectScreen> safeThis (this);

        // Relay host: typed IP wins; otherwise /tmp/take_session.json (written by
        // start_artist.py once it has joined); 127.0.0.1 for single-machine dev.
        juce::String relayHost = relayHostEditor.getText().trim();
        if (relayHost.isEmpty())
            relayHost = TakeUI::readRelayHost();

        // Build the body with the JSON writer so passwords survive quoting
        juce::String body;
        {
            auto* obj = new juce::DynamicObject();
            obj->setProperty ("code", code);
            obj->setProperty ("ip", ip);
            if (password.isNotEmpty())
                obj->setProperty ("password", password);
            body = juce::JSON::toString (juce::var (obj), true);
        }

        std::thread ([code, password, relayHost, body, cb, safeThis]() mutable
        {
            juce::String engineerIP;
            int statusCode = 0;
            const bool ok = rawHttpPost (relayHost.toRawUTF8(), 5010, "/session/join",
                                         body, engineerIP, statusCode);

            juce::MessageManager::callAsync ([cb, safeThis, ok, statusCode,
                                              engineerIP, code, password]() mutable
            {
                if (ok)
                {
                    if (cb) cb (engineerIP, code, password);
                    return;
                }
                if (safeThis == nullptr) return;
                safeThis->joinButton.setEnabled (true);
                safeThis->errorLabel.setText (
                    statusCode == 403 ? "Wrong password"
                  : statusCode == 404 ? "Session not found"
                                      : "Could not reach the engineer",
                    juce::dontSendNotification);
                safeThis->errorLabel.setVisible (true);
            });
        }).detach();
    }

    // POSIX HTTP POST - avoids juce::URL which fires internal assertions on connection failure.
    static bool rawHttpPost (const char* host, int port, const char* path,
                             const juce::String& jsonBody, juce::String& responseIP,
                             int& statusCode)
    {
        DBG ("rawHttpPost called: " + juce::String (host) + ":" + juce::String (port));
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

        DBG ("rawHttpPost: recv loop done, buf.getSize()=" + juce::String ((int) buf.getSize()));
        if (buf.getSize() == 0) return false;

        DBG ("rawHttpPost: constructing juce::String from buf");
        juce::String full = juce::String::fromUTF8 (static_cast<const char*> (buf.getData()), (int) buf.getSize());

        // Status line: "HTTP/1.0 200 OK"
        if (full.startsWith ("HTTP/"))
            statusCode = full.fromFirstOccurrenceOf (" ", false, false)
                             .upToFirstOccurrenceOf (" ", false, false).getIntValue();

        int sep = full.indexOf ("\r\n\r\n");
        DBG ("rawHttpPost: header sep=" + juce::String (sep));
        if (sep < 0) return false;

        DBG ("rawHttpPost: constructing body substring");
        juce::String body = full.substring (sep + 4).trim();
        if (body.isEmpty()) return false;

        DBG ("rawHttpPost: parsing JSON: " + body);
        auto json = juce::JSON::parse (body);
        responseIP = json["engineer_ip"].toString();
        DBG ("rawHttpPost: engineer_ip=" + responseIP);
        return responseIP.isNotEmpty();
    }

    TakeLookAndFeel  laf;
    juce::Label      subtitleLabel;
    juce::TextEditor sessionCodeEditor;
    juce::TextEditor passwordEditor;
    juce::TextEditor relayHostEditor;
    juce::TextButton joinButton;
    juce::Label      errorLabel;
    bool             isFormattingCode { false };
};

//==============================================================================
class MainComponent : public juce::Component
{
public:
    enum class Screen { ROLE_SELECT, ARTIST, ENGINEER };

    MainComponent();
    ~MainComponent() override;

    void paint (juce::Graphics&) override;
    void resized() override;
    void showScreen (Screen screen);

private:
    Screen      currentScreen { Screen::ROLE_SELECT };
    juce::String engineerIP;
    juce::String rawCode;
    juce::String sessionPassword;
    std::unique_ptr<juce::Component> screenComponent;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainComponent)
};
