// Sofik: the window.chrome object a page finds in Chrome -- loadTimes(), csi()
// and app. Upstream the first two come from chrome/renderer and the third from
// the extensions renderer, neither of which the Sofik engine contains, and a
// page that finds `window.chrome` undefined knows at once it is not in Chrome.
// Registered by HeadlessContentRendererClient when the engine presents as a
// browser.
//
// Copyright 2006-2008 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The ChromeObjectExtension is a v8 extension to access the time it took
// to load a page.

#ifndef HEADLESS_LIB_RENDERER_SOFIK_CHROME_OBJECT_H_
#define HEADLESS_LIB_RENDERER_SOFIK_CHROME_OBJECT_H_

#include <memory>

namespace v8 {
class Extension;
}

namespace sofik_v8 {

class ChromeObjectExtension {
 public:
  static std::unique_ptr<v8::Extension> Get();
};

}  // namespace sofik_v8

#endif  // HEADLESS_LIB_RENDERER_SOFIK_CHROME_OBJECT_H_
