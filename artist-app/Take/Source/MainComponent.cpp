#include "MainComponent.h"

//==============================================================================
MainComponent::MainComponent()
{
    setSize (400, 640);
    showScreen (Screen::ROLE_SELECT);
}

MainComponent::~MainComponent() {}

void MainComponent::paint (juce::Graphics& g)
{
    g.fillAll (juce::Colour (0xFF0A0A0B));
}

void MainComponent::resized()
{
    if (screenComponent)
        screenComponent->setBounds (getLocalBounds());
}

void MainComponent::showScreen (Screen screen)
{
    currentScreen = screen;
    screenComponent.reset();

    if (screen == Screen::ROLE_SELECT)
    {
        auto* s = new RoleSelectScreen();
        s->onJoin = [this] (const juce::String& ip, const juce::String& code) {
            engineerIP = ip;
            rawCode    = code;
            showScreen (Screen::ARTIST);
        };
        screenComponent.reset (s);
    }
    else  // ARTIST
    {
        auto* s = new ArtistScreen();
        s->setEngineerIP (engineerIP, rawCode);
        if (rawCode.length() == 6)
        {
            // XX · XX · XX — same format as the engineer app
            auto sep = " " + juce::String::fromUTF8 ("\xC2\xB7") + " ";
            s->setSessionCode (rawCode.substring (0, 2) + sep
                             + rawCode.substring (2, 4) + sep
                             + rawCode.substring (4, 6));
        }
        s->onBack = [this] { showScreen (Screen::ROLE_SELECT); };
        screenComponent.reset (s);
    }

    addAndMakeVisible (*screenComponent);
    resized();

    setSize (400, 640);
    if (auto* rw = dynamic_cast<juce::ResizableWindow*> (getTopLevelComponent()))
        rw->setContentComponentSize (400, 640);
}
