// Copyright 2026 Sofik. All rights reserved.

#ifndef SOFIK_ENGINE_ENGINE_H_
#define SOFIK_ENGINE_ENGINE_H_

#include <map>
#include <memory>
#include <string>

#include "base/memory/raw_ptr.h"
#include "sofik/engine/sofik_engine.h"

namespace content {
class ContentMainRunner;
class WebContents;
}

namespace headless {
class HeadlessBrowser;
class HeadlessBrowserContext;
class HeadlessContentMainDelegate;
}  // namespace headless

namespace sofik {

class Downloads;
class View;

// The one browser of the process. Lives on the engine's UI thread, which on
// macOS is the host application's main thread.
class Engine {
 public:
  static Engine* Get();

  // 0 on success. Returns once the browser is up; the host's loop runs it.
  static int Initialize(const sofik_settings& settings);
  static void Shutdown();

  View* CreateView(const sofik_view_config& config,
                   const sofik_view_callbacks& callbacks,
                   void* user);
  View* FindView(sofik_view_id id) const;
  View* FindView(content::WebContents* web_contents) const;
  Downloads& downloads() { return *downloads_; }
  void DestroyView(sofik_view_id id);

  // One browser context per profile name; nullptr/"" is off the record.
  headless::HeadlessBrowserContext* ContextFor(const char* profile);

 private:
  Engine();
  ~Engine();

  void OnBrowserStart(headless::HeadlessBrowser* browser);

  std::unique_ptr<headless::HeadlessContentMainDelegate> delegate_;
  std::unique_ptr<content::ContentMainRunner> runner_;
  raw_ptr<headless::HeadlessBrowser> browser_ = nullptr;
  std::string cache_root_;
  std::map<std::string, raw_ptr<headless::HeadlessBrowserContext>> contexts_;
  std::map<sofik_view_id, std::unique_ptr<View>> views_;
  // Outlives every browser context, which hold it unowned.
  std::unique_ptr<Downloads> downloads_;
  sofik_view_id next_view_id_ = 1;
};

// Replaces the UI thread's message pump with one the host's run loop drives.
// Must run before the content layer creates its main loop.
void InstallHostLoopMessagePump();

}  // namespace sofik

#endif  // SOFIK_ENGINE_ENGINE_H_
