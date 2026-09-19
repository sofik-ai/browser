// Copyright 2026 Sofik. All rights reserved.

#include "sofik/engine/probe.h"

#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "base/command_line.h"
#include "base/files/file_path.h"
#include "base/files/file_util.h"
#include "base/functional/bind.h"
#include "base/logging.h"
#include "base/memory/raw_ptr.h"
#include "base/memory/weak_ptr.h"
#include "base/memory/read_only_shared_memory_region.h"
#include "base/process/process.h"
#include "base/strings/string_number_conversions.h"
#include "base/task/single_thread_task_runner.h"
#include "base/task/thread_pool.h"
#include "base/time/time.h"
#include "build/build_config.h"
#include "components/os_crypt/common/os_crypt_switches.h"
#include "components/viz/host/client_frame_sink_video_capturer.h"
#include "content/public/browser/render_widget_host_view.h"
#include "content/public/browser/web_contents.h"
#include "content/public/browser/web_contents_observer.h"
#include "content/public/common/content_switches.h"
#include "headless/lib/browser/headless_browser_impl.h"
#include "headless/lib/browser/headless_web_contents_impl.h"
#include "headless/lib/headless_content_main_delegate.h"
#include "headless/public/headless_browser.h"
#include "headless/public/headless_browser_context.h"
#include "headless/public/headless_web_contents.h"
#include "media/base/video_frame.h"
#include "media/base/video_types.h"
#include "media/capture/mojom/video_capture_buffer.mojom.h"
#include "media/capture/mojom/video_capture_types.mojom.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "third_party/skia/include/core/SkBitmap.h"
#include "third_party/skia/include/core/SkImageInfo.h"
#include "ui/gfx/codec/png_codec.h"
#include "ui/gfx/geometry/rect.h"
#include "ui/gfx/geometry/size.h"
#include "ui/gfx/geometry/skia_conversions.h"
#include "url/gurl.h"

namespace sofik {
namespace {

constexpr char kFrameOut[] = "frame-out";
constexpr char kSettleMs[] = "settle-ms";
constexpr gfx::Size kViewSize(1280, 800);

// Takes frames from the page's compositor and keeps the newest as a PNG.
//
// This is the path the Browser Card will be fed by. FrameSinkVideoCapturer is
// what CEF's off-screen rendering sits on too; here it is reached straight
// through content's public API, with no CEF and no //chrome underneath.
class FrameGrabber : public viz::mojom::FrameSinkVideoConsumer,
                     public content::WebContentsObserver {
 public:
  FrameGrabber(content::WebContents* web_contents,
               base::FilePath frame_out,
               base::TimeDelta settle,
               base::OnceClosure done)
      : content::WebContentsObserver(web_contents),
        frame_out_(std::move(frame_out)),
        settle_(settle),
        done_(std::move(done)) {}

  FrameGrabber(const FrameGrabber&) = delete;
  FrameGrabber& operator=(const FrameGrabber&) = delete;
  ~FrameGrabber() override = default;

 private:
  // content::WebContentsObserver:
  void DidStopLoading() override {
    if (capturer_) {
      return;
    }
    content::RenderWidgetHostView* view =
        web_contents()->GetRenderWidgetHostView();
    if (!view) {
      LOG(ERROR) << "sofik: the page has no view to capture";
      Finish();
      return;
    }
    capturer_ = view->CreateVideoCapturer();
    capturer_->SetFormat(media::PIXEL_FORMAT_ARGB);
    capturer_->SetAutoThrottlingEnabled(false);
    capturer_->SetMinSizeChangePeriod(base::TimeDelta());
    capturer_->SetResolutionConstraints(kViewSize, kViewSize,
                                        /*use_fixed_aspect_ratio=*/true);
    capturer_->Start(this, viz::mojom::BufferFormatPreference::kDefault);
    capturer_->RequestRefreshFrame();

    // A page goes on painting after load stops (fonts, images, animation), so
    // the frame worth keeping is the last one inside a short window, not the
    // first.
    base::SingleThreadTaskRunner::GetCurrentDefault()->PostDelayedTask(
        FROM_HERE,
        base::BindOnce(&FrameGrabber::Finish, weak_factory_.GetWeakPtr()),
        settle_);
  }

  // viz::mojom::FrameSinkVideoConsumer:
  void OnFrameCaptured(
      media::mojom::VideoBufferHandlePtr data,
      media::mojom::VideoFrameInfoPtr info,
      const gfx::Rect& content_rect,
      mojo::PendingRemote<viz::mojom::FrameSinkVideoConsumerFrameCallbacks>
          callbacks) override {
    mojo::Remote<viz::mojom::FrameSinkVideoConsumerFrameCallbacks> remote(
        std::move(callbacks));
    ++frames_;

    if (info->pixel_format == media::PIXEL_FORMAT_ARGB &&
        data->is_read_only_shmem_region()) {
      base::ReadOnlySharedMemoryMapping mapping =
          data->get_read_only_shmem_region().Map();
      const size_t needed = media::VideoFrame::AllocationSize(
          info->pixel_format, info->coded_size);
      if (mapping.IsValid() && mapping.size() >= needed) {
        SkBitmap frame;
        // PIXEL_FORMAT_ARGB is BGRA in memory on every platform we ship.
        frame.installPixels(
            SkImageInfo::Make(info->coded_size.width(),
                              info->coded_size.height(), kBGRA_8888_SkColorType,
                              kPremul_SkAlphaType),
            const_cast<void*>(mapping.memory()),
            media::VideoFrame::RowBytes(media::VideoFrame::Plane::kARGB,
                                        info->pixel_format,
                                        info->coded_size.width()));
        SkBitmap visible;
        frame.extractSubset(&visible, gfx::RectToSkIRect(content_rect));
        // Encoded while the mapping is alive; only the bytes outlive it.
        latest_png_ =
            gfx::PNGCodec::EncodeBGRASkBitmap(visible,
                                              /*discard_transparency=*/true);
        latest_size_ = content_rect.size();
      }
    } else {
      LOG(ERROR) << "sofik: unexpected frame, format " << info->pixel_format;
    }
    remote->Done();
  }
  void OnFrameWithEmptyRegionCapture() override {}
  void OnStopped() override {}
  void OnLog(const std::string& message) override {}
  void OnNewCaptureVersion(
      const media::CaptureVersion& capture_version) override {}

  void Finish() {
    if (capturer_) {
      capturer_->Stop();
    }
    if (!latest_png_) {
      Report(false);
      return;
    }
    // Disk I/O is not allowed on the browser's UI thread.
    base::ThreadPool::PostTaskAndReplyWithResult(
        FROM_HERE, {base::MayBlock()},
        base::BindOnce(
            [](base::FilePath path, std::vector<uint8_t> png) {
              return base::WriteFile(path, png);
            },
            frame_out_, *latest_png_),
        base::BindOnce(&FrameGrabber::Report, weak_factory_.GetWeakPtr()));
  }

  void Report(bool written) {
    LOG(ERROR) << "sofik: frames=" << frames_
               << " size=" << latest_size_.ToString()
               << " png=" << (latest_png_ ? latest_png_->size() : 0) << " bytes"
               << (written ? " -> " + frame_out_.AsUTF8Unsafe()
                           : " (nothing written)");
    if (done_) {
      std::move(done_).Run();
    }
  }

  const base::FilePath frame_out_;
  const base::TimeDelta settle_;
  base::OnceClosure done_;
  std::unique_ptr<viz::ClientFrameSinkVideoCapturer> capturer_;
  std::optional<std::vector<uint8_t>> latest_png_;
  gfx::Size latest_size_;
  int frames_ = 0;
  base::WeakPtrFactory<FrameGrabber> weak_factory_{this};
};

class Probe {
 public:
  Probe() = default;
  Probe(const Probe&) = delete;
  Probe& operator=(const Probe&) = delete;

  void OnBrowserStart(headless::HeadlessBrowser* browser) {
    browser_ = browser;
    const base::CommandLine& command_line =
        *base::CommandLine::ForCurrentProcess();

    headless::HeadlessBrowserContext* context =
        browser_->CreateBrowserContextBuilder().Build();
    browser_->SetDefaultBrowserContext(context);

    base::CommandLine::StringVector args = command_line.GetArgs();
    GURL url(args.empty() ? "about:blank" : args.front());

    headless::HeadlessWebContents* contents =
        context->CreateWebContentsBuilder()
            .SetInitialURL(url)
            .SetWindowBounds(gfx::Rect(kViewSize))
            .Build();
    if (!contents) {
      LOG(ERROR) << "sofik: could not open " << url;
      Shutdown();
      return;
    }

    int settle_ms = 1500;
    base::StringToInt(command_line.GetSwitchValueASCII(kSettleMs), &settle_ms);
    grabber_ = std::make_unique<FrameGrabber>(
        headless::HeadlessWebContentsImpl::From(contents)->web_contents(),
        command_line.GetSwitchValuePath(kFrameOut),
        base::Milliseconds(settle_ms),
        base::BindOnce(&Probe::Shutdown, base::Unretained(this)));
  }

 private:
  void Shutdown() {
    grabber_.reset();
    browser_.ExtractAsDangling()->Shutdown();
  }

  raw_ptr<headless::HeadlessBrowser> browser_ = nullptr;
  std::unique_ptr<FrameGrabber> grabber_;
};

}  // namespace

int ProbeMain(content::ContentMainParams params) {
#if BUILDFLAG(IS_WIN)
  base::CommandLine::Init(0, nullptr);
#else
  base::CommandLine::Init(params.argc, params.argv);
#endif
  base::CommandLine& command_line = *base::CommandLine::ForCurrentProcess();

  if (command_line.HasSwitch(::switches::kProcessType)) {
    headless::HeadlessContentMainDelegate delegate(nullptr);
    params.delegate = &delegate;
    int rc = content::ContentMain(std::move(params));
    base::Process::TerminateCurrentProcessImmediately(rc);
  }

#if BUILDFLAG(IS_MAC)
  command_line.AppendSwitch(os_crypt::switches::kUseMockKeychain);
#endif

  Probe probe;
  auto browser = std::make_unique<headless::HeadlessBrowserImpl>(
      base::BindOnce(&Probe::OnBrowserStart, base::Unretained(&probe)));
  headless::HeadlessContentMainDelegate delegate(std::move(browser));
  params.delegate = &delegate;
  return content::ContentMain(std::move(params));
}

}  // namespace sofik
