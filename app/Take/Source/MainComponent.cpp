#include "MainComponent.h"

//==============================================================================
MainComponent::MainComponent()
{
    setSize (400, 500);
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
        s->onRoleSelected = [this] (bool isArtist) {
            showScreen (isArtist ? Screen::ARTIST : Screen::ENGINEER);
        };
        screenComponent.reset (s);
    }
    else if (screen == Screen::ARTIST)
    {
        screenComponent = std::make_unique<ArtistScreen>();
    }
    else
    {
        screenComponent = std::make_unique<EngineerScreen>();
    }

    addAndMakeVisible (*screenComponent);
    resized();

    if (screen == Screen::ENGINEER)
    {
        setSize (820, 700);
        if (auto* rw = dynamic_cast<juce::ResizableWindow*> (getTopLevelComponent()))
            rw->setContentComponentSize (820, 700);
    }
}
