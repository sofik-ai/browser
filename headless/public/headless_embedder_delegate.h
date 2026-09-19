// Copyright 2026 Sofik. All rights reserved.

#ifndef HEADLESS_PUBLIC_HEADLESS_EMBEDDER_DELEGATE_H_
#define HEADLESS_PUBLIC_HEADLESS_EMBEDDER_DELEGATE_H_

#include "headless/public/headless_export.h"

class GURL;

namespace content {
class JavaScriptDialogManager;
}

namespace headless {

// Sofik: what an application embedding headless decides for itself.
//
// Headless answers these questions the way an unattended process should: a
// new window becomes another headless page nobody asked for, and a dialog is
// left to a DevTools client or dropped. Behind a Browser Card a person or an
// agent is looking at the page, and the host has to be asked. One per web
// contents; it must outlive it.
class HEADLESS_EXPORT HeadlessEmbedderDelegate {
 public:
  // window.open, target=_blank, a middle click. Return true to take the
  // request: headless then creates nothing, and the embedder opens the URL
  // wherever it sees fit, or nowhere.
  virtual bool OnNewWindowRequested(const GURL& url, bool user_gesture) = 0;

  // alert, confirm, prompt and beforeunload. Returning nullptr keeps
  // headless's behaviour.
  virtual content::JavaScriptDialogManager* GetJavaScriptDialogManager() = 0;

 protected:
  virtual ~HeadlessEmbedderDelegate() = default;
};

}  // namespace headless

#endif  // HEADLESS_PUBLIC_HEADLESS_EMBEDDER_DELEGATE_H_
