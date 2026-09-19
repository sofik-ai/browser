// Copyright 2026 Sofik. All rights reserved.

#include "sofik/engine/offscreen_contents_view.h"

#include "content/browser/renderer_host/render_widget_host_impl.h"
#include "content/browser/web_contents/web_contents_impl.h"
#include "content/public/browser/render_view_host.h"
#include "content/public/browser/render_widget_host.h"
#include "content/public/browser/web_contents_delegate.h"
#include "sofik/engine/offscreen_view.h"

namespace sofik {

// static
OffscreenContentsView* OffscreenContentsView::Install(
    content::WebContents::CreateParams* params,
    const gfx::Size& size,
    float scale,
    int frame_rate) {
  auto* view = new OffscreenContentsView(size, scale, frame_rate);
  // The web contents takes `view`, and uses `delegate_view` unowned.
  params->view = view;
  params->delegate_view = view;
  return view;
}

OffscreenContentsView::OffscreenContentsView(const gfx::Size& size,
                                             float scale,
                                             int frame_rate)
    : size_(size), scale_(scale), frame_rate_(frame_rate) {}

OffscreenContentsView::~OffscreenContentsView() = default;

void OffscreenContentsView::SetSize(const gfx::Size& size) {
  if (size == size_) {
    return;
  }
  size_ = size;
  if (OffscreenView* view = GetView()) {
    view->WasResized();
  }
}

void OffscreenContentsView::SetScale(float scale) {
  if (scale == scale_) {
    return;
  }
  scale_ = scale;
  if (OffscreenView* view = GetView()) {
    view->OnScaleChanged();
  }
}

OffscreenView* OffscreenContentsView::GetView() const {
  if (!web_contents_) {
    return nullptr;
  }
  // Every widget view of this contents is one of ours: nothing else makes
  // them.
  return static_cast<OffscreenView*>(
      web_contents_->GetRenderViewHost()->GetWidget()->GetView());
}

gfx::NativeView OffscreenContentsView::GetNativeView() const {
  return gfx::NativeView();
}

gfx::NativeView OffscreenContentsView::GetContentNativeView() const {
  return gfx::NativeView();
}

gfx::NativeWindow OffscreenContentsView::GetTopLevelNativeWindow() const {
  return gfx::NativeWindow();
}

gfx::Rect OffscreenContentsView::GetContainerBounds() const {
  return gfx::Rect(size_);
}

gfx::Rect OffscreenContentsView::GetViewBounds() const {
  return gfx::Rect(size_);
}

gfx::Size OffscreenContentsView::GetSize() const {
  return size_;
}

void OffscreenContentsView::Focus() {
  if (OffscreenView* view = GetView()) {
    view->SetFocused(true);
  }
}

content::DropData* OffscreenContentsView::GetDropData() const {
  return nullptr;
}

content::RenderWidgetHostViewBase* OffscreenContentsView::CreateViewForWidget(
    content::RenderWidgetHost* render_widget_host) {
  if (render_widget_host->GetView()) {
    return static_cast<content::RenderWidgetHostViewBase*>(
        render_widget_host->GetView());
  }
  return new OffscreenView(render_widget_host, nullptr,
                           weak_ptr_factory_.GetWeakPtr());
}

content::RenderWidgetHostViewBase*
OffscreenContentsView::CreateViewForChildWidget(
    content::RenderWidgetHost* render_widget_host) {
  OffscreenView* page = GetView();
  CHECK(page);
  return new OffscreenView(render_widget_host, page,
                           weak_ptr_factory_.GetWeakPtr());
}

#if BUILDFLAG(IS_MAC)
bool OffscreenContentsView::CloseTabAfterEventTrackingIfNeeded() {
  return false;
}
#endif

content::BackForwardTransitionAnimationManager*
OffscreenContentsView::GetBackForwardTransitionAnimationManager() {
  return nullptr;
}

void OffscreenContentsView::StartDragging(
    content::RenderFrameHost& source_rfh,
    const content::DropData& drop_data,
    blink::DragOperationsMask allowed_ops,
    const gfx::ImageSkia& image,
    const gfx::Vector2d& cursor_offset,
    const gfx::Rect& drag_obj_rect,
    const blink::mojom::DragEventSourceInfo& event_info) {
  // No system drag can start from a texture. The page has to hear that it
  // ended, or it keeps waiting and swallows the mouse. An agent drags with
  // Input.dispatchDragEvent, which never comes through here.
  if (web_contents_) {
    static_cast<content::WebContentsImpl*>(web_contents_.get())
        ->SystemDragEnded(static_cast<content::RenderWidgetHostImpl*>(
            source_rfh.GetRenderWidgetHost()));
  }
}

void OffscreenContentsView::GotFocus(
    content::RenderWidgetHostImpl* render_widget_host) {
  if (web_contents_) {
    static_cast<content::WebContentsImpl*>(web_contents_.get())
        ->NotifyWebContentsFocused(render_widget_host);
  }
}

void OffscreenContentsView::LostFocus(
    content::RenderWidgetHostImpl* render_widget_host) {
  if (web_contents_) {
    static_cast<content::WebContentsImpl*>(web_contents_.get())
        ->NotifyWebContentsLostFocus(render_widget_host);
  }
}

void OffscreenContentsView::TakeFocus(bool reverse) {
  if (web_contents_ && web_contents_->GetDelegate()) {
    web_contents_->GetDelegate()->TakeFocus(web_contents_, reverse);
  }
}

}  // namespace sofik
