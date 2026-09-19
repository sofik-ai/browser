// Copyright 2018 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "headless/lib/headless_content_main_delegate.h"

#import <Cocoa/Cocoa.h>

#include "headless/lib/browser/headless_shell_application_mac.h"

namespace headless {

void HeadlessContentMainDelegate::PlatformPreBrowserMain() {
  // Sofik: embedded, NSApp is the host application's and stays that way. The
  // rest of this function would refuse any NSApplication but headless's own
  // and then take the host out of the Dock.
  if (embedder_owns_message_loop_) {
    return;
  }

  // Force the NSApplication subclass to be used.
  [HeadlessShellCrApplication sharedApplication];

  // If there was an invocation to NSApp prior to this method, then the NSApp
  // will not be a HeadlessShellCrApplication, but will instead be an
  // NSApplication. This is undesirable and we must enforce that this doesn't
  // happen.
  CHECK([NSApp isKindOfClass:[HeadlessShellCrApplication class]]);

  // Force hide dock and menu bar.
  NSApp.activationPolicy = NSApplicationActivationPolicyAccessory;
}

}  // namespace headless
