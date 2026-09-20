// Copyright 2026 Sofik. All rights reserved.

#include "sofik/engine/engine.h"

#include <string>
#include <utility>
#include <vector>

#include "base/command_line.h"
#include "base/files/file_path.h"
#include "base/files/file_util.h"
#include "base/functional/bind.h"
#include "base/logging.h"
#include "base/no_destructor.h"
#include "base/path_service.h"
#include "base/process/process.h"
#include "base/strings/string_number_conversions.h"
#include "base/strings/string_split.h"
#include "build/build_config.h"
#include "components/os_crypt/common/os_crypt_switches.h"
#include "content/public/app/content_main.h"
#include "content/public/app/content_main_runner.h"
#include "content/public/common/content_switches.h"
#include "headless/lib/browser/headless_browser_impl.h"
#include "headless/lib/headless_content_main_delegate.h"
#include "headless/public/headless_browser.h"
#include "headless/public/headless_browser_context.h"
#include "headless/public/switches.h"
#include "headless/lib/browser/headless_browser_context_impl.h"
#include "sofik/engine/downloads.h"
#include "sofik/engine/view.h"
#include "ui/base/ui_base_switches.h"
#include "ui/display/display_switches.h"
#include "ui/gl/gl_switches.h"

#if BUILDFLAG(IS_MAC)
#include "base/apple/bundle_locations.h"
#include "sandbox/mac/seatbelt_exec.h"
#endif

namespace sofik {
namespace {

Engine* g_engine = nullptr;

// argv has to outlive the content layer, which keeps pointers into it.
std::vector<std::string>& ArgvStorage() {
  static base::NoDestructor<std::vector<std::string>> storage;
  return *storage;
}

// icudtl.dat, the .pak files and the V8 snapshots. The content layer looks for
// them next to the *executable*, which for an embedded engine is the host
// application -- somebody else's bundle. They ship with the engine, so by
// default they are found from the engine's own library, in every process:
// beside it in a build directory, or in Resources/ when the library is the
// binary of SofikEngine.framework (see package_mac.py).
void PointAssetsAtTheEngine() {
  const base::CommandLine& command_line =
      *base::CommandLine::ForCurrentProcess();
  base::FilePath assets =
      command_line.GetSwitchValuePath(headless::switches::kSofikResourcesDir);
  base::FilePath bundle;
  if (assets.empty()) {
    base::FilePath library_dir;
    if (!base::PathService::Get(base::DIR_MODULE, &library_dir)) {
      return;
    }
    assets = library_dir;
    // <name>.framework/Versions/A/<library>
    const base::FilePath framework = library_dir.DirName().DirName();
    if (framework.MatchesExtension(FILE_PATH_LITERAL(".framework")) &&
        base::PathExists(library_dir.Append(FILE_PATH_LITERAL("Resources")))) {
      assets = library_dir.Append(FILE_PATH_LITERAL("Resources"));
      bundle = framework;
    }
  }
  base::PathService::Override(base::DIR_ASSETS, assets);
#if BUILDFLAG(IS_MAC)
  // On macOS ICU and V8 do not ask for DIR_ASSETS: they ask the "framework
  // bundle", which is the main bundle unless told otherwise, and a bundled GPU
  // process loads ANGLE from its Libraries/. A plain directory serves as one.
  base::apple::SetOverrideFrameworkBundlePath(bundle.empty() ? assets : bundle);
#endif
}

void AppendIfSet(base::CommandLine& command_line,
                 const char* name,
                 const char* value) {
  if (value && *value) {
    command_line.AppendSwitchASCII(name, value);
  }
}

}  // namespace

Engine::Engine() : downloads_(std::make_unique<Downloads>()) {}
Engine::~Engine() = default;

// static
Engine* Engine::Get() {
  return g_engine;
}

// static
int Engine::Initialize(const sofik_settings& settings) {
  if (g_engine) {
    LOG(ERROR) << "sofik: the engine is already initialised";
    return 1;
  }
  if (settings.abi != SOFIK_ENGINE_ABI) {
    LOG(ERROR) << "sofik: settings built for ABI " << settings.abi
               << ", this engine is ABI " << SOFIK_ENGINE_ABI;
    return 2;
  }
#if !BUILDFLAG(IS_MAC)
  // Windows and Linux run the engine on a UI thread of its own, which is not
  // written yet. Failing here is better than half-working there.
  LOG(ERROR) << "sofik: the engine only runs on macOS so far";
  return 3;
#else
  ArgvStorage() = {"sofik_engine"};
  const char* argv0 = ArgvStorage()[0].c_str();
  base::CommandLine::Init(1, &argv0);
  base::CommandLine& command_line = *base::CommandLine::ForCurrentProcess();

  AppendIfSet(command_line, ::switches::kBrowserSubprocessPath,
              settings.helper_path);
  AppendIfSet(command_line, headless::switches::kSofikResourcesDir,
              settings.resources_dir);
  PointAssetsAtTheEngine();
  AppendIfSet(command_line, headless::switches::kUserDataDir,
              settings.cache_root);
  AppendIfSet(command_line, ::switches::kLang, settings.locale);
  AppendIfSet(command_line, headless::switches::kAcceptLang,
              settings.accept_languages);
  AppendIfSet(command_line, headless::switches::kUserAgent,
              settings.user_agent);
  if (settings.remote_debugging_port > 0) {
    command_line.AppendSwitchASCII(
        ::switches::kRemoteDebuggingPort,
        base::NumberToString(settings.remote_debugging_port));
  }
  if (settings.device_scale_factor > 0) {
    command_line.AppendSwitchASCII(
        ::switches::kForceDeviceScaleFactor,
        base::NumberToString(settings.device_scale_factor));
  }

  // Headless renders in software unless told otherwise, and its software
  // path is SwiftShader, which this browser does not contain: a page that
  // reads "SwiftShader" as the WebGL renderer knows there is no GPU behind
  // it. With the real GPU the renderer string is the one Chrome reports.
  command_line.AppendSwitch(headless::switches::kEnableGPU);
  command_line.AppendSwitchASCII(::switches::kUseANGLE, "metal");
  // As headless_shell does. The real keychain belongs with profile
  // encryption, which comes with profile import.
  command_line.AppendSwitch(os_crypt::switches::kUseMockKeychain);

  if (settings.extra_switches && *settings.extra_switches) {
    for (const std::string& token :
         base::SplitString(settings.extra_switches, " ", base::TRIM_WHITESPACE,
                           base::SPLIT_WANT_NONEMPTY)) {
      std::string name = token.starts_with("--") ? token.substr(2) : token;
      size_t equals = name.find('=');
      if (equals == std::string::npos) {
        command_line.AppendSwitch(name);
      } else {
        command_line.AppendSwitchASCII(name.substr(0, equals),
                                       name.substr(equals + 1));
      }
    }
  }

  g_engine = new Engine();
  if (settings.cache_root) {
    g_engine->cache_root_ = settings.cache_root;
  }

  // The host owns the main loop; the engine's work has to arrive through it.
  InstallHostLoopMessagePump();

  headless::HeadlessBrowser::UseBrowserIdentity();
  auto browser = std::make_unique<headless::HeadlessBrowserImpl>(
      base::BindOnce(&Engine::OnBrowserStart, base::Unretained(g_engine)));
  g_engine->delegate_ = std::make_unique<headless::HeadlessContentMainDelegate>(
      std::move(browser));
  g_engine->delegate_->set_embedder_owns_message_loop(true);

  g_engine->runner_ = content::ContentMainRunner::Create();
  content::ContentMainParams params(g_engine->delegate_.get());
  params.argc = 1;
  params.argv = &argv0;
  // The host application has its own signal handling.
  params.disable_signal_handlers = true;

  int exit_code =
      content::ContentMainInitialize(std::move(params), g_engine->runner_.get());
  if (exit_code >= 0) {
    LOG(ERROR) << "sofik: content initialisation failed, " << exit_code;
    return 4;
  }
  // In embedded mode this returns as soon as the browser is initialised.
  content::ContentMainRun(g_engine->runner_.get());
  if (!g_engine->browser_) {
    LOG(ERROR) << "sofik: the browser did not start";
    return 5;
  }
  return 0;
#endif
}

// static
void Engine::Shutdown() {
  if (!g_engine) {
    return;
  }
  g_engine->views_.clear();
  g_engine->contexts_.clear();
  g_engine->browser_ = nullptr;
  g_engine->delegate_->ShutdownEmbeddedBrowser();
  content::ContentMainShutdown(g_engine->runner_.get());
  delete g_engine;
  g_engine = nullptr;
}

void Engine::OnBrowserStart(headless::HeadlessBrowser* browser) {
  browser_ = browser;
  // The default context is what Target.createTarget falls back to.
  browser_->SetDefaultBrowserContext(ContextFor(nullptr));
}

headless::HeadlessBrowserContext* Engine::ContextFor(const char* profile) {
  std::string name = profile ? profile : "";
  auto found = contexts_.find(name);
  if (found != contexts_.end()) {
    return found->second;
  }
  headless::HeadlessBrowserContext::Builder builder =
      browser_->CreateBrowserContextBuilder();
  if (name.empty() || cache_root_.empty()) {
    builder.SetIncognitoMode(true);
  } else {
    // The name is the host's, never a page's, but it still becomes a path.
    base::FilePath leaf = base::FilePath(name).BaseName();
    builder.SetIncognitoMode(false);
    builder.SetUserDataDir(
        base::FilePath(cache_root_).Append(FILE_PATH_LITERAL("profiles"))
            .Append(leaf));
  }
  headless::HeadlessBrowserContext* context = builder.Build();
  headless::HeadlessBrowserContextImpl::From(context)
      ->set_download_manager_delegate(downloads_.get());
  contexts_[name] = context;
  return context;
}

View* Engine::CreateView(const sofik_view_config& config,
                         const sofik_view_callbacks& callbacks,
                         void* user) {
  sofik_view_id id = next_view_id_++;
  auto view = View::Create(id, ContextFor(config.profile), config, callbacks,
                           user);
  if (!view) {
    return nullptr;
  }
  View* raw = view.get();
  views_[id] = std::move(view);
  return raw;
}

View* Engine::FindView(sofik_view_id id) const {
  auto found = views_.find(id);
  return found == views_.end() ? nullptr : found->second.get();
}

View* Engine::FindView(content::WebContents* web_contents) const {
  if (!web_contents) {
    return nullptr;
  }
  for (const auto& [id, view] : views_) {
    if (view->web_contents() == web_contents) {
      return view.get();
    }
  }
  return nullptr;
}

void Engine::DestroyView(sofik_view_id id) {
  views_.erase(id);
}

}  // namespace sofik

// ---- the C API -------------------------------------------------------------

int sofik_engine_run_child_process(int argc, const char** argv) {
  base::CommandLine::Init(argc, argv);
  if (!base::CommandLine::ForCurrentProcess()->HasSwitch(
          ::switches::kProcessType)) {
    return -1;
  }
  sofik::PointAssetsAtTheEngine();
  content::ContentMainParams params(nullptr);
  params.argc = argc;
  params.argv = argv;
#if BUILDFLAG(IS_MAC)
  // The sandbox has to be entered before anything else runs in the child.
  sandbox::SeatbeltExecServer::CreateFromArgumentsResult seatbelt =
      sandbox::SeatbeltExecServer::CreateFromArguments(
          argv[0], argc, const_cast<char**>(argv));
  if (seatbelt.sandbox_required) {
    CHECK(seatbelt.server->InitializeSandbox());
  }
#endif
  headless::HeadlessContentMainDelegate delegate(nullptr);
  params.delegate = &delegate;
  int exit_code = content::ContentMain(std::move(params));
  base::Process::TerminateCurrentProcessImmediately(exit_code);
}

int sofik_engine_initialize(const sofik_settings* settings) {
  return settings ? sofik::Engine::Initialize(*settings) : 1;
}

void sofik_engine_shutdown(void) {
  sofik::Engine::Shutdown();
}
