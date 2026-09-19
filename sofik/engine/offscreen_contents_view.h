// Copyright 2026 Sofik. All rights reserved.

#ifndef SOFIK_ENGINE_OFFSCREEN_CONTENTS_VIEW_H_
#define SOFIK_ENGINE_OFFSCREEN_CONTENTS_VIEW_H_

#include <string>

#include "base/memory/raw_ptr.h"
#include "base/memory/weak_ptr.h"
#include "build/build_config.h"
#include "content/browser/renderer_host/render_view_host_delegate_view.h"
#include "content/browser/web_contents/web_contents_view.h"
#include "content/public/browser/web_contents.h"
#include "ui/gfx/geometry/size.h"

namespace sofik {

class OffscreenView;
class OffscreenViewDelegate;

// The view of a web contents that is shown nowhere: it makes OffscreenViews
// for the contents' widgets and holds what they all share -- the size, the
// scale and the frame rate the host asked for, and who to report to.
//
// Owned by the web contents it is installed in.
class OffscreenContentsView : public content::WebContentsView,
                              public content::RenderViewHostDelegateView {
 public:
  // Installs a new view in `params`; the returned pointer lives as long as
  // the web contents created from them.
  static OffscreenContentsView* Install(
      content::WebContents::CreateParams* params,
      const gfx::Size& size,
      float scale,
      int frame_rate);

  OffscreenContentsView(const OffscreenContentsView&) = delete;
  OffscreenContentsView& operator=(const OffscreenContentsView&) = delete;
  ~OffscreenContentsView() override;

  void set_web_contents(content::WebContents* web_contents) {
    web_contents_ = web_contents;
  }
  void set_delegate(OffscreenViewDelegate* delegate) { delegate_ = delegate; }
  OffscreenViewDelegate* delegate() const { return delegate_; }

  const gfx::Size& size() const { return size_; }
  float scale() const { return scale_; }  // 0: the screen's
  int frame_rate() const { return frame_rate_; }
  void SetSize(const gfx::Size& size);
  void SetScale(float scale);

  // The page's view; null between a crash and the reload.
  OffscreenView* GetView() const;

  // content::WebContentsView:
  gfx::NativeView GetNativeView() const override;
  gfx::NativeView GetContentNativeView() const override;
  gfx::NativeWindow GetTopLevelNativeWindow() const override;
  gfx::Rect GetContainerBounds() const override;
  void Focus() override;
  void SetInitialFocus() override {}
  void StoreFocus() override {}
  void RestoreFocus() override {}
  void FocusThroughTabTraversal(bool reverse) override {}
  content::DropData* GetDropData() const override;
  gfx::Rect GetViewBounds() const override;
  void Resize(const gfx::Rect& new_bounds) override {}
  gfx::Size GetSize() const override;
  void CreateView(gfx::NativeView context) override {}
  content::RenderWidgetHostViewBase* CreateViewForWidget(
      content::RenderWidgetHost* render_widget_host) override;
  content::RenderWidgetHostViewBase* CreateViewForChildWidget(
      content::RenderWidgetHost* render_widget_host) override;
  void SetPageTitle(const std::u16string& title) override {}
  void RenderViewReady() override {}
  void RenderViewHostChanged(content::RenderViewHost* old_host,
                             content::RenderViewHost* new_host) override {}
  void SetOverscrollControllerEnabled(bool enabled) override {}
  void OnCapturerCountChanged() override {}
#if BUILDFLAG(IS_MAC)
  bool CloseTabAfterEventTrackingIfNeeded() override;
#endif
  void FullscreenStateChanged(bool is_fullscreen) override {}
  content::BackForwardTransitionAnimationManager*
  GetBackForwardTransitionAnimationManager() override;
  void DestroyBackForwardTransitionAnimationManager() override {}

  // content::RenderViewHostDelegateView:
  void ShowContextMenu(content::RenderFrameHost& render_frame_host,
                       const content::ContextMenuParams& params) override {}
  void StartDragging(
      content::RenderFrameHost& source_rfh,
      const content::DropData& drop_data,
      blink::DragOperationsMask allowed_ops,
      const gfx::ImageSkia& image,
      const gfx::Vector2d& cursor_offset,
      const gfx::Rect& drag_obj_rect,
      const blink::mojom::DragEventSourceInfo& event_info) override;
  void UpdateDragOperation(ui::mojom::DragOperation operation,
                           bool document_is_handling_drag) override {}
  void GotFocus(content::RenderWidgetHostImpl* render_widget_host) override;
  void LostFocus(content::RenderWidgetHostImpl* render_widget_host) override;
  void TakeFocus(bool reverse) override;

 private:
  OffscreenContentsView(const gfx::Size& size, float scale, int frame_rate);

  raw_ptr<content::WebContents> web_contents_ = nullptr;
  raw_ptr<OffscreenViewDelegate> delegate_ = nullptr;
  gfx::Size size_;
  float scale_;
  const int frame_rate_;

  base::WeakPtrFactory<OffscreenContentsView> weak_ptr_factory_{this};
};

}  // namespace sofik

#endif  // SOFIK_ENGINE_OFFSCREEN_CONTENTS_VIEW_H_
