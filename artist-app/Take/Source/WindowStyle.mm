// The artist window's title bar: transparent, with the content drawn under it
// and the macOS window buttons centred in the app's 44 px header — the same
// look as the engineer app (Electron: titleBarStyle 'hiddenInset',
// trafficLightPosition { x: 16, y: 15 }).
#import <Cocoa/Cocoa.h>
#include "WindowStyle.h"

static void placeWindowButtons (NSWindow* window)
{
    constexpr CGFloat kHeader = 44, kLeft = 16, kSpacing = 20;
    NSButton* close = [window standardWindowButton: NSWindowCloseButton];
    NSView* container = close.superview.superview;   // the title bar container
    if (container == nil) return;
    NSRect f = container.frame;
    f.size.height = kHeader;
    f.origin.y = window.frame.size.height - kHeader;
    container.frame = f;

    const NSWindowButton buttons[] = { NSWindowCloseButton, NSWindowMiniaturizeButton, NSWindowZoomButton };
    for (int i = 0; i < 3; ++i)
    {
        NSButton* b = [window standardWindowButton: buttons[i]];
        [b setFrameOrigin: NSMakePoint (kLeft + i * kSpacing, (kHeader - b.frame.size.height) / 2)];
    }
}

void takeStyleWindow (void* nativeView)
{
    NSWindow* window = [(NSView*) nativeView window];
    if (window == nil) return;
    window.titlebarAppearsTransparent = YES;
    window.titleVisibility = NSWindowTitleHidden;
    window.styleMask |= NSWindowStyleMaskFullSizeContentView;
    placeWindowButtons (window);

    // AppKit lays the buttons out again on these; put them back each time.
    for (NSNotificationName n : @[ NSWindowDidResizeNotification, NSWindowDidBecomeKeyNotification,
                                   NSWindowDidResignKeyNotification, NSWindowDidBecomeMainNotification ])
        [[NSNotificationCenter defaultCenter] addObserverForName: n object: window queue: nil
                                                      usingBlock: ^(NSNotification*) { placeWindowButtons (window); }];
}

// The content view covers the transparent title bar, so clicks in the header
// reach the app, not the title bar — which is what normally moves a window.
// Called from the header's mouseDown: hand that click to AppKit as a window
// drag (same behaviour as a real title bar, including screen-edge snapping).
void takeDragWindow (void* nativeView)
{
    NSWindow* window = [(NSView*) nativeView window];
    NSEvent* event = [NSApp currentEvent];
    if (window != nil && event != nil && event.type == NSEventTypeLeftMouseDown)
        [window performWindowDragWithEvent: event];
}
