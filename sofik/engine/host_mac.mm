// Copyright 2026 Sofik. All rights reserved.
//
// A test host: the smallest application that can embed the engine. It plays
// the part the Flutter plugin will play, and uses nothing but the C API, the
// same way the plugin will have to -- a window, the engine's frames on a layer,
// the mouse and the keyboard sent back.
//
//   sofik_engine_host [--shot=/path.png --after-ms=4000] <url>
//   sofik_engine_host --input-test <url of a page with a report() function>

#import <Cocoa/Cocoa.h>
#import <IOSurface/IOSurface.h>
#import <QuartzCore/QuartzCore.h>

#include <mach-o/dyld.h>

#include <string>

#include "sofik/engine/sofik_engine.h"

namespace {

sofik_view_id g_view = 0;

uint32_t Modifiers(NSEvent* event) {
  NSEventModifierFlags flags = event.modifierFlags;
  uint32_t result = 0;
  if (flags & NSEventModifierFlagShift) result |= SOFIK_MOD_SHIFT;
  if (flags & NSEventModifierFlagControl) result |= SOFIK_MOD_CONTROL;
  if (flags & NSEventModifierFlagOption) result |= SOFIK_MOD_ALT;
  if (flags & NSEventModifierFlagCommand) result |= SOFIK_MOD_META;
  NSUInteger buttons = NSEvent.pressedMouseButtons;
  if (buttons & 1) result |= SOFIK_MOD_LEFT_BUTTON;
  if (buttons & 2) result |= SOFIK_MOD_RIGHT_BUTTON;
  if (buttons & 4) result |= SOFIK_MOD_MIDDLE_BUTTON;
  return result;
}

// Enough of the Windows virtual-key table for a test host. The plugin carries
// the full one; KeyboardEvent.code comes from the native key code either way.
int WindowsKeyCode(NSEvent* event) {
  switch (event.keyCode) {
    case 36: return 0x0D;   // return
    case 48: return 0x09;   // tab
    case 49: return 0x20;   // space
    case 51: return 0x08;   // backspace
    case 53: return 0x1B;   // escape
    case 117: return 0x2E;  // forward delete
    case 123: return 0x25;  // left
    case 124: return 0x27;  // right
    case 125: return 0x28;  // down
    case 126: return 0x26;  // up
    case 115: return 0x24;  // home
    case 119: return 0x23;  // end
    case 116: return 0x21;  // page up
    case 121: return 0x22;  // page down
  }
  NSString* characters = event.charactersIgnoringModifiers;
  if (characters.length == 0) return 0;
  unichar c = [characters characterAtIndex:0];
  if (c >= 'a' && c <= 'z') return c - 'a' + 'A';
  if ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) return c;
  return 0;
}

}  // namespace

@interface SofikPageView : NSView
@end

@implementation SofikPageView {
  NSTrackingArea* _tracking;
}

- (instancetype)initWithFrame:(NSRect)frame {
  if ((self = [super initWithFrame:frame])) {
    self.wantsLayer = YES;
    self.layer.backgroundColor = NSColor.whiteColor.CGColor;
    self.layer.contentsGravity = kCAGravityTopLeft;
    // The engine's frames are top-down, like every image; a layer is not.
    self.layer.geometryFlipped = YES;
  }
  return self;
}

- (BOOL)acceptsFirstResponder { return YES; }
- (BOOL)isFlipped { return YES; }

- (void)updateTrackingAreas {
  [super updateTrackingAreas];
  if (_tracking) [self removeTrackingArea:_tracking];
  _tracking = [[NSTrackingArea alloc]
      initWithRect:self.bounds
           options:NSTrackingMouseMoved | NSTrackingMouseEnteredAndExited |
                   NSTrackingActiveInKeyWindow | NSTrackingInVisibleRect
             owner:self
          userInfo:nil];
  [self addTrackingArea:_tracking];
}

- (NSPoint)where:(NSEvent*)event {
  return [self convertPoint:event.locationInWindow fromView:nil];
}

- (void)mouseMoved:(NSEvent*)e {
  NSPoint p = [self where:e];
  sofik_view_mouse_move(g_view, p.x, p.y, Modifiers(e), 0);
}
- (void)mouseDragged:(NSEvent*)e { [self mouseMoved:e]; }
- (void)rightMouseDragged:(NSEvent*)e { [self mouseMoved:e]; }
- (void)mouseExited:(NSEvent*)e {
  NSPoint p = [self where:e];
  sofik_view_mouse_move(g_view, p.x, p.y, Modifiers(e), 1);
}

- (void)button:(sofik_mouse_button)button up:(BOOL)up event:(NSEvent*)e {
  NSPoint p = [self where:e];
  sofik_view_mouse_button(g_view, p.x, p.y, button, up, (int)e.clickCount,
                          Modifiers(e));
}
- (void)mouseDown:(NSEvent*)e {
  [self.window makeFirstResponder:self];
  [self button:SOFIK_BUTTON_LEFT up:NO event:e];
}
- (void)mouseUp:(NSEvent*)e { [self button:SOFIK_BUTTON_LEFT up:YES event:e]; }
- (void)rightMouseDown:(NSEvent*)e {
  [self button:SOFIK_BUTTON_RIGHT up:NO event:e];
}
- (void)rightMouseUp:(NSEvent*)e {
  [self button:SOFIK_BUTTON_RIGHT up:YES event:e];
}

- (void)scrollWheel:(NSEvent*)e {
  NSPoint p = [self where:e];
  CGFloat scale = e.hasPreciseScrollingDeltas ? 1.0 : 40.0;
  sofik_view_mouse_wheel(g_view, p.x, p.y, e.scrollingDeltaX * scale,
                         e.scrollingDeltaY * scale, Modifiers(e));
}

- (void)keyDown:(NSEvent*)e {
  uint32_t modifiers = Modifiers(e) | (e.isARepeat ? SOFIK_MOD_IS_REPEAT : 0);
  int vkey = WindowsKeyCode(e);
  sofik_view_key(g_view, SOFIK_KEY_RAW_DOWN, vkey, e.keyCode, 0, modifiers);
  // Text goes as a separate event, and never for a Command shortcut.
  if (!(e.modifierFlags & NSEventModifierFlagCommand)) {
    NSString* text = e.characters;
    for (NSUInteger i = 0; i < text.length; ++i) {
      unichar c = [text characterAtIndex:i];
      if (c == 0x7f) c = 0x08;
      if (c < 0xF700 || c > 0xF8FF) {  // not an AppKit function-key code
        sofik_view_key(g_view, SOFIK_KEY_CHAR, vkey, e.keyCode, c, modifiers);
      }
    }
  }
}
- (void)keyUp:(NSEvent*)e {
  sofik_view_key(g_view, SOFIK_KEY_UP, WindowsKeyCode(e), e.keyCode, 0,
                 Modifiers(e));
}

- (void)setFrameSize:(NSSize)size {
  [super setFrameSize:size];
  if (g_view) sofik_view_resize(g_view, size.width, size.height);
}

@end

@interface SofikHost : NSObject <NSApplicationDelegate, NSWindowDelegate>
@property(strong) NSWindow* window;
@property(strong) SofikPageView* page;
@property(copy) NSString* url;
@property(copy) NSString* shotPath;
@property int shotAfterMs;
@property BOOL inputTest;
@property BOOL dialogTest;
@property int frames;
@end

static SofikHost* g_host = nil;

static void OnFrame(void*, sofik_view_id, const sofik_frame* frame) {
  g_host.frames++;
  CALayer* layer = g_host.page.layer;
  [CATransaction begin];
  [CATransaction setDisableActions:YES];
  if (frame->io_surface) {
    // Zero copy: the GPU surface the engine rendered into is what the layer
    // shows. It stays valid until the next frame, which is the API's promise.
    layer.contents = (__bridge id)(IOSurfaceRef)frame->io_surface;
    layer.contentsScale = g_host.window.backingScaleFactor;
  } else if (frame->pixels) {
    CGColorSpaceRef space = CGColorSpaceCreateDeviceRGB();
    CGContextRef context = CGBitmapContextCreate(
        (void*)frame->pixels, frame->width, frame->height, 8, frame->stride,
        space,
        (CGBitmapInfo)kCGImageAlphaPremultipliedFirst |
            (CGBitmapInfo)kCGBitmapByteOrder32Little);
    CGImageRef image = CGBitmapContextCreateImage(context);
    layer.contents = (__bridge id)image;
    layer.contentsScale = g_host.window.backingScaleFactor;
    CGImageRelease(image);
    CGContextRelease(context);
    CGColorSpaceRelease(space);
  }
  [CATransaction commit];
}

static void OnTitle(void*, sofik_view_id, const char* title) {
  // %s would read the UTF-8 as MacRoman.
  g_host.window.title =
      [NSString stringWithFormat:@"%@ — Sofik engine", @(title)];
}
static void OnAddress(void*, sofik_view_id, const char* url) {
  NSLog(@"sofik host: address %s", url);
}
static void OnLoading(void*, sofik_view_id, int loading, int back, int fwd) {
  NSLog(@"sofik host: loading=%d back=%d forward=%d", loading, back, fwd);
}
static void OnLoadError(void*, sofik_view_id, int code, const char* text,
                        const char* url) {
  NSLog(@"sofik host: load error %d %s for %s", code, text, url);
}
static void OnDialog(void*, sofik_view_id view, uint32_t request,
                     sofik_dialog_kind kind, const char* message,
                     const char* default_prompt) {
  NSLog(@"sofik host: dialog kind=%d message=%@ default=%@", kind, @(message),
        @(default_prompt));
  // A real host shows its own UI here. Answered on a later turn of the loop,
  // as a person would: the page stays blocked in between.
  dispatch_async(dispatch_get_main_queue(), ^{
    sofik_view_answer_dialog(view, request, 1,
                             kind == SOFIK_DIALOG_PROMPT ? "Sofik" : NULL);
  });
}
static void OnPopup(void*, sofik_view_id, const char* url, int gesture) {
  NSLog(@"sofik host: popup requested %s gesture=%d", url, gesture);
}
static void OnCdp(void*, sofik_view_id, const char* message) {
  NSString* text = @(message);
  NSLog(@"sofik host: cdp %@",
        text.length > 300 ? [text substringToIndex:300] : text);
}

@implementation SofikHost

- (void)applicationDidFinishLaunching:(NSNotification*)notification {
  const NSRect frame = NSMakeRect(0, 0, 1280, 800);
  self.window = [[NSWindow alloc]
      initWithContentRect:frame
                styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
                          NSWindowStyleMaskResizable |
                          NSWindowStyleMaskMiniaturizable
                  backing:NSBackingStoreBuffered
                    defer:NO];
  self.window.delegate = self;
  self.window.title = @"Sofik engine";
  self.page = [[SofikPageView alloc] initWithFrame:frame];
  self.window.contentView = self.page;
  [self.window center];
  [self.window makeKeyAndOrderFront:nil];
  [self.window makeFirstResponder:self.page];
  [NSApp activateIgnoringOtherApps:YES];

  // The helper sits next to this executable.
  char path[4096];
  uint32_t size = sizeof(path);
  _NSGetExecutablePath(path, &size);
  std::string helper =
      std::string(path).substr(0, std::string(path).rfind('/')) +
      "/sofik_engine_helper";

  sofik_settings settings = {};
  settings.abi = SOFIK_ENGINE_ABI;
  settings.helper_path = helper.c_str();
  settings.accept_languages = "pt-BR,pt,en-US,en";
  settings.locale = "pt-BR";
  settings.device_scale_factor = self.window.backingScaleFactor;
  int result = sofik_engine_initialize(&settings);
  if (result != 0) {
    NSLog(@"sofik host: the engine did not start (%d)", result);
    [NSApp terminate:nil];
    return;
  }

  sofik_view_callbacks callbacks = {};
  callbacks.on_frame = OnFrame;
  callbacks.on_title_changed = OnTitle;
  callbacks.on_address_changed = OnAddress;
  callbacks.on_loading_state = OnLoading;
  callbacks.on_load_error = OnLoadError;
  callbacks.on_dialog = OnDialog;
  callbacks.on_popup_requested = OnPopup;

  sofik_view_config config = {};
  config.url = self.url.UTF8String;
  config.width = frame.size.width;
  config.height = frame.size.height;
  config.prefer_gpu_frames = 1;
  g_view = sofik_view_create(&config, &callbacks, nullptr);
  if (!g_view) {
    NSLog(@"sofik host: could not create the view");
    [NSApp terminate:nil];
    return;
  }
  sofik_view_set_focus(g_view, 1);

  if (self.dialogTest) {
    sofik_view_cdp_attach(g_view, OnCdp, nullptr);
    auto after = ^(int ms, dispatch_block_t block) {
      dispatch_after(dispatch_time(DISPATCH_TIME_NOW, ms * NSEC_PER_MSEC),
                     dispatch_get_main_queue(), block);
    };
    after(1500, ^{
      sofik_view_mouse_move(g_view, 100, 40, 0, 0);
      sofik_view_mouse_button(g_view, 100, 40, SOFIK_BUTTON_LEFT, 0, 1,
                              SOFIK_MOD_LEFT_BUTTON);
      sofik_view_mouse_button(g_view, 100, 40, SOFIK_BUTTON_LEFT, 1, 1, 0);
    });
    after(3500, ^{
      sofik_view_cdp_send(g_view,
                          "{\"id\":9,\"method\":\"Runtime.evaluate\","
                          "\"params\":{\"expression\":\"report()\"}}");
    });
    after(4300, ^{
      [NSApp terminate:nil];
    });
    return;
  }

  if (self.inputTest) {
    // Drives the input API against a page that records what it received.
    sofik_view_cdp_attach(g_view, OnCdp, nullptr);
    auto after = ^(int ms, dispatch_block_t block) {
      dispatch_after(dispatch_time(DISPATCH_TIME_NOW, ms * NSEC_PER_MSEC),
                     dispatch_get_main_queue(), block);
    };
    after(1500, ^{
      sofik_view_mouse_move(g_view, 60, 35, 0, 0);
      sofik_view_mouse_move(g_view, 100, 35, 0, 0);
      sofik_view_mouse_button(g_view, 100, 35, SOFIK_BUTTON_LEFT, 0, 1,
                              SOFIK_MOD_LEFT_BUTTON);
      sofik_view_mouse_button(g_view, 100, 35, SOFIK_BUTTON_LEFT, 1, 1, 0);
    });
    after(2200, ^{
      // "Sofik" -- native key codes are macOS virtual key codes.
      struct { int vkey, native; unichar c; uint32_t mods; } keys[] = {
          {'S', 1, 'S', SOFIK_MOD_SHIFT}, {'O', 31, 'o', 0}, {'F', 3, 'f', 0},
          {'I', 34, 'i', 0},              {'K', 40, 'k', 0}};
      for (auto& k : keys) {
        sofik_view_key(g_view, SOFIK_KEY_RAW_DOWN, k.vkey, k.native, 0, k.mods);
        sofik_view_key(g_view, SOFIK_KEY_CHAR, k.vkey, k.native, k.c, k.mods);
        sofik_view_key(g_view, SOFIK_KEY_UP, k.vkey, k.native, 0, k.mods);
      }
    });
    after(2800, ^{
      sofik_view_mouse_wheel(g_view, 400, 400, 0, -600, 0);
    });
    after(3800, ^{
      sofik_view_cdp_send(g_view,
                          "{\"id\":7,\"method\":\"Runtime.evaluate\","
                          "\"params\":{\"expression\":\"report()\"}}");
    });
    after(4600, ^{
      [NSApp terminate:nil];
    });
    return;
  }

  if (self.shotPath) {
    // Self-test: prove the DevTools session and the window both work, then
    // leave, so this can run unattended.
    sofik_view_cdp_attach(g_view, OnCdp, nullptr);
    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, self.shotAfterMs * NSEC_PER_MSEC),
        dispatch_get_main_queue(), ^{
          sofik_view_cdp_send(
              g_view,
              "{\"id\":1,\"method\":\"Runtime.evaluate\",\"params\":"
              "{\"expression\":\"document.title + ' | ' + location.href\"}}");
        });
    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW,
                      (self.shotAfterMs + 1000) * NSEC_PER_MSEC),
        dispatch_get_main_queue(), ^{
          [self snapshot];
          [NSApp terminate:nil];
        });
  }
}

// What the window shows, as the window server composes it: the honest test
// that the engine's surface reached the screen.
- (void)snapshot {
  CGImageRef image = CGWindowListCreateImage(
      CGRectNull, kCGWindowListOptionIncludingWindow,
      (CGWindowID)self.window.windowNumber, kCGWindowImageBoundsIgnoreFraming);
  if (!image) {
    NSLog(@"sofik host: no window image (screen recording permission?)");
    return;
  }
  NSBitmapImageRep* rep = [[NSBitmapImageRep alloc] initWithCGImage:image];
  NSData* png = [rep representationUsingType:NSBitmapImageFileTypePNG
                                  properties:@{}];
  [png writeToFile:self.shotPath atomically:YES];
  NSLog(@"sofik host: frames=%d window %zux%zu -> %@", self.frames,
        CGImageGetWidth(image), CGImageGetHeight(image), self.shotPath);
  CGImageRelease(image);
}

- (void)windowWillClose:(NSNotification*)notification {
  [NSApp terminate:nil];
}

- (void)applicationWillTerminate:(NSNotification*)notification {
  if (g_view) {
    sofik_view_close(g_view);
    g_view = 0;
  }
  sofik_engine_shutdown();
}

@end

int main(int argc, const char** argv) {
  @autoreleasepool {
    g_host = [[SofikHost alloc] init];
    g_host.url = @"https://pt.wikipedia.org/wiki/Navegador_web";
    g_host.shotAfterMs = 4000;
    for (int i = 1; i < argc; ++i) {
      NSString* arg = @(argv[i]);
      if ([arg hasPrefix:@"--shot="]) {
        g_host.shotPath = [arg substringFromIndex:7];
      } else if ([arg isEqualToString:@"--dialog-test"]) {
        g_host.dialogTest = YES;
      } else if ([arg isEqualToString:@"--input-test"]) {
        g_host.inputTest = YES;
      } else if ([arg hasPrefix:@"--after-ms="]) {
        g_host.shotAfterMs = [arg substringFromIndex:11].intValue;
      } else if (![arg hasPrefix:@"--"]) {
        g_host.url = arg;
      }
    }
    NSApplication* app = NSApplication.sharedApplication;
    app.activationPolicy = NSApplicationActivationPolicyRegular;
    app.delegate = g_host;
    [app run];
  }
  return 0;
}
