#pragma once

// Transparent title bar with the window buttons centred in the 44 px header
// (WindowStyle.mm). Pass the window's native NSView (ComponentPeer::getNativeHandle).
void takeStyleWindow (void* nativeView);
