#ifndef LIBCEF_BROWSER_OSR_VIDEO_CONSUMER_OSR_H_
#define LIBCEF_BROWSER_OSR_VIDEO_CONSUMER_OSR_H_

#include <optional>

#include "base/functional/callback.h"
#include "base/memory/raw_ptr.h"
#include "components/viz/host/client_frame_sink_video_capturer.h"
#include "media/capture/mojom/video_capture_types.mojom.h"

class CefRenderWidgetHostViewOSR;

class CefVideoConsumerOSR : public viz::mojom::FrameSinkVideoConsumer {
 public:
  CefVideoConsumerOSR(CefRenderWidgetHostViewOSR* view,
                      bool use_shared_texture);

  CefVideoConsumerOSR(const CefVideoConsumerOSR&) = delete;
  CefVideoConsumerOSR& operator=(const CefVideoConsumerOSR&) = delete;

  ~CefVideoConsumerOSR() override;

  void SetActive(bool active);
  void SetFrameRate(base::TimeDelta frame_rate);
  void SizeChanged(const gfx::Size& size_in_pixels);
  void RequestRefreshFrame(const std::optional<gfx::Rect>& bounds_in_pixels);

 private:
  // Sofik: the frame callbacks of the *previous* accelerated frame, held so
  // that its GPU buffer is not recycled the instant OnFrameCaptured returns.
  //
  // Upstream calls Done() at the end of OnFrameCaptured, so the IOSurface /
  // shared texture handed to OnAcceleratedPaint is only valid for the duration
  // of that call -- which forces every embedder to blit the whole frame into a
  // buffer of its own, and (on macOS) to block on that blit because the source
  // disappears on return. Holding one frame instead keeps the surface alive
  // until the next one arrives, which is exactly how a presented texture is
  // consumed: show the latest, swap when a newer lands.
  //
  // Exactly one frame is held, so at most one buffer of viz's pool is
  // outstanding and capture cannot be starved.
  mojo::Remote<viz::mojom::FrameSinkVideoConsumerFrameCallbacks>
      held_frame_callbacks_;

  // viz::mojom::FrameSinkVideoConsumer implementation.
  void OnFrameCaptured(
      media::mojom::VideoBufferHandlePtr data,
      media::mojom::VideoFrameInfoPtr info,
      const gfx::Rect& content_rect,
      mojo::PendingRemote<viz::mojom::FrameSinkVideoConsumerFrameCallbacks>
          callbacks) override;
  void OnFrameWithEmptyRegionCapture() override {}
  void OnStopped() override {}
  void OnLog(const std::string& message) override {}
  void OnNewCaptureVersion(
      const media::CaptureVersion& capture_version) override {}

  const bool use_shared_texture_;

  const raw_ptr<CefRenderWidgetHostViewOSR> view_;
  std::unique_ptr<viz::ClientFrameSinkVideoCapturer> video_capturer_;

  gfx::Size size_in_pixels_;
  std::optional<gfx::Rect> bounds_in_pixels_;
};

#endif  // LIBCEF_BROWSER_OSR_VIDEO_CONSUMER_OSR_H_
