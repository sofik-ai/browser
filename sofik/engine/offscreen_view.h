// Copyright 2026 Sofik. All rights reserved.
// Portions copyright 2014 The Chromium Embedded Framework Authors and 2012 The
// Chromium Authors, under the BSD-style licence in //cef/LICENSE.txt: the
// surface synchronisation here descends from CEF's off-screen view.

#ifndef SOFIK_ENGINE_OFFSCREEN_VIEW_H_
#define SOFIK_ENGINE_OFFSCREEN_VIEW_H_

#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "base/memory/raw_ptr.h"
#include "base/memory/weak_ptr.h"
#include "build/build_config.h"
#include "cc/layers/deadline_policy.h"
#include "components/viz/common/surfaces/parent_local_surface_id_allocator.h"
#include "content/browser/renderer_host/input/mouse_wheel_phase_handler.h"
#include "content/browser/renderer_host/render_widget_host_view_base.h"
#include "content/browser/renderer_host/text_input_manager.h"
#include "ui/compositor/compositor.h"
#include "ui/gfx/geometry/rect.h"
#include "ui/gfx/geometry/size.h"

namespace content {
class DelegatedFrameHost;
class DelegatedFrameHostClient;
class RenderWidgetHostImpl;
}  // namespace content

namespace input {
class CursorManager;
}

namespace ui {
class Layer;
}

namespace sofik {

class OffscreenContentsView;

// What a native view would have done on its own, reported instead. One per
// web contents; every widget of that contents (the page, a <select>
// drop-down, a fullscreen element) reports to the same one.
class OffscreenViewDelegate {
 public:
  virtual void OnCursorChanged(const ui::Cursor& cursor) = 0;
  virtual void OnTooltipChanged(const std::u16string& text) = 0;
  // `is_editable` is false when focus left every text field.
  virtual void OnTextInputStateChanged(bool is_editable,
                                       const gfx::Rect& caret) = 0;
  virtual void OnImeCompositionBoundsChanged(const gfx::Rect& bounds) = 0;

 protected:
  virtual ~OffscreenViewDelegate() = default;
};

// A widget's view with no window behind it.
//
// The platform views (RenderWidgetHostViewMac, ...Aura) are built around a
// native view in a native window: the cursor is set on it, tooltips and IME
// go through it, a <select> opens a real window next to it, and its scale is
// the monitor's. None of that exists for a page painted into a texture, and
// all of it is what the host has to be told about instead. So the engine has
// its own view, which owns a compositor with no output surface at all -- the
// frames leave through the video capturer -- and turns everything the platform
// view would have done natively into a call on the delegate.
//
// A popup widget does not get a compositor of its own. Its layer is added to
// the page's, at the popup's position, so the drop-down arrives inside the
// page's frames already composited on the GPU and the host draws nothing.
class OffscreenView : public content::RenderWidgetHostViewBase,
                      public ui::CompositorDelegate,
                      public content::TextInputManager::Observer {
 public:
  OffscreenView(content::RenderWidgetHost* widget,
                OffscreenView* parent,
                base::WeakPtr<OffscreenContentsView> contents_view);

  OffscreenView(const OffscreenView&) = delete;
  OffscreenView& operator=(const OffscreenView&) = delete;

  // What the engine drives.
  void WasResized();
  void OnScaleChanged();
  void SetFocused(bool focused);
  void SendMouseEvent(const blink::WebMouseEvent& event);
  void SendMouseWheelEvent(const blink::WebMouseWheelEvent& event);
  void SendKeyEvent(const input::NativeWebKeyboardEvent& event);
  void ImeSetComposition(const std::u16string& text,
                         int selection_start,
                         int selection_end);
  void ImeCommitText(const std::u16string& text);
  void ImeCancel();

  bool is_popup() const { return widget_type_ == content::WidgetType::kPopup; }
  ui::Layer* root_layer() const { return root_layer_.get(); }
  content::RenderWidgetHostImpl* widget() const { return widget_; }

  // content::RenderWidgetHostView:
  void InitAsChild(gfx::NativeView parent_view) override;
  void SetSize(const gfx::Size& size) override {}
  void SetBounds(const gfx::Rect& rect) override {}
  gfx::NativeView GetNativeView() override;
  gfx::NativeViewAccessible GetNativeViewAccessible() override;
  void Focus() override;
  bool HasFocus() override;
  uint32_t GetCaptureSequenceNumber() const override;
  bool IsSurfaceAvailableForCopy() override;
  void ShowWithVisibility(
      content::PageVisibilityState page_visibility) override;
  void Hide() override;
  bool IsShowing() override;
  void EnsureSurfaceSynchronizedForWebTest() override;
  gfx::Rect GetViewBounds() override;
  void SetBackgroundColor(SkColor color) override;
  std::optional<SkColor> GetBackgroundColor() override;
  void UpdateBackgroundColor() override {}
  std::optional<content::DisplayFeature> GetDisplayFeature() override;
  void DisableDisplayFeatureOverrideForEmulation() override {}
  void OverrideDisplayFeatureForEmulation(
      const content::DisplayFeature* display_feature) override {}
  blink::mojom::PointerLockResult LockPointer(
      bool request_unadjusted_movement) override;
  blink::mojom::PointerLockResult ChangePointerLock(
      bool request_unadjusted_movement) override;
  void UnlockPointer() override {}
  void TakeFallbackContentFrom(content::RenderWidgetHostView* view) override;
#if BUILDFLAG(IS_MAC)
  void SetActive(bool active) override {}
  void ShowDefinitionForSelection() override {}
  void SpeakSelection() override {}
  void SetWindowFrameInScreen(const gfx::Rect& rect) override {}
  void ShowSharePicker(
      const std::string& title,
      const std::string& text,
      const GURL& url,
      const std::vector<std::string>& file_paths,
      blink::mojom::ShareService::ShareCallback callback) override;
  uint64_t GetNSViewId() const override;
#endif

  // content::RenderWidgetHostViewBase:
  void InvalidateLocalSurfaceIdAndAllocationGroup() override;
  void ClearFallbackSurfaceForCommitPending() override;
  void ResetFallbackToFirstNavigationSurface() override;
  void OnUnconfirmedTapConvertedToTap() override {}
  void InitAsPopup(content::RenderWidgetHostView* parent_host_view,
                   const gfx::Rect& bounds,
                   const gfx::Rect& anchor_rect) override;
  void UpdateCursor(const ui::Cursor& cursor) override;
  void DisplayCursor(const ui::Cursor& cursor) override;
  void SetIsLoading(bool is_loading) override {}
  void RenderProcessGone() override;
  void Destroy() override;
  void UpdateTooltipUnderCursor(const std::u16string& tooltip_text) override;
  input::CursorManager* GetCursorManager() override;
  gfx::Size GetCompositorViewportPixelSize() override;
  void CopyFromSurface(
      const gfx::Rect& src_rect,
      const gfx::Size& output_size,
      base::TimeDelta timeout,
      base::OnceCallback<void(const content::CopyFromSurfaceResult&)> callback)
      override;
  display::ScreenInfos GetNewScreenInfosForUpdate() override;
  void TransformPointToRootSurface(gfx::PointF* point) override {}
  gfx::Rect GetBoundsInRootWindow() override;
#if !BUILDFLAG(IS_MAC)
  viz::ScopedSurfaceIdAllocator DidUpdateVisualProperties(
      const cc::RenderFrameMetadata& metadata) override;
#endif
  viz::SurfaceId GetCurrentSurfaceId() const override;
  bool HasSavedCompositorFrame() const override;
  void ImeCompositionRangeChanged(
      const gfx::Range& range,
      const std::optional<std::vector<gfx::Rect>>& character_bounds) override;
  void ImeCancelComposition() override;
  std::unique_ptr<content::SyntheticGestureTarget>
  CreateSyntheticGestureTarget() override;
  bool TransformPointToCoordSpaceForView(
      const gfx::PointF& point,
      input::RenderWidgetHostViewInput* target_view,
      gfx::PointF* transformed_point) override;
  void DidNavigate() override;
  const viz::LocalSurfaceId& GetLocalSurfaceId() const override;
  void UpdateFrameSinkIdRegistration() override;
  const viz::FrameSinkId& GetFrameSinkId() const override;
  viz::FrameSinkId GetRootFrameSinkId() override;
  void NotifyHostAndDelegateOnWasShown(
      std::optional<blink::RecordContentToVisibleTimeRequest>
          visible_time_request) override;
  void RequestSuccessfulPresentationTimeFromHostOrDelegate(
      blink::RecordContentToVisibleTimeRequest visible_time_request) override;
  void CancelSuccessfulPresentationTimeRequestForHostAndDelegate() override;

  // ui::CompositorDelegate:
  std::unique_ptr<viz::HostDisplayClient> CreateHostDisplayClient() override;
  bool UseProxyOutputDevice() override;

  // content::TextInputManager::Observer:
  void OnUpdateTextInputStateCalled(
      content::TextInputManager* text_input_manager,
      content::RenderWidgetHostViewBase* updated_view,
      bool did_update_state) override;
  void OnSelectionBoundsChanged(
      content::TextInputManager* text_input_manager,
      content::RenderWidgetHostViewBase* updated_view) override;

  // For the frame host's client.
  void InvalidateLocalSurfaceId();
  void OnDidUpdateVisualPropertiesComplete(
      const cc::RenderFrameMetadata& metadata);

 private:
  ~OffscreenView() override;

  OffscreenViewDelegate* delegate() const;
  // The compositor this widget draws into: its own, or the page's for a popup.
  ui::Compositor* compositor() const;

  void SynchronizeVisualProperties(
      const cc::DeadlinePolicy& deadline_policy,
      const std::optional<viz::LocalSurfaceId>& child_local_surface_id);
  // True when the size or the scale changed.
  bool UpdateGeometry(bool force);
  void ApplyFrameRate();
  void ReportTextInputState();
  void CancelWidget();
  bool ShouldRouteEvents() const;

  void AllocateLocalSurfaceId();
  const viz::LocalSurfaceId& GetOrCreateLocalSurfaceId();

  raw_ptr<content::RenderWidgetHostImpl> widget_;
  base::WeakPtr<OffscreenContentsView> contents_view_;
  raw_ptr<OffscreenView> parent_;
  raw_ptr<OffscreenView> popup_ = nullptr;
  raw_ptr<OffscreenView> fullscreen_child_ = nullptr;

  SkColor background_color_ = SK_ColorWHITE;
  std::unique_ptr<ui::Compositor> compositor_;  // null for a popup
  std::unique_ptr<ui::Layer> root_layer_;
  std::unique_ptr<content::DelegatedFrameHostClient> frame_host_client_;
  std::unique_ptr<content::DelegatedFrameHost> frame_host_;
  std::unique_ptr<viz::ParentLocalSurfaceIdAllocator> surface_id_allocator_;
  viz::ParentLocalSurfaceIdAllocator compositor_surface_id_allocator_;
  std::unique_ptr<input::CursorManager> cursor_manager_;
  content::MouseWheelPhaseHandler mouse_wheel_phase_handler_;

  gfx::Rect bounds_;  // DIPs; a popup's are relative to the page
  float scale_ = 0;
  bool is_showing_ = false;
  bool is_destroyed_ = false;
  bool is_focused_ = false;
  bool is_first_navigation_ = true;
  bool frame_rate_applied_ = false;
  uint32_t capture_sequence_number_ = 0;

  base::WeakPtrFactory<OffscreenView> weak_ptr_factory_{this};
};

}  // namespace sofik

#endif  // SOFIK_ENGINE_OFFSCREEN_VIEW_H_
