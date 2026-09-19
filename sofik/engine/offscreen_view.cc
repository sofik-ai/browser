// Copyright 2026 Sofik. All rights reserved.
// Portions copyright 2014 The Chromium Embedded Framework Authors and 2012 The
// Chromium Authors, under the BSD-style licence in //cef/LICENSE.txt.

#include "sofik/engine/offscreen_view.h"

#include <utility>

#include "base/functional/bind.h"
#include "base/task/single_thread_task_runner.h"
#include "components/input/cursor_manager.h"
#include "components/input/render_input_router.h"
#include "components/input/render_widget_host_input_event_router.h"
#include "components/viz/common/surfaces/frame_sink_id_allocator.h"
#include "components/viz/host/host_display_client.h"
#include "content/browser/renderer_host/delegated_frame_host.h"
#include "content/browser/renderer_host/input/synthetic_gesture_target_base.h"
#include "content/browser/renderer_host/render_widget_host_delegate.h"
#include "content/browser/renderer_host/render_widget_host_impl.h"
#include "content/public/browser/context_factory.h"
#include "sofik/engine/offscreen_contents_view.h"
#include "ui/compositor/layer.h"
#include "ui/display/screen.h"
#include "ui/events/base_event_utils.h"
#include "ui/gfx/geometry/size_conversions.h"
#include "ui/latency/latency_info.h"

namespace sofik {
namespace {

class FrameHostClient : public content::DelegatedFrameHostClient {
 public:
  explicit FrameHostClient(OffscreenView* view) : view_(view) {}

  ui::Layer* DelegatedFrameHostGetLayer() const override {
    return view_->root_layer();
  }
  bool DelegatedFrameHostIsVisible() const override {
    return view_->IsShowing();
  }
  SkColor DelegatedFrameHostGetGutterColor() const override {
    // A fullscreen element rarely shares the page's background; black hides
    // the transition.
    if (view_->widget()->delegate() &&
        view_->widget()->delegate()->IsFullscreen()) {
      return SK_ColorBLACK;
    }
    return *view_->GetBackgroundColor();
  }
  void OnFrameTokenChanged(uint32_t frame_token,
                           base::TimeTicks activation_time) override {
    view_->widget()->DidProcessFrame(frame_token, activation_time);
  }
  float GetDeviceScaleFactor() const override {
    return view_->GetDeviceScaleFactor();
  }
  viz::FrameEvictorClient::EvictIds CollectSurfaceIdsForEviction() override {
    viz::FrameEvictorClient::EvictIds ids;
    ids.embedded_ids = view_->widget()->CollectSurfaceIdsForEviction();
    return ids;
  }
  void InvalidateLocalSurfaceIdOnEviction() override {
    view_->InvalidateLocalSurfaceId();
  }
  bool ShouldShowStaleContentOnEviction() override { return false; }

 private:
  const raw_ptr<OffscreenView> view_;
};

// Input the DevTools protocol synthesises (Input.synthesizeScrollGesture and
// friends) goes straight to the widget: there is no native event to fake.
class GestureTarget : public content::SyntheticGestureTargetBase {
 public:
  explicit GestureTarget(content::RenderWidgetHostImpl* host)
      : SyntheticGestureTargetBase(host) {}

  void DispatchWebTouchEventToPlatform(const blink::WebTouchEvent&,
                                       const ui::LatencyInfo&) override {
    // The engine takes a mouse and a keyboard; nothing here is a touch screen.
  }
  void DispatchWebMouseWheelEventToPlatform(
      const blink::WebMouseWheelEvent& event,
      const ui::LatencyInfo& latency) override {
    render_widget_host()->GetRenderInputRouter()
        ->ForwardWheelEventWithLatencyInfo(event, latency);
  }
  void DispatchWebGestureEventToPlatform(
      const blink::WebGestureEvent& event,
      const ui::LatencyInfo& latency) override {
    render_widget_host()->GetRenderInputRouter()
        ->ForwardGestureEventWithLatencyInfo(event, latency);
  }
  void DispatchWebMouseEventToPlatform(const blink::WebMouseEvent& event,
                                       const ui::LatencyInfo& latency) override {
    render_widget_host()->ForwardMouseEventWithLatencyInfo(event, latency);
  }

  content::mojom::GestureSourceType GetDefaultSyntheticGestureSourceType()
      const override {
    return content::mojom::GestureSourceType::kMouseInput;
  }
  float GetTouchSlopInDips() const override { return 0; }
  float GetSpanSlopInDips() const override { return 0; }
  float GetMinScalingSpanInDips() const override { return 0; }
};

ui::LatencyInfo LatencyFor(const blink::WebInputEvent& event) {
  ui::LatencyInfo latency;
  if (!event.TimeStamp().is_null()) {
    latency.AddLatencyNumberWithTimestamp(
        ui::INPUT_EVENT_LATENCY_ORIGINAL_COMPONENT, event.TimeStamp());
  }
  return latency;
}

}  // namespace

OffscreenView::OffscreenView(content::RenderWidgetHost* widget,
                             OffscreenView* parent,
                             base::WeakPtr<OffscreenContentsView> contents_view)
    : content::RenderWidgetHostViewBase(widget),
      widget_(content::RenderWidgetHostImpl::From(widget)),
      contents_view_(std::move(contents_view)),
      parent_(parent),
      mouse_wheel_phase_handler_(this) {
  CHECK(!widget_->GetView());

  frame_host_client_ = std::make_unique<FrameHostClient>(this);
  frame_host_ = std::make_unique<content::DelegatedFrameHost>(
      widget_->GetFrameSinkId(), frame_host_client_.get(),
      /*should_register_frame_sink_id=*/true);

  root_layer_ = std::make_unique<ui::Layer>(ui::LAYER_SOLID_COLOR);
  root_layer_->SetColor(background_color_);

  if (!parent_) {
    // A compositor whose output goes nowhere: with no widget the display
    // compositor draws into an off-screen surface, and the page leaves through
    // the video capturer, which reads that surface back as the host's frames.
    ui::ContextFactory* factory = content::GetContextFactory();
    compositor_ = std::make_unique<ui::Compositor>(
        factory->AllocateFrameSinkId(), factory,
        base::SingleThreadTaskRunner::GetCurrentDefault(),
        /*enable_pixel_canvas=*/false, /*use_external_begin_frame_control=*/false);
    compositor_->SetAcceleratedWidget(gfx::kNullAcceleratedWidget);
    compositor_->SetDelegate(this);
    compositor_->SetRootLayer(root_layer_.get());
    widget_->SetCompositorForFlingScheduler(compositor_.get());
  }

  cursor_manager_ = std::make_unique<input::CursorManager>(this);

  // May call back into GetFrameSinkId().
  widget_->SetView(this);

  if (GetTextInputManager()) {
    GetTextInputManager()->AddObserver(this);
  }

  if (!parent_) {
    // Popup and fullscreen widgets are laid out from InitAsPopup/InitAsChild.
    UpdateGeometry(/*force=*/true);
    if (!widget_->IsHidden()) {
      Show();
    }
  }
}

OffscreenView::~OffscreenView() {
  if (frame_host_) {
    if (is_showing_) {
      frame_host_->WasHidden(content::DelegatedFrameHost::HiddenCause::kOther);
    }
    frame_host_->DetachFromCompositor();
    frame_host_.reset();
  }
  if (compositor_) {
    widget_->SetCompositorForFlingScheduler(nullptr);
  }
  if (parent_ && root_layer_->parent()) {
    root_layer_->parent()->Remove(root_layer_.get());
  }
  compositor_.reset();
  root_layer_.reset();
  if (text_input_manager_) {
    text_input_manager_->RemoveObserver(this);
  }
}

OffscreenViewDelegate* OffscreenView::delegate() const {
  return contents_view_ ? contents_view_->delegate() : nullptr;
}

ui::Compositor* OffscreenView::compositor() const {
  return parent_ ? parent_->compositor() : compositor_.get();
}

// ---- geometry ---------------------------------------------------------------

bool OffscreenView::UpdateGeometry(bool force) {
  const float old_scale = scale_;
  UpdateScreenInfo();  // Calls GetNewScreenInfosForUpdate().
  scale_ = GetDeviceScaleFactor();

  gfx::Rect bounds = bounds_;
  if (!is_popup() && contents_view_) {
    bounds = gfx::Rect(contents_view_->size());
  }
  const bool changed = bounds != bounds_ || scale_ != old_scale;
  if (!changed && !force) {
    return false;
  }
  bounds_ = bounds;

  if (parent_ && is_popup()) {
    root_layer_->SetBounds(bounds_);
  } else {
    root_layer_->SetBounds(gfx::Rect(bounds_.size()));
  }
  if (compositor_) {
    compositor_surface_id_allocator_.GenerateId();
    compositor_->SetScaleAndSize(
        scale_, gfx::ScaleToCeiledSize(bounds_.size(), scale_),
        compositor_surface_id_allocator_.GetCurrentLocalSurfaceId());
  }
  return changed;
}

void OffscreenView::WasResized() {
  SynchronizeVisualProperties(cc::DeadlinePolicy::UseExistingDeadline(),
                              std::nullopt);
}

void OffscreenView::OnScaleChanged() {
  InvalidateLocalSurfaceId();
  SynchronizeVisualProperties(cc::DeadlinePolicy::UseDefaultDeadline(),
                              std::nullopt);
  if (widget_->delegate()) {
    widget_->delegate()->SendScreenRects();
  } else {
    widget_->SendScreenRects();
  }
  widget_->NotifyScreenInfoChanged();
}

void OffscreenView::SynchronizeVisualProperties(
    const cc::DeadlinePolicy& deadline_policy,
    const std::optional<viz::LocalSurfaceId>& child_local_surface_id) {
  ApplyFrameRate();

  const bool resized = UpdateGeometry(/*force=*/false);
  bool surface_id_updated = false;
  if (!resized && child_local_surface_id && surface_id_allocator_) {
    surface_id_allocator_->UpdateFromChild(*child_local_surface_id);
    surface_id_updated = true;
  }
  // A new id after a resize, or when the old one was evicted.
  if (resized || !GetOrCreateLocalSurfaceId().is_valid()) {
    AllocateLocalSurfaceId();
    surface_id_updated = true;
  }
  if (surface_id_updated && frame_host_) {
    frame_host_->EmbedSurface(GetOrCreateLocalSurfaceId(), bounds_.size(),
                              deadline_policy);
    // The widget reads the new geometry back from this view, so it goes last.
    widget_->SynchronizeVisualProperties();
  }
}

void OffscreenView::ApplyFrameRate() {
  if (frame_rate_applied_ || !compositor_ || !contents_view_) {
    return;
  }
  frame_rate_applied_ = true;
  compositor_->SetDisplayVSyncParameters(
      base::TimeTicks::Now(),
      base::Seconds(1) / std::max(1, contents_view_->frame_rate()));
}

gfx::Rect OffscreenView::GetViewBounds() {
  return bounds_;
}

gfx::Rect OffscreenView::GetBoundsInRootWindow() {
  if (parent_) {
    return parent_->GetBoundsInRootWindow();
  }
  // The window a page believes it is in. A page whose outerHeight equals its
  // innerHeight is in a window with no title bar, no tabs and no toolbar --
  // that is, in no browser anyone uses -- and it takes one comparison to see.
  // The card is inside a real window; this gives the page the shape of
  // Chrome's: about 52px of tab strip and 35px of toolbar above the content.
  constexpr int kBrowserChromeHeight = 87;
  gfx::Rect window = bounds_;
  window.set_height(window.height() + kBrowserChromeHeight);
  return window;
}

gfx::Size OffscreenView::GetCompositorViewportPixelSize() {
  return gfx::ScaleToCeiledSize(GetRequestedRendererSize(),
                                GetDeviceScaleFactor());
}

display::ScreenInfos OffscreenView::GetNewScreenInfosForUpdate() {
  // The monitor is the real one -- a page must not find a screen exactly the
  // size of the browser it is in -- but the scale is the view's: a texture is
  // shown at whatever density the host composites it, monitor or not.
  display::ScreenInfo info;
  if (display::Screen::HasScreen()) {
    const display::Display display = display::Screen::Get()->GetPrimaryDisplay();
    info.rect = display.bounds();
    info.available_rect =
        display.work_area().IsEmpty() ? display.bounds() : display.work_area();
    info.device_scale_factor = display.device_scale_factor();
    info.depth = display.color_depth();
    info.depth_per_component = display.depth_per_component();
    info.is_monochrome = display.is_monochrome();
  }
  if (info.rect.IsEmpty()) {
    info.rect = info.available_rect =
        gfx::Rect(contents_view_ ? contents_view_->size() : gfx::Size(1, 1));
  }
  if (contents_view_ && contents_view_->scale() > 0) {
    info.device_scale_factor = contents_view_->scale();
  }
  return display::ScreenInfos(info);
}

// ---- surfaces ---------------------------------------------------------------

void OffscreenView::AllocateLocalSurfaceId() {
  if (!surface_id_allocator_) {
    surface_id_allocator_ =
        std::make_unique<viz::ParentLocalSurfaceIdAllocator>();
  }
  surface_id_allocator_->GenerateId();
}

const viz::LocalSurfaceId& OffscreenView::GetOrCreateLocalSurfaceId() {
  if (!surface_id_allocator_) {
    AllocateLocalSurfaceId();
  }
  return surface_id_allocator_->GetCurrentLocalSurfaceId();
}

void OffscreenView::InvalidateLocalSurfaceId() {
  if (surface_id_allocator_) {
    surface_id_allocator_->Invalidate();
  }
}

const viz::LocalSurfaceId& OffscreenView::GetLocalSurfaceId() const {
  return const_cast<OffscreenView*>(this)->GetOrCreateLocalSurfaceId();
}

void OffscreenView::InvalidateLocalSurfaceIdAndAllocationGroup() {
  InvalidateLocalSurfaceId();
}

void OffscreenView::ClearFallbackSurfaceForCommitPending() {
  if (frame_host_) {
    frame_host_->ClearFallbackSurfaceForCommitPending();
  }
  InvalidateLocalSurfaceId();
}

void OffscreenView::ResetFallbackToFirstNavigationSurface() {
  if (frame_host_) {
    frame_host_->ResetFallbackToFirstNavigationSurface();
  }
}

void OffscreenView::OnDidUpdateVisualPropertiesComplete(
    const cc::RenderFrameMetadata& metadata) {
  if (host()->IsHidden()) {
    // Take the child's id, but embed nothing while hidden; showing allocates
    // a fresh one if this was evicted meanwhile.
    if (metadata.local_surface_id && surface_id_allocator_) {
      surface_id_allocator_->UpdateFromChild(*metadata.local_surface_id);
    } else {
      AllocateLocalSurfaceId();
    }
  } else {
    SynchronizeVisualProperties(cc::DeadlinePolicy::UseDefaultDeadline(),
                                metadata.local_surface_id);
  }
}

#if !BUILDFLAG(IS_MAC)
viz::ScopedSurfaceIdAllocator OffscreenView::DidUpdateVisualProperties(
    const cc::RenderFrameMetadata& metadata) {
  return viz::ScopedSurfaceIdAllocator(
      base::BindOnce(&OffscreenView::OnDidUpdateVisualPropertiesComplete,
                     weak_ptr_factory_.GetWeakPtr(), metadata));
}
#endif

viz::SurfaceId OffscreenView::GetCurrentSurfaceId() const {
  return frame_host_ ? frame_host_->GetCurrentSurfaceId() : viz::SurfaceId();
}

bool OffscreenView::HasSavedCompositorFrame() const {
  return frame_host_ && frame_host_->HasSavedFrame();
}

void OffscreenView::UpdateFrameSinkIdRegistration() {
  RenderWidgetHostViewBase::UpdateFrameSinkIdRegistration();
  if (frame_host_) {
    frame_host_->SetIsFrameSinkIdOwner(is_frame_sink_id_owner());
  }
}

const viz::FrameSinkId& OffscreenView::GetFrameSinkId() const {
  return frame_host_ ? frame_host_->frame_sink_id()
                     : viz::FrameSinkIdAllocator::InvalidFrameSinkId();
}

viz::FrameSinkId OffscreenView::GetRootFrameSinkId() {
  ui::Compositor* root = compositor();
  return root ? root->frame_sink_id() : viz::FrameSinkId();
}

void OffscreenView::DidNavigate() {
  if (!IsShowing()) {
    // No new id while hidden; Show() allocates one once sizes are known.
    InvalidateLocalSurfaceId();
  } else if (is_first_navigation_) {
    // The renderer can keep the id it was already given.
    SynchronizeVisualProperties(cc::DeadlinePolicy::UseExistingDeadline(),
                                GetLocalSurfaceId());
  } else {
    SynchronizeVisualProperties(cc::DeadlinePolicy::UseExistingDeadline(),
                                std::nullopt);
  }
  if (frame_host_) {
    frame_host_->DidNavigate();
  }
  is_first_navigation_ = false;
}

void OffscreenView::TakeFallbackContentFrom(
    content::RenderWidgetHostView* view) {
  auto* other = static_cast<OffscreenView*>(view);
  SetBackgroundColor(other->background_color_);
  if (frame_host_ && other->frame_host_) {
    frame_host_->TakeFallbackContentFrom(other->frame_host_.get());
  }
}

void OffscreenView::CopyFromSurface(
    const gfx::Rect& src_rect,
    const gfx::Size& output_size,
    base::TimeDelta timeout,
    base::OnceCallback<void(const content::CopyFromSurfaceResult&)> callback) {
  if (frame_host_) {
    frame_host_->CopyFromCompositingSurface(src_rect, output_size, timeout,
                                            std::move(callback));
  }
}

bool OffscreenView::IsSurfaceAvailableForCopy() {
  return frame_host_ && frame_host_->CanCopyFromCompositingSurface();
}

uint32_t OffscreenView::GetCaptureSequenceNumber() const {
  return capture_sequence_number_;
}

void OffscreenView::EnsureSurfaceSynchronizedForWebTest() {
  ++capture_sequence_number_;
  SynchronizeVisualProperties(cc::DeadlinePolicy::UseInfiniteDeadline(),
                              std::nullopt);
}

// ---- visibility -------------------------------------------------------------

void OffscreenView::ShowWithVisibility(content::PageVisibilityState) {
  if (is_showing_) {
    return;
  }
  is_showing_ = true;

  if (!GetLocalSurfaceId().is_valid()) {
    // Evicted while hidden, and nothing else changed since.
    AllocateLocalSurfaceId();
    SynchronizeVisualProperties(cc::DeadlinePolicy::UseDefaultDeadline(),
                                GetLocalSurfaceId());
  }
  widget_->WasShown(/*record_tab_switch_time_request=*/{});
  if (frame_host_) {
    frame_host_->AttachToCompositor(compositor());
    frame_host_->WasShown(GetLocalSurfaceId(), bounds_.size(),
                          /*record_tab_switch_time_request=*/{});
  }
}

void OffscreenView::Hide() {
  if (!is_showing_) {
    return;
  }
  is_showing_ = false;
  if (widget_->delegate()) {
    widget_->WasHidden();
  }
  if (frame_host_) {
    frame_host_->WasHidden(content::DelegatedFrameHost::HiddenCause::kOther);
    frame_host_->DetachFromCompositor();
  }
}

bool OffscreenView::IsShowing() {
  return is_showing_;
}

void OffscreenView::NotifyHostAndDelegateOnWasShown(
    std::optional<blink::RecordContentToVisibleTimeRequest>) {
  // Only reached through RenderWidgetHostViewBase::OnShowWithPageVisibility,
  // which this view does not use.
  NOTREACHED();
}

void OffscreenView::RequestSuccessfulPresentationTimeFromHostOrDelegate(
    blink::RecordContentToVisibleTimeRequest) {
  NOTREACHED();
}

void OffscreenView::CancelSuccessfulPresentationTimeRequestForHostAndDelegate() {
  NOTREACHED();
}

void OffscreenView::SetBackgroundColor(SkColor color) {
  // The renderer reports its colour with the first frame; show something
  // sensible until then.
  if (color != background_color_) {
    background_color_ = color;
    root_layer_->SetFillsBoundsOpaquely(SkColorGetA(color) == SK_AlphaOPAQUE);
    root_layer_->SetColor(color);
  }
  content::RenderWidgetHostViewBase::SetBackgroundColor(color);
}

std::optional<SkColor> OffscreenView::GetBackgroundColor() {
  return background_color_;
}

std::optional<content::DisplayFeature> OffscreenView::GetDisplayFeature() {
  return std::nullopt;
}

// ---- child widgets ----------------------------------------------------------

void OffscreenView::InitAsPopup(content::RenderWidgetHostView* parent_host_view,
                                const gfx::Rect& bounds,
                                const gfx::Rect& anchor_rect) {
  CHECK_EQ(parent_, parent_host_view);
  if (parent_->popup_) {
    parent_->popup_->CancelWidget();
  }
  parent_->popup_ = this;

  // `bounds` is in screen coordinates, and the page is at the screen's origin
  // as far as it knows.
  bounds_ = bounds;
  parent_->root_layer()->Add(root_layer_.get());
  parent_->root_layer()->StackAtTop(root_layer_.get());
  UpdateGeometry(/*force=*/true);
  Show();
}

// A fullscreen widget (a legacy path: plugins, never HTML fullscreen).
void OffscreenView::InitAsChild(gfx::NativeView) {
  CHECK(parent_);
  if (parent_->fullscreen_child_) {
    parent_->fullscreen_child_->CancelWidget();
  }
  parent_->fullscreen_child_ = this;
  bounds_ = gfx::Rect(parent_->bounds_.size());
  parent_->root_layer()->Add(root_layer_.get());
  parent_->root_layer()->StackAtTop(root_layer_.get());
  UpdateGeometry(/*force=*/true);
  Show();
}

void OffscreenView::CancelWidget() {
  if (widget_) {
    widget_->LostCapture();
  }
  Hide();
  if (parent_) {
    if (parent_->popup_ == this) {
      parent_->popup_ = nullptr;
    }
    if (parent_->fullscreen_child_ == this) {
      parent_->fullscreen_child_ = nullptr;
    }
    if (root_layer_->parent()) {
      root_layer_->parent()->Remove(root_layer_.get());
    }
    parent_ = nullptr;
  }
  if (widget_ && !is_destroyed_) {
    is_destroyed_ = true;
    // The widget of a page is owned by its RenderViewHost; a popup's is not.
    widget_->ShutdownAndDestroyWidget(!widget_->owner_delegate());
  }
}

void OffscreenView::RenderProcessGone() {
  Destroy();
}

void OffscreenView::Destroy() {
  if (!is_destroyed_) {
    is_destroyed_ = true;
    if (parent_) {
      CancelWidget();
    } else {
      if (popup_) {
        popup_->CancelWidget();
      }
      if (fullscreen_child_) {
        fullscreen_child_->CancelWidget();
      }
      Hide();
    }
  }
  delete this;
}

// ---- input ------------------------------------------------------------------

bool OffscreenView::ShouldRouteEvents() const {
  // A popup cannot contain frames of another process; the page can, and the
  // router is what finds which one is under the pointer.
  return widget_->delegate() &&
         widget_->delegate()->IsWidgetForPrimaryMainFrame(widget_) &&
         widget_->delegate()->GetInputEventRouter();
}

void OffscreenView::SendMouseEvent(const blink::WebMouseEvent& event) {
  blink::WebMouseEvent web_event(event);
  if (!is_popup() && popup_) {
    const gfx::Rect& popup = popup_->bounds_;
    if (popup.Contains(event.PositionInWidget().x(),
                       event.PositionInWidget().y())) {
      web_event.SetPositionInWidget(event.PositionInWidget().x() - popup.x(),
                                    event.PositionInWidget().y() - popup.y());
      web_event.SetPositionInScreen(web_event.PositionInWidget());
      popup_->SendMouseEvent(web_event);
      return;
    }
  }
  ui::LatencyInfo latency = LatencyFor(web_event);
  if (ShouldRouteEvents()) {
    widget_->delegate()->GetInputEventRouter()->RouteMouseEvent(this, &web_event,
                                                                latency);
  } else {
    ProcessMouseEvent(web_event, latency);
  }
}

void OffscreenView::SendMouseWheelEvent(const blink::WebMouseWheelEvent& event) {
  blink::WebMouseWheelEvent web_event(event);
  if (!is_popup() && popup_) {
    const gfx::Rect& popup = popup_->bounds_;
    if (popup.Contains(event.PositionInWidget().x(),
                       event.PositionInWidget().y())) {
      web_event.SetPositionInWidget(event.PositionInWidget().x() - popup.x(),
                                    event.PositionInWidget().y() - popup.y());
      web_event.SetPositionInScreen(web_event.PositionInWidget());
      popup_->SendMouseWheelEvent(web_event);
      return;
    }
    // Scrolling the page under an open drop-down closes it, as in any
    // browser. Not from inside this call: it deletes the popup's view.
    base::SingleThreadTaskRunner::GetCurrentDefault()->PostTask(
        FROM_HERE, base::BindOnce(&OffscreenView::CancelWidget,
                                  popup_->weak_ptr_factory_.GetWeakPtr()));
  }
  ui::LatencyInfo latency = LatencyFor(web_event);
  mouse_wheel_phase_handler_.SendWheelEndForTouchpadScrollingIfNeeded(false);
  mouse_wheel_phase_handler_.AddPhaseIfNeededAndScheduleEndEvent(
      web_event, false, /*is_fling_capable=*/false);
  if (ShouldRouteEvents()) {
    widget_->delegate()->GetInputEventRouter()->RouteMouseWheelEvent(
        this, &web_event, latency);
  } else {
    ProcessMouseWheelEvent(web_event, latency);
  }
}

void OffscreenView::SendKeyEvent(const input::NativeWebKeyboardEvent& event) {
  // An open drop-down takes the keyboard: arrows, Enter, Escape.
  if (!is_popup() && popup_) {
    popup_->SendKeyEvent(event);
    return;
  }
  content::RenderWidgetHostImpl* target = widget_;
  if (!is_popup() && widget_->delegate()) {
    // With out-of-process frames, the one holding focus.
    target = widget_->delegate()->GetFocusedRenderWidgetHost(widget_);
  }
  if (target && target->GetView()) {
    target->ForwardKeyboardEventWithLatencyInfo(event, LatencyFor(event));
  }
}

void OffscreenView::SetFocused(bool focused) {
  if (focused == is_focused_) {
    return;
  }
  is_focused_ = focused;
  if (focused) {
    widget_->GotFocus();
    widget_->SetActive(true);
  } else {
    if (popup_) {
      popup_->CancelWidget();
    }
    widget_->SetActive(false);
    widget_->LostFocus();
  }
}

void OffscreenView::Focus() {
  SetFocused(true);
}

bool OffscreenView::HasFocus() {
  return is_focused_;
}

blink::mojom::PointerLockResult OffscreenView::LockPointer(bool) {
  return blink::mojom::PointerLockResult::kPermissionDenied;
}

blink::mojom::PointerLockResult OffscreenView::ChangePointerLock(bool) {
  return blink::mojom::PointerLockResult::kPermissionDenied;
}

std::unique_ptr<content::SyntheticGestureTarget>
OffscreenView::CreateSyntheticGestureTarget() {
  return std::make_unique<GestureTarget>(host());
}

bool OffscreenView::TransformPointToCoordSpaceForView(
    const gfx::PointF& point,
    input::RenderWidgetHostViewInput* target_view,
    gfx::PointF* transformed_point) {
  if (target_view == this) {
    *transformed_point = point;
    return true;
  }
  return target_view->TransformPointToLocalCoordSpace(point, GetFrameSinkId(),
                                                      transformed_point);
}

// ---- what a native view would have done natively ------------------------------

void OffscreenView::UpdateCursor(const ui::Cursor& cursor) {
  // Through the manager, which knows which frame is under the pointer; it
  // comes back as DisplayCursor() on the page's view.
  GetCursorManager()->UpdateCursor(this, cursor);
}

void OffscreenView::DisplayCursor(const ui::Cursor& cursor) {
  if (OffscreenViewDelegate* target = delegate()) {
    target->OnCursorChanged(cursor);
  }
}

input::CursorManager* OffscreenView::GetCursorManager() {
  return parent_ ? parent_->GetCursorManager() : cursor_manager_.get();
}

void OffscreenView::UpdateTooltipUnderCursor(const std::u16string& text) {
  if (OffscreenViewDelegate* target = delegate()) {
    target->OnTooltipChanged(text);
  }
}

void OffscreenView::OnUpdateTextInputStateCalled(
    content::TextInputManager*,
    content::RenderWidgetHostViewBase*,
    bool did_update_state) {
  if (did_update_state) {
    ReportTextInputState();
  }
}

void OffscreenView::OnSelectionBoundsChanged(
    content::TextInputManager*,
    content::RenderWidgetHostViewBase*) {
  ReportTextInputState();
}

void OffscreenView::ReportTextInputState() {
  OffscreenViewDelegate* target = delegate();
  if (!target || !text_input_manager_) {
    return;
  }
  const ui::mojom::TextInputState* state =
      text_input_manager_->GetTextInputState();
  const bool is_editable = state && state->type != ui::TEXT_INPUT_TYPE_NONE;
  gfx::Rect caret;
  if (is_editable) {
    if (const content::TextInputManager::SelectionRegion* region =
            text_input_manager_->GetSelectionRegion()) {
      caret = gfx::BoundingRect(region->focus.edge_start_rounded(),
                                region->focus.edge_end_rounded());
    }
  }
  target->OnTextInputStateChanged(is_editable, caret);
}

void OffscreenView::ImeSetComposition(const std::u16string& text,
                                      int selection_start,
                                      int selection_end) {
  std::vector<ui::ImeTextSpan> underlines;
  underlines.emplace_back(ui::ImeTextSpan::Type::kComposition, 0, text.size(),
                          ui::ImeTextSpan::Thickness::kThin,
                          ui::ImeTextSpan::UnderlineStyle::kSolid,
                          SK_ColorTRANSPARENT);
  // The bounds of what is being composed, for the candidate window.
  widget_->RequestCompositionUpdates(false, true);
  widget_->ImeSetComposition(text, underlines, gfx::Range::InvalidRange(),
                             selection_start, selection_end);
}

void OffscreenView::ImeCommitText(const std::u16string& text) {
  widget_->ImeCommitText(text, std::vector<ui::ImeTextSpan>(),
                         gfx::Range::InvalidRange(), 0);
  widget_->RequestCompositionUpdates(false, false);
}

void OffscreenView::ImeCancel() {
  ImeCancelComposition();
}

void OffscreenView::ImeCancelComposition() {
  widget_->ImeCancelComposition();
  widget_->RequestCompositionUpdates(false, false);
}

void OffscreenView::ImeCompositionRangeChanged(
    const gfx::Range& range,
    const std::optional<std::vector<gfx::Rect>>& character_bounds) {
  OffscreenViewDelegate* target = delegate();
  if (!target || !character_bounds || character_bounds->empty()) {
    return;
  }
  gfx::Rect bounds;
  for (const gfx::Rect& rect : *character_bounds) {
    bounds.Union(rect);
  }
  target->OnImeCompositionBoundsChanged(bounds);
}

// ---- nothing native ---------------------------------------------------------

gfx::NativeView OffscreenView::GetNativeView() {
  return gfx::NativeView();
}

gfx::NativeViewAccessible OffscreenView::GetNativeViewAccessible() {
  return gfx::NativeViewAccessible();
}

#if BUILDFLAG(IS_MAC)
void OffscreenView::ShowSharePicker(
    const std::string& title,
    const std::string& text,
    const GURL& url,
    const std::vector<std::string>& file_paths,
    blink::mojom::ShareService::ShareCallback callback) {
  std::move(callback).Run(blink::mojom::ShareError::INTERNAL_ERROR);
}

uint64_t OffscreenView::GetNSViewId() const {
  return 0;
}
#endif

std::unique_ptr<viz::HostDisplayClient> OffscreenView::CreateHostDisplayClient() {
  return std::make_unique<viz::HostDisplayClient>(gfx::kNullAcceleratedWidget);
}

bool OffscreenView::UseProxyOutputDevice() {
  // That is CEF's software path, pixels over shared memory per paint. Frames
  // leave this view through the capturer in both GPU and software modes.
  return false;
}

}  // namespace sofik
