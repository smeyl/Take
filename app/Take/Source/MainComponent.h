#pragma once

#include <JuceHeader.h>
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
class RoleSelectScreen : public juce::Component
{
public:
    std::function<void(bool isArtist)> onRoleSelected;

    RoleSelectScreen()
    {
        setLookAndFeel (&laf);

        titleLabel.setText ("Take", juce::dontSendNotification);
        titleLabel.setFont (juce::Font (juce::FontOptions (56.0f).withStyle ("Bold")));
        titleLabel.setColour (juce::Label::textColourId, juce::Colour (0xFFF0F0F8));
        titleLabel.setJustificationType (juce::Justification::centred);
        addAndMakeVisible (titleLabel);

        subtitleLabel.setText ("Remote recording session", juce::dontSendNotification);
        subtitleLabel.setFont (juce::Font (juce::FontOptions (13.0f)));
        subtitleLabel.setColour (juce::Label::textColourId, juce::Colour (0xFF5C5C6E));
        subtitleLabel.setJustificationType (juce::Justification::centred);
        addAndMakeVisible (subtitleLabel);

        sessionCodeEditor.setTextToShowWhenEmpty ("Session code", juce::Colour (0xFF5C5C6E));
        sessionCodeEditor.setColour (juce::TextEditor::backgroundColourId,     juce::Colour (0xFF18181C));
        sessionCodeEditor.setColour (juce::TextEditor::textColourId,           juce::Colour (0xFFF0F0F8));
        sessionCodeEditor.setColour (juce::TextEditor::outlineColourId,        juce::Colour (0xFF222228));
        sessionCodeEditor.setColour (juce::TextEditor::focusedOutlineColourId, juce::Colour (0xFF3A3A48));
        sessionCodeEditor.setCaretVisible (true);
        sessionCodeEditor.setFont (juce::Font (juce::FontOptions (15.0f)));
        sessionCodeEditor.setJustification (juce::Justification::centred);
        addAndMakeVisible (sessionCodeEditor);

        artistButton.setButtonText ("Join as Artist");
        artistButton.setColour (juce::TextButton::buttonColourId,   juce::Colour (0xFF1D9E75));
        artistButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFF17805E));
        artistButton.setColour (juce::TextButton::textColourOffId,  juce::Colour (0xFFF0F0F8));
        artistButton.setColour (juce::TextButton::textColourOnId,   juce::Colour (0xFFF0F0F8));
        artistButton.onClick = [this] { if (onRoleSelected) onRoleSelected (true); };
        addAndMakeVisible (artistButton);

        engineerButton.setButtonText ("Join as Engineer");
        engineerButton.setColour (juce::TextButton::buttonColourId,   juce::Colour (0xFF185FA5));
        engineerButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFF124C84));
        engineerButton.setColour (juce::TextButton::textColourOffId,  juce::Colour (0xFFF0F0F8));
        engineerButton.setColour (juce::TextButton::textColourOnId,   juce::Colour (0xFFF0F0F8));
        engineerButton.onClick = [this] { if (onRoleSelected) onRoleSelected (false); };
        addAndMakeVisible (engineerButton);
    }

    ~RoleSelectScreen() override
    {
        setLookAndFeel (nullptr);
    }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (juce::Colour (0xFF0A0A0B));
    }

    void resized() override
    {
        int w = getWidth();

        titleLabel.setBounds (0, 100, w, 66);
        subtitleLabel.setBounds (0, 164, w, 26);

        int editorW = 240, editorH = 46;
        sessionCodeEditor.setBounds ((w - editorW) / 2, 234, editorW, editorH);

        int btnW = 110, btnH = 46, gap = 20;
        int btnX = (w - btnW * 2 - gap) / 2;
        artistButton.setBounds  (btnX,              318, btnW, btnH);
        engineerButton.setBounds (btnX + btnW + gap, 318, btnW, btnH);
    }

private:
    // Declared first — destroyed last, outlives all child components.
    TakeLookAndFeel  laf;

    juce::Label      titleLabel;
    juce::Label      subtitleLabel;
    juce::TextEditor sessionCodeEditor;
    juce::TextButton artistButton, engineerButton;
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
    Screen currentScreen { Screen::ROLE_SELECT };
    std::unique_ptr<juce::Component> screenComponent;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainComponent)
};
