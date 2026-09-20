// Copyright 2026 Sofik. All rights reserved.

#ifndef HEADLESS_PUBLIC_HEADLESS_EMBEDDER_DELEGATE_H_
#define HEADLESS_PUBLIC_HEADLESS_EMBEDDER_DELEGATE_H_

#include <vector>

#include "base/functional/callback.h"
#include "base/memory/scoped_refptr.h"
#include "content/public/browser/media_stream_request.h"
#include "headless/public/headless_export.h"
#include "third_party/blink/public/common/permissions/permission_utils.h"
#include "third_party/blink/public/mojom/choosers/file_chooser.mojom-forward.h"
#include "third_party/blink/public/mojom/permissions/permission_status.mojom.h"

class GURL;

namespace content {
class FileSelectListener;
class JavaScriptDialogManager;
class RenderFrameHost;
struct ContextMenuParams;
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

  // The page's main frame is about to request `url`, or was redirected to
  // it. Return true to cancel: the page stays where it is.
  virtual bool OnBeforeNavigation(const GURL& url,
                                  bool user_gesture,
                                  bool is_redirect) = 0;

  // alert, confirm, prompt and beforeunload. Returning nullptr keeps
  // headless's behaviour.
  virtual content::JavaScriptDialogManager* GetJavaScriptDialogManager() = 0;

  // A page asking for camera, location, notifications and the like. Headless
  // on its own pretends the prompt was dismissed. The embedder must run
  // `callback`, now or later, with one status per requested type, in order;
  // ASK for all of them is that same dismissal.
  using PermissionCallback = base::OnceCallback<void(
      const std::vector<blink::mojom::PermissionStatus>&)>;
  virtual void OnPermissionsRequested(
      const GURL& origin,
      const std::vector<blink::PermissionType>& types,
      PermissionCallback callback) = 0;

  // getUserMedia. Headless on its own has no answer, so the content layer
  // fails every request. Return true to take it; `callback` must then be run,
  // now or later.
  virtual bool OnMediaAccessRequested(
      const content::MediaStreamRequest& request,
      content::MediaResponseCallback callback) = 0;
  // Whether `origin` already holds camera or microphone access: what decides
  // if enumerateDevices() names the devices.
  virtual bool HasMediaAccess(const url::Origin& origin,
                              blink::mojom::MediaStreamType type) = 0;

  // A right click, or the keyboard's menu key. Headless shows nothing.
  virtual void OnContextMenu(content::RenderFrameHost& frame,
                             const content::ContextMenuParams& params) = 0;

  // <input type=file>. Headless on its own cancels it. Return true to take
  // the request; `listener` must then be answered, FileSelected() or
  // FileSelectionCanceled(), exactly once.
  virtual bool OnFileChooser(
      scoped_refptr<content::FileSelectListener> listener,
      const blink::mojom::FileChooserParams& params) = 0;

 protected:
  virtual ~HeadlessEmbedderDelegate() = default;
};

}  // namespace headless

#endif  // HEADLESS_PUBLIC_HEADLESS_EMBEDDER_DELEGATE_H_
