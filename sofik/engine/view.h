// Copyright 2026 Sofik. All rights reserved.

#ifndef SOFIK_ENGINE_VIEW_H_
#define SOFIK_ENGINE_VIEW_H_

#include <map>
#include <memory>
#include <string>
#include <vector>

#include "base/memory/raw_ptr.h"
#include "base/memory/scoped_refptr.h"
#include "components/viz/host/client_frame_sink_video_capturer.h"
#include "content/public/browser/devtools_agent_host_client.h"
#include "content/public/browser/javascript_dialog_manager.h"
#include "content/public/browser/web_contents_observer.h"
#include "headless/public/headless_embedder_delegate.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "sofik/engine/sofik_engine.h"
#include "ui/gfx/geometry/size.h"

namespace content {
class DevToolsAgentHost;
class RenderWidgetHost;
}  // namespace content

namespace headless {
class HeadlessBrowserContext;
class HeadlessWebContentsImpl;
}  // namespace headless

namespace sofik {

// One page: a web contents, the frames it paints, the input it takes and the
// events it reports. Everything runs on the engine's UI thread.
class View : public content::WebContentsObserver,
             public viz::mojom::FrameSinkVideoConsumer,
             public content::DevToolsAgentHostClient,
             public headless::HeadlessEmbedderDelegate,
             public content::JavaScriptDialogManager {
 public:
  static std::unique_ptr<View> Create(sofik_view_id id,
                                      headless::HeadlessBrowserContext* context,
                                      const sofik_view_config& config,
                                      const sofik_view_callbacks& callbacks,
                                      void* user);

  View(const View&) = delete;
  View& operator=(const View&) = delete;
  ~View() override;

  sofik_view_id id() const { return id_; }

  void Resize(const gfx::Size& size_dips);
  void SetVisible(bool visible);
  void SetFocus(bool focused);
  void Invalidate();

  void LoadURL(const std::string& url);
  void GoBack();
  void GoForward();
  void Reload(bool ignore_cache);
  void Stop();
  void SetZoom(double level);

  void MouseMove(int x, int y, uint32_t modifiers, bool left_the_view);
  void MouseButton(int x, int y, sofik_mouse_button button, bool is_up,
                   int click_count, uint32_t modifiers);
  void MouseWheel(int x, int y, float delta_x, float delta_y,
                  uint32_t modifiers);
  void Key(sofik_key_type type, int windows_key_code, int native_key_code,
           uint32_t character, uint32_t modifiers);

  void AnswerDialog(uint32_t request, bool accepted, const std::string& prompt);

  void CdpAttach(sofik_cdp_callback callback, void* user);
  void CdpSend(const std::string& message);
  void CdpDetach();

 private:
  View(sofik_view_id id,
       headless::HeadlessWebContentsImpl* contents,
       const sofik_view_config& config,
       const sofik_view_callbacks& callbacks,
       void* user);

  content::RenderWidgetHost* widget() const;
  void StartCapture();
  void ApplyCaptureSize();
  void ReportLoadingState();

  // content::WebContentsObserver:
  void RenderViewReady() override;
  void RenderViewHostChanged(content::RenderViewHost* old_host,
                             content::RenderViewHost* new_host) override;
  void DidStartLoading() override;
  void DidStopLoading() override;
  void DidFinishNavigation(content::NavigationHandle* handle) override;
  void DidFailLoad(content::RenderFrameHost* frame,
                   const GURL& url,
                   int error_code) override;
  void TitleWasSet(content::NavigationEntry* entry) override;
  void DidUpdateFaviconURL(
      content::RenderFrameHost* frame,
      const std::vector<blink::mojom::FaviconURLPtr>& candidates) override;
  void OnDidAddMessageToConsole(
      content::RenderFrameHost* frame,
      blink::mojom::ConsoleMessageLevel level,
      const std::u16string& message,
      int32_t line,
      const std::u16string& source,
      const std::optional<std::u16string>& stack) override;
  void WebContentsDestroyed() override;

  // viz::mojom::FrameSinkVideoConsumer:
  void OnFrameCaptured(
      media::mojom::VideoBufferHandlePtr data,
      media::mojom::VideoFrameInfoPtr info,
      const gfx::Rect& content_rect,
      mojo::PendingRemote<viz::mojom::FrameSinkVideoConsumerFrameCallbacks>
          callbacks) override;
  void OnFrameWithEmptyRegionCapture() override {}
  void OnStopped() override {}
  void OnLog(const std::string& message) override {}
  void OnNewCaptureVersion(const media::CaptureVersion& version) override {}

  // headless::HeadlessEmbedderDelegate:
  bool OnNewWindowRequested(const GURL& url, bool user_gesture) override;
  content::JavaScriptDialogManager* GetJavaScriptDialogManager() override;

  // content::JavaScriptDialogManager:
  void RunJavaScriptDialog(content::WebContents* web_contents,
                           content::RenderFrameHost* frame,
                           content::JavaScriptDialogType type,
                           const std::u16string& message,
                           const std::u16string& default_prompt,
                           DialogClosedCallback callback,
                           bool* did_suppress_message) override;
  void RunBeforeUnloadDialog(content::WebContents* web_contents,
                             content::RenderFrameHost* frame,
                             bool is_reload,
                             DialogClosedCallback callback) override;
  bool HandleJavaScriptDialog(content::WebContents* web_contents,
                              bool accept,
                              const std::u16string* prompt_override) override;
  void CancelDialogs(content::WebContents* web_contents,
                     bool reset_state) override;

  // content::DevToolsAgentHostClient:
  void DispatchProtocolMessage(content::DevToolsAgentHost* host,
                               base::span<const uint8_t> message) override;
  void AgentHostClosed(content::DevToolsAgentHost* host) override;

  const sofik_view_id id_;
  raw_ptr<headless::HeadlessWebContentsImpl> contents_;
  const sofik_view_callbacks callbacks_;
  const raw_ptr<void> user_;
  const bool prefer_gpu_frames_;
  const int frame_rate_;
  gfx::Size size_dips_;

  std::unique_ptr<viz::ClientFrameSinkVideoCapturer> capturer_;
  // The callbacks of the GPU frame the host is showing. Releasing them lets
  // viz recycle the buffer, so they are held until the next frame replaces it:
  // the host is promised a surface that stays valid that long. Exactly one is
  // ever held, so capture cannot be starved of buffers.
  mojo::Remote<viz::mojom::FrameSinkVideoConsumerFrameCallbacks> held_frame_;

  // Dialogs the page is blocked on, by the request number given to the host.
  std::map<uint32_t, DialogClosedCallback> dialogs_;
  uint32_t next_request_ = 1;

  scoped_refptr<content::DevToolsAgentHost> cdp_host_;
  sofik_cdp_callback cdp_callback_ = nullptr;
  raw_ptr<void> cdp_user_ = nullptr;
};

}  // namespace sofik

#endif  // SOFIK_ENGINE_VIEW_H_
