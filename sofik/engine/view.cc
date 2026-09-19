// Copyright 2026 Sofik. All rights reserved.

#include "sofik/engine/view.h"

#include <optional>
#include <utility>

#include "base/functional/bind.h"
#include "base/logging.h"
#include "base/memory/ptr_util.h"
#include "base/memory/read_only_shared_memory_region.h"
#include "base/strings/utf_string_conversions.h"
#include "base/task/single_thread_task_runner.h"
#include "base/time/time.h"
#include "build/build_config.h"
#include "components/input/native_web_keyboard_event.h"
#include "components/download/public/common/download_item.h"
#include "content/public/browser/browser_context.h"
#include "content/public/browser/devtools_agent_host.h"
#include "content/public/browser/download_manager.h"
#include "content/public/browser/navigation_controller.h"
#include "content/public/browser/navigation_entry.h"
#include "content/public/browser/navigation_handle.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/browser/render_widget_host.h"
#include "content/public/browser/reload_type.h"
#include "content/public/browser/render_widget_host_view.h"
#include "content/public/browser/web_contents.h"
#include "content/public/browser/host_zoom_map.h"
#include "content/public/browser/javascript_dialog_manager.h"
#include "headless/lib/browser/headless_web_contents_impl.h"
#include "headless/public/headless_browser_context.h"
#include "headless/public/headless_web_contents.h"
#include "media/base/video_frame.h"
#include "media/base/video_types.h"
#include "media/capture/mojom/video_capture_buffer.mojom.h"
#include "media/capture/mojom/video_capture_types.mojom.h"
#include "net/base/net_errors.h"
#include "sofik/engine/downloads.h"
#include "sofik/engine/engine.h"
#include "sofik/engine/offscreen_contents_view.h"
#include "sofik/engine/offscreen_view.h"
#include "third_party/blink/public/common/input/web_input_event.h"
#include "third_party/blink/public/common/input/web_mouse_event.h"
#include "third_party/blink/public/common/input/web_mouse_wheel_event.h"
#include "third_party/blink/public/mojom/favicon/favicon_url.mojom.h"
#include "ui/base/cursor/cursor.h"
#include "ui/base/cursor/mojom/cursor_type.mojom-shared.h"
#include "ui/base/page_transition_types.h"
#include "ui/events/base_event_utils.h"
#include "ui/events/event_constants.h"
#include "ui/events/keycodes/dom/dom_code.h"
#include "ui/events/keycodes/dom/dom_key.h"
#include "ui/events/keycodes/dom/keycode_converter.h"
#include "ui/events/keycodes/keyboard_code_conversion.h"
#include "ui/events/types/scroll_types.h"
#include "ui/gfx/geometry/rect.h"
#include "ui/gfx/geometry/size_conversions.h"
#include "url/gurl.h"

namespace sofik {
namespace {

int ToBlinkModifiers(uint32_t modifiers) {
  int result = 0;
  if (modifiers & SOFIK_MOD_SHIFT) {
    result |= blink::WebInputEvent::kShiftKey;
  }
  if (modifiers & SOFIK_MOD_CONTROL) {
    result |= blink::WebInputEvent::kControlKey;
  }
  if (modifiers & SOFIK_MOD_ALT) {
    result |= blink::WebInputEvent::kAltKey;
  }
  if (modifiers & SOFIK_MOD_META) {
    result |= blink::WebInputEvent::kMetaKey;
  }
  if (modifiers & SOFIK_MOD_LEFT_BUTTON) {
    result |= blink::WebInputEvent::kLeftButtonDown;
  }
  if (modifiers & SOFIK_MOD_MIDDLE_BUTTON) {
    result |= blink::WebInputEvent::kMiddleButtonDown;
  }
  if (modifiers & SOFIK_MOD_RIGHT_BUTTON) {
    result |= blink::WebInputEvent::kRightButtonDown;
  }
  if (modifiers & SOFIK_MOD_IS_REPEAT) {
    result |= blink::WebInputEvent::kIsAutoRepeat;
  }
  return result;
}

// ui::EventFlags, which is what the keyboard layout tables take. Not the
// same bits as blink's modifiers: Shift is 1 << 0 there and 1 << 1 here.
int ToUiEventFlags(uint32_t modifiers) {
  int result = 0;
  if (modifiers & SOFIK_MOD_SHIFT) {
    result |= ui::EF_SHIFT_DOWN;
  }
  if (modifiers & SOFIK_MOD_CONTROL) {
    result |= ui::EF_CONTROL_DOWN;
  }
  if (modifiers & SOFIK_MOD_ALT) {
    result |= ui::EF_ALT_DOWN;
  }
  if (modifiers & SOFIK_MOD_META) {
    result |= ui::EF_COMMAND_DOWN;
  }
  return result;
}

sofik_rect ToRect(const gfx::Rect& rect) {
  return {rect.x(), rect.y(), rect.width(), rect.height()};
}

}  // namespace

// static
std::unique_ptr<View> View::Create(sofik_view_id id,
                                   headless::HeadlessBrowserContext* context,
                                   const sofik_view_config& config,
                                   const sofik_view_callbacks& callbacks,
                                   void* user) {
  const gfx::Size size(config.width > 0 ? config.width : 1280,
                       config.height > 0 ? config.height : 800);
  GURL url(config.url && *config.url ? config.url : "about:blank");
  const int frame_rate = config.frame_rate > 0 ? config.frame_rate : 60;
  // The page's first widget view is made inside Build(), so the view that
  // makes it has to be in place before: it goes in with the parameters the
  // web contents is created from.
  OffscreenContentsView* contents_view = nullptr;
  headless::HeadlessWebContents* contents =
      context->CreateWebContentsBuilder()
          .SetInitialURL(url)
          .SetWindowBounds(gfx::Rect(size))
          .SetCreateParamsCallback(base::BindOnce(
              [](OffscreenContentsView** out, const gfx::Size& size,
                 float scale, int frame_rate,
                 content::WebContents::CreateParams* params) {
                *out = OffscreenContentsView::Install(params, size, scale,
                                                      frame_rate);
              },
              &contents_view, size, config.device_scale_factor, frame_rate))
          .Build();
  if (!contents) {
    LOG(ERROR) << "sofik: could not create a view for " << url;
    return nullptr;
  }
  CHECK(contents_view);
  auto* contents_impl = headless::HeadlessWebContentsImpl::From(contents);
  contents_view->set_web_contents(contents_impl->web_contents());
  auto view = base::WrapUnique(
      new View(id, contents_impl, contents_view, config, callbacks, user));
  contents_view->set_delegate(view.get());
  view->size_dips_ = size;
  view->contents_->set_embedder_delegate(view.get());
  view->StartCapture();
  return view;
}

View::View(sofik_view_id id,
           headless::HeadlessWebContentsImpl* contents,
           OffscreenContentsView* contents_view,
           const sofik_view_config& config,
           const sofik_view_callbacks& callbacks,
           void* user)
    : content::WebContentsObserver(contents->web_contents()),
      id_(id),
      contents_(contents),
      contents_view_(contents_view),
      callbacks_(callbacks),
      user_(user),
      prefer_gpu_frames_(config.prefer_gpu_frames != 0),
      frame_rate_(config.frame_rate > 0 ? config.frame_rate : 60) {}

View::~View() {
  CancelDialogs(nullptr, /*reset_state=*/true);
  for (auto& [request, pending] : permissions_) {
    std::move(pending.callback).Run(std::vector<blink::mojom::PermissionStatus>(
        pending.types.size(), blink::mojom::PermissionStatus::ASK));
  }
  permissions_.clear();
  if (contents_) {
    contents_->set_embedder_delegate(nullptr);
    contents_view_->set_delegate(nullptr);
  }
  contents_view_ = nullptr;
  CdpDetach();
  capturer_.reset();
  held_frame_.reset();
  Observe(nullptr);
  if (contents_) {
    // Deletes the web contents; nothing may touch it afterwards.
    contents_.ExtractAsDangling()->Close();
  }
}

content::WebContents* View::web_contents() const {
  return contents_ ? contents_->web_contents() : nullptr;
}

OffscreenView* View::page_view() const {
  if (!contents_ || !contents_->web_contents()->GetRenderWidgetHostView()) {
    return nullptr;
  }
  return contents_view_->GetView();
}

// ---- frames -----------------------------------------------------------------

void View::StartCapture() {
  if (!contents_) {
    return;
  }
  content::RenderWidgetHostView* view =
      contents_->web_contents()->GetRenderWidgetHostView();
  if (!view) {
    return;  // RenderViewReady() will come back here.
  }
  // A cross-site navigation replaces the widget, and with it the frame sink a
  // capturer is bound to; a new capturer on the new view is the simple answer.
  held_frame_.reset();
  capturer_ = view->CreateVideoCapturer();
  // Not the page's own frame sink, which CreateVideoCapturer() aims at, but
  // the compositor's above it: that one has a <select>'s drop-down in it too,
  // which is a widget of its own stacked over the page.
  capturer_->ChangeTarget(viz::VideoCaptureTarget(static_cast<OffscreenView*>(
                              view)->GetRootFrameSinkId()),
                          /*sub_capture_target_version=*/0);
  capturer_->SetFormat(media::PIXEL_FORMAT_ARGB);
  capturer_->SetAnimationFpsLockIn(false, 0.0);
  // The texture is shown 1:1: never trade resolution for throughput.
  capturer_->SetAutoThrottlingEnabled(false);
  capturer_->SetMinSizeChangePeriod(base::TimeDelta());
  capturer_->SetMinCapturePeriod(base::Seconds(1) / frame_rate_);
  ApplyCaptureSize();
  capturer_->Start(
      this, prefer_gpu_frames_
                ? viz::mojom::BufferFormatPreference::kPreferMappableSharedImage
                : viz::mojom::BufferFormatPreference::kDefault);
  capturer_->RequestRefreshFrame();
}

void View::ApplyCaptureSize() {
  if (!capturer_ || !contents_) {
    return;
  }
  content::RenderWidgetHostView* view =
      contents_->web_contents()->GetRenderWidgetHostView();
  const float scale = view ? view->GetDeviceScaleFactor() : 1.0f;
  const gfx::Size pixels = gfx::ScaleToCeiledSize(size_dips_, scale);
  capturer_->SetResolutionConstraints(pixels, pixels,
                                      /*use_fixed_aspect_ratio=*/true);
}

void View::OnFrameCaptured(
    media::mojom::VideoBufferHandlePtr data,
    media::mojom::VideoFrameInfoPtr info,
    const gfx::Rect& content_rect,
    mojo::PendingRemote<viz::mojom::FrameSinkVideoConsumerFrameCallbacks>
        callbacks) {
  mojo::Remote<viz::mojom::FrameSinkVideoConsumerFrameCallbacks> done(
      std::move(callbacks));

  gfx::Rect damage(info->coded_size);
  if (info->metadata.capture_update_rect &&
      !info->metadata.capture_update_rect->IsEmpty()) {
    damage = *info->metadata.capture_update_rect;
  }

  sofik_frame frame = {};
  frame.width = info->coded_size.width();
  frame.height = info->coded_size.height();
  frame.content = ToRect(content_rect);
  frame.damage = ToRect(damage);
  frame.format = info->pixel_format == media::PIXEL_FORMAT_ABGR
                     ? SOFIK_PIXEL_RGBA
                     : SOFIK_PIXEL_BGRA;
  frame.dmabuf_fd = -1;

  if (data->is_gpu_memory_buffer_handle()) {
#if BUILDFLAG(IS_APPLE)
    frame.io_surface = data->get_gpu_memory_buffer_handle().io_surface().get();
#endif
    if (callbacks_.on_frame) {
      callbacks_.on_frame(user_, id_, &frame);
    }
    // Only now may the previous surface go back to viz: until this call the
    // host was still showing it.
    held_frame_ = std::move(done);
    return;
  }

  if (data->is_read_only_shmem_region() &&
      info->pixel_format == media::PIXEL_FORMAT_ARGB) {
    base::ReadOnlySharedMemoryMapping mapping =
        data->get_read_only_shmem_region().Map();
    if (mapping.IsValid() &&
        mapping.size() >= media::VideoFrame::AllocationSize(
                              info->pixel_format, info->coded_size)) {
      frame.pixels = static_cast<const uint8_t*>(mapping.memory());
      frame.stride = static_cast<int>(media::VideoFrame::RowBytes(
          media::VideoFrame::Plane::kARGB, info->pixel_format,
          info->coded_size.width()));
      if (callbacks_.on_frame) {
        callbacks_.on_frame(user_, id_, &frame);
      }
    }
  }
  done->Done();
}

void View::Resize(const gfx::Size& size_dips) {
  if (!contents_ || size_dips.IsEmpty() || size_dips == size_dips_) {
    return;
  }
  size_dips_ = size_dips;
  // The window the page believes it is in (window.outerWidth, screenX)...
  contents_->SetBounds(gfx::Rect(size_dips_));
  // ...and the surface it paints.
  contents_view_->SetSize(size_dips_);
  ApplyCaptureSize();
  Invalidate();
}

void View::SetScale(float scale) {
  if (!contents_ || scale <= 0) {
    return;
  }
  contents_view_->SetScale(scale);
  ApplyCaptureSize();
  Invalidate();
}

void View::SetVisible(bool visible) {
  if (!contents_) {
    return;
  }
  if (visible) {
    contents_->web_contents()->WasShown();
    Invalidate();
  } else {
    contents_->web_contents()->WasHidden();
  }
}

void View::SetFocus(bool focused) {
  if (OffscreenView* view = page_view()) {
    view->SetFocused(focused);
  }
}

void View::Invalidate() {
  if (capturer_) {
    capturer_->RequestRefreshFrame();
  }
}

// ---- navigation -------------------------------------------------------------

void View::LoadURL(const std::string& url) {
  if (!contents_) {
    return;
  }
  content::NavigationController::LoadURLParams params((GURL(url)));
  params.transition_type = ui::PageTransitionFromInt(
      ui::PAGE_TRANSITION_TYPED | ui::PAGE_TRANSITION_FROM_ADDRESS_BAR);
  contents_->web_contents()->GetController().LoadURLWithParams(params);
}

void View::GoBack() {
  if (contents_ && contents_->web_contents()->GetController().CanGoBack()) {
    contents_->web_contents()->GetController().GoBack();
  }
}

void View::GoForward() {
  if (contents_ && contents_->web_contents()->GetController().CanGoForward()) {
    contents_->web_contents()->GetController().GoForward();
  }
}

void View::Reload(bool ignore_cache) {
  if (contents_) {
    contents_->web_contents()->GetController().Reload(
        ignore_cache ? content::ReloadType::BYPASSING_CACHE
                     : content::ReloadType::NORMAL,
        /*check_for_repost=*/false);
  }
}

void View::Stop() {
  if (contents_) {
    contents_->web_contents()->Stop();
  }
}

void View::SetZoom(double level) {
  if (contents_) {
    content::HostZoomMap::SetZoomLevel(contents_->web_contents(), level);
  }
}

// ---- input ------------------------------------------------------------------

void View::MouseMove(int x, int y, uint32_t modifiers, bool left_the_view) {
  OffscreenView* view = page_view();
  if (!view) {
    return;
  }
  blink::WebMouseEvent event(
      left_the_view ? blink::WebInputEvent::Type::kMouseLeave
                    : blink::WebInputEvent::Type::kMouseMove,
      gfx::PointF(x, y), gfx::PointF(x, y),
      blink::WebPointerProperties::Button::kNoButton, 0,
      ToBlinkModifiers(modifiers), ui::EventTimeForNow());
  view->SendMouseEvent(event);
}

void View::MouseButton(int x, int y, sofik_mouse_button button, bool is_up,
                       int click_count, uint32_t modifiers) {
  OffscreenView* view = page_view();
  if (!view) {
    return;
  }
  blink::WebPointerProperties::Button blink_button =
      button == SOFIK_BUTTON_RIGHT
          ? blink::WebPointerProperties::Button::kRight
      : button == SOFIK_BUTTON_MIDDLE
          ? blink::WebPointerProperties::Button::kMiddle
          : blink::WebPointerProperties::Button::kLeft;
  blink::WebMouseEvent event(
      is_up ? blink::WebInputEvent::Type::kMouseUp
            : blink::WebInputEvent::Type::kMouseDown,
      gfx::PointF(x, y), gfx::PointF(x, y), blink_button,
      click_count > 0 ? click_count : 1, ToBlinkModifiers(modifiers),
      ui::EventTimeForNow());
  if (!is_up) {
    // A click lands where the keyboard should go next.
    SetFocus(true);
  }
  view->SendMouseEvent(event);
}

void View::MouseWheel(int x, int y, float delta_x, float delta_y,
                      uint32_t modifiers) {
  OffscreenView* view = page_view();
  if (!view) {
    return;
  }
  // Precise pixels, as a trackpad reports them. The scroll's phases -- it has
  // to begin and end for the compositor to take it -- are the view's business:
  // it has no gesture stream to read them from and times them instead.
  blink::WebMouseWheelEvent event(blink::WebInputEvent::Type::kMouseWheel,
                                  ToBlinkModifiers(modifiers),
                                  ui::EventTimeForNow());
  event.SetPositionInWidget(gfx::PointF(x, y));
  event.SetPositionInScreen(gfx::PointF(x, y));
  event.delta_x = delta_x;
  event.delta_y = delta_y;
  event.wheel_ticks_x = delta_x / 120.0f;
  event.wheel_ticks_y = delta_y / 120.0f;
  event.delta_units = ui::ScrollGranularity::kScrollByPrecisePixel;
  view->SendMouseWheelEvent(event);
}

void View::Key(sofik_key_type type, int windows_key_code, int native_key_code,
               uint32_t character, uint32_t modifiers) {
  OffscreenView* view = page_view();
  if (!view) {
    return;
  }
  blink::WebInputEvent::Type blink_type =
      type == SOFIK_KEY_UP     ? blink::WebInputEvent::Type::kKeyUp
      : type == SOFIK_KEY_CHAR ? blink::WebInputEvent::Type::kChar
                               : blink::WebInputEvent::Type::kRawKeyDown;
  input::NativeWebKeyboardEvent event(blink_type, ToBlinkModifiers(modifiers),
                                      ui::EventTimeForNow());
  event.windows_key_code = windows_key_code;
  event.native_key_code = native_key_code;

  // A page reads KeyboardEvent.code and .key, not the legacy keyCode.
  ui::DomCode dom_code =
      native_key_code
          ? ui::KeycodeConverter::NativeKeycodeToDomCode(native_key_code)
          : ui::UsLayoutKeyboardCodeToDomCode(
                static_cast<ui::KeyboardCode>(windows_key_code));
  event.dom_code = static_cast<int>(dom_code);
  ui::DomKey dom_key;
  ui::KeyboardCode ignored;
  if (character >= 0x20 && character != 0x7f) {
    dom_key = ui::DomKey::FromCharacter(character);
  } else if (!ui::DomCodeToUsLayoutDomKey(dom_code, ToUiEventFlags(modifiers),
                                          &dom_key, &ignored)) {
    dom_key = ui::DomKey::UNIDENTIFIED;
  }
  event.dom_key = static_cast<int>(dom_key);

  if (character && character <= 0xffff) {
    event.text[0] = static_cast<char16_t>(character);
    event.unmodified_text[0] = static_cast<char16_t>(character);
  }
  view->SendKeyEvent(event);
}

// ---- events -----------------------------------------------------------------

void View::RenderViewReady() {
  if (!capturer_) {
    StartCapture();
  }
}

void View::RenderViewHostChanged(content::RenderViewHost* old_host,
                                 content::RenderViewHost* new_host) {
  StartCapture();
}

void View::ReportLoadingState() {
  if (!callbacks_.on_loading_state || !contents_) {
    return;
  }
  content::WebContents* web_contents = contents_->web_contents();
  callbacks_.on_loading_state(user_, id_, web_contents->IsLoading(),
                              web_contents->GetController().CanGoBack(),
                              web_contents->GetController().CanGoForward());
}

void View::DidStartLoading() {
  ReportLoadingState();
}

void View::DidStopLoading() {
  ReportLoadingState();
}

void View::DidFinishNavigation(content::NavigationHandle* handle) {
  if (!handle->IsInPrimaryMainFrame() || !handle->HasCommitted()) {
    return;
  }
  if (callbacks_.on_address_changed) {
    callbacks_.on_address_changed(user_, id_, handle->GetURL().spec().c_str());
  }
  ReportLoadingState();
}

void View::DidFailLoad(content::RenderFrameHost* frame,
                       const GURL& url,
                       int error_code) {
  if (callbacks_.on_load_error && frame->IsInPrimaryMainFrame()) {
    callbacks_.on_load_error(
        user_, id_, error_code,
        net::ErrorToShortString(error_code).c_str(), url.spec().c_str());
  }
}

void View::TitleWasSet(content::NavigationEntry* entry) {
  if (callbacks_.on_title_changed && contents_) {
    callbacks_.on_title_changed(
        user_, id_,
        base::UTF16ToUTF8(contents_->web_contents()->GetTitle()).c_str());
  }
}

void View::DidUpdateFaviconURL(
    content::RenderFrameHost* frame,
    const std::vector<blink::mojom::FaviconURLPtr>& candidates) {
  if (!callbacks_.on_favicon_changed || !frame->IsInPrimaryMainFrame()) {
    return;
  }
  for (const auto& candidate : candidates) {
    if (candidate->icon_type == blink::mojom::FaviconIconType::kFavicon) {
      callbacks_.on_favicon_changed(user_, id_,
                                    candidate->icon_url.spec().c_str());
      return;
    }
  }
}

void View::OnDidAddMessageToConsole(
    content::RenderFrameHost* frame,
    blink::mojom::ConsoleMessageLevel level,
    const std::u16string& message,
    int32_t line,
    const std::u16string& source,
    const std::optional<std::u16string>& stack) {
  if (callbacks_.on_console_message) {
    callbacks_.on_console_message(user_, id_, static_cast<int>(level),
                                  base::UTF16ToUTF8(message).c_str(),
                                  base::UTF16ToUTF8(source).c_str(), line);
  }
}

void View::WebContentsDestroyed() {
  // The page closed itself (window.close, a crash handler, DevTools).
  contents_ = nullptr;
  contents_view_ = nullptr;
  capturer_.reset();
  held_frame_.reset();
  cdp_host_ = nullptr;
  if (callbacks_.on_closed) {
    callbacks_.on_closed(user_, id_);
  }
  base::SingleThreadTaskRunner::GetCurrentDefault()->PostTask(
      FROM_HERE, base::BindOnce(
                     [](sofik_view_id id) {
                       if (Engine* engine = Engine::Get()) {
                         engine->DestroyView(id);
                       }
                     },
                     id_));
}

// ---- what a native view would have shown -------------------------------------

namespace {

sofik_cursor ToSofikCursor(ui::mojom::CursorType type) {
  using ui::mojom::CursorType;
  switch (type) {
    case CursorType::kHand:
      return SOFIK_CURSOR_HAND;
    case CursorType::kIBeam:
      return SOFIK_CURSOR_IBEAM;
    case CursorType::kCross:
      return SOFIK_CURSOR_CROSS;
    case CursorType::kWait:
      return SOFIK_CURSOR_WAIT;
    case CursorType::kProgress:
      return SOFIK_CURSOR_PROGRESS;
    case CursorType::kHelp:
      return SOFIK_CURSOR_HELP;
    case CursorType::kNotAllowed:
    case CursorType::kNoDrop:
      return SOFIK_CURSOR_NOT_ALLOWED;
    case CursorType::kGrab:
      return SOFIK_CURSOR_GRAB;
    case CursorType::kGrabbing:
      return SOFIK_CURSOR_GRABBING;
    case CursorType::kMove:
    case CursorType::kMiddlePanning:
      return SOFIK_CURSOR_MOVE;
    case CursorType::kCopy:
      return SOFIK_CURSOR_COPY;
    case CursorType::kAlias:
      return SOFIK_CURSOR_ALIAS;
    case CursorType::kContextMenu:
      return SOFIK_CURSOR_CONTEXT_MENU;
    case CursorType::kCell:
      return SOFIK_CURSOR_CELL;
    case CursorType::kVerticalText:
      return SOFIK_CURSOR_VERTICAL_TEXT;
    case CursorType::kZoomIn:
      return SOFIK_CURSOR_ZOOM_IN;
    case CursorType::kZoomOut:
      return SOFIK_CURSOR_ZOOM_OUT;
    case CursorType::kColumnResize:
      return SOFIK_CURSOR_RESIZE_COLUMN;
    case CursorType::kRowResize:
      return SOFIK_CURSOR_RESIZE_ROW;
    case CursorType::kEastResize:
    case CursorType::kWestResize:
    case CursorType::kEastWestResize:
      return SOFIK_CURSOR_RESIZE_EW;
    case CursorType::kNorthResize:
    case CursorType::kSouthResize:
    case CursorType::kNorthSouthResize:
      return SOFIK_CURSOR_RESIZE_NS;
    case CursorType::kNorthEastResize:
    case CursorType::kSouthWestResize:
    case CursorType::kNorthEastSouthWestResize:
      return SOFIK_CURSOR_RESIZE_NESW;
    case CursorType::kNorthWestResize:
    case CursorType::kSouthEastResize:
    case CursorType::kNorthWestSouthEastResize:
      return SOFIK_CURSOR_RESIZE_NWSE;
    case CursorType::kNone:
      return SOFIK_CURSOR_NONE;
    case CursorType::kCustom:
      return SOFIK_CURSOR_CUSTOM;
    default:
      return SOFIK_CURSOR_POINTER;
  }
}

}  // namespace

void View::OnCursorChanged(const ui::Cursor& cursor) {
  const sofik_cursor mapped = ToSofikCursor(cursor.type());
  // The renderer repeats the cursor on every mouse move.
  if (mapped == last_cursor_ && mapped != SOFIK_CURSOR_CUSTOM) {
    return;
  }
  last_cursor_ = mapped;
  if (callbacks_.on_cursor) {
    callbacks_.on_cursor(user_, id_, mapped);
  }
}

void View::OnTooltipChanged(const std::u16string& text) {
  if (text == last_tooltip_) {
    return;
  }
  last_tooltip_ = text;
  if (callbacks_.on_tooltip) {
    callbacks_.on_tooltip(user_, id_, base::UTF16ToUTF8(text).c_str());
  }
}

void View::OnTextInputStateChanged(bool is_editable, const gfx::Rect& caret) {
  if (callbacks_.on_focused_node_changed) {
    callbacks_.on_focused_node_changed(user_, id_, is_editable, ToRect(caret));
  }
}

void View::OnImeCompositionBoundsChanged(const gfx::Rect& bounds) {
  if (callbacks_.on_ime_composition_bounds) {
    callbacks_.on_ime_composition_bounds(user_, id_, ToRect(bounds));
  }
}

void View::ImeSetComposition(const std::string& text, int selection_start,
                             int selection_end) {
  if (OffscreenView* view = page_view()) {
    view->ImeSetComposition(base::UTF8ToUTF16(text), selection_start,
                            selection_end);
  }
}

void View::ImeCommit(const std::string& text) {
  if (OffscreenView* view = page_view()) {
    view->ImeCommitText(base::UTF8ToUTF16(text));
  }
}

void View::ImeCancel() {
  if (OffscreenView* view = page_view()) {
    view->ImeCancel();
  }
}

// ---- new windows and dialogs ------------------------------------------------

bool View::OnNewWindowRequested(const GURL& url, bool user_gesture) {
  // Always taken, host or no host: a Browser Card is one page, and a window
  // nobody asked for and nobody can see is the worst answer available.
  if (callbacks_.on_popup_requested) {
    callbacks_.on_popup_requested(user_, id_, url.spec().c_str(), user_gesture);
  }
  return true;
}

content::JavaScriptDialogManager* View::GetJavaScriptDialogManager() {
  return this;
}

void View::RunJavaScriptDialog(content::WebContents* web_contents,
                               content::RenderFrameHost* frame,
                               content::JavaScriptDialogType type,
                               const std::u16string& message,
                               const std::u16string& default_prompt,
                               DialogClosedCallback callback,
                               bool* did_suppress_message) {
  if (!callbacks_.on_dialog) {
    // Nobody to ask. The content layer then answers for us, so that alert()
    // returns instead of hanging the page.
    *did_suppress_message = true;
    return;
  }
  const uint32_t request = next_request_++;
  dialogs_[request] = std::move(callback);
  sofik_dialog_kind kind =
      type == content::JAVASCRIPT_DIALOG_TYPE_CONFIRM  ? SOFIK_DIALOG_CONFIRM
      : type == content::JAVASCRIPT_DIALOG_TYPE_PROMPT ? SOFIK_DIALOG_PROMPT
                                                       : SOFIK_DIALOG_ALERT;
  callbacks_.on_dialog(user_, id_, request, kind,
                       base::UTF16ToUTF8(message).c_str(),
                       base::UTF16ToUTF8(default_prompt).c_str());
}

void View::RunBeforeUnloadDialog(content::WebContents* web_contents,
                                 content::RenderFrameHost* frame,
                                 bool is_reload,
                                 DialogClosedCallback callback) {
  if (!callbacks_.on_dialog) {
    // Leaving is what was asked for; a page must not be able to veto it
    // unseen.
    std::move(callback).Run(true, std::u16string());
    return;
  }
  const uint32_t request = next_request_++;
  dialogs_[request] = std::move(callback);
  callbacks_.on_dialog(user_, id_, request, SOFIK_DIALOG_BEFORE_UNLOAD, "", "");
}

void View::AnswerDialog(uint32_t request, bool accepted,
                        const std::string& prompt) {
  auto found = dialogs_.find(request);
  if (found == dialogs_.end()) {
    return;
  }
  DialogClosedCallback callback = std::move(found->second);
  dialogs_.erase(found);
  std::move(callback).Run(accepted, base::UTF8ToUTF16(prompt));
}

bool View::HandleJavaScriptDialog(content::WebContents* web_contents,
                                  bool accept,
                                  const std::u16string* prompt_override) {
  // DevTools' Page.handleJavaScriptDialog: an agent answering for itself.
  if (dialogs_.empty()) {
    return false;
  }
  AnswerDialog(dialogs_.begin()->first, accept,
               prompt_override ? base::UTF16ToUTF8(*prompt_override) : "");
  return true;
}

void View::CancelDialogs(content::WebContents* web_contents, bool reset_state) {
  std::map<uint32_t, DialogClosedCallback> pending = std::move(dialogs_);
  dialogs_.clear();
  for (auto& [request, callback] : pending) {
    std::move(callback).Run(false, std::u16string());
  }
}

// ---- permissions ------------------------------------------------------------

namespace {

// 0 for a permission the API does not name: those are never granted.
uint32_t ToSofikPermission(blink::PermissionType type) {
  switch (type) {
    case blink::PermissionType::VIDEO_CAPTURE:
      return SOFIK_PERMISSION_CAMERA;
    case blink::PermissionType::AUDIO_CAPTURE:
      return SOFIK_PERMISSION_MICROPHONE;
    case blink::PermissionType::GEOLOCATION:
    case blink::PermissionType::GEOLOCATION_APPROXIMATE:
      return SOFIK_PERMISSION_GEOLOCATION;
    case blink::PermissionType::NOTIFICATIONS:
      return SOFIK_PERMISSION_NOTIFICATIONS;
    case blink::PermissionType::CLIPBOARD_READ_WRITE:
    case blink::PermissionType::CLIPBOARD_SANITIZED_WRITE:
      return SOFIK_PERMISSION_CLIPBOARD;
    case blink::PermissionType::DISPLAY_CAPTURE:
      return SOFIK_PERMISSION_SCREEN_CAPTURE;
    default:
      return 0;
  }
}

}  // namespace

View::PermissionRequest::PermissionRequest() = default;
View::PermissionRequest::PermissionRequest(PermissionRequest&&) = default;
View::PermissionRequest::~PermissionRequest() = default;

void View::OnPermissionsRequested(
    const GURL& origin,
    const std::vector<blink::PermissionType>& types,
    PermissionCallback callback) {
  uint32_t asked = 0;
  for (blink::PermissionType type : types) {
    asked |= ToSofikPermission(type);
  }
  if (!callbacks_.on_permission_request || asked == 0) {
    // Nobody to ask, or nothing the host could name: the prompt is dismissed,
    // which is neither a grant nor a refusal the page can hold against us.
    std::move(callback).Run(std::vector<blink::mojom::PermissionStatus>(
        types.size(), blink::mojom::PermissionStatus::ASK));
    return;
  }
  const uint32_t request = next_request_++;
  PermissionRequest pending;
  pending.types = types;
  pending.callback = std::move(callback);
  permissions_.emplace(request, std::move(pending));
  callbacks_.on_permission_request(user_, id_, request, origin.spec().c_str(),
                                   asked);
}

void View::AnswerPermission(uint32_t request, uint32_t granted) {
  auto found = permissions_.find(request);
  if (found == permissions_.end()) {
    return;
  }
  PermissionRequest pending = std::move(found->second);
  permissions_.erase(found);
  std::vector<blink::mojom::PermissionStatus> statuses;
  for (blink::PermissionType type : pending.types) {
    const uint32_t bit = ToSofikPermission(type);
    statuses.push_back(bit && (granted & bit)
                           ? blink::mojom::PermissionStatus::GRANTED
                           : blink::mojom::PermissionStatus::DENIED);
  }
  std::move(pending.callback).Run(statuses);
}

void View::CancelDownload(uint32_t download) {
  if (!contents_) {
    return;
  }
  content::DownloadManager* manager =
      contents_->web_contents()->GetBrowserContext()->GetDownloadManager();
  if (download::DownloadItem* item = manager->GetDownload(download)) {
    item->Cancel(/*user_cancel=*/true);
  }
}

// ---- DevTools ---------------------------------------------------------------

void View::CdpAttach(sofik_cdp_callback callback, void* user) {
  if (!contents_ || cdp_host_) {
    return;
  }
  cdp_callback_ = callback;
  cdp_user_ = user;
  cdp_host_ =
      content::DevToolsAgentHost::GetOrCreateFor(contents_->web_contents());
  if (!cdp_host_->AttachClient(this)) {
    cdp_host_ = nullptr;
  }
}

void View::CdpSend(const std::string& message) {
  if (cdp_host_) {
    cdp_host_->DispatchProtocolMessage(this, base::as_byte_span(message));
  }
}

void View::CdpDetach() {
  if (cdp_host_) {
    cdp_host_->DetachClient(this);
    cdp_host_ = nullptr;
  }
  cdp_callback_ = nullptr;
  cdp_user_ = nullptr;
}

void View::DispatchProtocolMessage(content::DevToolsAgentHost* host,
                                   base::span<const uint8_t> message) {
  if (cdp_callback_) {
    std::string json(message.begin(), message.end());
    cdp_callback_(cdp_user_, id_, json.c_str());
  }
}

void View::AgentHostClosed(content::DevToolsAgentHost* host) {
  cdp_host_ = nullptr;
}

}  // namespace sofik

// ---- the C API -------------------------------------------------------------

namespace {

sofik::View* Find(sofik_view_id id) {
  sofik::Engine* engine = sofik::Engine::Get();
  return engine ? engine->FindView(id) : nullptr;
}

}  // namespace

sofik_view_id sofik_view_create(const sofik_view_config* config,
                                const sofik_view_callbacks* callbacks,
                                void* user) {
  sofik::Engine* engine = sofik::Engine::Get();
  if (!engine || !config) {
    return 0;
  }
  sofik_view_callbacks none = {};
  sofik::View* view =
      engine->CreateView(*config, callbacks ? *callbacks : none, user);
  return view ? view->id() : 0;
}

void sofik_view_close(sofik_view_id id) {
  if (sofik::Engine* engine = sofik::Engine::Get()) {
    engine->DestroyView(id);
  }
}

void sofik_view_resize(sofik_view_id id, int width, int height) {
  if (sofik::View* view = Find(id)) {
    view->Resize(gfx::Size(width, height));
  }
}

void sofik_view_set_scale(sofik_view_id id, float device_scale_factor) {
  if (sofik::View* view = Find(id)) {
    view->SetScale(device_scale_factor);
  }
}

void sofik_view_set_visible(sofik_view_id id, int visible) {
  if (sofik::View* view = Find(id)) {
    view->SetVisible(visible != 0);
  }
}

void sofik_view_set_focus(sofik_view_id id, int focused) {
  if (sofik::View* view = Find(id)) {
    view->SetFocus(focused != 0);
  }
}

void sofik_view_invalidate(sofik_view_id id) {
  if (sofik::View* view = Find(id)) {
    view->Invalidate();
  }
}

void sofik_view_load_url(sofik_view_id id, const char* url) {
  if (sofik::View* view = Find(id); view && url) {
    view->LoadURL(url);
  }
}

void sofik_view_go_back(sofik_view_id id) {
  if (sofik::View* view = Find(id)) {
    view->GoBack();
  }
}

void sofik_view_go_forward(sofik_view_id id) {
  if (sofik::View* view = Find(id)) {
    view->GoForward();
  }
}

void sofik_view_reload(sofik_view_id id, int ignore_cache) {
  if (sofik::View* view = Find(id)) {
    view->Reload(ignore_cache != 0);
  }
}

void sofik_view_stop(sofik_view_id id) {
  if (sofik::View* view = Find(id)) {
    view->Stop();
  }
}

void sofik_view_set_zoom(sofik_view_id id, double level) {
  if (sofik::View* view = Find(id)) {
    view->SetZoom(level);
  }
}

void sofik_view_mouse_move(sofik_view_id id, int x, int y, uint32_t modifiers,
                           int left_the_view) {
  if (sofik::View* view = Find(id)) {
    view->MouseMove(x, y, modifiers, left_the_view != 0);
  }
}

void sofik_view_mouse_button(sofik_view_id id, int x, int y,
                             sofik_mouse_button button, int is_up,
                             int click_count, uint32_t modifiers) {
  if (sofik::View* view = Find(id)) {
    view->MouseButton(x, y, button, is_up != 0, click_count, modifiers);
  }
}

void sofik_view_mouse_wheel(sofik_view_id id, int x, int y, float delta_x,
                            float delta_y, uint32_t modifiers) {
  if (sofik::View* view = Find(id)) {
    view->MouseWheel(x, y, delta_x, delta_y, modifiers);
  }
}

void sofik_view_key(sofik_view_id id, sofik_key_type type, int windows_key_code,
                    int native_key_code, uint32_t character,
                    uint32_t modifiers) {
  if (sofik::View* view = Find(id)) {
    view->Key(type, windows_key_code, native_key_code, character, modifiers);
  }
}

void sofik_view_ime_set_composition(sofik_view_id id, const char* text,
                                    int selection_start, int selection_end) {
  if (sofik::View* view = Find(id)) {
    view->ImeSetComposition(text ? text : "", selection_start, selection_end);
  }
}

void sofik_view_ime_commit(sofik_view_id id, const char* text) {
  if (sofik::View* view = Find(id)) {
    view->ImeCommit(text ? text : "");
  }
}

void sofik_view_ime_cancel(sofik_view_id id) {
  if (sofik::View* view = Find(id)) {
    view->ImeCancel();
  }
}

void sofik_view_answer_dialog(sofik_view_id id, uint32_t request, int accepted,
                              const char* prompt) {
  if (sofik::View* view = Find(id)) {
    view->AnswerDialog(request, accepted != 0, prompt ? prompt : "");
  }
}

void sofik_view_answer_permission(sofik_view_id id, uint32_t request,
                                  uint32_t granted) {
  if (sofik::View* view = Find(id)) {
    view->AnswerPermission(request, granted);
  }
}

void sofik_view_answer_download(sofik_view_id id, uint32_t request,
                                const char* path) {
  if (sofik::Engine* engine = sofik::Engine::Get()) {
    engine->downloads().Answer(request, path ? path : "");
  }
}

void sofik_view_cancel_download(sofik_view_id id, uint32_t download) {
  if (sofik::View* view = Find(id)) {
    view->CancelDownload(download);
  }
}

void sofik_view_cdp_attach(sofik_view_id id, sofik_cdp_callback callback,
                           void* user) {
  if (sofik::View* view = Find(id)) {
    view->CdpAttach(callback, user);
  }
}

void sofik_view_cdp_send(sofik_view_id id, const char* message_json) {
  if (sofik::View* view = Find(id); view && message_json) {
    view->CdpSend(message_json);
  }
}

void sofik_view_cdp_detach(sofik_view_id id) {
  if (sofik::View* view = Find(id)) {
    view->CdpDetach();
  }
}
