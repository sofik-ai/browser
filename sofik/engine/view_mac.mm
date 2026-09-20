// Copyright 2026 Sofik. All rights reserved.

#import <Cocoa/Cocoa.h>

#include "base/strings/sys_string_conversions.h"
#include "content/public/browser/context_menu_params.h"
#include "content/public/browser/navigation_controller.h"
#include "content/public/browser/web_contents.h"
#include "headless/lib/browser/headless_web_contents_impl.h"
#include "sofik/engine/engine.h"
#include "sofik/engine/view.h"
#include "third_party/blink/public/common/context_menu_data/edit_flags.h"

// A menu item that runs a block: NSMenu wants a target and a selector.
@interface SofikMenuItem : NSMenuItem
@property(nonatomic, copy) void (^run)(void);
@end
@implementation SofikMenuItem
@synthesize run = _run;
- (void)fire:(id)sender {
  if (self.run) self.run();
}
@end

namespace sofik {

void* View::NativeHandle() const {
  if (!contents_ || contents_view_) {
    return nullptr;  // Closed, or a view that delivers frames.
  }
  // Unretained: the web contents owns its NSView, and the C API says so.
  return (__bridge void*)contents_->web_contents()
      ->GetNativeView()
      .GetNativeNSView();
}

void View::ShowNativeContextMenu(const content::ContextMenuParams& params) {
  if (!contents_) {
    return;
  }
  NSView* native = contents_->web_contents()->GetNativeView().GetNativeNSView();
  if (!native.window) {
    return;
  }
  content::WebContents* page = contents_->web_contents();
  const sofik_view_id id = id_;
  // Looked up again when an item fires: the menu runs a loop of its own, and
  // the view may be gone by the time the person picks something.
  auto find = [](sofik_view_id id) -> View* {
    Engine* engine = Engine::Get();
    return engine ? engine->FindView(id) : nullptr;
  };

  NSMenu* menu = [[NSMenu alloc] initWithTitle:@""];
  menu.autoenablesItems = NO;
  auto add = [&](NSString* title, bool enabled, void (^run)(void)) {
    SofikMenuItem* item = [[SofikMenuItem alloc] initWithTitle:title
                                                        action:@selector(fire:)
                                                 keyEquivalent:@""];
    item.target = item;
    item.run = run;
    item.enabled = enabled;
    [menu addItem:item];
  };

  using blink::ContextMenuDataEditFlags;
  const std::string link = params.link_url.spec();
  if (params.link_url.is_valid()) {
    add(@"Open Link in New Tab", true, ^{
      if (View* view = find(id)) view->OpenLinkFromMenu(link);
    });
    add(@"Copy Link Address", true, ^{
      NSPasteboard* board = NSPasteboard.generalPasteboard;
      [board clearContents];
      [board setString:base::SysUTF8ToNSString(link)
               forType:NSPasteboardTypeString];
    });
    [menu addItem:NSMenuItem.separatorItem];
  }
  if (params.is_editable || !params.selection_text.empty()) {
    const int flags = params.edit_flags;
    if (params.is_editable) {
      add(@"Cut", flags & ContextMenuDataEditFlags::kCanCut, ^{
        if (View* view = find(id)) view->Edit(SOFIK_EDIT_CUT);
      });
    }
    add(@"Copy", flags & ContextMenuDataEditFlags::kCanCopy, ^{
      if (View* view = find(id)) view->Edit(SOFIK_EDIT_COPY);
    });
    if (params.is_editable) {
      add(@"Paste", flags & ContextMenuDataEditFlags::kCanPaste, ^{
        if (View* view = find(id)) view->Edit(SOFIK_EDIT_PASTE);
      });
      add(@"Select All", flags & ContextMenuDataEditFlags::kCanSelectAll, ^{
        if (View* view = find(id)) view->Edit(SOFIK_EDIT_SELECT_ALL);
      });
    }
    [menu addItem:NSMenuItem.separatorItem];
  }
  add(@"Back", page->GetController().CanGoBack(), ^{
    if (View* view = find(id)) view->GoBack();
  });
  add(@"Forward", page->GetController().CanGoForward(), ^{
    if (View* view = find(id)) view->GoForward();
  });
  add(@"Reload", true, ^{
    if (View* view = find(id)) view->Reload(false);
  });

  // The renderer reports the point in the view's top-left coordinates.
  NSPoint where = NSMakePoint(params.x, native.isFlipped
                                            ? params.y
                                            : NSHeight(native.bounds) - params.y);
  [menu popUpMenuPositioningItem:nil atLocation:where inView:native];
}

}  // namespace sofik
