// Copyright 2026 Sofik. All rights reserved.
// Portions copyright 2013 The Chromium Authors, under the BSD-style licence in
// //LICENSE: the embedder protocol here descends from content_shell's
// ShellDevToolsBindings.

#ifndef SOFIK_ENGINE_DEVTOOLS_FRONTEND_H_
#define SOFIK_ENGINE_DEVTOOLS_FRONTEND_H_

#include <memory>
#include <set>
#include <string>

#include "base/containers/unique_ptr_adapters.h"
#include "base/functional/callback.h"
#include "base/memory/raw_ptr.h"
#include "base/memory/scoped_refptr.h"
#include "base/values.h"
#include "content/public/browser/devtools_agent_host_client.h"
#include "content/public/browser/web_contents_observer.h"

namespace content {
class DevToolsAgentHost;
class DevToolsFrontendHost;
}  // namespace content

namespace sofik {

// The browser's half of a DevTools front end shown in one of the engine's own
// views: it carries the protocol between the front end's page and the agent of
// the page being inspected, and answers what the front end asks of whoever
// embeds it (preferences, fetching source maps).
//
// The front end loads from sofik-devtools://, out of the engine's resources,
// so nothing listens on a port. Lives as long as the front end's view.
class DevToolsFrontend : public content::WebContentsObserver,
                         public content::DevToolsAgentHostClient {
 public:
  // `on_inspected_gone`: the page under inspection closed.
  DevToolsFrontend(content::WebContents* frontend,
                   content::WebContents* inspected,
                   base::OnceClosure on_inspected_gone);
  DevToolsFrontend(const DevToolsFrontend&) = delete;
  DevToolsFrontend& operator=(const DevToolsFrontend&) = delete;
  ~DevToolsFrontend() override;

  static std::string URL();

 private:
  class ResourceLoader;

  void HandleMessage(base::DictValue message);
  void Call(const std::string& method,
            base::Value arg1 = {},
            base::Value arg2 = {},
            base::Value arg3 = {});
  void Ack(int request_id, base::DictValue result);
  void LoadNetworkResource(int request_id,
                           const std::string& url,
                           const std::string& headers,
                           int stream_id);

  // content::WebContentsObserver:
  void ReadyToCommitNavigation(content::NavigationHandle* handle) override;
  void PrimaryMainDocumentElementAvailable() override;
  void WebContentsDestroyed() override;

  // content::DevToolsAgentHostClient:
  void DispatchProtocolMessage(content::DevToolsAgentHost* host,
                               base::span<const uint8_t> message) override;
  void AgentHostClosed(content::DevToolsAgentHost* host) override;
  bool MayAccessAllCookies() override;

  raw_ptr<content::WebContents> inspected_;
  base::OnceClosure on_inspected_gone_;
  scoped_refptr<content::DevToolsAgentHost> agent_host_;
  std::unique_ptr<content::DevToolsFrontendHost> frontend_host_;
  // In memory: the front end's settings last as long as it is open.
  base::DictValue preferences_;
  std::set<std::unique_ptr<ResourceLoader>, base::UniquePtrComparator> loaders_;
};

}  // namespace sofik

#endif  // SOFIK_ENGINE_DEVTOOLS_FRONTEND_H_
