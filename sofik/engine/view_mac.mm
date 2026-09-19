// Copyright 2026 Sofik. All rights reserved.

#import <Cocoa/Cocoa.h>

#include "content/public/browser/web_contents.h"
#include "headless/lib/browser/headless_web_contents_impl.h"
#include "sofik/engine/view.h"

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

}  // namespace sofik
