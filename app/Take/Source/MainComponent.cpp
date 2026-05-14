#include "MainComponent.h"

//==============================================================================
MainComponent::MainComponent()
{
    setSize (400, 620);
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
    else if (screen == Screen::ARTIST)
    {
        auto* s = new ArtistScreen();
        s->setEngineerIP (engineerIP, rawCode);
        s->onBack = [this] { showScreen (Screen::ROLE_SELECT); };
        screenComponent.reset (s);
    }
    else
    {
        auto* s = new EngineerScreen();
        s->onBack = [this] { showScreen (Screen::ROLE_SELECT); };
        screenComponent.reset (s);
    }

    addAndMakeVisible (*screenComponent);
    resized();

    if (screen == Screen::ENGINEER)
    {
        setSize (820, 700);
        if (auto* rw = dynamic_cast<juce::ResizableWindow*> (getTopLevelComponent()))
            rw->setContentComponentSize (820, 700);
    }
    else if (screen == Screen::ARTIST)
    {
        setSize (400, 620);
        if (auto* rw = dynamic_cast<juce::ResizableWindow*> (getTopLevelComponent()))
            rw->setContentComponentSize (400, 620);
    }
    else  // ROLE_SELECT
    {
        setSize (400, 620);
        if (auto* rw = dynamic_cast<juce::ResizableWindow*> (getTopLevelComponent()))
            rw->setContentComponentSize (400, 620);
    }
}
