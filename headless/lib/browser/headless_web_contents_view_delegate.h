// Copyright 2026 Sofik. All rights reserved.

#ifndef HEADLESS_LIB_BROWSER_HEADLESS_WEB_CONTENTS_VIEW_DELEGATE_H_
#define HEADLESS_LIB_BROWSER_HEADLESS_WEB_CONTENTS_VIEW_DELEGATE_H_

#include "base/memory/raw_ptr.h"
#include "content/public/browser/web_contents_view_delegate.h"

namespace content {
class WebContents;
}

namespace headless {

// Sofik: hands a page's context menu to whoever embeds it. Headless has no
// view delegate at all, so with a platform view -- which is what the engine's
// native-view mode shows -- a right click did nothing.
class HeadlessWebContentsViewDelegate : public content::WebContentsViewDelegate {
 public:
  explicit HeadlessWebContentsViewDelegate(content::WebContents* web_contents);
  ~HeadlessWebContentsViewDelegate() override;

  // content::WebContentsViewDelegate:
  void ShowContextMenu(content::RenderFrameHost& render_frame_host,
                       const content::ContextMenuParams& params) override;

 private:
  const raw_ptr<content::WebContents> web_contents_;
};

}  // namespace headless

#endif  // HEADLESS_LIB_BROWSER_HEADLESS_WEB_CONTENTS_VIEW_DELEGATE_H_
