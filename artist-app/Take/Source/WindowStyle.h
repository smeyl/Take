#pragma once

// Transparent title bar with the window buttons centred in the 44 px header
// (WindowStyle.mm). Pass the window's native NSView (ComponentPeer::getNativeHandle).
void takeStyleWindow (void* nativeView);

// Start moving the window with the mouse-down being handled — for clicks in the
// 44 px header, which sits where the title bar would be.
void takeDragWindow (void* nativeView);

#if JUCE_MAC
// Call from a header's mouseDown: drags the window like a title bar would.
inline void takeDragWindowFrom (juce::Component& c)
{
    if (auto* peer = c.getPeer())
        takeDragWindow (peer->getNativeHandle());
}
#endif
