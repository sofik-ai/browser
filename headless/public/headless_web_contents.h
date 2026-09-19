// Copyright 2015 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef HEADLESS_PUBLIC_HEADLESS_WEB_CONTENTS_H_
#define HEADLESS_PUBLIC_HEADLESS_WEB_CONTENTS_H_

#include <string_view>

#include "base/functional/callback.h"
#include "base/memory/raw_ptr.h"
#include "base/process/kill.h"
#include "content/public/browser/web_contents.h"
#include "headless/public/headless_export.h"
#include "headless/public/headless_window_state.h"
#include "ui/gfx/geometry/rect.h"
#include "url/gurl.h"

namespace headless {
class HeadlessBrowserContextImpl;
class HeadlessBrowserImpl;

// Class representing contents of a browser tab. Should be accessed from browser
// main thread.
class HEADLESS_EXPORT HeadlessWebContents {
 public:
  class HEADLESS_EXPORT Builder;

  HeadlessWebContents(const HeadlessWebContents&) = delete;
  HeadlessWebContents& operator=(const HeadlessWebContents&) = delete;

  virtual ~HeadlessWebContents() {}

  // Close this page. |HeadlessWebContents| object will be destroyed.
  virtual void Close() = 0;

 protected:
  HeadlessWebContents() {}
};

class HEADLESS_EXPORT HeadlessWebContents::Builder {
 public:
  Builder(const Builder&) = delete;
  Builder& operator=(const Builder&) = delete;

  ~Builder();
  Builder(Builder&&);

  // Set an initial URL to ensure that the renderer gets initialized and
  // eventually becomes ready to be inspected. See
  // HeadlessWebContents::Observer::DevToolsTargetReady. The default URL is
  // about:blank.
  Builder& SetInitialURL(const GURL& initial_url);

  // Specify the initial window bounds (default size is configured in browser
  // options).
  Builder& SetWindowBounds(const gfx::Rect& bounds);

  // Specify the initial window state, default is kNormal.
  Builder& SetWindowState(HeadlessWindowState window_state);

  // Specify whether BeginFrames should be controlled via DevTools commands.
  Builder& SetEnableBeginFrameControl(bool enable_begin_frame_control);

  // Sofik: lets an embedder finish the content layer's creation parameters,
  // which is the only moment a web contents can be given a view of the
  // embedder's own instead of the platform's.
  using CreateParamsCallback =
      base::OnceCallback<void(content::WebContents::CreateParams*)>;
  Builder& SetCreateParamsCallback(CreateParamsCallback callback);

  // The returned object is owned by HeadlessBrowser. Call
  // HeadlessWebContents::Close() to dispose it.
  HeadlessWebContents* Build();

 private:
  friend class HeadlessBrowserImpl;
  friend class HeadlessBrowserContextImpl;
  friend class HeadlessWebContentsImpl;

  explicit Builder(HeadlessBrowserContextImpl* browser_context);

  raw_ptr<HeadlessBrowserContextImpl, AcrossTasksDanglingUntriaged>
      browser_context_;

  GURL initial_url_ = GURL("about:blank");
  gfx::Rect window_bounds_;
  HeadlessWindowState window_state_ = HeadlessWindowState::kNormal;
  bool enable_begin_frame_control_ = false;
  CreateParamsCallback create_params_callback_;
};

}  // namespace headless

#endif  // HEADLESS_PUBLIC_HEADLESS_WEB_CONTENTS_H_
