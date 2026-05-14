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
    std::function<void(const juce::String&)> onJoin;

    RoleSelectScreen()
    {
        setLookAndFeel (&laf);

        subtitleLabel.setText ("Artist", juce::dontSendNotification);
        subtitleLabel.setFont (juce::Font (juce::FontOptions (11.0f)));
        subtitleLabel.setColour (juce::Label::textColourId, juce::Colour (0xFF5C5C6E));
        subtitleLabel.setJustificationType (juce::Justification::centred);
        addAndMakeVisible (subtitleLabel);

        sessionCodeEditor.setTextToShowWhenEmpty (juce::CharPointer_UTF8 ("A7 \xc2\xb7 F2 \xc2\xb7 K9"),
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
        joinButton.setBounds        (cx, 328, 240, 46);
        errorLabel.setBounds        (0,  382, w,   22);
    }

    // juce::TextEditor::Listener
    void textEditorTextChanged (juce::TextEditor& editor) override
    {
        if (isFormattingCode) return;
        isFormattingCode = true;

        const juce::String sep = " " + juce::String::charToString ((juce::juce_wchar) 0x00B7) + " ";

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

        juce::Component::SafePointer<RoleSelectScreen> safeThis (this);
        juce::String code = raw;
        juce::String ip   = localIP;

        std::thread ([safeThis, code, ip]() mutable
        {
            juce::String body = "{\"code\":\"" + code + "\",\"ip\":\"" + ip + "\"}";

            auto stream = juce::URL ("http://192.0.2.10:5010/session/join")
                              .withPOSTData (body)
                              .createInputStream (
                                  juce::URL::InputStreamOptions (juce::URL::ParameterHandling::inAddress)
                                      .withExtraHeaders ("Content-Type: application/json")
                                      .withConnectionTimeoutMs (5000));

            bool         success    = false;
            juce::String engineerIP;

            if (stream != nullptr)
            {
                auto json = juce::JSON::parse (stream->readEntireStreamAsString());
                engineerIP = json["engineer_ip"].toString();
                success    = engineerIP.isNotEmpty();
            }

            juce::MessageManager::callAsync ([safeThis, success, engineerIP]()
            {
                if (safeThis == nullptr) return;
                safeThis->joinButton.setEnabled (true);
                if (success)
                {
                    if (safeThis->onJoin) safeThis->onJoin (engineerIP);
                }
                else
                {
                    safeThis->errorLabel.setText ("Invalid code", juce::dontSendNotification);
                    safeThis->errorLabel.setVisible (true);
                }
            });
        }).detach();
    }

    TakeLookAndFeel  laf;
    juce::Label      subtitleLabel;
    juce::TextEditor sessionCodeEditor;
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
    std::unique_ptr<juce::Component> screenComponent;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainComponent)
};
